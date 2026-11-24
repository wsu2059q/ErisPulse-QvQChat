from __future__ import annotations

import time

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry
from ..conversation.memory import GLOBAL_SCOPE


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _scope_key(ctx: ToolContext, scope: str) -> str:
    # user 维度：同一 platform 同一 user_id 全会话共享，仅私聊自动注入；缺失时退回本会话键
    if scope == "user":
        if ctx.user_id and ctx.platform:
            return f"usermem:{ctx.platform}:{ctx.user_id}"
        return ctx.chat_key
    return GLOBAL_SCOPE if scope == "global" else ctx.chat_key


async def remember(ctx: ToolContext, content: str, category: str = "", importance: int = 3, scope: str = "chat") -> str:
    store = ctx.main.memory
    return await store.remember(_scope_key(ctx, scope), content, category=category, importance=importance)


async def recall(ctx: ToolContext, query: str = "", limit: int = 0, scope: str = "chat") -> str:
    store = ctx.main.memory
    entries = await store.recall(_scope_key(ctx, scope), query=query, limit=limit)
    if not entries:
        return texts.t("memory_empty")
    lines = [f"[{e.get('category', 'general')}|{e.get('importance', 3)}] {e.get('content', '')}" for e in entries]
    return "\n".join(lines)


async def forget(ctx: ToolContext, query: str, scope: str = "chat") -> str:
    store = ctx.main.memory
    removed = await store.forget(_scope_key(ctx, scope), query)
    return utils.to_text({"removed": removed})


async def list_memory(ctx: ToolContext, scope: str = "chat", page: int = 1,
                      category: str = "", q: str = "") -> str:
    """记忆分页浏览：大会话记忆多了以后 AI 自己也要能按页/按类/按关键词翻。"""
    store = ctx.main.memory
    entries = await store.entries(_scope_key(ctx, scope))
    entries.sort(key=lambda e: e.get("ts", 0), reverse=True)
    if category:
        entries = [e for e in entries if str(e.get("category") or "") == category.strip()]
    if q.strip():
        needle = q.strip().lower()
        entries = [e for e in entries if needle in str(e.get("content") or "").lower()]
    total = len(entries)
    if not total:
        return texts.t("memory_empty")
    page_size = 40
    try:
        page = max(1, int(page or 1))
    except (TypeError, ValueError):
        page = 1
    pages = (total + page_size - 1) // page_size
    page = min(page, pages)
    window = entries[(page - 1) * page_size : (page - 1) * page_size + page_size]
    lines = [
        f"[{e.get('category', 'general')}|{e.get('importance', 3)}|{time.strftime('%m-%d', time.localtime(float(e.get('ts') or 0)))}] {e.get('content', '')}"
        for e in window
    ]
    header = f"total={total} page={page}/{pages}" + ("" if pages <= 1 else " (use page=N to browse)")
    return header + "\n" + "\n".join(lines)


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="remember",
        access="safe",
        description="Store a long-term memory. DEFAULT scope is THIS session; scope=user stores it about the CURRENT USER (cross-session: shared across every chat you have with them, injected in private chats — use for stable facts about the person, not group-specific topics); use scope=global ONLY when the user explicitly asks to remember it bot-wide (e.g. \"帮我全局记住\").",
        parameters=_schema(
            {
                "content": _s(type="string", description="The fact to remember"),
                "category": _s(type="string", description="Category like preference / fact / todo"),
                "importance": _s(type="integer", description="1-5, higher survives longer; default 3"),
                "scope": _s(type="string", description="chat (default) / user (about this person, cross-session) / global — global requires the user's explicit request"),
            },
            ["content"],
        ),
        handler=remember,
    ))
    registry.register(Tool(
        name="recall",
        access="safe",
        description="Search long-term memories relevant to a query for the current chat (user scope = this person's cross-session memories, global scope = bot-wide).",
        parameters=_schema(
            {
                "query": _s(type="string", description="Search keywords; empty returns the newest ones"),
                "limit": _s(type="integer", description="Max entries, default from config"),
                "scope": _s(type="string", description="chat (default) / user / global"),
            },
            [],
        ),
        handler=recall,
    ))
    registry.register(Tool(
        name="forget",
        access="safe",
        description="Delete long-term memories matching a query for the current chat (user scope = this person's cross-session memories, global scope = bot-wide).",
        parameters=_schema(
            {
                "query": _s(type="string", description="Text that the memories to delete contain"),
                "scope": _s(type="string", description="chat (default) / user / global"),
            },
            ["query"],
        ),
        handler=forget,
    ))
    registry.register(Tool(
        name="list_memory",
        access="safe",
        description="Browse long-term memories, newest first, 40 per page (chat = this session; user = this person's cross-session memories; global = bot-wide). Filter by category or keyword; the header shows total and page position. Auto memories (injected by context compaction) decay over time; user memories never expire.",
        parameters=_schema(
            {
                "scope": _s(type="string", description="chat (default) / user / global"),
                "page": _s(type="integer", description="Page number, 1-based"),
                "category": _s(type="string", description="Filter by exact category (e.g. auto / preference / fact)"),
                "q": _s(type="string", description="Keyword filter inside content"),
            },
            [],
        ),
        handler=list_memory,
    ))
