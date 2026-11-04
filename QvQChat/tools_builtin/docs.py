"""内置文档检索工具：search_erispulse_docs / read_erispulse_doc / refresh_docs。"""
from __future__ import annotations

from .. import texts
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


async def search_docs(ctx: ToolContext, query: str, top_k: int = 5) -> str:
    docs = getattr(ctx.main, "docs", None)
    if docs is None:
        return texts.t("docs_disabled")
    results = docs.search(query, top_k=top_k)
    if not results:
        return texts.t("docs_empty", query=query)
    blocks = []
    for index, item in enumerate(results):
        blocks.append(f"[{index + 1}] {item['title']}  ({item['file']})\n{item['snippet']}")
    return texts.t("docs_search_header") + "\n\n" + "\n\n".join(blocks)


async def read_doc(ctx: ToolContext, file: str, limit: int = 8000) -> str:
    docs = getattr(ctx.main, "docs", None)
    if docs is None:
        return texts.t("docs_disabled")
    return docs.read(file, limit=limit)


async def refresh_docs(ctx: ToolContext) -> str:
    docs = getattr(ctx.main, "docs", None)
    if docs is None:
        return texts.t("docs_disabled")
    info = await docs.ensure_synced(force=True)
    return texts.t(
        "docs_refresh_done",
        source=info.get("source", "-"),
        version=info.get("version", "-"),
        files=info.get("files", 0),
        error=info.get("error", "") or "-",
    )


def register(registry: ToolRegistry, main) -> None:
    docs = getattr(main, "docs", None)
    if docs is None:
        return
    registry.register(Tool(
        name="search_erispulse_docs",
        access="safe",
        description=(
            "Search the local ErisPulse framework documentation (matched to the installed framework version). "
            "Use this to verify module/API behavior when writing or debugging ErisPulse modules instead of guessing."
        ),
        parameters=_schema(
            {
                "query": _s(type="string", description="Keywords: API name, module name, error text, topic"),
                "top_k": _s(type="integer", description="Max passages, default 5"),
            },
            ["query"],
        ),
        handler=search_docs,
    ))
    registry.register(Tool(
        name="read_erispulse_doc",
        access="safe",
        description="Read a full ErisPulse documentation file by its repo-relative path (from search results).",
        parameters=_schema(
            {
                "file": _s(type="string", description="Doc path from search results, e.g. developer-guide/module.md"),
                "limit": _s(type="integer", description="Max characters, default 8000"),
            },
            ["file"],
        ),
        handler=read_doc,
    ))
    registry.register(Tool(
        name="refresh_docs",
        access="admin",
        description="Force re-sync of the ErisPulse documentation cache to the installed framework version.",
        parameters=_schema({}, []),
        handler=refresh_docs,
    ))
