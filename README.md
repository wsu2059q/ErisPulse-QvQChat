<div align="center">

**简体中文** | [繁體中文](README.zh-TW.md) | [English](README.en.md) | [日本語](README.ja.md) | [Русский](README.ru.md)

<img src="https://raw.githubusercontent.com/ErisPulse/ErisPulse/main/.github/assets/ErisPulseLogo.png" width="180" alt="QvQChat" />

</div>

# QvQChat

**ErisPulse 的通用智能体模块：在你的机器人所在的平台上聊天、调用工具、写代码并执行、安排定时任务、维护长期记忆。**

QvQChat 的核心是一个工具循环。你给它接上模型之后，模型可以通过任意 ErisPulse 适配器收发消息、调用其它已安装模块的服务、读写文件、执行 shell 命令和 Python 代码、创建定时任务，并把值得记住的东西存进长期记忆。任意时刻有哪些工具可用，只取决于你装了什么，模块装卸不需要重启。

它写给已经在跑 ErisPulse 机器人、希望机器人真正去做事而不只是回话的人。你往模型池里填任意 OpenAI 兼容的接口，决定谁可以用哪些工具，之后每装一个生态模块，智能体就多一批能力。

模块需要 ErisPulse 2.8.0 或更高版本，以及至少一个平台适配器。它自带一个网页控制台，脱离 Dashboard 也能独立使用；聊天侧和网页侧走同一条管道，从 QQ 发起的任务会实时出现在浏览器里，也可以在浏览器里直接停掉。

<p>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/pypi/v/ErisPulse-QvQChat?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/ErisPulse-QvQChat/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/wsu2059q/ErisPulse-QvQChat/ci.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/ErisPulse-QvQChat/pkgs/container/erispulse-qvqchat"><img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
</p>

<img src=".github/assets/overview.png" width="860" alt="QvQChat 网页控制台" />

---

## 安装

用 ErisPulse CLI：

```bash
epsdk install ErisPulse-QvQChat
```

或用 pip（要求 Python 3.10+、ErisPulse >= 2.8.0，并至少安装一个平台适配器）：

```bash
pip install ErisPulse-QvQChat
```

或用 Docker。镜像基于 ErisPulse 官方镜像构建，已内置本模块：

```bash
docker run -d --name qvqchat -p 8000:8000 --restart unless-stopped ghcr.io/wsu2059q/erispulse-qvqchat:latest
```

## 快速开始

1. 安装模块和至少一个适配器，例如 `epsdk install ErisPulse-OneBotAdapter`。
2. 打开 Dashboard，进入 QvQChat 视窗。在模型池页面添加一个 OpenAI 兼容模型：名称、Base URL、API Key、模型名四项就够了。
3. 告诉智能体谁是管理员。`admins` 为空时聊天侧没有人拥有管理员权限，执行命令这类工具在聊天侧就不可用：

```toml
[QvQChat]
admins = ["123456"]   # 你在聊天平台上的用户 id
```

4. 打开 `http://<host>:8000/QvQChat/view` 进入独立控制台，或直接用 Dashboard 侧边栏的 QvQChat 入口。装有 Dashboard 时复用它的登录令牌；没装时 QvQChat 会在首次启动自动生成访问令牌并打印到日志，你也可以自己配置 `QvQChat.view_token`。
5. 私聊机器人，或在群里 @ 它。它在你的用户已经在的地方回答。

聊天命令的主命令是 `/qvq`（`/agent` 保留为兼容别名，各子命令同时接受英文写法）：

| 命令 | 作用 |
|---|---|
| `/qvq` | 查看命令帮助 |
| `/qvq 重置` | 重置当前会话的对话 |
| `/qvq 人格 [id]` | 查看或切换人格 |
| `/qvq 开场` | 重发当前人格的开场白（管理员） |
| `/qvq 任务` | 查看定时任务 |
| `/qvq 记忆` | 查看记忆、事实与用户画像，管理员可分级清空 |
| `/qvq 压缩` | 立即压缩当前会话上下文 |
| `/qvq 状态` | 模型、工具与会话概况 |
| `/qvq 接管 [分钟]` | 接管当前会话（管理员），默认 10 分钟 |
| `/qvq 释放` | 释放接管 |

---

## 智能体能做什么

### 带着一整套实用工具的工具循环

内置工具覆盖消息收发（`send_message`、`send_dsl`）、平台 API、文件访问、shell 与 Python 执行、长期记忆、知识库、定时任务和人格。`run_python_sdk` 在主进程内执行 Python，脚本可以直接使用 sdk、适配器和 storage。`spawn_agent` 会为值得单独探索的任务派出一个独立会话的子智能体，只把结论带回主对话。同一个工具连续失败两次时，会注入一条带错误摘要的修正提示，让模型自己调整参数重试（`tool_self_heal`，默认开启）。

