"""知识库：全文条目存储 + 即时分块 + 词面打分检索（零依赖默认）
+ Lorebook 世界书（触发式注入，SillyTavern World Info 模式）
+ 语义检索（可选 embedding 向量层，任何环节不可用回退词面打分）"""
from __future__ import annotations

import re
import time
import uuid

from .. import utils
from ..engine import vectors

KB_KEY = "QvQChat:kb"
VEC_PREFIX = "QvQChat:kbvec:" 
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
DEFAULT_COOLDOWN_MIN = 30
SEMANTIC_MIN_SCORE = 0.2 
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
         
        self._external_provider = None
        self.cfg = cfg
 
        self.vectors = vectors

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

    def set_external_provider(self, provider) -> None:
        """注入生态模块贡献的只读知识条目（经 qvq_extensions）。"""
        self._external_provider = provider

    def _external_entries(self) -> list[dict]:
        if self._external_provider is None:
            return []
        try:
            items = self._external_provider() or []
        except Exception:
            return []
        return [item for item in items if isinstance(item, dict) and item.get("content")]

    def _norm_triggers(self, triggers) -> list[str]:
        if triggers is None:
            return []
        raw = triggers if isinstance(triggers, (list, tuple)) else str(triggers).split(",")
        return [str(t).strip() for t in raw if str(t).strip()]

    @staticmethod
    def _visible(entry: dict, viewer: str | None) -> bool:
        """可见域过滤：owner="" 全局对所有人可见；否则仅本会话（chat_key 全等）或
        本适配器（owner == 平台名）可见。viewer=None（面板运维视角）不过滤。"""
        if viewer is None:
            return True
        owner = str(entry.get("owner") or "")
        if not owner:
            return True
        return owner == viewer or owner == viewer.split(":", 1)[0]

    def _default_cooldown(self) -> int:
        try:
            return int(getattr(self.cfg, "kb_cooldown_min", DEFAULT_COOLDOWN_MIN) or 0)
        except (TypeError, ValueError):
            return DEFAULT_COOLDOWN_MIN

    def add(
        self,
        title: str,
        content: str,
        source: str = "",
        triggers: list | None = None,
        priority: int = 0,
        cooldown_min: int | None = None,
        owner: str = "",
    ) -> dict:
        entry = {
            "id": uuid.uuid4().hex[:12],
            "title": str(title or "").strip() or "untitled",
            "content": str(content or ""),
            "source": str(source or ""),
            "owner": str(owner or ""),
            "created": utils.now_ts(),
        }
        trig = self._norm_triggers(triggers)
        if trig:
            entry["triggers"] = trig
            entry["priority"] = int(priority or 0)
            entry["cooldown_min"] = int(cooldown_min if cooldown_min is not None else self._default_cooldown())
        entries = self._load()
        entries[entry["id"]] = entry
        self._save(entries)
        return entry

    def update(self, kb_id: str, title: str | None = None, content: str | None = None,
               source: str | None = None, triggers: list | None = None,
               owner: str | None = None) -> dict | None:
        """编辑知识库条目：只改传入的字段；triggers 传 [] 清空触发词，None 不动。

        内容变化时同步失效向量缓存，下一次检索按新内容重嵌入。
        """
        entries = self._load()
        entry = entries.get(kb_id)
        if not isinstance(entry, dict):
            return None
        if title is not None:
            entry["title"] = str(title).strip() or "untitled"
        content_changed = False
        if content is not None and str(content) != entry.get("content", ""):
            entry["content"] = str(content)
            content_changed = True
        if source is not None:
            entry["source"] = str(source)
        if owner is not None:
            entry["owner"] = str(owner or "")
        if triggers is not None:
            trig = self._norm_triggers(triggers)
            if trig:
                entry["triggers"] = trig
            else:
                entry.pop("triggers", None)
                entry.pop("priority", None)
                entry.pop("cooldown_min", None)
        entry["updated"] = utils.now_ts()
        entries[kb_id] = entry
        self._save(entries)
        if content_changed:
            try:
                self.sdk.storage.delete(VEC_PREFIX + kb_id)
            except Exception:
                pass
        return entry

    def delete(self, kb_id: str) -> bool:
        entries = self._load()
        if kb_id not in entries:
            return False
        entries.pop(kb_id)
        self._save(entries)
        self.sdk.storage.delete(VEC_PREFIX + kb_id) 
        return True

    def list(self) -> list[dict]:
        return sorted(self._load().values(), key=lambda e: e.get("created", 0), reverse=True)

    def get(self, kb_id: str) -> dict | None:
        return self._load().get(kb_id)

    def _chunks(self, viewer: str | None = None) -> list[dict]:
        out = []
        entries = list(self._load().values()) + self._external_entries()
        for entry in entries:
            if not self._visible(entry, viewer):
                continue
            for piece in self.chunk(entry.get("content", "")):
                out.append({"entry": entry, "text": piece})
        return out

 

    def triggered(self, context_texts: list[str], now: float | None = None,
                  viewer: str | None = None) -> list[dict]:
        """扫描最近消息文本：任一 trigger 关键词命中（大小写不敏感包含）且不在冷却期
        → 按 priority 降序返回条目，并刷新 last_trigger_ts 写回 KV（命中即刷新）。
        无 triggers 字段的条目不参与（保持词面/语义检索行为，两机制并存互补）。
        viewer 给定时按可见域过滤（会话/适配器私有条目不外泄）。"""
        if not getattr(self.cfg, "kb_triggers_enabled", True):
            return []
        texts = " \n ".join(str(t or "") for t in (context_texts or []) if str(t or "").strip()).lower()
        if not texts:
            return []
        ts = float(now if now is not None else time.time())
        entries = self._load()
         
        external = self._external_entries()
        hits: list[dict] = []
        changed = False
        for entry in list(entries.values()) + external:
            if not self._visible(entry, viewer):
                continue
            trig = [str(t).lower() for t in (entry.get("triggers") or []) if str(t).strip()]
            if not trig:
                continue
            cooldown = float(int(entry.get("cooldown_min", DEFAULT_COOLDOWN_MIN) or 0))
            last = float(entry.get("last_trigger_ts") or 0)
            if last > 0 and cooldown > 0 and ts - last < cooldown * 60:
                continue 
            if any(t in texts for t in trig):
                hits.append(entry)
                entry["last_trigger_ts"] = ts
                changed = True
        if changed:
            self._save(entries)
        hits.sort(key=lambda e: (-int(e.get("priority", 0) or 0), float(e.get("created", 0) or 0)))
        return hits

 

    def _entry_vectors(self, entry: dict, texts: list[str]) -> list[list[float]] | None:
        """条目向量懒计算 + KV 缓存（QvQChat:kbvec:{doc_id}）；模型/分块参数变化自动重算。"""
        size, overlap = self._chunk_params()
        model = self.vectors.model_of(self.cfg)
        cache_key = VEC_PREFIX + str(entry.get("id") or "")
        cached = self.sdk.storage.get(cache_key, None)
        if (
            isinstance(cached, dict)
            and cached.get("model") == model
            and cached.get("size") == size
            and cached.get("overlap") == overlap
            and len(cached.get("vecs") or []) == len(texts)
        ):
            return cached["vecs"]
        vecs = self.vectors.embed(texts, self.cfg)
        if vecs is None or len(vecs) != len(texts):
            return None
        self.sdk.storage.set(cache_key, {"model": model, "size": size, "overlap": overlap, "vecs": vecs})
        return vecs

    def _semantic_search(self, query: str, top_k: int, viewer: str | None = None) -> list[dict] | None:
        """embedding_enabled 且向量层可用时的余弦检索；None = 不可用/失败 → 调用方回退词面。"""
        if not getattr(self.cfg, "embedding_enabled", False) or not self.vectors.available(self.cfg):
            return None
        qvecs = self.vectors.embed([str(query or "")], self.cfg)
        if not qvecs:
            return None
        qvec = qvecs[0]
        scored: list[tuple[float, dict, str]] = []
        for entry in self._load().values():
            if not self._visible(entry, viewer):
                continue
            texts = self.chunk(entry.get("content", ""))
            if not texts:
                continue
            vecs = self._entry_vectors(entry, texts)
            if vecs is None:
                return None 
            best_vec, best_text = max(
                ((v, t) for v, t in zip(vecs, texts)),
                key=lambda pair: self.vectors.cosine(qvec, pair[0]),
            )
            scored.append((self.vectors.cosine(qvec, best_vec), entry, best_text))
        scored.sort(key=lambda item: -item[0])
        results = []
        for score, entry, best_text in scored[: max(1, int(top_k or 0))]:
            if score < SEMANTIC_MIN_SCORE:
                continue
            results.append(
                {
                    "id": entry["id"],
                    "title": entry.get("title", ""),
                    "source": entry.get("source", ""),
                    "snippet": utils.truncate(best_text, 500),
                    "score": round(float(score), 4),
                }
            )
        return results

    def search(self, query: str, top_k: int = 2, viewer: str | None = None) -> list[dict]:
        """检索知识库。viewer=None 全量（面板）；给 chat_key 则全局条目 + 该会话/平台私有条目。"""
        tokens = _tokenize(query)
        if not tokens:
            return []
        semantic = self._semantic_search(query, top_k, viewer)
        if semantic is not None:
            return semantic
        scored = []
        for chunk in self._chunks(viewer):
            chunk_tokens = _tokenize(chunk["text"])
            if not chunk_tokens:
                continue
            bag: dict[str, int] = {}
            for token in chunk_tokens:
                bag[token] = bag.get(token, 0) + 1
            score = sum(bag.get(token, 0) for token in tokens)
 
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
            self.add(
                title,
                content,
                source=str(item.get("source") or ""),
                triggers=item.get("triggers"),
                priority=int(item.get("priority") or 0),
                cooldown_min=int(item["cooldown_min"]) if item.get("cooldown_min") is not None else None,
                owner=str(item.get("owner") or ""),
            )
            added += 1
        return added
