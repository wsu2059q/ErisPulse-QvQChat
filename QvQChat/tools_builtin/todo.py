from __future__ import annotations

from .. import utils
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _store(ctx: ToolContext):
    return ctx.main.conversations.todos


def _snapshot(items: list) -> list:
    return [
        {"id": i.get("id", ""), "status": i.get("status", "pending"), "content": i.get("content", "")}
        for i in items
    ]


async def todo_write(ctx: ToolContext, items: list) -> str:
    """全量替换清单（长任务开始/计划变更时重写）。"""
    contents = items if isinstance(items, list) else []
    result = _store(ctx).replace(ctx.chat_key, [str(i) for i in contents])
    return utils.to_text({"updated": len(result), "todos": _snapshot(result)})


async def todo_update(ctx: ToolContext, todo_id: str, status: str = "", content: str = "") -> str:
    """更新单条状态/内容（推进进度用：完成一条就标一条）。"""
    item = _store(ctx).update(ctx.chat_key, str(todo_id), status=status, content=content)
    if item is None:
        return utils.to_text({"ok": False, "error": f"todo {todo_id} not found or invalid status"})
    return utils.to_text({"ok": True, "todo": _snapshot([item])[0]})


async def todo_list(ctx: ToolContext) -> str:
    result = _store(ctx).items(ctx.chat_key)
    if not result:
        return utils.to_text({"todos": []})
    return utils.to_text({"todos": _snapshot(result)})


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="todo_write",
        access="safe",
        description="Replace the whole session TODO list (zcode TodoWrite semantics). Use when starting a multi-step task: break it into concrete items; keep exactly one item in_progress while working.",
        parameters=_schema(
            {
                "items": _s(type="array", items=_s(type="string"), description="Full list of task contents, in order"),
            },
            ["items"],
        ),
        handler=todo_write,
    ))
    registry.register(Tool(
        name="todo_update",
        access="safe",
        description="Update one todo item: mark progress (pending -> in_progress -> completed) or edit its content. Call as soon as a step's state changes, not in batches.",
        parameters=_schema(
            {
                "todo_id": _s(type="string", description="Todo item id"),
                "status": _s(type="string", description="pending / in_progress / completed"),
                "content": _s(type="string", description="Optional new content"),
            },
            ["todo_id", "status"],
        ),
        handler=todo_update,
    ))
    registry.register(Tool(
        name="todo_list",
        access="safe",
        description="List the current session TODO items with ids and statuses.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=todo_list,
    ))
