from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
import uuid

from .. import texts, utils
from ..agent.runner import AgentRunner
from ..agent.tools import Tool, ToolContext, ToolRegistry

# 后台子智能体探针（崩溃恢复用）：status running → done/error/interrupted
SUBJOB_PREFIX = "QvQChat:subjob:"
SUBJOB_INDEX_KEY = "QvQChat:subjob_index"
# 后台并发闸门：同时跑的后台子智能体上限（超出排队等槽）
_SUBJOB_SEMAPHORE = asyncio.Semaphore(2)


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


async def spawn_agent(ctx: ToolContext, task: str, tools: list[str] | None = None,
                      max_rounds: int = 8, background: bool = False) -> str:

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
# 仅 chat_key/session_key 用 sub: 前缀隔离上下文与记忆。
# self_id 必须显式继承：sub: 键把 @账户 藏在中段，后缀解析取不到，
# 不传的话子智能体发送会静默落到适配器默认账户（错身份）
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
        confirmer=None if background else ctx.confirmer,
        scene_note=str(getattr(ctx, "scene_note", "") or ""),
        parent_chat_key=str(ctx.chat_key or ""),
        self_id=str(getattr(ctx, "self_id", "") or ""),
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

    if background:
# 后台模式：立即返回，跑完经 qvq.subagent_done 事件插回主会话（Main 监听消化）
        _subjob_probe(main, sub_key, {
            "sub_key": sub_key,
            "parent_chat_key": str(ctx.chat_key or ""),
            "task": utils.truncate(task, 500),
            "status": "running",
            "started": time.time(),
        })
        main.spawn(_run_background(main, sub_key, sub_ctx, system, [str(t) for t in (tools or [])], task))
        return texts.t("subagent_background_started", session=sub_key)

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


async def _run_background(main, sub_key: str, sub_ctx, system: str, tools: list[str], task: str) -> None:
    """后台执行体：跑完落探针 + emit qvq.subagent_done（Main 监听后插回主会话消化）。"""
    started = time.monotonic()
    try:
        async with _SUBJOB_SEMAPHORE:
            result = await AgentRunner(main.pool, main.registry, sub_ctx.config).run(
                system=system,
                messages=[],
                ctx=sub_ctx,
                persona_tools=tools or None,
                priority=6,
            )
        answer = (result.text or "").strip() or "-"
        main.sessions.append(sub_key, "assistant", answer, trace=result.tool_trace)
        status = "done"
    except Exception as e:
        answer = ""
        status = "error"
        main.sessions.append(sub_key, "assistant", f"[error] {type(e).__name__}: {e}")
        main.logger.warning(f"background subagent failed: {type(e).__name__}: {e}")
    ms = int((time.monotonic() - started) * 1000)
    probe = main.sdk.storage.get(SUBJOB_PREFIX + sub_key, None)
    if isinstance(probe, dict):
        probe.update({"status": status, "finished": time.time(), "ms": ms})
        main.sdk.storage.set(SUBJOB_PREFIX + sub_key, probe)
    parent = str(getattr(sub_ctx, "parent_chat_key", "") or "")
    if not parent or status != "done":
        return
    try:
        await main.sdk.lifecycle.emit("qvq.subagent_done", {
            "sub_key": sub_key,
            "parent_chat_key": parent,
            "task": utils.truncate(task, 500),
            "answer": answer[:4000],
            "ms": ms,
        })
    except Exception as e:
        main.logger.warning(f"subagent_done emit failed: {type(e).__name__}: {e}")


def _subjob_probe(main, sub_key: str, payload: dict) -> None:
    """写探针 + 维护索引（崩溃恢复免全库扫描）。"""
    try:
        main.sdk.storage.set(SUBJOB_PREFIX + sub_key, payload)
        index = main.sdk.storage.get(SUBJOB_INDEX_KEY, [])
        index = [k for k in (index if isinstance(index, list) else []) if k != sub_key]
        main.sdk.storage.set(SUBJOB_INDEX_KEY, (index + [sub_key])[-100:])
    except Exception as e:
        main.logger.debug(f"subjob probe write failed: {type(e).__name__}: {e}")


def recover_subjobs(main) -> None:
    """启动恢复：上次进程遗留 running 的后台子智能体标记 interrupted（结果已丢失）。"""
    try:
        index = main.sdk.storage.get(SUBJOB_INDEX_KEY, [])
    except Exception:
        return
    for sub_key in (index if isinstance(index, list) else []):
        probe = main.sdk.storage.get(SUBJOB_PREFIX + str(sub_key), None)
        if isinstance(probe, dict) and probe.get("status") == "running":
            probe["status"] = "interrupted"
            probe["finished"] = time.time()
            main.sdk.storage.set(SUBJOB_PREFIX + str(sub_key), probe)


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
    recover_subjobs(main)
    registry.register(Tool(
        name="spawn_agent",
        access="admin",
        description="Spawn a sub-agent with an isolated session/context to explore a task independently and report back its conclusion. Best for long fetch/scrape/research subtasks. Use background=true for slow tasks: it runs unsupervised and its report is automatically delivered back into this chat when done (you keep the conversation free). Before spawning, send the user a short progress line (what you delegated, what happens next). The sub-agent's full process history is kept as its own session (prefix 'sub:') for review.",
        parameters=_schema(
            {
                "task": _s(type="string", description="Self-contained task description for the sub-agent"),
                "tools": _s(type="array", items=_s(type="string"), description="Optional tool-name whitelist for the sub-agent"),
                "max_rounds": _s(type="integer", description="Max tool rounds for the sub-agent (1-15, default 8)"),
                "background": _s(type="boolean", description="true = run unsupervised in background and auto-report into this chat when done (max 2 concurrent); false = wait for the result now"),
            },
            ["task"],
        ),
        handler=spawn_agent,
        danger=False,
    ))
