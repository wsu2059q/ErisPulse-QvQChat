from __future__ import annotations

import time
from types import SimpleNamespace
import uuid

from .. import texts, utils
from ..agent.runner import AgentRunner
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


async def spawn_agent(ctx: ToolContext, task: str, tools: list[str] | None = None, max_rounds: int = 8) -> str:

    if str(ctx.chat_key or "").startswith("sub:"):
        return texts.t("subagent_no_nest")
    main = ctx.main
    if main is None:
        return texts.t("tool_error", name="spawn_agent", error="no main")
    task = str(task or "").strip()
    if not task:
        return texts.t("tool_param_error", name="spawn_agent", error="task is empty")
    sub_key = "sub:" + str(ctx.chat_key) + ":" + uuid.uuid4().hex[:8]
    data = vars(main.cfg).copy()
    data["max_tool_rounds"] = max(1, min(int(max_rounds or 8), 15))
    sub_cfg = SimpleNamespace(**data)
# 权限与发送能力完整跟随发起用户的上下文：继承 platform/detail_type/target_id/event，
# admin 判定（平台主人/名单）与 send_message 缺省目标都与主智能体一致——
# 仅 chat_key/session_key 用 sub: 前缀隔离上下文与记忆
    sub_ctx = ToolContext(
        main=main,
        sdk=ctx.sdk,
        config=sub_cfg,
        chat_key=sub_key,
        session_key=sub_key,
        platform=str(ctx.platform or ""),
        detail_type=str(ctx.detail_type or "private"),
        target_id=str(ctx.target_id or ""),
        user_id=ctx.user_id,
        event=ctx.event,
        origin=ctx.origin,
        confirmer=ctx.confirmer,
        scene_note=str(getattr(ctx, "scene_note", "") or ""),
        parent_chat_key=str(ctx.chat_key or ""),
    )
# 场景与最近对话注入：让子智能体知道在为谁、在哪个群、最近聊了什么
    context_block = _context_block(main, ctx)
    system = texts.t("subagent_system", task=utils.truncate(task, 500))
    if context_block:
        system = system + "\n\n" + context_block
    runner = AgentRunner(main.pool, main.registry, sub_cfg)
    main.sessions.append(sub_key, "user", task)
    main.sessions.set_group_name(sub_key, utils.truncate(task, 40))
    # 子智能体步骤透传：加 agent=sub 标记 + step_id 前缀，父/子事件不会互相配对错
    outer_hook = getattr(ctx, "on_tool_event", None)

    def sub_hook(evt):
        if outer_hook is None or not isinstance(evt, dict):
            return None
        payload = dict(evt)
        payload["agent"] = "sub"
        payload["step_id"] = "sub:" + str(evt.get("step_id") or "")
        return outer_hook(payload)

    started = time.monotonic()
    try:
        result = await runner.run(
            system=system,
            messages=[],
            ctx=sub_ctx,
            persona_tools=[str(t) for t in (tools or [])] or None,
            on_tool_event=sub_hook if outer_hook is not None else None,
            priority=6,  # 子智能体是后台杂务：并发紧张时让位给用户直接提问
        )
    except Exception as e:
        return texts.t("tool_error", name="spawn_agent", error=f"{type(e).__name__}: {e}")
    answer = (result.text or "").strip() or "-"
    main.sessions.append(sub_key, "assistant", answer, trace=result.tool_trace)
    ms = int((time.monotonic() - started) * 1000)
    meta = texts.t("subagent_meta", session=sub_key, tools=len(result.tool_trace), ms=ms)
    return answer + "\n\n" + meta


def _context_block(main, ctx) -> str:
    """子智能体上下文块：场景注记 + 父会话最近对话摘要（带发言人标注）。"""
    parts: list[str] = []
    scene = str(getattr(ctx, "scene_note", "") or "").strip()
    if scene:
        parts.append("<scene>\n" + scene + "\n</scene>")
    try:
# 传入的是父 ctx：读它自己的 chat_key（parent_chat_key 只存在于子 ctx 上）
        contexts = main.sessions.get_contexts(str(getattr(ctx, "chat_key", "") or ""))
    except Exception:
        contexts = []
    lines: list[str] = []
    for message in list(contexts or [])[-6:]:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        content = message.get("content")
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text") or "") for part in content if isinstance(part, dict)
            )
        text = utils.truncate(str(content or "").strip(), 160)
        if not text:
            continue
        if role == "user":
            sender = str(message.get("sender_name") or message.get("sender_id") or "?")
            lines.append(f"{sender}: {text}")
        elif role == "assistant":
            lines.append(f"[bot]: {text}")
    if lines:
        parts.append("<recent-chat>\n" + "\n".join(lines) + "\n</recent-chat>")
    if not parts:
        return ""
    return (
        "Context you inherit from the main agent (for orientation only — do NOT reply to "
        "the chat directly; your report goes back to the main agent):\n" + "\n".join(parts)
    )


def register(registry: ToolRegistry, main) -> None:
    if not bool(getattr(main.cfg, "multi_agent", True)):
        return
    registry.register(Tool(
        name="spawn_agent",
        access="admin",
        description="Spawn a sub-agent with an isolated session/context to explore a task independently and report back its conclusion. Best for long fetch/scrape/research subtasks. Before spawning, send the user a short progress line (what you delegated, what happens next). The sub-agent's full process history is kept as its own session (prefix 'sub:') for review.",
        parameters=_schema(
            {
                "task": _s(type="string", description="Self-contained task description for the sub-agent"),
                "tools": _s(type="array", items=_s(type="string"), description="Optional tool-name whitelist for the sub-agent"),
                "max_rounds": _s(type="integer", description="Max tool rounds for the sub-agent (1-15, default 8)"),
            },
            ["task"],
        ),
        handler=spawn_agent,
        danger=False,
    ))
