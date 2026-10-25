"""跨会话用户画像（ProfileStore）。

存储：``QvQChat:profile:{platform}:{uid}`` →
``{"traits": [{"text","ts"}...], "preferences": [...], "facts": [...], "updated": ts}``
（每类上限 ``profile_max``（默认 20）条，单条 160 字符）。

consolidate(user_key)：聚合该用户各会话的 facts（user_seen 倒排 + 平台私聊会话）
与会话 memory 条目（global 全量 / 逐会话 importance>=4），包含式归并去重后经
LLM（dispatch kind="compact" prefer="cheap"）提炼为 traits/preferences（失败保留
原始条目）；traits 超过 ``profile_decay_days`` 天未被新事实强化则淘汰。

digest(user_key, limit=profile_inject)：注入系统提示用的紧凑行列表。
"""
from __future__ import annotations

import re as _re

from .. import texts, utils
from ..engine.base import ChatRequest, TaskSpec

PROFILE_PREFIX = "QvQChat:profile:"
PROFILE_ITEM_CHARS = 160

USER_SEEN_PREFIX = "QvQChat:user_seen:"
MEM_PREFIX = "QvQChat:mem:"
GLOBAL_SCOPE = "global"


def split_user_key(user_key: str) -> tuple[str, str]:
    """platform:uid → (platform, uid)；无分隔时返回 ("", user_key)。"""
    text = str(user_key or "")
    if ":" not in text:
        return ("", text)
    platform, _, uid = text.rpartition(":")
    return (platform, uid)


class ProfileStore:

    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self.config = getattr(main, "cfg", None)

