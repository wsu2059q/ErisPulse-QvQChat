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
        _launch_background(main, sub_key, sub_ctx, system, [str(t) for t in (tools or [])], task)
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


def _launch_background(main, sub_key: str, sub_ctx, system: str, tools: list[str], task: str) -> asyncio.Task:
    """后台执行公共体：探针写 running + spawn _run_background + 注册进程内可取消任务。

    spawn_agent 的 background 分支与 demote_to_background 共用，保证两条路径的
    崩溃恢复探针 / qvq.subagent_done 回插 / 取消注册表行为完全一致。
    """
    _subjob_probe(main, sub_key, {
        "sub_key": sub_key,
# parent_chat_key 存在 sub_ctx 上（它自己的 chat_key 是 sub: 键）——探针与回插都靠它溯源
        "parent_chat_key": str(getattr(sub_ctx, "parent_chat_key", "") or ""),
        "task": utils.truncate(task, 500),
        "status": "running",
        "started": time.time(),
    })
    spawned = main.spawn(_run_background(main, sub_key, sub_ctx, system, tools, task))
    register_live_subjob(sub_key, spawned)
    return spawned


async def demote_to_background(main, event, chat_key: str, task_prompt: str) -> str:
    """长任务让路：把被新消息打断的任务转为后台子智能体续跑（auto demote 决策的执行端）。

    与 spawn_agent(background) 的差别：任务文本由调用方拼接（原任务+已有部分输出）、
    不注入父会话上下文（正被让路的对话对续跑无意义）、无确认器与工具透传。
    返回 sub_key；子智能体跑完经 qvq.subagent_done 自动插回 chat_key 会话。
    """
    chat_key = str(chat_key or "")
# 防重入：子智能体自己的回合不会再产生 demote（避免 sub 生 sub 无限嵌套）
    if chat_key.startswith("sub:"):
        raise ValueError("demote_to_background cannot run inside a sub-agent session")
    task_prompt = str(task_prompt or "").strip()
    if not task_prompt:
        raise ValueError("demote_to_background requires a non-empty task prompt")
    sub_key = "sub:" + chat_key + ":demote:" + uuid.uuid4().hex[:8]
    data = vars(main.cfg).copy()
    data["max_tool_rounds"] = 10
    sub_cfg = SimpleNamespace(**data)
# 发送身份与目标完整继承发起会话：platform/detail_type/target_id/user_id/self_id 从事件取，
# 子智能体汇报（qvq.subagent_done 的插回）与主动发送才落到正确的群/私聊与账户
    platform = str(event.get_platform() or "")
    is_group = bool(event.is_group_message())
    target_id = str(event.get_group_id() or "") if is_group else str(event.get_user_id() or "")
    self_id = ""
    try:
        self_id = str(event.get_self_account_id() or "")
    except Exception:
        self_id = ""
    sub_ctx = ToolContext(
        main=main,
        sdk=main.sdk,
        config=sub_cfg,
        chat_key=sub_key,
        session_key=sub_key,
        platform=platform,
        detail_type="group" if is_group else "private",
        target_id=target_id,
        user_id=str(event.get_user_id() or ""),
        event=event,
        origin="chat",
        confirmer=None,
        scene_note="",
        parent_chat_key=chat_key,
        self_id=self_id,
    )
# 不加 _context_block：主会话正要让路给新消息，历史对话塞给续跑任务反而干扰
    system = texts.t("subagent_system", task=utils.truncate(task_prompt, 500))
    main.sessions.append(sub_key, "user", task_prompt)
    main.sessions.set_group_name(sub_key, utils.truncate(task_prompt, 40))
    _launch_background(main, sub_key, sub_ctx, system, [], task_prompt)
    return sub_key


async def _run_background(main, sub_key: str, sub_ctx, system: str, tools: list[str], task: str) -> None:
    """后台执行体：跑完落探针 + emit qvq.subagent_done（Main 监听后插回主会话消化）。

    成败都 emit：失败静默违背"自动汇报"承诺——发起者应知道任务黄了。
    """
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
        error = ""
    except asyncio.CancelledError:
