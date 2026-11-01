from __future__ import annotations

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _owner_of(ctx: ToolContext, scope: str) -> str:
    """可见域 → 存储键：chat=本会话 / platform=本适配器 / global=全局共享（默认仅本会话）。"""
    scope = str(scope or "chat").strip().lower()
    if scope == "global":
        return ""
    if scope == "platform":
        return str(getattr(ctx, "platform", "") or "")
    return str(getattr(ctx, "chat_key", "") or "")


async def knowledge_search(ctx: ToolContext, query: str, top_k: int = 2) -> str:
    results = ctx.main.knowledge.search(query, top_k=top_k, viewer=str(getattr(ctx, "chat_key", "") or ""))
    if not results:
        return texts.t("kb_empty")
    return "\n\n".join(
        f"[{index + 1}] {item['title']}" + (f" ({item['source']})" if item["source"] else "") +
        f"\n{item['snippet']}"
        for index, item in enumerate(results)
    )


async def knowledge_add(ctx: ToolContext, title: str, content: str, source: str = "",
                        scope: str = "chat", triggers: str = "") -> str:
    trig = [t.strip() for t in str(triggers or "").split(",") if t.strip()]
    entry = ctx.main.knowledge.add(
        title, content, source=source, triggers=trig or None, owner=_owner_of(ctx, scope)
    )
    return utils.to_text({"ok": True, "id": entry["id"], "scope": scope or "chat"})


async def knowledge_update(ctx: ToolContext, kb_id: str, title: str = "", content: str = "",
                           source: str = "", triggers: str | None = None, scope: str = "") -> str:
    updates: dict = {}
    if title:
        updates["title"] = title
    if content:
        updates["content"] = content
    if source:
        updates["source"] = source
    if triggers is not None: 
        updates["triggers"] = [t.strip() for t in str(triggers or "").split(",") if t.strip()]
    if scope:
        updates["owner"] = _owner_of(ctx, scope)
    entry = ctx.main.knowledge.update(kb_id, **updates)
    if entry is None:
        return texts.t("kb_not_found", kb_id=kb_id)
    return utils.to_text({"ok": True, "id": kb_id})


async def knowledge_delete(ctx: ToolContext, kb_id: str) -> str:
    removed = ctx.main.knowledge.delete(kb_id)
    return utils.to_text({"ok": removed})


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="knowledge_search",
        access="safe",
        description="Search the knowledge base for relevant passages (global entries plus this session's/platform's private ones). Use for facts, docs or stored notes.",
        parameters=_schema(
            {
                "query": _s(type="string", description="Search keywords"),
                "top_k": _s(type="integer", description="Max passages, default 2"),
            },
            ["query"],
        ),
        handler=knowledge_search,
    ))
    registry.register(Tool(
        name="knowledge_add",
        access="admin",
        description="Store a durable note into the knowledge base. DEFAULT scope is THIS session only; use scope=platform to share across this adapter's sessions, or scope=global ONLY when the user explicitly asks for a bot-wide note (operator-visible).",
        parameters=_schema(
            {
                "title": _s(type="string", description="Short title"),
                "content": _s(type="string", description="Full text content"),
                "source": _s(type="string", description="Optional source label"),
                "scope": _s(type="string", description="chat (default) / platform / global — global requires the user's explicit request"),
                "triggers": _s(type="string", description="Optional Lorebook trigger keywords, comma-separated (auto-inject when mentioned)"),
            },
            ["title", "content"],
        ),
        handler=knowledge_add,
    ))
    registry.register(Tool(
        name="knowledge_update",
        access="admin",
        description="Edit an existing knowledge base entry by id (title/content/source/triggers/scope; only provided fields change).",
        parameters=_schema(
            {
                "kb_id": _s(type="string", description="Entry id from knowledge_search / list"),
                "title": _s(type="string", description="New title (empty = unchanged)"),
                "content": _s(type="string", description="New content (empty = unchanged)"),
                "source": _s(type="string", description="New source label (empty = unchanged)"),
                "triggers": _s(type="string", description="New trigger keywords, comma-separated (empty = unchanged)"),
                "scope": _s(type="string", description="chat / platform / global (empty = unchanged)"),
            },
            ["kb_id"],
        ),
        handler=knowledge_update,
    ))
    registry.register(Tool(
        name="knowledge_delete",
        access="admin",
        description="Delete a knowledge base entry by id.",
        parameters=_schema(
            {"kb_id": _s(type="string", description="Entry id from knowledge_search / list")},
            ["kb_id"],
        ),
        handler=knowledge_delete,
    ))
