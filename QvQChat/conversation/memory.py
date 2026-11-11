from __future__ import annotations

import time
from typing import Any

from .. import texts, utils

MEM_PREFIX = "QvQChat:mem:"
GLOBAL_SCOPE = "global"
FORGET_PRUNE_KEY = "QvQChat:memforget:last_prune"  # 前缀避开 MEM_PREFIX（list_scopes 按 keys() 枚举）

# 遗忘曲线（只作用 source="auto" 的自动记忆；user 主动记的永不自动清）：
# importance → 保留天数。低权重旧记忆淡出，重要记忆留到自然失效为止，
# 5 级与人工记忆不过期——"有些是要长期记忆的，不是一刀切"
RETENTION_DAYS = {1: 14, 2: 14, 3: 60, 4: 180, 5: 0}  # 0 = 永久


class MemoryStore:
    def __init__(self, sdk: Any, config: Any):
        self.sdk = sdk
        self.config = config
        self._vectors = None  # 懒构造（engine.vectors），embedding_enabled 时 recall 走语义分支

    def _vectors_if_enabled(self):
        if self._vectors is not None:
            return self._vectors
        try:
            from ..engine import vectors as _vectors

# 低token模式：语义检索每次查询都是一次 embedding 调用——降级为词面 overlap 匹配
            if (
                getattr(self.config, "embedding_enabled", False)
                and not bool(getattr(self.config, "budget_mode", False))
                and _vectors.available(self.config)
            ):
                self._vectors = _vectors
                return self._vectors
        except Exception:
            pass
        return None

    def entries(self, chat_key: str) -> list[dict]:
        data = self.sdk.storage.get(MEM_PREFIX + chat_key, [])
        return data if isinstance(data, list) else []

    def _save(self, chat_key: str, entries: list[dict]) -> None:
        self.sdk.storage.set(MEM_PREFIX + chat_key, entries)

    @staticmethod
    def _normalized(text: str) -> str:
        return "".join(str(text).lower().split())

    def remember(self, chat_key: str, content: str, category: str = "", importance: int = 3,
                 source: str = "user") -> str:
        content = content.strip()
        if not content:
            return texts.t("memory_empty_content")
        entries = self.entries(chat_key)
        normalized = self._normalized(content)
        for entry in entries:
            existing = self._normalized(entry.get("content", ""))
            if not existing:
                continue
            if existing == normalized or (normalized in existing and len(normalized) * 3 >= len(existing)) or (existing in normalized and len(existing) * 3 >= len(normalized)):
                return texts.t("memory_duplicate")
        entries.append(
            {
                "content": content,
                "category": category or "general",
                "importance": max(1, min(5, int(importance or 3))),
                "ts": utils.now_ts(),
                "source": source if source in ("user", "auto") else "user",
            }
        )
        self._maybe_forget(chat_key, entries)
        max_items = int(getattr(self.config, "memory_max", 200))
        if len(entries) > max_items:
            entries.sort(key=lambda e: (e.get("importance", 3), e.get("ts", 0)), reverse=True)
            entries = entries[:max_items]
        self._save(chat_key, entries)
        return texts.t("memory_added", count=len(entries))

    def _maybe_forget(self, chat_key: str, entries: list) -> int:
        """遗忘曲线懒清理：跨天首条写入时对全部会话执行一次（照 usage 滚动清理模式）。

        只淡出 source="auto" 且超过分级保留期的条目；user 记忆与 importance 5 永不过期。
        返回本次清理条数。"""
        if not bool(getattr(self.config, "memory_forget", True)):
            return 0
        today = time.strftime("%Y-%m-%d")
        try:
            last = self.sdk.storage.get(FORGET_PRUNE_KEY, "")
            if last == today:
                return 0
        except Exception:
            pass
        removed_total = 0
        try:
            now = time.time()
            for key in [str(k) for k in (self.sdk.storage.keys() or []) if str(k).startswith(MEM_PREFIX)]:
                stored = self.sdk.storage.get(key, [])
                if not isinstance(stored, list) or not stored:
                    continue
                kept = []
                for entry in stored:
                    if not isinstance(entry, dict) or entry.get("source") != "auto":
                        kept.append(entry)
                        continue
                    days = RETENTION_DAYS.get(int(entry.get("importance") or 3), 60)
                    if days <= 0:
                        kept.append(entry)
                        continue
                    if now - float(entry.get("ts") or 0) > days * 86400:
                        removed_total += 1
                        continue
                    kept.append(entry)
                if len(kept) != len(stored):
                    self.sdk.storage.set(key, kept)
            self.sdk.storage.set(FORGET_PRUNE_KEY, today)
        except Exception:
            return removed_total
        return removed_total

    def recall(self, chat_key: str, query: str = "", limit: int = 0) -> list[dict]:
        entries = self.entries(chat_key)
        if not entries:
            return []
        now = utils.now_ts()
        if limit <= 0:
            limit = int(getattr(self.config, "memory_recall", 6))
        if not query.strip():
            return sorted(entries, key=lambda e: e.get("ts", 0), reverse=True)[:limit]
        vectors = self._vectors_if_enabled()
        if vectors is not None:
