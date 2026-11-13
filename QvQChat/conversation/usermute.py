"""用户级屏蔽存储（AI/管理员把某个具体用户挡在本会话之外）。

键 ``QvQChat:usermute:{chat_key}`` 单 KV / 会话；条目
``{user_id, reason(≤120), until(epoch, 0=永久), by: ai|admin, created}``。
容量 USERMUTE_MAX=50（FIFO 淘汰最旧）。读取时惰性剔除过期条目；
被屏蔽者的消息在入站早闸整条丢弃（不旁听、不触发、不进历史）。
"""

from __future__ import annotations

from typing import Any

USERMUTE_PREFIX = "QvQChat:usermute:"
USERMUTE_MAX = 50
REASON_MAX = 120


class UserMuteStore:
    def __init__(self, sdk: Any, config: Any = None):
        self.sdk = sdk
        self.config = config

    def _key(self, chat_key: str) -> str:
        return USERMUTE_PREFIX + str(chat_key or "")

    def _load(self, chat_key: str) -> list:
        raw = self.sdk.storage.get(self._key(chat_key), [])
        return [item for item in (raw if isinstance(raw, list) else []) if isinstance(item, dict)]

    def _save(self, chat_key: str, items: list) -> None:
        self.sdk.storage.set(self._key(chat_key), items[:USERMUTE_MAX])

    def add(self, chat_key: str, user_id: str, reason: str = "", hours: float = 0, by: str = "admin") -> dict | None:
        """新增或刷新一条屏蔽；hours<=0 表示永久。同一用户已屏蔽则覆盖原因与期限。"""
        uid = str(user_id or "").strip()
        if not uid:
            return None
        now = self._now()
        try:
            hours_f = float(hours or 0)
        except (TypeError, ValueError):
            hours_f = 0.0
        until = now + hours_f * 3600 if hours_f > 0 else 0
        items = self._load(chat_key)
        for item in items:
            if str(item.get("user_id")) == uid:
                item.update({"reason": str(reason or "")[:REASON_MAX],
                             "until": until, "by": str(by or "admin"), "created": now})
                self._save(chat_key, items)
                return item
        items.append({"user_id": uid, "reason": str(reason or "")[:REASON_MAX],
                      "until": until, "by": str(by or "admin"), "created": now})
        self._save(chat_key, items)
        return items[-1]

    def remove(self, chat_key: str, user_id: str) -> bool:
        uid = str(user_id or "").strip()
        items = self._load(chat_key)
        kept = [item for item in items if str(item.get("user_id")) != uid]
        if len(kept) == len(items):
            return False
        self._save(chat_key, kept)
        return True

    def get(self, chat_key: str, user_id: str) -> dict | None:
        uid = str(user_id or "").strip()
        for item in self._active(self._load(chat_key)):
            if str(item.get("user_id")) == uid:
                return item
        return None

    def active(self, chat_key: str) -> list:
        return self._active(self._load(chat_key))

    def clear(self, chat_key: str) -> None:
        self.sdk.storage.delete(self._key(chat_key))

    # ---------- 内部 ----------

    def _active(self, items: list) -> list:
        now = self._now()
        return [item for item in items
                if not item.get("until") or float(item.get("until") or 0) > now]

    @staticmethod
    def _now() -> float:
        import time

        return time.time()
