from __future__ import annotations

import asyncio
import base64 as _base64
import hashlib as _hashlib
import re as _re
from pathlib import Path
from typing import Any
from urllib.parse import unquote as _unquote

from .. import texts, utils
from ..engine import tokens
from ..engine.base import TaskSpec
from ..prompts import CAPABILITY_PROMPT, NARRATE_PROMPT, SKILL_OFFER_NOTE
from .budget import ContextPacker, SystemPart
from .compactor import Compactor, context_tokens, estimate_tokens, extract_facts

CONV_PREFIX = "QvQChat:conv:"
ROUTES_KEY = "QvQChat:routes"
# 会话索引（单键 list[chat_key]，list_sessions/create 免全库 keys() 扫描）
CONV_INDEX_KEY = "QvQChat:conv_index"
# 用户→群会话倒排（recent_user_messages 免全库扫描）
USER_SEEN_PREFIX = "QvQChat:user_seen:"
USER_SEEN_MAX = 20
UPLOAD_DIR = Path("data/QvQChat/uploads")

DASHBOARD_PLATFORM = "dashboard"


def make_chat_key(platform: str, detail_type: str, target_id: str) -> str:
    return f"{platform}:{detail_type}:{target_id}"


def parse_chat_key(chat_key: str) -> tuple[str, str, str]:
    parts = chat_key.split(":", 2)
    if len(parts) != 3:
        return ("", "", "")
    return (parts[0], parts[1], parts[2])


_ISOLATION_RE = _re.compile(r"^([^:]+):group:([^:]+):u[^:]+$")


def strip_isolation(chat_key: str) -> str:
    """仅对形如 platform:group:<群>:u<成员> 的隔离 key 剥离成员后缀"""
    m = _ISOLATION_RE.match(chat_key or "")
    return f"{m.group(1)}:group:{m.group(2)}" if m else (chat_key or "")


class ConversationService:


    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self.config = main.cfg
        self.compactor = Compactor(main)
# 模块级注入 token 估算配置
        tokens.configure(self.config)
# 上下文预算装填器
        self.packer = ContextPacker()
# summary 异步合并的 per-chat 锁与待合并队列
        self._summary_locks: dict[str, asyncio.Lock] = {}
        self._summary_pending: dict[str, list[str]] = {}
# 启动后首次访问会话索引时做一次全量对账
        self._index_ready = False

    @property
    def profile(self):
        """跨会话用户画像（ProfileStore，懒构造；实现在 conversation/profile.py）。"""
        if getattr(self, "_profile", None) is None:
            from .profile import ProfileStore

            self._profile = ProfileStore(self.main)
        return self._profile


    def _state(self, chat_key: str) -> dict:
        return self._normalize_state(self.sdk.storage.get(CONV_PREFIX + chat_key, None))

    @staticmethod
    def _normalize_state(raw) -> dict:
        state = raw if isinstance(raw, dict) else {}
        contexts = state.get("contexts")
        if not isinstance(contexts, list):
            contexts = []
        state["contexts"] = contexts
# facts 列表懒迁移
        if not isinstance(state.get("facts"), list):
            state["facts"] = []
        state.setdefault("persona", None)
        state.setdefault("updated", 0.0)
        return state

    def _save(self, chat_key: str, state: dict) -> None:
        state["updated"] = utils.now_ts()
        limit = max(2, int(getattr(self.config, "context_limit", 30))) * 2
        state["contexts"] = state["contexts"][-limit:]
        self.sdk.storage.set(CONV_PREFIX + chat_key, state)
        self._index_add(chat_key)

    def _save_no_touch(self, chat_key: str, state: dict) -> None:
        limit = max(2, int(getattr(self.config, "context_limit", 30))) * 2
        state["contexts"] = state["contexts"][-limit:]
        self.sdk.storage.set(CONV_PREFIX + chat_key, state)
        self._index_add(chat_key)

