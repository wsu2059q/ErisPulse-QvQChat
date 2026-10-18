<div align="center">

[English](./README.en.md) | 简体中文

<img src="https://raw.githubusercontent.com/ErisPulse/ErisPulse/main/.github/assets/ErisPulseLogo.png" width="180" alt="QvQChat" />

# QvQChat

**一个智能体完成所有事。**

<p>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/pypi/v/ErisPulse-QvQChat?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/ErisPulse-QvQChat/pkgs/container/erispulse-qvqchat"><img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
  <a href="https://github.com/ErisPulse/ErisPulse"><img src="https://img.shields.io/badge/Powered_by-ErisPulse-8FB7E0?style=for-the-badge&logo=bookstack&logoColor=white" alt="ErisPulse"></a>
</p>

<img src=".github/assets/overview.png" width="860" alt="QvQChat Dashboard" />

</div>

---

基于 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 的通用智能体模块。围绕工具循环构建：收发消息、调用生态模块服务、编写并运行代码、操作电脑、生成图片语音、管理定时任务与长期记忆，全部通过同一套工具协议完成。

## 界面

| 对话 | 模型池 |
|---|---|
| ![对话](.github/assets/chat.png) | ![模型池](.github/assets/models.png) |

对话页支持流式输出、工具调用串行时间线、Markdown 表格与代码高亮、发送暂存队列、停止生成。左侧边栏管理会话（置顶 / 归档 / AI 自动命名 / 运行指示），网页端与聊天端共用同一管道——聊天侧发起的任务，网页端实时可见并可直接停止。

## 核心特性

| 特性 | 说明 |
|---|---|
| 工具循环智能体 | 模型输出工具调用 → 并发执行 → 结果回填 → 继续推理，直到给出最终回答 |
| 流式对话 | SSE 逐字输出，工具步骤实时可见；浏览器刷新 / 切走再回来，进度不丢 |
| 上下文压缩 | 超过 token 阈值自动把旧对话压缩为摘要（默认 128000 估算，可自定义），长任务不怕撑爆 |
| 生态服务桥 | 自动发现装有的生态模块声明的服务并转成工具，装卸模块即增减能力，无需重启 |
| MCP 客户端 | 支持 stdio 与 Streamable HTTP 两种传输，MCP 工具并入同一工具集 |
| 子智能体 | `spawn_agent` 派出拥有独立会话的子智能体探索任务，只汇报结论，主对话记忆不被污染 |
| 进程内执行 | `run_python_sdk` 直接在主进程运行 Python，可访问 sdk / adapter / storage 等运行时对象 |
| 内置工具 | SendDSL 发送、适配器原生 API、跨模块调用、会话接管、shell / 文件、Python 执行、生图、语音、记忆、定时任务 |
| 电脑操作沙箱 | strict / standard / permissive 三级安全，危险操作聊天内确认，全程审计 |
| 会话接管 | 管理员可让智能体独占一个会话，期间所有消息由智能体优先处理 |
| 人格系统 | 人格 = 系统提示词 + 开场对话 + 工具白名单，可按会话绑定 |
| 定时任务 | cron / 一次性 / 间隔三种计划，持久化存储，重启后过期任务自动补发 |
| 视觉理解 | 图片自动注入模型（不支持图片时自动剥离重试）；Ctrl+V 直接粘贴截图 |
| 附件上传 | 支持任意文件（zip / pdf 等），按内容 hash 去重落盘，路径交给 AI 自行处理 |
| 分享会话 | 生成临时只读链接（可设有效期与 token 预算），导出 Markdown |
| AI 自动命名 | 会话首轮回复后自动生成简短标题 |
| 扩展规范 | 外部模块即扩展：声明服务自动成为工具，可选 `qvq_prompts` / `qvq_personas` / `qvq_schemas` 深度集成 |

<div align="center">

### 社交平台

<img src=".github/assets/qq.png" width="680" alt="QQ 群聊" />

</div>

## 安装

```bash
epsdk install ErisPulse-QvQChat
```

或

```bash
pip install ErisPulse-QvQChat
```

或 Docker：

```bash
docker run -d --name qvqchat -p 8000:8000 ghcr.io/wsu2059qq/erispulse-qvqchat:latest
```

## 快速开始

