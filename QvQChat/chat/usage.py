"""用量记账（拆分自 Main.py）：按日 token/调用数/会话/模型维度落 storage，滚动清理。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

# 上次清理日标记（跨天首条记账才执行一次全扫）
USAGE_LAST_PRUNE_KEY = "QvQChat:usage:last_prune"


class UsageMixin:
    """Main 的用量记账 mixin。依赖宿主提供 self.sdk / self.cfg / self.logger。"""

    def _usage_today(self) -> dict:
        data = self.sdk.storage.get(f"QvQChat:usage:{time.strftime('%Y-%m-%d')}", {})
        return data if isinstance(data, dict) else {}

    def record_usage(self, chat_key: str, usage: dict, model: str = "") -> None:
        try:
            today = time.strftime("%Y-%m-%d")
            key = f"QvQChat:usage:{today}"
            data = self.sdk.storage.get(key, {})
            if not isinstance(data, dict):
                data = {}
            tokens = int(usage.get("total_tokens", 0) or 0)
            data["tokens"] = int(data.get("tokens", 0) or 0) + tokens
            data["calls"] = int(data.get("calls", 0) or 0) + 1
            by_chat = data.get("by_chat")
            if not isinstance(by_chat, dict):
                by_chat = {}
            by_chat[chat_key] = int(by_chat.get(chat_key, 0) or 0) + tokens
            data["by_chat"] = by_chat
            if model:
                by_model = data.get("by_model")
                if not isinstance(by_model, dict):
                    by_model = {}
                entry = by_model.get(model)
                entry = {"tokens": 0, "in": 0, "out": 0} if not isinstance(entry, dict) else entry
                entry["tokens"] = int(entry.get("tokens", 0) or 0) + tokens
                entry["in"] = int(entry.get("in", 0) or 0) + int(usage.get("prompt_tokens", 0) or 0)
                entry["out"] = int(entry.get("out", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)
                by_model[model] = entry
                data["by_model"] = by_model
            self.sdk.storage.set(key, data)
            self._prune_usage(today)
        except Exception as e:
# 记账路径不允许完全静默
            self.logger.debug(f"record_usage failed: {e}")

    def _prune_usage(self, today: str) -> None:
        days = int(getattr(self.cfg, "usage_retention_days", 14) or 0)
        if days <= 0:
            return
# 同一天只扫一次（此前每条消息记账后都全库 keys() 扫描）
        if self.sdk.storage.get(USAGE_LAST_PRUNE_KEY, "") == today:
            return
        try:
            cutoff = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days)
        except ValueError:
            return
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith("QvQChat:usage:"):
                date_part = key.rsplit(":", 1)[-1]
                try:
                    if datetime.strptime(date_part, "%Y-%m-%d") < cutoff:
                        self.sdk.storage.delete(key)
                except ValueError:
                    continue
        self.sdk.storage.set(USAGE_LAST_PRUNE_KEY, today)

    def _usage_history(self, days: int = 14) -> list[dict]:
        history = []
        for offset in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
            data = self.sdk.storage.get(f"QvQChat:usage:{date}", {})
            history.append(
                {
                    "date": date,
                    "tokens": int((data or {}).get("tokens", 0) or 0) if isinstance(data, dict) else 0,
                    "calls": int((data or {}).get("calls", 0) or 0) if isinstance(data, dict) else 0,
                    "by_chat": (data or {}).get("by_chat", {}),
                    "by_model": (data or {}).get("by_model", {}),
                }
            )
        return history
