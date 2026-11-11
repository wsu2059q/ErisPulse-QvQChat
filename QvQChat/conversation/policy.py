"""会话级策略存储：屏蔽（muted）/ 省钱（low_token）/ 资源优先级（priority）。

键 ``QvQChat:chatcfg:{chat_key}`` 单 KV / 会话，值为
``{"muted": bool, "low_token": bool, "priority": "high"|"normal"|"low"}``。

- ``muted``：消息完全不触发回复与旁听（_on_message 最前早闸，省资源也保隐私）。
- ``low_token``：省钱模式——系统提示词瘦身（跳过 kb/技能/画像等重组件）、
  历史窗口与单条长度收紧（service.prepare 消费）。
- ``priority``：并发闸门优先级偏移（engine/gate 数值越小越先拿到空位），
  high=-2（满载时先于其它直答）/ normal=0（不干预）/ low=+5（让位）。

全局侧：``chat_listen_mode``=whitelist 时仅 ``chat_whitelist`` 名单内会话响应。
"""

from __future__ import annotations

from typing import Any

POLICY_PREFIX = "QvQChat:chatcfg:"
PRIORITY_LEVELS = ("high", "normal", "low")
# gate 语义：数值越小越先拿到并发空位；0=用户直答、6=插话/子智能体、8=后台
PRIORITY_OFFSET = {"high": -2, "normal": 0, "low": 5}


def get_policy(sdk: Any, chat_key: str) -> dict:
    """读会话策略；缺省 {muted: False, low_token: False, priority: "normal"}。"""
    raw = {}
    try:
        raw = sdk.storage.get(POLICY_PREFIX + str(chat_key or ""), {})
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    priority = str(raw.get("priority") or "normal")
    if priority not in PRIORITY_LEVELS:
        priority = "normal"
    return {
        "muted": bool(raw.get("muted", False)),
        "low_token": bool(raw.get("low_token", False)),
        "priority": priority,
    }


def set_policy(sdk: Any, chat_key: str, **updates) -> dict:
    """更新会话策略（只传要改的键），返回更新后的完整策略。非法值静默归一。"""
    current = get_policy(sdk, chat_key)
    if "muted" in updates:
        current["muted"] = bool(updates["muted"])
    if "low_token" in updates:
        current["low_token"] = bool(updates["low_token"])
    if "priority" in updates:
        priority = str(updates["priority"] or "normal").lower()
        current["priority"] = priority if priority in PRIORITY_LEVELS else "normal"
    sdk.storage.set(POLICY_PREFIX + str(chat_key or ""), current)
    return current


def listen_allowed(config: Any, sdk: Any, chat_key: str) -> bool:
    """消息入口早闸：muted 或白名单模式未命中名单 → 不响应（含旁听）。"""
    chat_key = str(chat_key or "")
    if get_policy(sdk, chat_key).get("muted"):
        return False
    if str(getattr(config, "chat_listen_mode", "all") or "all") != "whitelist":
        return True
    entries = [str(item or "").strip() for item in (getattr(config, "chat_whitelist", None) or [])]
    if not entries:
        return False
# 前缀匹配：填平台段（如 "onebot11:"）即可放行该平台全部会话
    return any(chat_key.startswith(entry) for entry in entries if entry)


def priority_offset(chat_key_policy: dict) -> int:
    """策略 → gate 优先级偏移量。"""
    return PRIORITY_OFFSET.get(str(chat_key_policy.get("priority") or "normal"), 0)


def apply_priority(chat_key_policy: dict, base: int) -> int:
    """在来源基准优先级上叠加会话策略偏移（钳制在 gate 合法区间）。"""
    return max(-2, min(9, int(base) + priority_offset(chat_key_policy)))