1. 打开 Dashboard 的 QvQChat 视窗，在「模型池」添加一个 OpenAI 兼容模型（名称、Base URL、API Key、模型名四项）
2. 私聊机器人，或群里 @ 它，即可对话
3. 需要更多能力时装对应生态模块（生图、Cron 等），智能体自动获得新工具

聊天命令：

| 命令 | 说明 |
|---|---|
| `/agent` | 查看帮助 |
| `/agent 重置` | 重置当前会话对话 |
| `/agent 人格 [id]` | 查看或切换人格 |
| `/agent 任务` | 查看定时任务 |
| `/agent 状态` | 运行状态摘要 |
| `/agent 接管 [分钟]` | 接管当前会话（管理员） |
| `/agent 释放` | 释放接管 |

## 电脑操作安全

| 级别 | 行为 |
|---|---|
| `strict` | 禁止执行命令与代码，仅允许白名单目录内只读文件操作，写入需确认 |
| `standard`（默认） | 危险命令聊天内确认后执行，文件访问限制在白名单目录 |
| `permissive` | 放开执行与路径限制，全部操作落入审计记录 |

## 工具权限模型

工具分两类访问级别：

- **基础安全集（所有人可用）**：聊天发送（send_message / send_dsl）、平台查询、长期记忆四件套、只读文件（read_file / list_dir）、定时任务三件套（任务执行时按创建者权限再校验一次）
- **管理员独占（默认清单）**：run_command、run_python、run_python_sdk、spawn_agent、write_file、call_adapter_api、call_module、会话接管，以及全部 `eco_*` / `mcp_*` 扩展工具

规则：`admins` 为空时聊天侧无人拥有管理员权限（Dashboard / 本地来源除外），主人需把自己的用户 id 填进 `admins`；`safe_tools` 可把指定工具显式放行给所有人；非管理员调用受限工具会得到明确提示。开启 `owner_only` 后整个智能体仅限主人使用。

黑名单命令始终拒绝；开启 `trust_agent` 后跳过所有确认但仍记录审计。

## 扩展 QvQChat

> 详细的模块间通信、事件订阅、附件处理与权限模型见 [docs/inter-module.md](./docs/inter-module.md)。

QvQChat 的扩展就是普通的 ErisPulse 模块，不需要任何专门接口：

**第一层（自动）**：模块在 `get_meta()` 声明 `services`，每个服务自动成为智能体的工具，调用走 `sdk.module.call`。装上模块、声明服务，能力即上线，卸载即消失。

**第二层（可选规范）**：模块额外实现以下任意服务，即可深度参与智能体行为：

| 服务 | 返回 | 作用 |
|---|---|---|
| `qvq_prompts()` | `list[str]` 或 `list[{"text", "priority"}]` | 注入系统提示词 |
| `qvq_personas()` | `list[{"id", "name", "system", "tools"?}]` | 注册人格预设 |
| `qvq_schemas()` | `dict[服务名, JSON Schema]` | 为本模块的服务提供显式参数 schema |

示例（生图扩展模块）：

```python
from ErisPulse.Core.Bases import BaseModule, ModuleMeta

class Main(BaseModule):
    @staticmethod
    def get_meta() -> ModuleMeta:
        return ModuleMeta(name="Draw", services=[
            {"name": "draw", "description": "根据描述生成图片，返回图片 URL"},
        ])

    async def draw(self, prompt: str, size: str = "1024x1024"):
        """根据描述生成图片"""
        return {"image_url": "https://..."}

    async def qvq_prompts(self):
        return [{"text": "画图后用 send_message 把图片发给用户。", "priority": 40}]
```

**事件订阅**：QvQChat 在每条消息处理时广播 `qvq.message`，回复后广播 `qvq.replied`。扩展模块用 `sdk.lifecycle.on("qvq.message")` 即可订阅。

## 鉴权与独立访问

- QvQChat 的全部 API 路由都做鉴权：装有 Dashboard 时复用 Dashboard 的 token 校验；未装 Dashboard 时使用自己的访问令牌——首次启动自动生成并打印在日志中
- 独立访问地址：`/QvQChat/view`，无令牌时展示登录页
- Dashboard 侧边栏保留 QvQChat 视窗入口（iframe 嵌入同一页面）

## 定时任务格式

| 格式 | 示例 | 含义 |
|---|---|---|
| `cron:分 时 日 月 周` | `cron:0 9 * * 1-5` | 工作日每天 9 点 |
| `at:YYYY-MM-DD HH:MM` | `at:2026-10-17 09:00` | 指定时刻一次性 |
| `in:Nm/Nh/Nd` | `in:30m` | 延迟一段时长 |
| `every:Nm/Nh/Nd` | `every:2h` | 固定间隔循环 |

