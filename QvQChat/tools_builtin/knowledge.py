from __future__ import annotations

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


async def knowledge_search(ctx: ToolContext, query: str, top_k: int = 2) -> str:
    results = ctx.main.knowledge.search(query, top_k=top_k)
    if not results:
        return texts.t("kb_empty")
    return "\n\n".join(
        f"[{index + 1}] {item['title']}" + (f" ({item['source']})" if item["source"] else "") +
        f"\n{item['snippet']}"
        for index, item in enumerate(results)
    )


async def knowledge_add(ctx: ToolContext, title: str, content: str, source: str = "") -> str:
    entry = ctx.main.knowledge.add(title, content, source=source)
    return utils.to_text({"ok": True, "id": entry["id"]})


async def knowledge_delete(ctx: ToolContext, kb_id: str) -> str:
    removed = ctx.main.knowledge.delete(kb_id)
    return utils.to_text({"ok": removed})


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="knowledge_search",
        access="safe",
        description="Search the shared knowledge base for relevant passages. Use for facts, docs or notes stored by the operator.",
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
        description="Store a durable note into the shared knowledge base (retrievable later and auto-injected when relevant).",
        parameters=_schema(
            {
                "title": _s(type="string", description="Short title"),
                "content": _s(type="string", description="Full text content"),
                "source": _s(type="string", description="Optional source label"),
            },
            ["title", "content"],
        ),
        handler=knowledge_add,
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
