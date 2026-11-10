from __future__ import annotations

from typing import Any

from .. import texts, utils

MEM_PREFIX = "QvQChat:mem:"
GLOBAL_SCOPE = "global"


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

            if getattr(self.config, "embedding_enabled", False) and _vectors.available(self.config):
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

    def remember(self, chat_key: str, content: str, category: str = "", importance: int = 3) -> str:
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
            }
        )
        max_items = int(getattr(self.config, "memory_max", 200))
        if len(entries) > max_items:
            entries.sort(key=lambda e: (e.get("importance", 3), e.get("ts", 0)), reverse=True)
            entries = entries[:max_items]
        self._save(chat_key, entries)
        return texts.t("memory_added", count=len(entries))

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