# ===== 基础存取 =====

    def _key(self, user_key: str) -> str:
        return PROFILE_PREFIX + str(user_key or "")

    def _load(self, user_key: str) -> dict:
        data = self.sdk.storage.get(self._key(user_key), None)
        if not isinstance(data, dict):
            return {"traits": [], "preferences": [], "facts": [], "updated": 0.0}
        for name in ("traits", "preferences", "facts"):
            items = data.get(name)
            data[name] = [
                {"text": str(item.get("text") or ""), "ts": float(item.get("ts") or 0.0)}
                for item in items
                if isinstance(item, dict) and str(item.get("text") or "").strip()
            ] if isinstance(items, list) else []
        data.setdefault("updated", 0.0)
        return data

    def _save(self, user_key: str, data: dict) -> None:
        max_n = max(1, int(getattr(self.config, "profile_max", 20) or 20))
        for name in ("traits", "preferences", "facts"):
            items = data.get(name) or []
            data[name] = items[-max_n:] if len(items) > max_n else items
        data["updated"] = utils.now_ts()
        self.sdk.storage.set(self._key(user_key), data)

    def get(self, user_key: str) -> dict:
        """画像全文（结构化 dict，供 CLI/Dashboard 只读展示）。"""
        return self._load(user_key)

    def clear(self, user_key: str) -> int:
        data = self._load(user_key)
        removed = len(data["traits"]) + len(data["preferences"]) + len(data["facts"])
        if removed:
            self.sdk.storage.delete(self._key(user_key))
        return removed

    @staticmethod
    def _clean_item(text: str) -> str:
        return str(text or "").strip()[:PROFILE_ITEM_CHARS]

    @staticmethod
    def _normalized(text: str) -> str:
        return "".join(str(text).lower().split())

    @classmethod
    def _similar(cls, a: str, b: str) -> bool:
        """包含式相似：归一化后互为包含（与 memory.py 同款 3 倍长度护栏）。"""
        na, nb = cls._normalized(a), cls._normalized(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        return (na in nb and len(na) * 3 >= len(nb)) or (nb in na and len(nb) * 3 >= len(na))

    @classmethod
    def _merge_texts(cls, items: list[str]) -> list[str]:
        """包含式归并去重：互为包含的条目保留更完整（更长）的一条，保持出现顺序。"""
        kept: list[str] = []
        for item in items:
            text = str(item or "").strip()
            if not text:
                continue
            merged = False
            for i, existing in enumerate(kept):
                if cls._similar(existing, text):
                    kept[i] = text if len(text) > len(existing) else existing
                    merged = True
                    break
            if not merged:
                kept.append(text)
        return kept

# ===== 注入 =====

    def digest(self, user_key: str, limit: int = 0) -> list[str]:
        """注入用紧凑行列表（limit<=0 时用 profile_inject 配置）。"""
        if limit <= 0:
            limit = int(getattr(self.config, "profile_inject", 8) or 8)
        data = self._load(user_key)
        lines: list[str] = []
        for name, tag in (("traits", "trait"), ("preferences", "pref"), ("facts", "fact")):
            for item in data.get(name) or []:
                text = self._clean_item(item.get("text") or "")
                if text:
                    lines.append(f"[{tag}] {text}")
                if len(lines) >= limit:
                    return lines
        return lines

    def describe(self, user_key: str) -> str:
        """画像全文的多行文本（CLI 透明展示用；空画像返回 profile_empty）。"""
        data = self._load(user_key)
        blocks: list[str] = []
        for name, key in (("traits", "profile_section_traits"), ("preferences", "profile_section_preferences"), ("facts", "profile_section_facts")):
            items = data.get(name) or []
            if not items:
                continue
            lines = [texts.t(key)] + [f"- {self._clean_item(i.get('text') or '')}" for i in items]
            blocks.append("\n".join(lines))
        if not blocks:
            return texts.t("profile_empty")
        return "\n".join(blocks)

# ===== 聚合源 =====

    def session_candidates(self, user_key: str) -> list[str]:
        """该用户的会话候选：user_seen 倒排（群）+ 平台私聊会话 key（去重）。"""
        platform, uid = split_user_key(user_key)
        if not uid:
            return []
        seen = self.sdk.storage.get(USER_SEEN_PREFIX + uid, None)
        candidates: list[str] = []
        if isinstance(seen, list):
            for item in seen:
                if isinstance(item, dict) and isinstance(item.get("chat_key"), str) and item["chat_key"]:
                    candidates.append(item["chat_key"])
        if platform:
            candidates.append(f"{platform}:private:{uid}")
        return list(dict.fromkeys(candidates))

    def _collect_raw_items(self, user_key: str) -> list[str]:
        """聚合各会话 facts + memory 条目（global 全量 / 逐会话 importance>=4）。"""
        service = getattr(self.main, "conversations", None)
        memory = getattr(self.main, "memory", None)
        items: list[str] = []
        for chat_key in self.session_candidates(user_key):
            if service is not None:
                items.extend(str(f) for f in service.facts_of(chat_key) if f)
            if memory is not None:
                for entry in memory.entries(chat_key):
                    if not (isinstance(entry, dict) and str(entry.get("content") or "").strip()):
                        continue
# 逐会话记忆仅取 importance>=4（global 作用域不受此限）
                    try:
                        importance = int(entry.get("importance", 3) or 3)
                    except (TypeError, ValueError):
                        importance = 3
                    if importance >= 4:
                        items.append(str(entry["content"]).strip())
        if memory is not None:
            for entry in memory.entries(GLOBAL_SCOPE):
                if isinstance(entry, dict) and str(entry.get("content") or "").strip():
                    items.append(str(entry["content"]).strip())
        return items

# ===== LLM 提炼 =====

    def _pool(self):
        return getattr(self.main, "pool", None)

    async def _distill(self, raw_items: list[str]) -> tuple[list[str], list[str]]:
        """LLM 把散条归纳为 (traits, preferences)；失败/无输出返回 ([], []) 由调用方兜底。"""
        pool = self._pool()
        if pool is None or not raw_items:
            return ([], [])
        dispatch = getattr(pool, "dispatch", None)
        body = "\n".join(f"- {item}" for item in raw_items[:60])
        request = ChatRequest(
            messages=[
                {"role": "system", "content": texts.t("profile_distill_prompt")},
                {"role": "user", "content": body},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        try:
            if callable(dispatch):
                response = await dispatch(TaskSpec(kind="compact", prefer="cheap"), request)
            else:
                response = await pool.chat(request)
        except Exception as e:
            logger = getattr(self.main, "logger", None)
            if logger is not None:
                logger.warning(f"profile distill failed: {e}")
            return ([], [])
        content = str(getattr(response, "content", "") or "").strip()
        if not content:
            return ([], [])
        traits = self._parse_tag(content, "traits")
        preferences = self._parse_tag(content, "preferences")
        return (traits, preferences)

    @staticmethod
    def _parse_tag(content: str, tag: str) -> list[str]:
        match = _re.search(rf"<{tag}>(.*?)</{tag}>", content, _re.DOTALL | _re.IGNORECASE)
        if not match:
            return []
        out: list[str] = []
        for line in match.group(1).splitlines():
            line = line.strip().lstrip("-*•·").strip()
            if line:
                out.append(line)
        return out

    @staticmethod
    def _fallback_classify(raw_items: list[str]) -> tuple[list[str], list[str]]:
        """LLM 失败兜底：PREFERENCE| 类条目归 preferences，其余（ENTITY/TODO/memory）归 traits。"""
        traits: list[str] = []
        preferences: list[str] = []
        for item in raw_items:
            if item.upper().startswith("PREFERENCE|"):
                preferences.append(item)
            else:
                traits.append(item)
        return (traits, preferences)

# ===== 固化 =====

    async def consolidate(self, user_key: str) -> dict:
        """聚合源 → 去重 → LLM 提炼（失败保留原始条目）→ 衰减 → 落盘。"""
        user_key = str(user_key or "").strip()
        if not user_key:
            return {"user_key": "", "changed": False}
        now = utils.now_ts()
        existing = self._load(user_key)
        raw_items = self._merge_texts([self._clean_item(i) for i in self._collect_raw_items(user_key)])
        facts_raw = [item for item in raw_items if _re.match(r"^(ENTITY|PREFERENCE|TODO)\|", item, _re.IGNORECASE)]

        traits, preferences = await self._distill(raw_items)
        if not traits and not preferences:
            traits, preferences = self._fallback_classify(raw_items)

        traits = self._merge_texts([self._clean_item(t) for t in traits])[: max(0, int(getattr(self.config, "profile_max", 20) or 20))]
        preferences = self._merge_texts([self._clean_item(p) for p in preferences])[: max(0, int(getattr(self.config, "profile_max", 20) or 20))]

# 新条目视为本次已强化（ts=now）；未被新结果/新源覆盖的旧条目保留原 ts（交由衰减裁决）
        merged_traits = [{"text": t, "ts": now} for t in traits]
        merged_prefs = [{"text": p, "ts": now} for p in preferences]
        for old in existing["traits"]:
            if not any(self._similar(old["text"], t) for t in traits) and not any(self._similar(old["text"], s) for s in raw_items):
                merged_traits.append(old)
        for old in existing["preferences"]:
            if not any(self._similar(old["text"], p) for p in preferences) and not any(self._similar(old["text"], s) for s in raw_items):
                merged_prefs.append(old)

# 衰减：超过 profile_decay_days 天未被强化的 traits 淘汰（0 关闭；仅 traits）
        decay_days = int(getattr(self.config, "profile_decay_days", 30) or 0)
        decayed = 0
        if decay_days > 0:
            cutoff = now - decay_days * 86400
            before = len(merged_traits)
            merged_traits = [t for t in merged_traits if t["ts"] >= cutoff]
            decayed = before - len(merged_traits)

        merged_facts = self._merge_entries([{"text": item, "ts": now} for item in facts_raw])

        data = {"traits": merged_traits, "preferences": merged_prefs, "facts": merged_facts, "updated": now}
        changed = (
            [t["text"] for t in merged_traits] != [t["text"] for t in existing["traits"]]
            or [p["text"] for p in merged_prefs] != [p["text"] for p in existing["preferences"]]
            or [f["text"] for f in merged_facts] != [f["text"] for f in existing["facts"]]
        )
        if changed or merged_traits or merged_prefs or merged_facts:
            self._save(user_key, data)
        return {"user_key": user_key, "changed": changed, "decayed": decayed,
                "traits": len(merged_traits), "preferences": len(merged_prefs), "facts": len(merged_facts)}

    def _merge_entries(self, entries: list[dict]) -> list[dict]:
        """facts 条目按包含式归并（保留更长/更新的一条）。"""
        out: list[dict] = []
        for entry in entries:
            replaced = False
            for i, kept in enumerate(out):
                if self._similar(kept["text"], entry["text"]):
                    out[i] = entry if len(entry["text"]) > len(kept["text"]) or entry["ts"] > kept["ts"] else kept
                    replaced = True
                    break
            if not replaced:
                out.append(entry)
        return out

# ===== 近期活跃用户 =====

    def active_user_keys(self, within_hours: float = 24.0) -> list[str]:
        """user_seen 倒排里 updated 近 within_hours 的用户 → platform:uid 键列表（去重）。"""
        cutoff = utils.now_ts() - max(0.0, float(within_hours)) * 3600
        keys: list[str] = []
        for key in self.sdk.storage.keys():
            if not (isinstance(key, str) and key.startswith(USER_SEEN_PREFIX)):
                continue
            uid = key[len(USER_SEEN_PREFIX):]
            if not uid:
                continue
            seen = self.sdk.storage.get(key, None)
            if not isinstance(seen, list):
                continue
            latest = max((float(item.get("ts") or 0.0) for item in seen if isinstance(item, dict)), default=0.0)
            if latest < cutoff:
                continue
            platforms = {
                str(item.get("chat_key") or "").split(":", 1)[0]
                for item in seen
                if isinstance(item, dict) and str(item.get("chat_key") or "").strip()
            }
            for platform in sorted(platforms):
                if platform:
                    keys.append(f"{platform}:{uid}")
        return list(dict.fromkeys(keys))