# ===== 会话索引（单键 list[chat_key]，免全库 keys() 扫描） =====

    def _index_load(self) -> list[str] | None:
        """读索引；损坏/缺失返回 None（调用方回退 keys() 扫描自愈）。"""
        data = self.sdk.storage.get(CONV_INDEX_KEY, None)
        if not isinstance(data, list):
            return None
        return [str(k) for k in data if isinstance(k, str) and k]

    def _index_save(self, keys: list[str]) -> None:
        self.sdk.storage.set(CONV_INDEX_KEY, keys)

    def _index_add(self, chat_key: str) -> None:
        """会话键落盘时同步维护索引（去重）。索引损坏时先全量对账，防止单键索引覆盖其余会话。"""
        index = self._index_load()
        if index is None:
            index = self.rebuild_index()
        if chat_key in index:
            return
        self._index_save(index + [chat_key])

    def _index_remove(self, chat_key: str) -> None:
        index = self._index_load()
        if index is None or chat_key not in index:
            return
        self._index_save([k for k in index if k != chat_key])

    def rebuild_index(self) -> list[str]:
        """全量对账：keys() 扫描 vs 索引差集修复（首访一次；索引缺失/失同步时自愈）。"""
        scanned = sorted(
            key[len(CONV_PREFIX):]
            for key in self.sdk.storage.keys()
            if isinstance(key, str) and key.startswith(CONV_PREFIX)
        )
        index = self._index_load()
        known = list(index) if index is not None else []
        if index is None:
            self.main.logger.debug("conv_index missing/corrupt, rebuilding from storage scan")
        elif sorted(known) != scanned:
            self.main.logger.debug(
                f"conv_index out of sync (index={len(known)}, storage={len(scanned)}), repairing"
            )
        else:
            self._index_ready = True
            return known
        self._index_save(scanned)
        self._index_ready = True
        return scanned

    def _session_keys(self) -> list[str]:
        """取会话键全集：索引优先；首访全量对账一次；索引损坏回退 keys() 扫描并自愈。"""
        if not self._index_ready:
            self.rebuild_index()
        index = self._index_load()
        if index is not None:
            return index
        self.main.logger.debug("conv_index unreadable, falling back to storage scan")
        scanned = sorted(
            key[len(CONV_PREFIX):]
            for key in self.sdk.storage.keys()
            if isinstance(key, str) and key.startswith(CONV_PREFIX)
        )
        self._index_save(scanned)
        return scanned


    def get_contexts(self, chat_key: str) -> list:
        return list(self._state(chat_key)["contexts"])

    def replace_contexts(self, chat_key: str, contexts: list) -> None:
        state = self._state(chat_key)
        state["contexts"] = list(contexts)
        self._save(chat_key, state)

    def seed_contexts(self, chat_key: str, seed: list) -> list:
        state = self._state(chat_key)
        if state["contexts"]:
            return list(state["contexts"])
        state["contexts"] = list(seed)
        self._save(chat_key, state)
        return list(seed)

    def append(self, chat_key: str, role: str, content, trace: list | None = None, rounds: list | None = None) -> None:
        state = self._state(chat_key)
        entry: dict = {"role": role, "content": content}
        if trace:
            entry["trace"] = list(trace)
        if rounds:
            entry["rounds"] = list(rounds)
        state["contexts"].append(entry)
        self._save(chat_key, state)

    def append_user(self, chat_key: str, content, sender_id: str = "") -> None:

        state = self._state(chat_key)
        entry: dict = {"role": "user", "content": content}
        if sender_id:
            entry["sender"] = sender_id
        state["contexts"].append(entry)
        state["turns"] = int(state.get("turns") or 0) + 1
        self._save(chat_key, state)
        if sender_id:
            self._user_seen_record(sender_id, chat_key, self._text_of(content))

    def pop_last_user_if(self, chat_key: str, text: str) -> bool:
        """末条上下文为内容匹配的 user 消息时弹出并保存（悬空恢复防重复；仅动末条）。

        多模态 content（parts 列表）按文本部分拼接比对；不匹配/末条非 user 一律不动。
        """
        state = self._state(chat_key)
        contexts = state["contexts"]
        if not contexts:
            return False
        entry = contexts[-1]
        if not isinstance(entry, dict) or entry.get("role") != "user":
            return False
        if self._text_of(entry.get("content")) != str(text or ""):
            return False
        contexts.pop()
        self._save(chat_key, state)
        return True

# ===== 用户→群会话倒排（recent_user_messages 免全库扫描） =====

    def _user_seen(self, uid: str) -> list[dict] | None:
        """读倒排；损坏/缺失返回 None（调用方回退旧全扫）。"""
        data = self.sdk.storage.get(USER_SEEN_PREFIX + uid, None)
        if not isinstance(data, list):
            return None
        return [item for item in data if isinstance(item, dict) and isinstance(item.get("chat_key"), str) and item["chat_key"]]

    def _user_seen_record(self, uid: str, chat_key: str, head: str) -> None:
        """uid → 最近发言的群会话（新在前、去重、上限 USER_SEEN_MAX）。仅记群会话。"""
        if ":group:" not in chat_key:
            return
        seen = self._user_seen(uid) or []
        rest = [item for item in seen if item.get("chat_key") != chat_key]
        entry = {"chat_key": chat_key, "ts": utils.now_ts(), "head": utils.truncate(str(head or ""), 60)}
        self.sdk.storage.set(USER_SEEN_PREFIX + uid, ([entry] + rest)[:USER_SEEN_MAX])

    def reset(self, chat_key: str) -> None:
        state = self._state(chat_key)
        state["contexts"] = []
        state["summary"] = ""
        state["facts"] = []
        state["turns"] = 0
        state["compacted_at_turn"] = 0
        self._save(chat_key, state)

    def edit_message(self, chat_key: str, index: int, content: str, attachments: list | None = None) -> bool:
        contexts = self.get_contexts(chat_key)
        if not (0 <= index < len(contexts)):
            return False
        entry = contexts[index]
        if isinstance(attachments, list):
            entry["content"] = self.rebuild_user_content(content, attachments)
        elif isinstance(entry.get("content"), list):
            kept = [p for p in entry["content"] if isinstance(p, dict) and p.get("type") != "text"]
            merged = ([{"type": "text", "text": content}] + kept) if content else kept
            entry["content"] = merged or content
        else:
            entry["content"] = content
        self.replace_contexts(chat_key, contexts)
        return True

    def delete_message(self, chat_key: str, index: int) -> bool:
        contexts = self.get_contexts(chat_key)
        if not (0 <= index < len(contexts)):
            return False
        contexts.pop(index)
        self.replace_contexts(chat_key, contexts)
        return True

    def trim_overflow(self, chat_key: str, keep: int) -> list:
        state = self._state(chat_key)
        contexts = state["contexts"]
        if len(contexts) <= keep:
            return []
        removed = contexts[: len(contexts) - keep]
        state["contexts"] = contexts[-keep:]
        self._save(chat_key, state)
        return removed


    def set_persona(self, chat_key: str, persona_id: str | None) -> None:
        state = self._state(chat_key)
        state["persona"] = persona_id
        self._save_no_touch(chat_key, state)

    def persona_of(self, chat_key: str) -> str | None:
        return self._state(chat_key)["persona"]

    def set_flags(self, chat_key: str, flags: dict | None = None, pinned: bool | None = None, archived: bool | None = None) -> None:
        """置会话标记。兼容旧签名（pinned/archived 关键字）；起支持任意布尔标记 dict
（如 {"opening_sent": True}），供开场白防重等状态写入。"""
        state = self._state(chat_key)
        if pinned is not None:
            state["pinned"] = bool(pinned)
        if archived is not None:
            state["archived"] = bool(archived)
        if flags:
            for name, value in flags.items():
                state[str(name)] = bool(value)
        self._save_no_touch(chat_key, state)

    def get_flag(self, chat_key: str, name: str) -> bool:
        """读会话布尔标记（缺省 False），与 set_flags 的 dict 形态配对。"""
        return bool(self._state(chat_key).get(name))