工具还有另外两个来源：你连接的每个 MCP 服务器都会贡献自己的工具（支持 stdio 和 Streamable HTTP）；装了声明 `services` 的 ErisPulse 模块，它的服务也会被自动调用。见下文[扩展 QvQChat](#扩展-qvqchat)。

完成一次新的多步任务后，你可以让模型把做法保存为技能。技能就是 `data/QvQChat/skills` 下的 Markdown 文件，需要时注入系统提示；`skill_induct` 可以整体关掉这个机制。

### 网页控制台

<img src=".github/assets/chat.png" width="49%" alt="对话页" /> <img src=".github/assets/models.png" width="49%" alt="模型池页" />

`/QvQChat/view` 的对话页流式输出回复，每个工具调用在时间线上各占一步，模型的思考过程折叠展示。这里有为想晚点再发的消息准备的暂存队列，也有停止正在运行任务的按钮。刷新页面或者过一会再回来，跑着的任务会从原处接上。会话可以置顶、归档、改名，新会话由模型自动命名。任何会话都能生成临时只读分享链接，可以设过期时间和 token 预算，也可以导出为 Markdown。

控制台同时承载管理页面：模型池、人格、知识库、审计记录、任务执行记录和成本估算。设置页用合适的控件渲染每一个配置项，带校验和脏检查。需要程序化接入时，还有 OpenAI 兼容端点 `GET /v1/models` 和 `POST /v1/chat/completions`（含流式），用同一个访问令牌做 Bearer 认证。

因为两侧共用同一条管道，智能体在聊天平台发起的任务会逐个工具调用地实时出现在浏览器里，并且可以在那边停掉。

### 群聊与人格

群里被 @ 时智能体醒来，可以配置唤醒前缀，私聊默认触发。纯对话的回复按段落切开逐条发送，节奏可配、接近真人；工具任务的结果在平台支持时打包成合并转发卡片。开启 `reply_narrate` 后，智能体做工具任务时会像工作播报一样边做边说：动手前说一句要做什么，每个结果简短汇报，最后给一句结论，每句话单独发到群里。

人格携带系统提示、开场白、语气参数和示例对话，还可以限定可用的工具子集。群成员可以有成员级人格，逐级回落到群级和全局人格。`group_isolation` 则让群里每位成员拥有独立的上下文、人格和记忆，适合更在意隔离的群。在群里不被 @ 也主动插话这件事，核心故意没做：它交给参与决策插件判断，并且在你开启 `participation_enabled` 之前保持关闭（见下文 QvQStalker）。

<img src=".github/assets/qq.png" width="680" alt="智能体在 QQ 群里工作" />

### 记忆、用户画像与知识库

智能体按会话维护长期记忆，另有全局作用域，每次请求注入相关的几条，也可以通过工具让它记住或忘记某件事。偏好、约定这类事实会从对话中自动抽取，之后注入回来。在此之上，同一个用户在各会话的事实和记忆会定期（默认每 6 小时）固化为跨会话画像；30 天内没有任何新事实强化的画像条目会自动淘汰。`/qvq 记忆` 和控制台的记忆页可以查看存了什么，也能按类别清空。

知识库存放较长的文档。条目分块后按词面打分检索，相关片段自动注入系统提示。条目也可以像 SillyTavern 世界书那样配置触发关键词，只有聊到相关内容时才注入对应设定。如果配置了 OpenAI 兼容的 embedding 接口，检索会切换为余弦相似度，链路上任何一环不可用时自动回退词面检索。

### 会自我照料的模型池

模型放在按提供商组织的池子里，任意 OpenAI 兼容接口都能用，常用厂商有预设，添加只是一张短表单。模型条目会从 models.dev 目录自动补全能力位（视觉、文件、工具调用、推理）和价格，两者都可以手工覆盖。请求失败时沿池顺序故障转移，连续失败三次的模型进入指数退避的冷却期，故障转移链会跳过缺少所需能力的模型。主模型不会看图时，由视觉模型代为描述再把文字交给它。难度感知路由可以把寒暄分给便宜模型、代码和长分析分给强模型，属于实验特性，默认关闭。用量按模型按日记录并给出成本估算，摘要、起标题这类后台任务可以通过 `task_models` 指定给更便宜的模型。如果你愿意（`self_config`，默认开启），智能体甚至能通过仅管理员可用的工具自己管理模型池、MCP 服务器和设置。

### 扛得住长任务的上下文

旧的工具输出会持续瘦身。估算的上下文规模超过阈值时（CJK 口径估算，默认 128000），旧轮次被摘要成一段早期上下文摘要而不是直接丢弃；压缩也可以每 N 轮预防性执行，或用 `/qvq 压缩` 手动触发。可选的预算模式按优先级把系统提示的各部件和历史装进所选模型的上下文窗口，溢出时触发压缩，压缩的同时还会把实体、偏好和待办抽取为事实。工具预算给得很宽（默认 50 轮、150 次调用），接近上限时模型收到的是收敛提醒，而不是被硬生生掐断。

### 重启也扛得住的定时任务

定时任务由智能体自己通过工具用自然语言创建。支持四种格式：`cron:0 9 * * 1-5`、`at:2026-10-17 09:00`、`in:30m`、`every:2h`。标记为深度的任务按三段执行：计划、执行、审查，审查发现缺口时自动做一轮有界修正。任务的执行记录会落盘，可在控制台查看。装有 ErisPulse-Cron 时 cron 任务交给它托管。进程在生成中途重启的话，被中断的回复会被识别并重跑，发送失败队列在启动时重放，中断的任务执行记录也会被标记（`recovery_enabled` 及相关配置）。

### 安全模型

电脑操作分三个级别。`strict` 不执行任何命令和代码，只允许白名单目录内的只读文件操作。`standard`（默认）下危险命令要在聊天里确认后才执行，确认提示会带出命令全文，文件访问限制在 `work_dirs` 内。`permissive` 解除限制，改为把所有操作记入审计日志。工具分为所有人可用的基础安全集（发消息、记忆、只读文件、定时任务）和管理员专属（执行、写文件、子智能体、适配器与模块调用）。定时任务以创建者的权限运行。`admins` 决定谁是管理员，`safe_tools` 可以把指定工具放行给所有人，`owner_only` 把整个智能体限制为主人使用，`trust_agent` 跳过确认但仍然全部审计。

---

## 配套插件

有两个独立模块扩展了 QvQChat，也顺带展示了扩展点能做什么：

- [ErisPulse-QvQStalker](https://github.com/wsu2059q/ErisPulse-QvQStalker)：让智能体通过旁听通道关注群聊，自己判断什么时候该插话。热度跟踪、五层判定和冲动值共同决定它何时开口，15 项行为参数通过 `qvq_settings` 注册，在设置页里直接调。
- [ErisPulse-QvQMemes](https://github.com/wsu2059q/ErisPulse-QvQMemes)：给智能体一个表情包习惯。`send_sticker` 工具让模型自己挑当下该发哪张，群里的图片经旁听通道自动收录并由视觉模型打标签，新鲜度降权让它不至于翻来覆去就那几张。

在你开启 `participation_enabled` 之前，群聊参与始终是关闭的；装插件本身不会打开这道门。

## 扩展 QvQChat

扩展就是普通的 ErisPulse 模块，不需要任何专门接口。模块在 `get_meta()` 里声明 `services`，每个服务就自动成为智能体的工具，装上即生效、卸载即消失：

```python
from ErisPulse.Core.Bases import BaseModule, ModuleMeta

class Main(BaseModule):
    @staticmethod
    def get_meta() -> ModuleMeta:
        return ModuleMeta(name="Draw", services=[
            {"name": "draw", "description": "根据描述生成图片，返回图片 URL"},
        ])

    async def draw(self, prompt: str, size: str = "1024x1024"):
        return {"image_url": "https://..."}
```

想集成得更深，模块可以实现以下约定服务中的任意几个，生态桥会发现它们并在模块装卸时热刷新：

- `qvq_personas()` 返回人格预设（id、名称、系统提示，可选的工具子集）；
- `qvq_schemas()` 为本模块的服务返回显式 JSON Schema，覆盖签名推断；
- `qvq_settings()` 声明配置描述符，设置页会渲染它们，值经 `plugin_config` 服务和 `qvq.plugin_config` 事件回流到插件。

模块也可以订阅 `qvq.message`、`qvq.replied` 这类生命周期事件。反过来，QvQChat 自己声明了 `chat`、`run_prompt`、`get_status` 三个服务供其它模块调用。完整的约定，包括附件处理和权限模型，见 [docs/inter-module.md](docs/inter-module.md)。

## 配置

所有配置都在 `QvQChat` 节下，可以在 Dashboard 设置页里修改，按模型、触发、对话、工具、生态、MCP、记忆、知识库、技能、任务、用量、安全、参与、访问分组。本页提到的每一个键，从 `wake_prefixes`、`user_rate_limit` 到 `daily_token_limit`、`delivery_profiles`，都是那里一个带说明的普通配置项。最近的变更见 [CHANGELOG.md](CHANGELOG.md)，模块的内部结构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 开发

```bash
git clone https://github.com/wsu2059q/ErisPulse-QvQChat
cd ErisPulse-QvQChat
pip install -e .[test]
pytest
```

## 许可证

[MIT](LICENSE)
