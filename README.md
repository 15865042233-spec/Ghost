# Ghost（古斯特）

**跨设备情感陪伴智能体**

**A Cross-Device Emotional Companion Agent**

Ghost 通过 OpenAI API 提供中文文字陪伴对话。本版本是本机开发原型：包含聊天页面、对话上下文、模型配置和中文错误提示。

## 当前能力

- 在本机浏览器中与 Ghost 对话，按 Enter 发送，Shift + Enter 换行。
- 最近 9 轮历史随新消息一起发送，保持短期对话上下文。
- API 密钥由后端读取，页面不会获取密钥。
- 聊天仅存在当前页面内存中；刷新页面或点击“新对话”后清空。
- 使用 Responses API，并设置 `store=False`，不创建供之后检索的 Response 记录。此设置不等于零数据保留；其他数据处理政策以 OpenAI 官方说明为准。
- 当前尚未实现账号、跨设备同步、长期记忆、语音和工具执行。

## 第一次配置

需要 Python 3.10 或更新版本，以及有可用额度和模型权限的 OpenAI API 项目。

1. 登录 [OpenAI API 平台](https://platform.openai.com/)。
2. 在平台中选择或创建用于 Ghost 的 API 项目，并在 Billing 中确认 API 计费和可用额度。
3. 打开 [API keys](https://platform.openai.com/api-keys)，创建项目 API 密钥。可使用 `Ghost-local` 作为便于识别的名称。
4. 将项目根目录的 `.env.example` 复制为 `.env`（已存在时不要覆盖），只在本机编辑：
   ```dotenv
   OPENAI_API_KEY=在本机填入你的真实密钥
   OPENAI_MODEL=gpt-5.4-mini
   ```
5. 密钥保存在 `G:\古斯特\.env`，不要发到聊天、放进网页代码或提交到 GitHub。`.env` 已被 Git 忽略。

模型可以通过 `OPENAI_MODEL` 更换为 API 项目有权限使用的、支持 Responses API 的文本模型。本例采用 `gpt-5.4-mini`；配置密钥不代表已经验证模型权限，首次发送消息才会实际调用 API 并产生相应费用。

## 启动

在 PowerShell 中运行：

```powershell
Set-Location -LiteralPath 'G:\古斯特'
.\start.ps1 -Install
```

然后在浏览器访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。

脚本会在项目内创建 `.venv`、`.tmp`、`.cache` 并安装依赖。修改 `.env` 后，按 Ctrl+C 停止服务，再运行 `.\start.ps1`。如果系统不允许运行 PowerShell 脚本，可在已安装依赖后直接运行：

```powershell
Set-Location -LiteralPath 'G:\古斯特'
.\.venv\Scripts\python.exe -m uvicorn ghost.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

本版本绑定 `127.0.0.1`，仅供本机使用。跨设备访问需先补充用户认证、HTTPS、访问控制和数据同步，再单独部署。

## 验证

离线测试使用替代响应，不发送真实 OpenAI 请求，也不消耗 API 额度：

```powershell
Set-Location -LiteralPath 'G:\古斯特'
$env:TEMP = 'G:\古斯特\.tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = 'G:\古斯特\.cache\pip'
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
node --test tests/test_frontend.cjs
```

API 接口：

- `GET /api/status`：返回密钥是否已配置和模型名称，不验证远程连通性。
- `POST /api/chat`：发送交替排列、以用户消息结尾的 `messages` 数组，返回 `reply`。
- 单条消息最多 8000 个字符，单次最多 19 条消息，总长度最多 60000 个字符；页面输入框限制为 4000 个字符。
- 当前只返回完整回复，尚未实现逐字流式显示。

真实连通性需在本机配置密钥后，打开聊天页面发送一句话验证。

## 项目结构

```text
ghost/
  app.py              FastAPI 服务和 Responses API 调用
  config.py           从项目根目录读取本地配置
  static/             本机聊天页面
tests/                离线测试
.env.example          可公开的空白密钥模板
start.ps1             Windows 启动脚本
requirements.txt      运行依赖
requirements-dev.txt  测试依赖
```

## 项目存放与协作

公开仓库：[15865042233-spec/Ghost](https://github.com/15865042233-spec/Ghost)。

本机项目统一保存在 `G:\古斯特`。源代码、依赖环境、可控制的临时文件和缓存均保存在项目内。遵守 [AGENTS.md](AGENTS.md) 中的存放规则。

## 官方参考

- [OpenAI 开发快速入门](https://developers.openai.com/api/docs/quickstart)
- [API 身份验证和密钥管理](https://developers.openai.com/api/reference/overview#authentication)
- [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)
- [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [API 数据控制](https://developers.openai.com/api/docs/guides/your-data)
