# 扩展与模块间通信

QvQChat 的能力来自 [ErisPulse](https://github.com/ErisPulse/ErisPulse) 的模块化架构。任何 ErisPulse 模块都可以扩展 QvQChat 的能力，不需要专门接口。

## 快速上手：让模块变成工具

模块在 `get_meta()` 声明 `services`，每个服务自动成为 QvQChat 的工具：

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
```

装上模块即上线，卸载即消失。无需重启 QvQChat。

## 三条可选深度集成服务

模块可以额外实现以下服务，参与智能体的行为定制：

### `qvq_prompts()` → 注入系统提示词

返回 `list[str]` 或 `list[{"text": str, "priority": int}]`。按 `priority` 升序拼接到系统提示词末尾。

适合：使用约定（"画完图后发给用户"）、行为约束、知识库说明。

### `qvq_personas()` → 注册人格预设

返回 `list[{"id", "name", "system", "tools"?}]`。id 自动加 `ext.<模块名>.` 前缀，模块卸载自动清理。

适合：注册专用人格（翻译专员、代码审查员等），`tools` 可选限定该人格可用的工具子集。

### `qvq_schemas()` → 显式参数 schema

返回 `dict[服务名, JSON Schema]`，覆盖签名推断。参数复杂时可用。

## 事件订阅

QvQChat 广播两个生命周期事件，扩展模块用 `sdk.lifecycle.on()` 订阅：

| 事件 | 时机 | 载荷字段 |
|---|---|---|
| `qvq.message` | 收到用户消息时 | `chat_key` `platform` `sender_id` `sender_name` `text` `is_group` |
| `qvq.replied` | 回复发出后 | `chat_key` `reply` `tools` |

```python
async def setup(self):
    sdk.lifecycle.on("qvq.message", self.on_message)

async def on_message(self, data):
    if "help" in data.get("text", ""):
        # 你可以在这里做任何事：记录、触发其他模块、推送通知等
        pass
```

## 作为服务被其他模块调用

QvQChat 自身声明了三个服务，可被其他模块反向调用：

```python
# 与智能体对话（同步等结果）
result = await sdk.module.call("QvQChat", "chat", "test:private:123", "帮我查一下天气")
# 运行一段提示词并将结果发到指定会话
await sdk.module.call("QvQChat", "run_prompt", "onebot11:group:456", "播报今日新闻")
# 获取运行状态
status = await sdk.module.call("QvQChat", "get_status")
```

| 服务 | 签名 | 说明 |
|---|---|---|
| `chat` | `(session_id, prompt, persona="")` | 对话，返回文本；`session_id` 为 `platform:detail_type:target_id` |
| `run_prompt` | `(chat_key, prompt, ...)` | 运行提示词，可将结果发送到目标会话 |
| `get_status` | `()` | 运行状态摘要 |

## 附件

用户在对话中发送的文件与图片：

- **图片**：自动转 base64 注入模型请求（支持 Ctrl+V 粘贴）；模型不支持视觉时自动剥离重试
- **任意文件**（zip / pdf / 代码等）：按 SHA-256 hash 去重后落盘到 `data/QvQChat/uploads/`，文件路径以 `[attachment xxx] 已保存到: /path/to/file` 形式追加到对话——AI 拿到路径后可自行用 `read_file` / `run_command` 等工具读取、解压或分析
- **附件编辑不丢失**：编辑历史消息时，图片等多模态段自动保留，仅文本段被替换

AI 也可以主动通过 `send_message` 的 `path` 参数向用户发送文件或图片。

## 权限模型

| 来源 | 权限 | 说明 |
|---|---|---|
| Dashboard / 本地 | 框架主人 | 全部工具可用 |
| 聊天端 · 管理员 | 管理员 | `admins` 列表中的用户，危险工具可用（需确认） |
| 聊天端 · 普通用户 | 基础安全集 | 发消息、记忆、只读文件、定时任务 |

定时任务按**创建者的权限**运行：管理员创建的任务以管理员身份执行，普通用户创建的任务中危险工具不可用。

## MCP

支持 stdio 与 Streamable HTTP 两种传输。MCP 服务器的工具自动并入同一工具集，与内置工具、生态桥接工具平等参与模型选择。

在 Dashboard「MCP」页直接添加 / 连接 / 断开，或修改 `mcp_servers` 配置后重启。
