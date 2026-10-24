const form = document.querySelector("#composer");
const input = document.querySelector("#message");
const send = document.querySelector("#send");
const clear = document.querySelector("#clear");
const statusLabel = document.querySelector("#status");
const feedback = document.querySelector("#feedback");
const conversation = document.querySelector("#conversation");
const welcome = document.querySelector("#welcome");
let history = [];
let configured = false;
let busy = false;

function bubble(text, role) {
  welcome.hidden = true;
  const item = document.createElement("div");
  item.className = "bubble " + role;
  item.textContent = text;
  conversation.appendChild(item);
  item.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function controls() {
  input.disabled = !configured || busy;
  send.disabled = !configured || busy;
  clear.disabled = busy;
}

async function checkConfiguration() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("无法检查本地服务状态。");
    const status = await response.json();
    configured = status.configured;
    statusLabel.textContent = configured
      ? "OpenAI · " + status.model + " · 密钥已配置，连接将在发送时验证"
      : "等待配置：请在项目 .env 文件中填写 OPENAI_API_KEY，然后重启服务。";
    document.querySelector("#dot").classList.toggle("ready", configured);
  } catch {
    statusLabel.textContent = "无法连接本地服务，请启动 Ghost 后刷新页面。";
  }
  controls();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || busy || !configured) return;
  busy = true;
  controls();
  bubble(text, "user");
  input.value = "";
  feedback.textContent = "Ghost 正在回复…";
  const messages = [...history.slice(-18), { role: "user", content: text }];
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(typeof result.detail === "string" ? result.detail : "消息未能发送，请开始新对话后重试。");
    }
    history = [...messages, { role: "assistant", content: result.reply }];
    bubble(result.reply, "assistant");
    feedback.textContent = "";
  } catch (error) {
    bubble(error.message || "连接中断，请稍后重试。", "error");
    input.value = text;
    feedback.textContent = "本条消息未加入对话上下文，可以重试。";
  } finally {
    busy = false;
    controls();
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

clear.addEventListener("click", () => {
  if (busy) return;
  history = [];
  conversation.querySelectorAll(".bubble").forEach((item) => item.remove());
  welcome.hidden = false;
  feedback.textContent = "";
  input.value = "";
  input.focus();
});

checkConfiguration();