# ===== 会话成员白名单与跨会话路由 =====

    def routes(self) -> dict:
        data = self.sdk.storage.get(ROUTES_KEY, {})
        return {k: str(v) for k, v in data.items() if isinstance(k, str) and v} if isinstance(data, dict) else {}

    def save_routes(self, routes: dict) -> None:
        self.sdk.storage.set(ROUTES_KEY, {str(k): str(v) for k, v in (routes or {}).items() if v})

    def resolve_route(self, chat_key: str) -> str:
        """消息来源 key → 目标会话 key；群隔离 key 先精确匹配再回落到群 base key"""
        routes = self.routes()
        if not routes:
            return ""
        if chat_key in routes:
            return routes[chat_key]
        base = strip_isolation(chat_key)
        if base != chat_key:
            return routes.get(base, "")
        return ""

    def routes_into(self, target: str) -> list[str]:
        return sorted(k for k, v in self.routes().items() if v == target)

    def members_of(self, chat_key: str) -> list[str]:
        members = self._state(chat_key).get("members")
        return members if isinstance(members, list) and members else ["*"]

    def set_members(self, chat_key: str, members: list) -> list[str]:
        cleaned: list[str] = []
        for item in members if isinstance(members, list) else []:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        state = self._state(chat_key)
        state["members"] = cleaned or ["*"]
        self._save_no_touch(chat_key, state)
        return state["members"]

    def member_allowed(self, chat_key: str, user_id: str, platform: str = "") -> bool:
        members = self.members_of(chat_key)
        if "*" in members:
            return True
        uid = str(user_id or "")
        if not uid:
            return False
        return uid in members or f"{platform}:{uid}" in members

    def set_ui(self, chat_key: str, ui: dict) -> dict:

        state = self._state(chat_key)
        cur = state.get("ui") if isinstance(state.get("ui"), dict) else {}
        cur.update({k: v for k, v in (ui or {}).items() if v is not None})
        state["ui"] = cur
        self._save_no_touch(chat_key, state)
        return cur

    def group_name_of(self, chat_key: str) -> str:
        return str(self._state(chat_key).get("group_name") or "")

    def set_group_name(self, chat_key: str, name: str) -> None:
        state = self._state(chat_key)
        state["group_name"] = name
        self._save(chat_key, state)

    def user_name_of(self, chat_key: str) -> str:
        return str(self._state(chat_key).get("user_name") or "")

    def set_user_name(self, chat_key: str, name: str) -> None:
        state = self._state(chat_key)
        state["user_name"] = name
        self._save(chat_key, state)

    def label_incoming(self, text: str, sender_id: str = "", sender_name: str = "") -> str:
        if not sender_id and not sender_name:
            return text
        who = f"{sender_name}({sender_id})" if sender_name else f"({sender_id})"
        return f"{who}: {text}"

    def summary_of(self, chat_key: str) -> str:
        return str(self._state(chat_key).get("summary") or "")

    @staticmethod
    def _fallback_merge(old: str, text: str, cap: int) -> str:
        """兜底：头 60% + “…[中段省略]…” + 尾 40%（替代纯丢头）。"""
        merged = (old + "\n" + text).strip() if old else text.strip()
        if len(merged) <= cap:
            return merged
        head_len = int(cap * 0.6)
        tail_len = int(cap * 0.4)
        head = merged[:head_len]
        tail = merged[-tail_len:] if tail_len else ""
        return (head + "…[中段省略]…" + tail).strip()

    def _write_summary(self, chat_key: str, text: str) -> None:
        state = self._state(chat_key)
        state["summary"] = text
        self._save(chat_key, state)

    def _summary_lock(self, chat_key: str) -> asyncio.Lock:
        lock = self._summary_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._summary_locks[chat_key] = lock
        return lock

    def _spawn_task(self, coro) -> None:
        spawn = getattr(self.main, "spawn", None)
        if callable(spawn):
            spawn(coro)
        else:
            coro.close()

    def append_summary(self, chat_key: str, text: str, cap: int | None = None) -> None:
        """追加摘要；超过 cap 时先写兜底合并，再异步 LLM 压缩。"""
        if cap is None:
            cap = int(getattr(self.config, "summary_cap", 1500) or 1500)
        text = str(text or "").strip()
        if not text:
            return
        old = self.summary_of(chat_key)
        if not old:
            self._write_summary(chat_key, text[:cap])
            return
        merged = (old + "\n" + text).strip()
        if len(merged) <= cap:
            self._write_summary(chat_key, merged)
            return
        fallback = self._fallback_merge(old, text, cap)
        self._write_summary(chat_key, fallback)
        self._summary_pending.setdefault(chat_key, []).append(text)
        self._spawn_task(self._merge_summary(chat_key, cap))

    async def _merge_summary(self, chat_key: str, cap: int) -> None:
