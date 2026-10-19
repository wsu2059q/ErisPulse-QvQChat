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
class ChatResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict = field(default_factory=dict)


class EngineError(RuntimeError):
    pass
