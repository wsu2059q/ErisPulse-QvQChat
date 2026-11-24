"""
会话让渡（handover）

主智能体把对话窗口让渡给一个全新上下文的智能体：状态存 KV
``QvQChat:handover:{chat_key}``，对话历史用 ``sub:handover:`` 隔离会话键。

{!--< tips >!--}
到期判定是惰性的：下一轮消息到达时检查轮数与空闲超时，无后台定时器。
{!--< /tips >!--}
"""
from __future__ import annotations

import time
import uuid

from .. import texts, utils

# 会话让渡状态（KV 持久化）
HANDOVER_PREFIX = "QvQChat:handover:"


def state_key(chat_key: str) -> str:
    return HANDOVER_PREFIX + str(chat_key or "")


async def get_state(sdk, chat_key: str) -> dict | None:
    """读取让渡状态；无 / 已失效 / 存储异常一律返回 None。"""
    try:
        raw = await sdk.storage.aget(state_key(chat_key), None)
    except Exception:
        return None
    if isinstance(raw, dict) and raw.get("active"):
        return raw
    return None


def build_system(setup: str, scene_note: str = "", recent: list | None = None) -> str:
    """
    构建让渡智能体的 system prompt：角色设定 + 场景定向 + 收场守则。

    :param setup: [str] 角色/场景设定文本
    :param scene_note: [str] 主会话场景注记（群名/当前说话人） (默认: "")
    :param recent: [list] 让渡前主会话最近对话，每条为消息 dict (默认: None)
    :return: [str] 完整 system prompt
    """
    setup = str(setup or "").strip()
    system = texts.t("handover_system", setup=utils.truncate(setup, 2000))
    context_block = _context_block(scene_note, recent)
    if context_block:
        system = system + "\n" + context_block
    return system + texts.t("handover_system_rules")


def _context_block(scene_note: str, recent: list | None) -> str:
    """
    {!--< internal-use >!--}
    场景与最近对话定向块；两者皆空返回空串。
    """
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
    """
    让渡会话上下文转写为总结用文本。

    :param contexts: [list] sub: 会话消息列表
    :return: [str] "用户(sender): 内容 / 角色: 内容" 逐行转写，空返回 ""
    """
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


async def start(sdk, cfg, chat_key: str, *, setup: str, model: str = "",
          listen: str = "inherit", max_turns: int = 0,
          scene_note: str = "", recent: list | None = None) -> dict:
    """
    开启让渡：建 ``sub:handover:`` 隔离会话键，落 KV 状态。

    :param sdk: [Any] SDK 实例（storage 读写）
    :param cfg: [Any] QvQConfig 实例（handover_max_turns / handover_idle_minutes）
    :param chat_key: [str] 主会话键
    :param setup: [str] 角色/场景设定文本
    :param model: [str] 池内模型 id (默认: "")
    :param listen: [str] "inherit" 跟随现有触发规则 / "all" 全场接话 (默认: "inherit")
    :param max_turns: [int] 轮数上限，0 走全局 handover_max_turns (默认: 0)
    :param scene_note: [str] 场景定向文本，注入角色 system (默认: "")
    :param recent: [list] 让渡前主会话最近消息 (默认: None)
    :return: [dict] 让渡状态
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
    await sdk.storage.aset(state_key(chat_key), state)
    return state


async def stop(sdk, chat_key: str) -> dict | None:
    """
    结束让渡并删除 KV 状态。

    :param sdk: [Any] SDK 实例
    :param chat_key: [str] 主会话键
    :return: [dict | None] 被结束的状态；无让渡返回 None
    """
    state = await get_state(sdk, chat_key)
    if state is None:
        return None
    try:
        await sdk.storage.adelete(state_key(chat_key))
    except Exception:
        pass
    return state


def expired_reason(state: dict) -> str:
    """
    惰性到期判定：轮数尽或空闲超时。

    :param state: [dict] 让渡状态
    :return: [str] "turns" / "idle"；未到期返回 ""
    """
    max_turns = int(state.get("max_turns") or 0)
    if max_turns > 0 and int(state.get("turns") or 0) >= max_turns:
        return "turns"
    idle_minutes = float(state.get("idle_minutes") or 0)
    if idle_minutes > 0 and (time.time() - float(state.get("last_ts") or 0)) > idle_minutes * 60:
        return "idle"
    return ""


async def touch(sdk, state: dict, chat_key: str) -> dict:
    """
    回合完成后推进计数：turns +1、刷新 last_ts 并回写 KV。

    :param sdk: [Any] SDK 实例
    :param state: [dict] 让渡状态
    :param chat_key: [str] 主会话键
    :return: [dict] 更新后的状态
    """
    state["turns"] = int(state.get("turns") or 0) + 1
    state["last_ts"] = time.time()
    await sdk.storage.aset(state_key(chat_key), state)
    return state