# 语义分支：余弦为主，重要性/时间衰减做轻调（条目少时 embedding 也保真）
            try:
                qvecs = vectors.embed([query], self.config)
                qvec = qvecs[0] if qvecs else None
                if qvec is not None:
                    contents = [str(e.get("content") or "") for e in entries]
                    dvecs = vectors.embed(contents, self.config) if contents else []
                    if len(dvecs) == len(entries):
                        scored = []
                        for entry, dvec in zip(entries, dvecs):
                            score = vectors.cosine(qvec, dvec) * 3.0
                            if score <= 0:
                                continue
                            score += entry.get("importance", 3) * 0.1
                            days = max(0.0, (now - entry.get("ts", now)) / 86400)
                            score -= days * 0.05
                            scored.append((score, entry))
                        scored.sort(key=lambda pair: pair[0], reverse=True)
                        return [entry for score, entry in scored[:limit] if score > 0.2]
            except Exception:
                pass  # 语义环节任何失败回退词面
        scored = []
        for entry in entries:
            score = utils.overlap_score(query, entry.get("content", "")) * 2.0
            if score <= 0:
                continue
            score += entry.get("importance", 3) * 0.1
            days = max(0.0, (now - entry.get("ts", now)) / 86400)
            score -= days * 0.05
            scored.append((score, entry))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for score, entry in scored[:limit] if score > 0.2]

    def forget(self, chat_key: str, query: str) -> int:
        query_norm = self._normalized(query)
        if not query_norm:
            return 0
        entries = self.entries(chat_key)
        remaining = [
            e
            for e in entries
            if query_norm not in self._normalized(e.get("content", ""))
            and self._normalized(e.get("content", "")) not in query_norm
        ]
        removed = len(entries) - len(remaining)
        if removed:
            self._save(chat_key, remaining)
        return removed

    def remove(self, chat_key: str, content: str) -> bool:
        entries = self.entries(chat_key)
        remaining = [e for e in entries if e.get("content") != content]
        if len(remaining) == len(entries):
            return False
        if remaining:
            self._save(chat_key, remaining)
        else:
            self.sdk.storage.delete(MEM_PREFIX + chat_key)
        return True

    def clear(self, chat_key: str) -> int:
        entries = self.entries(chat_key)
        if entries:
            self.sdk.storage.delete(MEM_PREFIX + chat_key)
        return len(entries)

    def list_scopes(self) -> list[dict]:
        scopes: list[dict] = []
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith(MEM_PREFIX):
                scopes.append(
                    {
                        "chat_key": key[len(MEM_PREFIX):],
                        "count": len(self.entries(key[len(MEM_PREFIX):])),
                    }
                )
        scopes.sort(key=lambda s: s["chat_key"])
        return scopes
