"""会话让渡（handover）：主智能体把对话窗口让渡给一个全新上下文的智能体。

与 spawn_agent 的区别：子智能体是"后台干活→汇报回主会话"，让渡是"接管窗口直接
回复用户"——扮演病人/医生、临时人格陪聊、剧本主持等场景，让渡期间用户消息由
新智能体直答，主会话上下文完全不沾让渡内容（结束后仅注入一行事实注记）。

状态存 KV（``QvQChat:handover:{chat_key}``），重启存活；对话历史用 ``sub:`` 隔离
会话键（复用 spawn_agent 的隔离模式），到期判定是惰性的（下一轮消息到达时检查，
无后台定时器）。
"""
from __future__ import annotations

import time
import uuid

from .. import texts, utils

# 会话让渡状态（KV 持久化）
HANDOVER_PREFIX = "QvQChat:handover:"


def state_key(chat_key: str) -> str:
    return HANDOVER_PREFIX + str(chat_key or "")


def get_state(sdk, chat_key: str) -> dict | None:
    """读取让渡状态；无 / 已失效 / 存储异常一律返回 None。"""
    try:
        raw = sdk.storage.get(state_key(chat_key), None)
    except Exception:
        return None
    if isinstance(raw, dict) and raw.get("active"):
        return raw
    return None


def build_system(setup: str, scene_note: str = "", recent: list | None = None) -> str:
    """让渡智能体的 system prompt：角色设定 + 场景定向 + 守则（含退出标签说明）。

    scene_note 是主会话的场景注记（群名/当前说话人/触发方式）；recent 是让渡前
    主会话最近几条对话（带发送者标签）。定向信息只帮它入戏，明确告知别回应旧话题。
    """
    setup = str(setup or "").strip()
    system = texts.t("handover_system", setup=utils.truncate(setup, 2000))
    context_block = _context_block(scene_note, recent)
    if context_block:
        system = system + "\n" + context_block
    return system + texts.t("handover_system_rules")


def _context_block(scene_note: str, recent: list | None) -> str:
    """接手定向块：场景（谁在哪个群）+ 最近对话（聊到哪了）。两者皆空返回空串。"""
    parts: list[str] = []
    note = str(scene_note or "").strip()
    if note:
        parts.append("<scene>\n" + note + "\n</scene>")
    lines: list[str] = []
    for message in list(recent or [])[-6:]:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text") or "") for part in content if isinstance(part, dict)
            )
        text = utils.truncate(str(content or "").strip(), 160)
        if not text:
            continue
        role = str(message.get("role") or "")
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
        texts.t("handover_context_note")
        + "\n"
        + "\n".join(parts)
        + "\n"
    )


def transcript_of(contexts: list) -> str:
    """让渡会话 → 总结用转写（每条截断，cap 条数上限；空转写返回空串）。"""
    lines: list[str] = []
    for message in list(contexts or [])[-40:]:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text") or "") for part in content if isinstance(part, dict)
            )
        text = utils.truncate(str(content or "").strip(), 200)
        if not text:
            continue
        role = str(message.get("role") or "")
        sender = str(message.get("sender_name") or message.get("sender_id") or "?")
        lines.append(f"{'用户(' + sender + ')' if role == 'user' else '角色'}: {text}")
    return "\n".join(lines)


def start(sdk, cfg, chat_key: str, *, setup: str, model: str = "",
          listen: str = "inherit", max_turns: int = 0,
          scene_note: str = "", recent: list | None = None) -> dict:
    """开启让渡：建 ``sub:handover:`` 隔离会话键，落 KV 状态并返回。

    max_turns=0 走全局 handover_max_turns；idle 恒取全局 handover_idle_minutes。
    listen="all" 让渡期间全场接话（仅放宽 at_only/群触发规则，off/lurk 硬闸不越）。
    scene_note/recent 注入角色 system（接手定向），服务/命令入口可不传。
    """
    setup = str(setup or "").strip()
    state = {
        "active": True,
        "sub_key": "sub:handover:" + str(chat_key or "") + ":" + uuid.uuid4().hex[:8],
        "role_prompt": build_system(setup, scene_note=scene_note, recent=recent),
        "setup": utils.truncate(setup, 80),
        "model": str(model or "").strip(),
        "listen": "all" if str(listen or "").strip().lower() == "all" else "inherit",
        "started": time.time(),
        "last_ts": time.time(),
        "turns": 0,
        "max_turns": int(max_turns) if max_turns else int(getattr(cfg, "handover_max_turns", 30) or 30),
        "idle_minutes": float(getattr(cfg, "handover_idle_minutes", 15.0) or 0),
    }
    sdk.storage.set(state_key(chat_key), state)
    return state


def stop(sdk, chat_key: str) -> dict | None:
    """结束让渡：清状态并返回原状态（调用方据此给主会话写注记）；无让渡返回 None。"""
    state = get_state(sdk, chat_key)
    if state is None:
        return None
    try:
        sdk.storage.delete(state_key(chat_key))
    except Exception:
        pass
    return state


def expired_reason(state: dict) -> str:
    """惰性到期判定：返回 "turns" / "idle" / ""。

    在下一轮消息到达时检查（无后台定时器），到期的让渡当场收场并在主会话留注记。
    """
    max_turns = int(state.get("max_turns") or 0)
    if max_turns > 0 and int(state.get("turns") or 0) >= max_turns:
        return "turns"
    idle_minutes = float(state.get("idle_minutes") or 0)
    if idle_minutes > 0 and (time.time() - float(state.get("last_ts") or 0)) > idle_minutes * 60:
        return "idle"
    return ""


def touch(sdk, state: dict, chat_key: str) -> dict:
    """回合完成后的计数推进：turns +1、刷新 last_ts 并回写 KV。"""
    state["turns"] = int(state.get("turns") or 0) + 1
    state["last_ts"] = time.time()
    sdk.storage.set(state_key(chat_key), state)
    return state