# per-chat 锁防并发合并互相覆盖
        async with self._summary_lock(chat_key):
            pending = self._summary_pending.pop(chat_key, [])
            if not pending:
                return
            current = self.summary_of(chat_key)
            joined = "\n".join(pending)
            merged = ""
            try:
                merged = await self.compactor.summarize_text(current, joined)
            except Exception as e:
                self.main.logger.warning(f"summary merge failed: {e}")
            if merged:
                self._write_summary(chat_key, merged[:cap])
            else:
# LLM 合并失败：维持/刷新兜底结果
                self._write_summary(chat_key, self._fallback_merge(current, joined, cap))

# ===== 会话事实（facts） =====

    def facts_of(self, chat_key: str) -> list[str]:
        facts = self._state(chat_key).get("facts")
        return [str(f) for f in facts if f] if isinstance(facts, list) else []

    def append_facts(self, chat_key: str, facts: list) -> int:
        """入库 facts（去重、单条截 200 字符、上限 facts_max 保最新）。返回新增条数。"""
        cleaned_input = [str(f or "").strip() for f in facts or []]
        if not cleaned_input:
            return 0
        state = self._state(chat_key)
        existing = state["facts"] if isinstance(state.get("facts"), list) else []
        max_n = int(getattr(self.config, "facts_max", 100) or 0)
        added = 0
        for item in cleaned_input:
            text = item[:200]
            if not text or text in existing:
                continue
            existing.append(text)
            added += 1
        if max_n > 0 and len(existing) > max_n:
            del existing[: len(existing) - max_n]
        state["facts"] = existing
        if added:
            self._save_no_touch(chat_key, state)
        return added


    def _turn_count(self, chat_key: str) -> int:
        return int(self._state(chat_key).get("turns") or 0)

    def turns_since_compact(self, chat_key: str) -> int:
        state = self._state(chat_key)
        return int(state.get("turns") or 0) - int(state.get("compacted_at_turn") or 0)

    def mark_compacted(self, chat_key: str) -> None:
        state = self._state(chat_key)
        state["compacted_at_turn"] = int(state.get("turns") or 0)
        self._save_no_touch(chat_key, state)

    async def compact_if_needed(self, chat_key: str) -> dict:
        return await self.compactor.compact(chat_key, force=False, reason="auto")

    async def compact_now(self, chat_key: str) -> dict:
        return await self.compactor.compact(chat_key, force=True, reason="manual")

    async def compact_budget(self, chat_key: str) -> dict:
        """预算装填溢出触发的压缩。"""
        return await self.compactor.compact(chat_key, force=True, reason="budget")


    def create(self, platform: str = DASHBOARD_PLATFORM, detail_type: str = "private", target_id: str = "") -> str:

        if target_id:
            chat_key = make_chat_key(platform, detail_type, target_id)
            self._state(chat_key)
            return chat_key
        prefix = make_chat_key(platform, detail_type, "")
# 改读会话索引，免全库 keys() 扫描（首访自动对账补齐旧会话）
        existing = set(self._session_keys())
        chat_key = prefix + "web"
        if chat_key in existing and (self._state(chat_key).get("contexts") or self._state(chat_key).get("summary")):
            n = 2
            while (prefix + f"web{n}") in existing:
                n += 1
            chat_key = prefix + f"web{n}"
        state = self._state(chat_key)
        self._save(chat_key, state)
        return chat_key

    def delete(self, chat_key: str) -> bool:

        existed = self.sdk.storage.get(CONV_PREFIX + chat_key, None) is not None
        registry = getattr(self.main, "live_registry", None)
        if registry is not None:
            live = registry.get(chat_key)
            if live is not None and live.status == "running":
                live.cancel()
            registry.drop(chat_key)
        self.sdk.storage.delete(CONV_PREFIX + chat_key)
        self._index_remove(chat_key)
        self.main.memory.clear(chat_key)
        personas = getattr(self.main, "personas", None)
        if personas is not None:
            personas.bind(chat_key, None)
        return existed

    def delete_archived(self) -> int:
        removed = 0
        for session in self.list_sessions():
            if session.get("archived"):
                if self.delete(session["chat_key"]):
                    removed += 1
        return removed

    def list_sessions(self) -> list[dict]:
        sessions: list[dict] = []
# 读会话索引遍历（每键仍整读 state 元数据，但省掉全库 keys() 枚举+过滤）
        for chat_key in dict.fromkeys(self._session_keys()):
            raw = self.sdk.storage.get(CONV_PREFIX + chat_key, None)
            if not isinstance(raw, dict):
