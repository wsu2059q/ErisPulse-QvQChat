from __future__ import annotations

from .. import utils
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _store(ctx: ToolContext):
    return ctx.main.conversations.user_mutes


def _entry_view(item: dict | None) -> dict:
    if not item:
        return {}
    import time

    until = float(item.get("until") or 0)
    remain = "permanent" if not until else f"{max(0, int(until - time.time()) // 3600 + 1)}h"
    return {"user_id": item.get("user_id", ""), "reason": item.get("reason", ""),
            "remaining": remain, "by": item.get("by", "")}


def _is_admin(ctx: ToolContext, user_id: str) -> bool:
    try:
        return bool(ctx.main.is_admin(str(user_id), ctx.origin, ctx.platform))
    except Exception:
        return False


async def user_mute(ctx: ToolContext, action: str = "list", user_id: str = "",
                    reason: str = "", hours: float = 0) -> str:
    """屏蔽/解除/列出被屏蔽的用户。屏蔽后你看不到 TA 的任何消息，TA 也无法再触发你。"""
    store = _store(ctx)
    action = str(action or "list").strip().lower()
    uid = str(user_id or "").strip()

    if action == "list":
        return utils.to_text({"muted": [_entry_view(i) for i in store.active(ctx.chat_key)]})

    if not uid:
        return utils.to_text({"ok": False, "error": "user_id is required for add/remove"})

    if action == "remove":
        removed = store.remove(ctx.chat_key, uid)
        if removed:
            ctx.main.audit("user_mute_remove", {"user_id": uid}, ctx)
        return utils.to_text({"ok": removed, "user_id": uid})

    if action == "add":
        if _is_admin(ctx, uid):
            return utils.to_text({"ok": False, "error": "cannot mute an admin"})
        if _is_admin(ctx, ctx.user_id):
            item = store.add(ctx.chat_key, uid, reason, hours=hours, by="admin")
            ctx.main.audit("user_mute_add", {"user_id": uid, "hours": hours,
                                             "reason": utils.truncate(reason, 80)}, ctx)
            return utils.to_text({"ok": True, "muted": _entry_view(item)})
        # 非管理员触发的回合：受 user_mute_ai 开关与时长上限约束
        if not bool(getattr(ctx.config, "user_mute_ai", True)):
            return utils.to_text({"ok": False, "error": "AI mute disabled by config"})
        max_hours = 72
        try:
            max_hours = int(getattr(ctx.config, "user_mute_max_hours", 72) or 0)
        except (TypeError, ValueError):
            max_hours = 72
        if max_hours <= 0:
            return utils.to_text({"ok": False, "error": "AI mute disabled by config"})
        try:
            hours_f = float(hours or 0)
        except (TypeError, ValueError):
            hours_f = 0
        if hours_f <= 0 or hours_f > max_hours:
            hours_f = float(max_hours)
        item = store.add(ctx.chat_key, uid, reason, hours=hours_f, by="ai")
        ctx.main.audit("user_mute_add", {"user_id": uid, "hours": hours_f, "by": "ai",
                                         "reason": utils.truncate(reason, 80)}, ctx)
        return utils.to_text({"ok": True, "muted": _entry_view(item),
                              "note": f"auto-unmute after {int(hours_f)}h"})

    return utils.to_text({"ok": False, "error": f"unknown action: {action}"})


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="user_mute",
        access="safe",
        description=(
            "Mute / unmute / list muted users for this conversation. A muted user's messages "
            "disappear for you completely (no listening, no triggering, no history). Use it when "
            "someone keeps harassing or abusing you — muting beats arguing back; you decide. "
            "Mutes you add expire automatically (configurable cap); admin-issued mutes can be permanent. "
            "Admins themselves can never be muted."
        ),
        parameters=_schema(
            {
                "action": _s(type="string", enum=["list", "add", "remove"], description="list / add / remove"),
                "user_id": _s(type="string", description="Target user id (required for add/remove)"),
                "reason": _s(type="string", description="Why, in one short phrase (stored and audited)"),
                "hours": _s(type="number", description="Duration in hours; omitted or 0 from an admin = permanent; AI mutes are clamped to the configured cap"),
            },
            ["action"],
        ),
        handler=user_mute,
    ))