## 配置

配置位于 `QvQChat` 节，可通过 Dashboard「设置」页修改。

<details>
<summary>全部配置项</summary>

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `default_model` | str | `""` | 默认模型（模型池 id），留空使用池中第一个 |
| `temperature` | float | `0.7` | 默认采样温度 |
| `max_tokens` | int | `0` | 单次回复最大生成 token，0 = 不限制（跟随模型上限） |
| `model_failover` | bool | `True` | 失败时按池顺序切换备用模型 |
| `reply_private` | bool | `True` | 私聊消息触发智能体 |
| `reply_at` | bool | `True` | 群聊被 @ 时触发智能体 |
| `wake_prefixes` | list | `[]` | 群聊文本唤醒前缀 |
| `command_prefixes` | list | `["#", "/"]` | 命令消息前缀 |
| `admins` | list | `[]` | 管理员用户 id |
| `owner_only` | bool | `False` | 仅框架主人可用 |
| `admin_tools` | list | 见说明 | 仅管理员可用的工具 |
| `safe_tools` | list | `[]` | 额外放行给所有人的工具 |
| `security_level` | str | `"standard"` | 电脑操作安全级别 |
| `trust_agent` | bool | `False` | 完全信任智能体 |
| `work_dirs` | list | `[]` | 文件访问白名单目录 |
| `command_timeout` | int | `60` | 单条命令执行超时（秒） |
| `blocked_patterns` | list | `[]` | 追加的命令黑名单正则 |
| `confirm_timeout` | int | `60` | 危险操作确认超时（秒） |
| `context_limit` | int | `30` | 每会话上下文条数上限 |
| `context_compress_tokens` | int | `128000` | 上下文压缩阈值（估算 token，0 关闭） |
| `history_seed` | int | `20` | 冷启动从收件箱回填的历史条数 |
| `forward_enabled` | bool | `True` | 长回复自动转为合并转发消息 |
| `forward_threshold` | int | `600` | 任务类回复超过该字符数转为合并转发 |
| `context_summary` | bool | `True` | 上下文超限时自动摘要旧对话 |
| `tool_notice_mode` | str | `"brief"` | 长任务播报：off / brief（AI 发言）/ all |
| `sensitive_paths` | list | 内置 | 敏感文件/目录匹配 |
| `aggregate_window` | float | `5.0` | 消息聚合窗口（秒） |
| `extra_prompts` | list | `[]` | 自定义注入提示词 |
| `daily_token_limit` | int | `0` | 单日 token 限额 |
| `usage_retention_days` | int | `14` | 用量统计保留天数 |
| `memory_max` | int | `200` | 每会话长期记忆上限 |
| `memory_recall` | int | `6` | 每次注入的相关记忆条数 |
| `tool_timeout` | int | `120` | 单次工具调用超时（秒） |
| `max_tool_rounds` | int | `15` | 工具循环最大轮数 |
| `max_tool_calls` | int | `30` | 单次对话工具总次数上限 |
| `disabled_tools` | list | `[]` | 禁用的工具名 |
| `eco_exclude` | list | `["QvQChat"]` | 不桥接服务目录的模块 |
| `eco_include` | list | `[]` | 仅桥接这些模块 |
| `mcp_timeout` | int | `30` | MCP 请求超时（秒） |
| `task_check_interval` | int | `20` | 任务轮询间隔（秒） |
| `task_use_cron_module` | bool | `True` | 装有 ErisPulse-Cron 时托管 cron |
| `view_token` | str | `""` | 独立访问令牌 |
| `skills_dir` | str | `data/QvQChat/skills` | 技能目录 |
| `skills_disabled` | list | `[]` | 禁用的技能名 |

</details>

## 作为服务被其他模块调用

| 服务 | 签名 | 说明 |
|---|---|---|
| `chat` | `(session_id, prompt, persona="")` | 与智能体对话，返回文本 |
| `run_prompt` | `(chat_key, prompt, ...)` | 运行提示词，可将结果发送到目标会话 |
| `get_status` | `()` | 运行状态摘要 |

## 开发

```bash
pip install -e .[test]
pytest
```

## License

[MIT](./LICENSE)
