from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ghost.config import ROOT, Settings

INSTRUCTIONS = """你是 Ghost（古斯特），一个温暖、自然、尊重用户自主性的 AI 陪伴助手。
默认使用中文，按用户使用的语言交流。回答简洁，先回应用户实际表达，再按需提供建议。
避免说教、模板化安慰和无必要的连续追问。对情绪的判断使用试探性表达，允许用户纠正。
保持诚实：你是 AI；不编造自己的现实经历，不声称已经完成没有工具支持的操作。
你的记忆仅限本次传入的对话，不声称拥有跨设备记忆、永久记忆或主动提醒能力。
支持用户与现实中的亲友保持联系，不要求排他关系，不以依赖或内疚维持互动。
涉及紧急人身危险时，优先鼓励联系身边可信赖的人与当地紧急服务，不编造求助号码。"""


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("消息不能为空。")
        return value


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[Message] = Field(min_length=1, max_length=19)

    @model_validator(mode="after")
    def valid_conversation(self):
        if len(self.messages) % 2 == 0:
            raise ValueError("对话必须以用户消息结束。")
        for index, message in enumerate(self.messages):
            expected = "user" if index % 2 == 0 else "assistant"
            if message.role != expected:
                raise ValueError("用户与助手消息应交替出现。")
        if sum(len(item.content) for item in self.messages) > 60000:
            raise ValueError("对话过长，请开始新对话。")
        return self


class ChatReply(BaseModel):
    reply: str


def create_app(settings=None, api_client=None):
    settings = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        owned = api_client is None and bool(settings.api_key)
        app.state.client = api_client
        if owned:
            app.state.client = AsyncOpenAI(
                api_key=settings.api_key,
                base_url="https://api.openai.com/v1",
                timeout=40.0,
                max_retries=0,
            )
        try:
            yield
        finally:
            if owned:
                await app.state.client.close()

    app = FastAPI(title="Ghost", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"]
    )

    @app.middleware("http")
    async def local_request_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method == "POST" and origin:
            if origin.rstrip("/") != str(request.base_url).rstrip("/"):
                return JSONResponse(
                    status_code=403, content={"detail": "请从 Ghost 本机页面发起请求。"}
                )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'"
        )
        return response

    @app.get("/", include_in_schema=False)
    async def home():
        return FileResponse(ROOT / "ghost" / "static" / "index.html")

    @app.get("/api/status")
    async def status():
        return {
            "configured": bool(settings.api_key),
            "model": settings.model,
            "provider": "OpenAI",
        }

    @app.post("/api/chat", response_model=ChatReply)
    async def chat(body: ChatRequest):
        client = app.state.client
        if client is None:
            raise HTTPException(
                status_code=503,
                detail="尚未配置 API 密钥。请填写项目中的 .env 文件，然后重启 Ghost。",
            )
        try:
            response = await client.responses.create(
                model=settings.model,
                instructions=INSTRUCTIONS,
                input=[message.model_dump() for message in body.messages],
                max_output_tokens=1024,
                store=False,
            )
        except AuthenticationError:
            raise HTTPException(503, "API 密钥验证失败，请检查本地配置。") from None
        except RateLimitError:
            raise HTTPException(
                429, "API 额度不足或请求过于频繁，请检查平台额度并稍后重试。"
            ) from None
        except APITimeoutError:
            raise HTTPException(504, "回复超时，请稍后重试。") from None
        except APIConnectionError:
            raise HTTPException(502, "暂时无法连接 OpenAI，请检查网络连接。") from None
        except APIStatusError:
            raise HTTPException(
                502, "OpenAI 暂未完成请求，请检查模型权限、配置或稍后重试。"
            ) from None

        if response.status != "completed":
            raise HTTPException(502, "回复未完整生成，请缩短问题后重试。")
        reply = response.output_text.strip()
        if not reply:
            raise HTTPException(502, "本次没有返回可显示的文字，请换一种说法。")
        return ChatReply(reply=reply)

    app.mount("/static", StaticFiles(directory=ROOT / "ghost" / "static"), name="static")
    return app
