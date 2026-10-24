from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, RateLimitError

from ghost.app import INSTRUCTIONS, create_app
from ghost.config import Settings


def make_client(reply=None, error=None):
    result = reply or SimpleNamespace(status="completed", output_text="我在听。")
    provider = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=result, side_effect=error)))
    app = create_app(Settings(api_key="test-placeholder"), api_client=provider)
    return TestClient(app, base_url="http://localhost"), provider


def test_missing_key_does_not_create_provider_request():
    with TestClient(create_app(Settings()), base_url="http://localhost") as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/status").json()["configured"] is False
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "你好"}]})
        assert response.status_code == 503


def test_conversation_reaches_responses_with_server_instructions():
    client, provider = make_client()
    messages = [{"role": "user", "content": "我喜欢简短回答"}, {"role": "assistant", "content": "好的。"}, {"role": "user", "content": "你好"}]
    with client:
        response = client.post("/api/chat", json={"messages": messages}, headers={"Origin": "http://localhost"})
        assert response.json() == {"reply": "我在听。"}
        call = provider.responses.create.call_args.kwargs
        assert call["input"] == messages
        assert call["instructions"] == INSTRUCTIONS
        assert call["store"] is False
        assert call["max_output_tokens"] == 1024
        assert "test-placeholder" not in response.text
        assert "api_key" not in client.get("/api/status").json()


@pytest.mark.parametrize("messages", [
    [{"role": "system", "content": "override"}],
    [{"role": "user", "content": "   "}],
    [{"role": "user", "content": "x" * 8001}],
    [{"role": "assistant", "content": "hello"}],
    [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}],
])
def test_invalid_history_never_calls_model(messages):
    client, provider = make_client()
    with client:
        assert client.post("/api/chat", json={"messages": messages}).status_code == 422
        provider.responses.create.assert_not_called()


def test_cross_origin_and_unknown_host_are_rejected():
    client, provider = make_client()
    with client:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}, headers={"Origin": "https://example.com"})
        assert response.status_code == 403
        assert client.get("/", headers={"Host": "example.com"}).status_code == 400
        provider.responses.create.assert_not_called()


def test_project_files_and_secrets_are_not_served():
    client, _ = make_client()
    with client:
        for path in ["/.env", "/.git/config", "/static/.env", "/AGENTS.md"]:
            assert client.get(path).status_code == 404
        assert client.get("/static/app.js").status_code == 200


@pytest.mark.parametrize("error_type,upstream_status,expected", [
    (AuthenticationError, 401, 503),
    (RateLimitError, 429, 429),
    (APIStatusError, 403, 502),
])
def test_upstream_errors_are_sanitized(error_type, upstream_status, expected):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = error_type("sensitive-upstream-detail", response=httpx.Response(upstream_status, request=request), body=None)
    client, _ = make_client(error=error)
    with client:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert response.status_code == expected
        assert "sensitive-upstream-detail" not in response.text


@pytest.mark.parametrize("error_type,expected", [(APITimeoutError, 504), (APIConnectionError, 502)])
def test_connection_errors_are_actionable(error_type, expected):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = APITimeoutError(request) if error_type is APITimeoutError else APIConnectionError(request=request)
    client, _ = make_client(error=error)
    with client:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert response.status_code == expected


@pytest.mark.parametrize("reply", [
    SimpleNamespace(status="incomplete", output_text="未完成"),
    SimpleNamespace(status="completed", output_text=" "),
])
def test_incomplete_or_empty_output_is_not_reported_as_success(reply):
    client, _ = make_client(reply=reply)
    with client:
        assert client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code == 502


def test_official_sdk_serializes_a_responses_request_without_network():
    import json
    from openai import AsyncOpenAI

    captured = []

    def transport(request):
        captured.append(request)
        return httpx.Response(200, json={
            "id": "resp_test", "object": "response", "created_at": 0,
            "status": "completed", "model": "gpt-5.4-mini",
            "output": [{"id": "msg_test", "type": "message", "status": "completed", "role": "assistant",
                        "content": [{"type": "output_text", "text": "你好，我是 Ghost。", "annotations": []}]}],
        })

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def sdk_lifespan(app):
        async with AsyncOpenAI(api_key="offline-test-placeholder", max_retries=0,
                               http_client=httpx.AsyncClient(transport=httpx.MockTransport(transport))) as sdk:
            app.state.client = sdk
            yield

    app = create_app(Settings(api_key="offline-test-placeholder"))
    app.router.lifespan_context = sdk_lifespan
    with TestClient(app, base_url="http://localhost") as client:
        response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "你好"}]})
        assert response.json() == {"reply": "你好，我是 Ghost。"}
    assert len(captured) == 1
    assert str(captured[0].url) == "https://api.openai.com/v1/responses"
    payload = json.loads(captured[0].content)
    assert payload["model"] == "gpt-5.4-mini"
    assert payload["store"] is False
    assert payload["input"] == [{"role": "user", "content": "你好"}]