# 索引陈旧条目（存储键被外部删除）：跳过，下次对账清出
                continue
            state = self._normalize_state(raw)
            preview = ""
            for entry in reversed(state["contexts"]):
                content = entry.get("content") if isinstance(entry, dict) else None
                if content:
                    preview = utils.truncate(self._text_of(content), 60)
                    break
            platform, detail_type, target_id = parse_chat_key(chat_key)
            sessions.append(
                {
                    "chat_key": chat_key,
                    "platform": platform,
                    "detail_type": detail_type,
                    "target_id": target_id,
                    "name": str(state.get("group_name") or "") or str(state.get("user_name") or ""),
                    "persona": state["persona"],
                    "turns": len(state["contexts"]),
                    "updated": state["updated"],
                    "preview": preview,
                    "pinned": bool(state.get("pinned")),
                    "archived": bool(state.get("archived")),
                    "ui": state.get("ui") if isinstance(state.get("ui"), dict) else {},
                }
            )
        sessions.sort(key=lambda s: (not s["pinned"], -s["updated"]))
        return sessions

    def recent_user_messages(self, user_id: str, exclude_chat_key: str = "", limit: int = 6) -> list[dict]:
        needle = f"({user_id}):"
# 倒排优先取候选 chat_key（新在前）；缺失/损坏回退旧 keys() 全扫（旧数据兼容）
        seen = self._user_seen(user_id)
        if seen is not None:
            candidates = [item["chat_key"] for item in seen]
        else:
            candidates = [
                key[len(CONV_PREFIX):]
                for key in self.sdk.storage.keys()
                if isinstance(key, str) and key.startswith(CONV_PREFIX)
            ]
        found: list[dict] = []
        for chat_key in candidates:
            if chat_key == exclude_chat_key or ":group:" not in chat_key:
                continue
            state = self._state(chat_key)
            contexts = state.get("contexts") or []
            matches = [
                str(c.get("content") or "")
                for c in contexts
                if isinstance(c, dict)
                and c.get("role") == "user"
                and (c.get("sender") == user_id or needle in str(c.get("content") or ""))
            ]
            if not matches:
                continue
            group_name = str(state.get("group_name") or "")
            group_id = chat_key.split(":", 2)[2] if len(chat_key.split(":", 2)) == 3 else chat_key
            label = f"{group_name}({group_id})" if group_name else group_id
            found.append(
                {
                    "label": label,
                    "messages": matches[-3:],
                    "updated": state.get("updated") or 0.0,
                }
            )
        found.sort(key=lambda item: item["updated"], reverse=True)
        out: list[dict] = []
        for item in found[:3]:
            for content in item["messages"]:
                out.append({"label": item["label"], "content": content})
        return out[:limit]


    async def prepare(
        self,
        chat_key: str,
        text: str,
        *,
        images: list | None = None,
        scene: str = "",
        persona_id: str = "",
        active_skills: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        seed_provider: Any = None,
        cross_user_id: str = "",
        sender_id: str = "",
        profile_user: str = "",
        persist: bool = True,
    ) -> dict:


        await self.compact_if_needed(chat_key)
        contexts = self.get_contexts(chat_key)
# 发送级轮窗口：只携带最近 N 轮，历史本身不动
        max_turns = int(getattr(self.config, "max_context_turns", 0) or 0)
        if max_turns > 0:
            from .compactor import split_turns, merge_turns

            turns = split_turns(contexts)
            if len(turns) > max_turns:
                contexts = merge_turns(turns[-max_turns:])
# 进入时 contexts 为空且本次将做 seed → 首次接触（不依赖 seed 结果非空）
        first_contact = not contexts and seed_provider is not None
        seeded_done = False
        if not contexts and seed_provider is not None:
            seeded = seed_provider()
            if asyncio.iscoroutine(seeded):
                seeded = await seeded
            seeded = list(seeded) if seeded else []
            if not seeded and cross_user_id:
                cross = self.recent_user_messages(cross_user_id, exclude_chat_key=chat_key)
                if cross:
                    lines: list[str] = []
                    for item in cross:
                        lines.append(f"[来自 {item['label']}]")
                        lines.append(item["content"])
                    seeded = [{"role": "user", "content": texts.t("cross_session_header") + "\n" + "\n".join(lines)}]
            if seeded:
                contexts = self.seed_contexts(chat_key, seeded)
                seeded_done = bool(contexts)
        personas = getattr(self.main, "personas", None)
        persona = personas.get(persona_id) if (persona_id and personas) else personas.resolve(chat_key)
        memory = getattr(self.main, "memory", None)
        recalled: list = []
        if memory is not None:
            recalled = memory.recall(chat_key, query=self._text_of(text), limit=int(getattr(self.config, "memory_recall", 6))) or []
# Lorebook 触发扫描窗口：contexts 尾部 N 条文本 + 本次消息（供 kb 段触发式注入）
        window = max(0, int(getattr(self.config, "kb_trigger_window", 6) or 0))
        kb_texts = [self._text_of(c.get("content")) for c in contexts[-window:]] + [self._text_of(text)]
        parts = self.build_system_parts(
            persona,
            scene=scene,
            chat_key=chat_key,
            active_skills=active_skills,
            mcp_tools=mcp_tools,
            kb_query=self._text_of(text),
            kb_texts=kb_texts,
            profile_user=profile_user,
        )
        if recalled:
            lines = "\n".join(f"- {entry.get('content', '')}" for entry in recalled)
            parts.append(SystemPart("memory", "Related memories:\n" + lines))
        user_msg: dict = {"role": "user", "content": text}
        if images:
            pool = getattr(self.main, "pool", None)
            caps = {}
            try:
                caps = pool.primary_capabilities() if pool else {}
            except Exception:
                caps = {}
            if caps.get("vision") is False:
                described = await pool.describe_images(images) if pool else []
                lines = [f"[image {i + 1}] {d}" for i, d in enumerate(described) if d]
                if lines:
                    merged = (text + "\n\n" if text else "") + texts.t("vision_delegate_note") + "\n" + "\n".join(lines)
                    user_msg["content"] = merged
                    images = None
            if images:
                parts_list: list = [{"type": "text", "text": text}] if text else []
                parts_list += [{"type": "image_url", "image_url": {"url": url}} for url in images[:3]]
                user_msg["content"] = parts_list
