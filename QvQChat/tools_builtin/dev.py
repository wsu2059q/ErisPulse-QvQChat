"""ErisPulse 模块开发辅助：reload_module 热加载工具（配合内置 erispulse-dev 技能）。"""
from __future__ import annotations

from .. import texts
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


async def reload_module(ctx: ToolContext, name: str) -> str:
    """热加载指定模块（写模块 → reload → 自测闭环）。"""
    name = str(name or "").strip()
    if not name:
        return texts.t("reload_name_required")
    manager = getattr(ctx.sdk, "module", None)
    reload_fn = getattr(manager, "reload", None)
    if not callable(reload_fn):
        return texts.t("reload_unsupported")
    try:
        ok = await reload_fn(name)
    except Exception as e:
        return texts.t("reload_failed", name=name, error=f"{type(e).__name__}: {e}")
    if ok:
        return texts.t("reload_ok", name=name)
    return texts.t("reload_failed", name=name, error=texts.t("reload_returned_false"))


def register(registry: ToolRegistry, main) -> None:
    if not bool(getattr(main.cfg, "skill_dev", True)):
        return
    registry.register(Tool(
        name="reload_module",
        access="admin",
        danger=True,
        description=(
            "Hot-reload an installed ErisPulse module by name after editing its source. "
            "Use it to verify changes without restarting the whole bot (the erispulse-dev skill covers the workflow)."
        ),
        parameters=_schema(
            {"name": {"type": "string", "description": "Module name as registered (use the installed module's exact name)"}},
            ["name"],
        ),
        handler=reload_module,
    ))
