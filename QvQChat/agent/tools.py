from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .. import texts, utils

Handler = Callable[..., Awaitable[Any]]


@dataclass
class ToolContext:
    main: Any = None
    sdk: Any = None
    config: Any = None
    chat_key: str = ""
    session_key: str = ""
    platform: str = ""
    detail_type: str = ""
    target_id: str = ""
    user_id: str = ""
    event: Any = None
    origin: str = "chat"
    confirmer: Any = None
    # 本次运行中 AI 实际发送过的目标 [(platform, target_type, target_id)]，
    # 供主动任务判断"已投递过内容"，避免总结段重复发送
    sent_log: list = field(default_factory=list)

    async def confirm(self, text: str, timeout: int = 60) -> bool:
        if self.confirmer is None:
            return False
        return bool(await self.confirmer(self, text, timeout))


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Handler
    origin: str = "builtin"
    danger: bool = False
    meta: dict = field(default_factory=dict)


def _allowed(name: str, whitelist: list[str] | None) -> bool:
    if whitelist is None:
        return True
    for entry in whitelist:
        if entry.endswith("*"):
            if name.startswith(entry[:-1]):
                return True
        elif name == entry:
            return True
    return False


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def unregister_prefix(self, prefix: str) -> int:
        names = [n for n in self._tools if n.startswith(prefix)]
        for name in names:
            del self._tools[name]
        return len(names)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self, origin: str | None = None) -> list[Tool]:
        tools = list(self._tools.values())
        if origin:
            tools = [t for t in tools if t.origin == origin]
        return tools

    def count_by_origin(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for tool in self._tools.values():
            counts[tool.origin] = counts.get(tool.origin, 0) + 1
        return counts

    @staticmethod
    def _disabled_match(name: str, disabled: list[str]) -> bool:
        for entry in disabled:
            if entry.endswith("*"):
                if name.startswith(entry[:-1]):
                    return True
            elif name == entry:
                return True
        return False

    def llm_schemas(self, whitelist: list[str] | None = None, disabled: list[str] | None = None) -> list[dict]:
        schemas: list[dict] = []
        for tool in self._tools.values():
            if disabled and self._disabled_match(tool.name, disabled):
                continue
            if not _allowed(tool.name, whitelist):
                continue
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return schemas

    async def invoke(self, name: str, arguments: dict, ctx: ToolContext, timeout: float = 120.0) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return texts.t("tool_not_found", name=name)
        if ctx.main is not None:
            checker = getattr(ctx.main, "check_tool_permission", None)
            if checker is not None:
                allowed, reason = checker(tool, ctx)
                if not allowed:
                    return reason
        try:
            result = await asyncio.wait_for(tool.handler(ctx, **(arguments or {})), timeout=timeout)
        except asyncio.TimeoutError:
            return texts.t("tool_timeout", name=name, seconds=int(timeout))
        except TypeError as e:
            return texts.t("tool_param_error", name=name, error=e)
        except Exception as e:
            return texts.t("tool_error", name=name, error=f"{type(e).__name__}: {e}")
        return utils.to_text(result)