# 按选中模型 context_length 走 ContextPacker 装填（默认 off 保持现状）
        model_info = self._resolve_chat_model()
        model_length = 0
        if isinstance(model_info, dict):
            try:
                model_length = int(model_info.get("context_length") or 0)
            except (TypeError, ValueError):
                model_length = 0
        default_length = int(getattr(self.config, "default_context_length", 0) or 0)
        mode = str(getattr(self.config, "context_budget_mode", "off") or "off").lower()
        if mode == "auto":
            pack_enabled = model_length > 0
            context_length = model_length
        elif mode == "tokens":
            pack_enabled = (model_length or default_length) > 0
            context_length = model_length or default_length
        else:
            pack_enabled = False
            context_length = 0
        overflow = False
        if pack_enabled:
            packed = self.packer.pack(
                context_length=context_length,
                parts=parts,
                history=contexts,
                user_msg=user_msg,
                max_output=int(getattr(self.config, "max_tokens", 0) or 0),
                context_reserve=float(getattr(self.config, "context_reserve", 0.85) or 0.85),
            )
            system = packed.system
            contexts = packed.messages[:-1]
            user_msg = packed.messages[-1]
            overflow = bool(packed.stats.get("overflow_turns") or packed.stats.get("dropped"))
        else:
            system = "\n".join(p.text for p in parts if p.text)
        if persist:
            self.append_user(chat_key, user_msg["content"], sender_id=self._persist_sender(chat_key, cross_user_id, sender_id))
        if overflow:
# 装填溢出：异步压缩存储侧历史（reason="budget"），本次请求先用装填结果
            self._spawn_task(self.compact_budget(chat_key))
        return {
            "system": system,
            "contexts": contexts,
            "user_msg": user_msg,
            "persona": persona,
            "model": (model_info or {}).get("id", "") if isinstance(model_info, dict) else "",
            "first_contact": first_contact,
            "seeded": seeded_done,
        }

    def _resolve_chat_model(self) -> dict | None:
        """预取本会话主对话将选中的模型（kind="chat"），保证装填与 runner 选型一致。"""
        pool = getattr(self.main, "pool", None)
        resolver = getattr(pool, "resolve_task_model", None)
        if not callable(resolver):
            return None
        try:
            return resolver(TaskSpec(kind="chat"))
        except Exception:
            return None

    @staticmethod
    def _persist_sender(chat_key: str, cross_user_id: str, sender_id: str = "") -> str:
        platform, detail_type, _ = parse_chat_key(chat_key)
        if platform == DASHBOARD_PLATFORM:
            return "dashboard"
# 群聊也持久化发言者 uid（此前恒为空串，导致历史消息无法归因）
        return sender_id or (cross_user_id if detail_type != "group" else "")

    def finalize(
        self,
        chat_key: str,
        reply: str,
        *,
        trace: list | None = None,
        rounds: list | None = None,
        usage: dict | None = None,
        model: str = "",
        title_from: str = "",
    ) -> str:

        self.append(chat_key, "assistant", reply, trace=trace, rounds=rounds)
        if usage:
            self.main.record_usage(chat_key, usage, model)
        overflow = self.trim_overflow(chat_key, keep=max(2, int(getattr(self.config, "context_limit", 30))))
        if overflow:
            self.main.spawn(self._summarize_overflow(chat_key, overflow))
        if title_from and not self.group_name_of(chat_key):
            self.main.spawn(self.title_task(chat_key, title_from, reply))
        return reply

    async def _summarize_overflow(self, chat_key: str, removed: list) -> None:
        summary = await self.compactor.summarize_entries(removed)
        if not summary:
            return