# 取消也是终态：探针标 cancelled，插回一条取消说明（不是 error）
        probe = main.sdk.storage.get(SUBJOB_PREFIX + sub_key, None)
        if isinstance(probe, dict):
            probe.update({"status": "cancelled", "finished": time.time()})
            main.sdk.storage.set(SUBJOB_PREFIX + sub_key, probe)
        parent = str(getattr(sub_ctx, "parent_chat_key", "") or "")
        if parent:
            try:
                await main.sdk.lifecycle.emit("qvq.subagent_done", {
                    "sub_key": sub_key,
                    "parent_chat_key": parent,
                    "task": utils.truncate(task, 500),
                    "answer": "",
                    "status": "cancelled",
                    "error": "",
                    "ms": int((time.monotonic() - started) * 1000),
                })
            except Exception:
                pass
        raise
    except Exception as e:
        answer = ""
        status = "error"
        error = f"{type(e).__name__}: {e}"
        main.sessions.append(sub_key, "assistant", f"[error] {error}")
        main.logger.warning(f"background subagent failed: {error}")
    ms = int((time.monotonic() - started) * 1000)
    probe = main.sdk.storage.get(SUBJOB_PREFIX + sub_key, None)
    if isinstance(probe, dict):
        probe.update({"status": status, "finished": time.time(), "ms": ms,
                      "error": error if status == "error" else ""})
        main.sdk.storage.set(SUBJOB_PREFIX + sub_key, probe)
    parent = str(getattr(sub_ctx, "parent_chat_key", "") or "")
    if not parent:
        return
    try:
        await main.sdk.lifecycle.emit("qvq.subagent_done", {
            "sub_key": sub_key,
            "parent_chat_key": parent,
            "task": utils.truncate(task, 500),
            "answer": answer[:4000],
            "status": status,
            "error": error,
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


# ===== 可观测：进程内子任务注册表（运行中可取消，终态查探针） =====

_LIVE_SUBJOBS: dict[str, asyncio.Task] = {}


def register_live_subjob(sub_key: str, task: asyncio.Task) -> None:
    _LIVE_SUBJOBS[sub_key] = task


def unregister_live_subjob(sub_key: str) -> None:
    _LIVE_SUBJOBS.pop(sub_key, None)


def cancel_subjob(main, sub_key: str) -> bool:
    """取消后台子智能体：进程内任务 cancel（终态由 _run_background 的
    CancelledError 分支落探针 + 插回取消说明）；不在进程内则 False。"""
    task = _LIVE_SUBJOBS.get(str(sub_key))
    if task is None or task.done():
        return False
    task.cancel()
    return True


def list_subjobs(main, limit: int = 50) -> list:
    """子智能体任务列表：运行中（进程内注册表）+ 终态（探针，新在前）。"""
    rows: list = []
    listed: set = set()
    for sub_key, task in _LIVE_SUBJOBS.items():
        if task.done():
            continue
        probe = main.sdk.storage.get(SUBJOB_PREFIX + str(sub_key), None) or {}
        rows.append({
            "sub_key": str(sub_key),
            "status": "running",
            "task": probe.get("task", ""),
            "parent_chat_key": probe.get("parent_chat_key", ""),
            "started": probe.get("started", 0),
        })
        listed.add(str(sub_key))
    try:
        index = main.sdk.storage.get(SUBJOB_INDEX_KEY, [])
    except Exception:
        index = []
    for sub_key in (index if isinstance(index, list) else []):
        key = str(sub_key)
        if key in listed:
            continue
        probe = main.sdk.storage.get(SUBJOB_PREFIX + key, None)
        if isinstance(probe, dict):
            rows.append({
                "sub_key": key,
                "status": str(probe.get("status") or "?"),
                "task": probe.get("task", ""),
                "parent_chat_key": probe.get("parent_chat_key", ""),
                "started": probe.get("started", 0),
                "finished": probe.get("finished", 0),
                "ms": probe.get("ms", 0),
                "error": probe.get("error", ""),
            })
    return rows[: max(1, int(limit))]


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
    for message in list(contexts or [])[-5:]:
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
        description="Spawn a sub-agent with an isolated session/context to explore a task independently and report back its conclusion. Best for long fetch/scrape/research subtasks. Use background=true for slow tasks (long-form writing, batch fetching, multi-step research): it runs unsupervised and its report is automatically delivered back into this chat when done (you keep the conversation free). Before spawning, send the user a short progress line (what you delegated, what happens next). The sub-agent's full process history is kept as its own session (prefix 'sub:') for review.",
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
