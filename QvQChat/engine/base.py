from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict


@dataclass
class ChatRequest:
    messages: list
    tools: list | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    needs: list | None = None


@dataclass
class TaskSpec:
    """任务分派规格：kind 为任务类别（chat/compact/title/announce/vision/tool_heavy…），
    needs 为能力需求列表，prefer 为偏好（如 "cheap" 按成本升序），model 为显式指定模型。
    解析优先级：显式 model > cfg.task_models[kind] > needs 过滤 > prefer=cheap > 池序。
    chat_key 为会话键（可选）：仅用于难度感知路由的分级缓存（routing_ttl），不影响模型解析。"""

    kind: str = "chat"
    needs: list | None = None
    prefer: str = ""
    model: str | None = None
    chat_key: str = ""


@dataclass
class ChatResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict = field(default_factory=dict)
# 引擎因模型/平台拒图而剥图重试过：上层据此补视觉描述，避免模型"没看见图"却当成看过
    images_stripped: bool = False
    stripped_image_urls: list = field(default_factory=list)


class EngineError(RuntimeError):
    pass
