"""知识库：全文条目存储 + 即时分块 + 词面打分检索（零依赖，embedding 留可插拔接口）"""
from __future__ import annotations

import re
import time
import uuid

from .. import utils

KB_KEY = "QvQChat:kb"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
_TOKEN_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")


def _tokenize(text: str) -> list[str]:
    """英文按词、中文按单字 + 相邻二字组，供词面打分"""
    low = str(text or "").lower()
    singles = _TOKEN_RE.findall(low)
    cjk = [c for c in singles if "\u4e00" <= c <= "\u9fff"]
    bigrams = [cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1)]
    words = [t for t in singles if t not in cjk]
    return words + cjk + bigrams


def chunk_text(content: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = str(content or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks = []
    step = max(1, size - overlap)
    for start in range(0, len(text), step):
        piece = text[start:start + size]
        if piece.strip():
            chunks.append(piece.strip())
        if start + size >= len(text):
            break
    return chunks


class KnowledgeBase:
    def __init__(self, sdk, cfg=None):
        self.sdk = sdk
        self.cfg = cfg

    def _chunk_params(self) -> tuple[int, int]:
        size = int(getattr(self.cfg, "kb_chunk_size", CHUNK_SIZE) or CHUNK_SIZE)
        overlap = int(getattr(self.cfg, "kb_chunk_overlap", CHUNK_OVERLAP) or 0)
        return max(80, size), max(0, min(overlap, size // 2))

    def chunk(self, content: str) -> list[str]:
        size, overlap = self._chunk_params()
        return chunk_text(content, size=size, overlap=overlap)

    def _load(self) -> dict:
        data = self.sdk.storage.get(KB_KEY, {})
        return data if isinstance(data, dict) else {}

    def _save(self, entries: dict) -> None:
        self.sdk.storage.set(KB_KEY, entries)

    def add(self, title: str, content: str, source: str = "") -> dict:
        entry = {
            "id": uuid.uuid4().hex[:12],
            "title": str(title or "").strip() or "untitled",
            "content": str(content or ""),
            "source": str(source or ""),
            "created": utils.now_ts(),
        }
        entries = self._load()
        entries[entry["id"]] = entry
        self._save(entries)
        return entry

    def delete(self, kb_id: str) -> bool:
        entries = self._load()
        if kb_id not in entries:
            return False
        entries.pop(kb_id)
        self._save(entries)
        return True

    def list(self) -> list[dict]:
        return sorted(self._load().values(), key=lambda e: e.get("created", 0), reverse=True)

    def get(self, kb_id: str) -> dict | None:
        return self._load().get(kb_id)

    def _chunks(self) -> list[dict]:
        out = []
        for entry in self._load().values():
            for piece in self.chunk(entry.get("content", "")):
                out.append({"entry": entry, "text": piece})
        return out

    def search(self, query: str, top_k: int = 2) -> list[dict]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        scored = []
        for chunk in self._chunks():
            chunk_tokens = _tokenize(chunk["text"])
            if not chunk_tokens:
                continue
            bag: dict[str, int] = {}
            for token in chunk_tokens:
                bag[token] = bag.get(token, 0) + 1
            score = sum(bag.get(token, 0) for token in tokens)
            # 单字虚词命中只有 1 分，要求至少 2 分过滤噪声
            if score >= 2:
                scored.append((score, chunk))
        scored.sort(key=lambda pair: -pair[0])
        results = []
        for score, chunk in scored[:max(1, int(top_k or 0))]:
            entry = chunk["entry"]
            results.append(
                {
                    "id": entry["id"],
                    "title": entry.get("title", ""),
                    "source": entry.get("source", ""),
                    "snippet": utils.truncate(chunk["text"], 500),
                    "score": score,
                }
            )
        return results

    def stats(self) -> dict:
        entries = self._load()
        chunks = sum(len(self.chunk(e.get("content", ""))) for e in entries.values())
        return {"entries": len(entries), "chunks": chunks}

    def export(self) -> list[dict]:
        return self.list()

    def import_entries(self, items: list) -> int:
        added = 0
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "")
            if not title or not content.strip():
                continue
            self.add(title, content, source=str(item.get("source") or ""))
            added += 1
        return added