# 分离 <facts> 段（宽松解析，失败不入库）
        clean, facts = extract_facts(summary)
        if facts and getattr(self.config, "facts_extract", True):
            self.append_facts(chat_key, facts)
        self.append_summary(chat_key, clean or summary)


    @staticmethod
    def _persona_style_directives(style: dict) -> str:
        """style dict 编译为语言中性的约束值串（emoji_density/verbosity/formality）。"""
        bits = []
        for key in ("emoji_density", "verbosity", "formality"):
            value = str((style or {}).get(key) or "").strip()
            if value:
                bits.append(f"{key}: {value}")
        return "; ".join(bits)

    @classmethod
    def _persona_extra_text(cls, persona: dict) -> str:
        """persona 扩展字段（style/examples/banned_words/catchphrases）编译为注入文本块。"""
        lines: list[str] = []
        style = persona.get("style") if isinstance(persona.get("style"), dict) else {}
        directives = cls._persona_style_directives(style)
        if directives:
            lines.append(texts.t("style_line", value=directives))
        banned = [str(w) for w in (persona.get("banned_words") or []) if str(w).strip()]
        if banned:
            lines.append(texts.t("persona_banned_words", words=", ".join(banned)))
        catchphrases = [str(w) for w in (persona.get("catchphrases") or []) if str(w).strip()]
        if catchphrases:
            lines.append(texts.t("persona_catchphrases", phrases=", ".join(catchphrases)))
        examples = [e for e in (persona.get("examples") or []) if isinstance(e, dict)]
        if examples:
            blocks = [texts.t("persona_examples_header")]
            for item in examples:
                user = str(item.get("user") or "").strip()
                assistant = str(item.get("assistant") or "").strip()
                if user:
                    blocks.append(f"User: {user}")
                if assistant:
                    blocks.append(f"Assistant: {assistant}")
            lines.append("<persona-examples>\n" + "\n".join(blocks) + "\n</persona-examples>")
        return "\n".join(lines)

    def build_system_parts(
        self,
        persona: dict,
        scene: str = "",
        chat_key: str = "",
        active_skills: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        kb_query: str = "",
        profile_user: str = "",
        kb_texts: list[str] | None = None,
    ) -> list[SystemPart]:
        """系统提示词按语义拆分为部件（供 ContextPacker 按优先级装填）。"""
# 首行人格身份认知 + 主人称呼（并入 persona 部件，required 保位）
        persona_text = (
            texts.t("persona_identity", name=str(persona.get("name") or ""), id=str(persona.get("id") or ""))
            + "\n" + persona["system"] + "\n" + utils.time_line()
        )
        owner_title = str(persona.get("owner_title") or "").strip()
        if owner_title:
            persona_text += "\n" + texts.t("owner_title_line", title=owner_title)
        parts: list[SystemPart] = [
            SystemPart("persona", persona_text, required=True),
            SystemPart("capability", CAPABILITY_PROMPT + "\n" + texts.t("system_brevity"), required=True),
        ]
# 扩展字段独立部件（PRIORITY 未收录 persona_extra → pack 兜底按 extra 优先级稳定排序，
# 插在 extra 类部件之前；不预算时按列表顺序紧跟 persona 呈现）
        persona_extra = self._persona_extra_text(persona)
        if persona_extra:
            parts.insert(1, SystemPart("persona_extra", persona_extra))
        if getattr(self.config, "reply_narrate", False):
            parts.append(SystemPart("narrate", NARRATE_PROMPT))
        if getattr(self.config, "skill_induct", True):
            parts.append(SystemPart("skill_offer", SKILL_OFFER_NOTE))
        if scene:
            parts.append(SystemPart("scene", scene))
        if chat_key:
            summary = self.summary_of(chat_key)
            if summary:
                parts.append(SystemPart("summary", "Earlier conversation summary (older than recent messages):\n" + summary))
            facts = self.facts_of(chat_key)
            if facts:
                parts.append(SystemPart("facts", texts.t("facts_header") + "\n" + "\n".join(f"- {f}" for f in facts)))
# 跨会话用户画像注入（profile_user = platform:uid；PRIORITY 位于 facts 与 memory 之间）
        if profile_user and getattr(self.config, "profile_enabled", True):
            lines = self.profile.digest(profile_user)
            if lines:
                parts.append(SystemPart("profile", texts.t("profile_header") + "\n" + "\n".join(f"- {line}" for line in lines)))
        skills = getattr(self.main, "skills", None)
        if skills:
            if active_skills:
                for name in active_skills:
                    skill = skills.get_skill(str(name))
                    if not skill:
                        continue
                    parts.append(
                        SystemPart(
                            "skill_full",
                            "<active-skill name=\"" + str(name) + "\">\n"
                            + utils.truncate(str(skill.get("body") or ""), 8000)
                            + "\n</active-skill>",
                        )
                    )
            enabled = [s for s in skills.list_skills() if s.get("enabled")]
            if enabled:
                lines = "\n".join(f"- {s['name']}: {s.get('description') or ''}" for s in enabled)
                parts.append(SystemPart("skill_list", "<skills>\n" + texts.t("skills_system_note") + "\n" + lines + "\n</skills>"))
        if mcp_tools:
            tools_hint = [str(t) for t in mcp_tools if str(t)]
            if tools_hint:
                parts.append(SystemPart("extra", texts.t("dashboard_mcp_hint", tools=", ".join(tools_hint))))
        if getattr(self.config, "kb_auto_inject", True) and kb_query:
            kb = getattr(self.main, "knowledge", None)
            hits = kb.search(kb_query, top_k=int(getattr(self.config, "kb_top_k", 2) or 0)) if kb else []
# Lorebook：最近上下文命中触发条目优先排前合并注入（[triggered] 标记，同条目去重）
            lore = kb.triggered(kb_texts or []) if (kb and kb_texts) else []
            hit_ids = {e.get("id") for e in lore}
            hits = [h for h in hits if h.get("id") not in hit_ids]
            if hits or lore:
                lore_blocks = [
                    f"<kb-doc title=\"{h.get('title', '')} [triggered]\">\n{utils.truncate(str(h.get('content') or ''), 1500)}\n</kb-doc>"
                    for h in lore
                ]
                hit_blocks = [f"<kb-doc title=\"{h['title']}\">\n{h['snippet']}\n</kb-doc>" for h in hits]
                parts.append(SystemPart("kb", texts.t("kb_system_note") + "\n" + "\n\n".join(lore_blocks + hit_blocks)))
        for line in getattr(self.config, "extra_prompts", []) or []:
            line = str(line).strip()
            if line:
                parts.append(SystemPart("extra", line))
        return parts

    def build_system(
        self,
        persona: dict,
        scene: str = "",
        chat_key: str = "",
        active_skills: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        kb_query: str = "",
    ) -> str:
# 兼容层：原字符串拼接入口改为部件 join
        parts = self.build_system_parts(
            persona,
            scene=scene,
            chat_key=chat_key,
            active_skills=active_skills,
            mcp_tools=mcp_tools,
            kb_query=kb_query,
        )
        return "\n".join(p.text for p in parts if p.text)


    async def resolve_session_names(self, sessions: list[dict]) -> None:

        for session in sessions[:20]:
            chat_key = str(session.get("chat_key") or "")
            if session.get("name") or not chat_key:
                continue
            platform = str(session.get("platform") or "")
            detail_type = str(session.get("detail_type") or "")
            target_id = str(session.get("target_id") or "")
            if platform == DASHBOARD_PLATFORM or not platform or not target_id:
                continue
            try:
                adapter = self.sdk.adapter.get(platform)
            except Exception:
                adapter = None
            if adapter is None:
                continue
            name = ""
            try:
                if detail_type == "group":
                    info = await asyncio.wait_for(
                        adapter.call_api("get_group_info", group_id=target_id), 6
                    )
                    name = str((info or {}).get("group_name") or "") if isinstance(info, dict) else ""
                    if name:
                        self.set_group_name(chat_key, name)
                else:
                    for endpoint in ("get_stranger_info", "get_user_info"):
                        try:
                            info = await asyncio.wait_for(
                                adapter.call_api(endpoint, user_id=target_id), 6
                            )
                        except Exception:
                            continue
                        if isinstance(info, dict):
                            name = str(info.get("nickname") or info.get("card") or "")
                            if name:
                                break
                    if name:
                        self.set_user_name(chat_key, name)
            except Exception:
                continue

    async def title_task(self, chat_key: str, user_text: str, reply: str) -> None:

        pool = getattr(self.main, "pool", None)
        if pool is None:
            return
        from ..engine.base import ChatRequest

        request = ChatRequest(
            messages=[
                {"role": "system", "content": texts.t("title_system")},
                {
                    "role": "user",
                    "content": utils.truncate(user_text, 200) + "\n---\n" + utils.truncate(reply, 300),
                },
            ],
            max_tokens=48,
            temperature=0.3,
        )
        try:
# 标题生成迁 dispatch(kind="title", prefer="cheap")
            dispatch = getattr(pool, "dispatch", None)
            if callable(dispatch):
                resp = await dispatch(TaskSpec(kind="title", prefer="cheap"), request)
            else:
                resp = await pool.chat(request)
            title = (resp.content or "").strip().strip("\"“”‘’。.!!??")
            title = title.splitlines()[0][:40] if title else ""
            if title:
                self.set_group_name(chat_key, title)
        except Exception as e:
            self.main.logger.warning(f"title generation failed: {e}")


    def save_upload(self, name: str, data: str) -> str | None:

        payload: bytes | None = None
        m = _re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data, _re.DOTALL)
        if m and m.group(2):
            try:
                payload = _base64.b64decode(m.group(3))
            except Exception:
                return None
        elif m:
            payload = _unquote(m.group(3)).encode("utf-8", "replace")
        else:
            payload = data.encode("utf-8", "replace")
        if payload is None:
            return None
        digest = _hashlib.sha256(payload).hexdigest()[:16]
        safe = _re.sub(r"[^\w.\-]+", "_", name, flags=_re.UNICODE).strip("_") or "file"
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            for existing in UPLOAD_DIR.iterdir():
                if existing.is_file() and existing.name.startswith(digest + "_"):
                    return str(existing)
            target = UPLOAD_DIR / f"{digest}_{safe}"
            target.write_bytes(payload)
        except OSError:
            return None
        return str(target)

    def rebuild_user_content(self, text: str, attachments: list):

        parts: list = []
        notes: list[str] = []
        if text:
            parts.append({"type": "text", "text": text})
        for att in attachments or []:
            if not isinstance(att, dict):
                continue
            name = str(att.get("name") or "file")
            mime = str(att.get("mime") or "").lower()
            data = str(att.get("data") or "")
            if not data:
                continue
            if mime.startswith("image/") and len(parts) < 4 and len(data) <= 7_000_000:
                url = data if data.startswith("data:") else f"data:{mime};base64,{data}"
                parts.append({"type": "image_url", "image_url": {"url": url}})
                continue
            saved = self.save_upload(name, data)
            if saved:
                size = Path(saved).stat().st_size
                notes.append(texts.t("attachment_saved", name=name, path=saved, size=size))
            else:
                notes.append(f"[attachment {name}]（保存失败，内容不可用）")
        if notes:
            tail = "\n\n".join(notes)
            if parts and parts[0].get("type") == "text":
                parts[0]["text"] = (parts[0]["text"] + "\n\n" + tail).strip()
            else:
                parts.insert(0, {"type": "text", "text": tail})
        if not parts:
            return text or ""
        if len(parts) == 1 and parts[0].get("type") == "text":
            return parts[0]["text"]
        return parts


    @staticmethod
    def _text_of(content) -> str:
        if isinstance(content, list):
            return " ".join(
                str(p.get("text") or "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        return str(content or "")
