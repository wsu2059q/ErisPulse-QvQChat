"""会话让渡工具：主智能体把对话窗口让渡给一个全新上下文的智能体。

让渡状态见 conversation/handover.py；消息路由在 chat/inbox.py。
"""
from __future__ import annotations

from .. import texts
from ..agent.tools import Tool, ToolContext, ToolRegistry
from ..conversation import handover


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _s(**simple) -> dict:
    return simple


async def handover_session(ctx: ToolContext, setup: str, model: str = "",
                           listen: str = "inherit", max_turns: int = 0) -> str:
    main = ctx.main
    if main is None:
        return texts.t("tool_error", name="handover_session", error="no main")
    if str(ctx.chat_key or "").startswith("sub:"):
        return texts.t("handover_no_nested")
    setup = str(setup or "").strip()
    if not setup:
        return texts.t("tool_param_error", name="handover_session", error="setup is empty")
    existing = handover.get_state(ctx.sdk, ctx.chat_key)
    if existing:
        return texts.t("handover_already_active", setup=str(existing.get("setup") or "-"))
    # 接手定向：场景注记（群名/当前说话人）+ 让渡前主会话最近几条对话
    try:
        recent = list(main.sessions.get_contexts(str(ctx.chat_key)) or [])[-6:]
    except Exception:
        recent = []
    state = handover.start(
        ctx.sdk, main.cfg, ctx.chat_key,
        setup=setup, model=str(model or ""), listen=str(listen or "inherit"),
        max_turns=int(max_turns or 0),
        scene_note=str(getattr(ctx, "scene_note", "") or ""),
        recent=recent,
    )
    # 开让渡后立刻失效触发判定的 5s 进程内缓存，避免紧随其后的用户消息命中旧缓存
    invalidate = getattr(main, "_handover_state_invalidate", None)
    if callable(invalidate):
        invalidate(ctx.chat_key)
    return texts.t(
        "handover_active_now",
        session=str(state.get("sub_key") or ""),
        model=str(state.get("model") or "-"),
        listen=str(state.get("listen") or "inherit"),
    )


def register(registry: ToolRegistry, main) -> None:
    if not bool(getattr(main.cfg, "handover_enabled", True)):
        return
    registry.register(Tool(
        name="handover_session",
        access="safe",
        description=(
            "Hand the conversation window over to a fresh-context stand-in agent: it gets a clean "
            "session, no tools, no memory of this chat, and acts ONLY as the role/scene you write in "
            "setup. It then directly replies to subsequent user messages in this chat until the scene "
            "ends (it outputs the exit tag, the user runs /qvq handover off, or turn/idle limits hit); "
            "afterwards a one-line note is left in your context. Use it when the user wants roleplay "
            "(e.g. 'you play the patient, I'm the doctor'), a temporary persona, or any self-contained "
            "scripted dialogue that must NOT pollute the main conversation history. You must announce "
            "the handover naturally in your own reply right after calling this."
        ),
        parameters=_schema(
            {
                "setup": _s(type="string", description="Self-contained role/scene setup for the stand-in agent (who it plays, how it talks, when to end). It knows nothing else, so write everything it needs."),
                "model": _s(type="string", description="Optional model pool id (provider:model) for the stand-in; empty follows handover_model config / the main model"),
                "listen": _s(type="string", description="inherit (default) keeps current trigger rules (in groups the user still needs to @/wake you); all makes the stand-in reply to every message in this chat for the game (off/lurk policies still win)"),
                "max_turns": _s(type="integer", description="Optional turn cap for this handover (2-100); default from handover_max_turns config"),
            },
            ["setup"],
        ),
        handler=handover_session,
        danger=False,
    ))
