from __future__ import annotations

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry
from ..session.store import GLOBAL_SCOPE


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _scope_key(ctx: ToolContext, scope: str) -> str:
    return GLOBAL_SCOPE if scope == "global" else ctx.chat_key


async def remember(ctx: ToolContext, content: str, category: str = "", importance: int = 3, scope: str = "chat") -> str:
    store = ctx.main.memory
    return store.remember(_scope_key(ctx, scope), content, category=category, importance=importance)


async def recall(ctx: ToolContext, query: str = "", limit: int = 0, scope: str = "chat") -> str:
    store = ctx.main.memory
    entries = store.recall(_scope_key(ctx, scope), query=query, limit=limit)
    if not entries:
        return texts.t("memory_empty")
    lines = [f"[{e.get('category', 'general')}|{e.get('importance', 3)}] {e.get('content', '')}" for e in entries]
    return "\n".join(lines)


async def forget(ctx: ToolContext, query: str, scope: str = "chat") -> str:
    store = ctx.main.memory
    removed = store.forget(_scope_key(ctx, scope), query)
    return utils.to_text({"removed": removed})


async def list_memory(ctx: ToolContext, scope: str = "chat") -> str:
    store = ctx.main.memory
    entries = store.entries(_scope_key(ctx, scope))
    if not entries:
        return texts.t("memory_empty")
    lines = [f"[{e.get('category', 'general')}|{e.get('importance', 3)}] {e.get('content', '')}" for e in entries]
    return "\n".join(lines)


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="remember",
        description="Store a long-term memory for the current chat (or globally). Use for stable facts about the user, preferences, ongoing matters.",
        parameters=_schema(
            {
                "content": _s(type="string", description="The fact to remember"),
                "category": _s(type="string", description="Category like preference / fact / todo"),
                "importance": _s(type="integer", description="1-5, higher survives longer; default 3"),
                "scope": _s(type="string", description="chat or global"),
            },
            ["content"],
        ),
        handler=remember,
    ))
    registry.register(Tool(
        name="recall",
        description="Search long-term memories relevant to a query for the current chat (or global scope).",
        parameters=_schema(
            {
                "query": _s(type="string", description="Search keywords; empty returns the newest ones"),
                "limit": _s(type="integer", description="Max entries, default from config"),
                "scope": _s(type="string", description="chat or global"),
            },
            [],
        ),
        handler=recall,
    ))
    registry.register(Tool(
        name="forget",
        description="Delete long-term memories matching a query for the current chat (or global scope).",
        parameters=_schema(
            {
                "query": _s(type="string", description="Text that the memories to delete contain"),
                "scope": _s(type="string", description="chat or global"),
            },
            ["query"],
        ),
        handler=forget,
    ))
    registry.register(Tool(
        name="list_memory",
        description="List all long-term memories of the current chat (or global scope).",
        parameters=_schema(
            {"scope": _s(type="string", description="chat or global")},
            [],
        ),
        handler=list_memory,
    ))
