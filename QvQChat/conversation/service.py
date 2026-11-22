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
from ..prompts import CAPABILITY_PROMPT, SKILL_OFFER_NOTE
from .budget import ContextPacker, SystemPart
from .compactor import Compactor, context_tokens, estimate_tokens, extract_facts
from .policy import get_policy

# 存储/上传常量本体已迁 repository.py / assembler.py（M6-4）；此处 re-export 保兼容
from .repository import (  # noqa: F401 — 键名/key 工具/SEED 常量本体已迁 repository.py，此处 re-export 保兼容
    CONV_PREFIX, ROUTES_KEY, IDENTITY_MAP_KEY, CONV_INDEX_KEY, USER_SEEN_PREFIX, USER_SEEN_MAX,
    DASHBOARD_PLATFORM, make_chat_key, parse_chat_key, strip_isolation, strip_account, account_of,
    SEED_BOT_PREFIXES, SEED_HEADER_PREFIXES, LOW_TOKEN_CONTENT_CHARS,
    SessionRepository,
)
from .assembler import PromptAssembler

# H6 记忆回捞提示的最近使用时间（uid → ts）
RECALL_LAST_PREFIX = "QvQChat:recall_last:"

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
# 懒构造子仓（见下方 profile/todos/user_mutes 属性）：__init__ 不触发 KV 读
        self._profile = None
        self._todos = None
        self._user_mutes = None
# 启动后首次访问会话索引时做一次全量对账
# 存储半区（repository）与装配半区（assembler）：M6-4 拆出，公开方法经 __getattr__ 转发
        self.repository = SessionRepository(self)
        self.assembler = PromptAssembler(self)

    @property
    def profile(self):
        """跨会话用户画像（ProfileStore，懒构造；实现在 conversation/profile.py）。"""
        if self._profile is None:
            from .profile import ProfileStore

            self._profile = ProfileStore(self.main)
        return self._profile

    @property
    def todos(self):
        """会话级 TODO 清单（TodoStore，懒构造；实现在 conversation/todo.py）。"""
        if self._todos is None:
            from .todo import TodoStore

            self._todos = TodoStore(self.sdk, self.config)
        return self._todos

    @property
    def user_mutes(self):
        """用户级屏蔽（UserMuteStore，懒构造；实现在 conversation/usermute.py）。"""
        if self._user_mutes is None:
            from .usermute import UserMuteStore

            self._user_mutes = UserMuteStore(self.sdk, self.config)
        return self._user_mutes



    def _admin_ids_for(self, platform: str) -> list[str]:
        """当前平台的管理员 id（配置 admins 原序在前 + 框架主人表追加）。

        原序保留：admins 是运营方排好的权限名单，字典序重排会让"第一个"漂移
        到别人身上（请求上报/受限提示的"负责管理员"都依赖首元素）。
        """
        ids: list[str] = []
        seen: set[str] = set()
        for x in (getattr(self.config, "admins", []) or []):
            uid = str(x).strip()
            if uid and uid not in seen:
                ids.append(uid)
                seen.add(uid)
        try:
            from ..Main import framework_masters

            g, p = framework_masters()
            extra = {str(x) for x in g} | {str(x) for x in (p.get(platform) or set())}
            for uid in sorted(extra):
                if uid not in seen:
                    ids.append(uid)
                    seen.add(uid)
        except Exception:
            pass
        return ids

    def notify_admin_ids_for(self, platform: str) -> list[str]:
        """上报/求助通知的目标：notify_admins 配置优先（保序、全部通知）；
        留空回落 admins+主人的第一个——挂名管理员不收上报也不在权限提示里暴露。"""
        notify = [str(x).strip() for x in (getattr(self.config, "notify_admins", []) or []) if str(x).strip()]
        if notify:
            return notify
        return self._admin_ids_for(platform)[:1]

    def __getattr__(self, name):
# M6-4 拆分转发：repository（存储半区）/ assembler（装配半区）的方法经属性
# 转发保持公开签名不变（get_contexts/append/build_system_parts/身份迁移等）。
# __getattr__ 只在常规查找失败时触发——本类自有方法/属性优先。
# 用 self.__dict__ 探测协作对象（getattr 会再次触发本方法，构造期死循环）。
        for attr_name in ("repository", "assembler"):
            holder = self.__dict__.get(attr_name)
            if holder is None:
                continue
            try:
                return getattr(holder, name)
            except AttributeError:
                pass
        raise AttributeError(name)

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

    def group_style_of(self, chat_key: str) -> str:
        state = self._state(chat_key)
        style = state.get("group_style")
        return str(style.get("text") or "") if isinstance(style, dict) else ""

    def set_group_style(self, chat_key: str, text: str) -> None:
        state = self._state(chat_key)
        state["group_style"] = {"text": str(text or "").strip()[:160], "ts": utils.now_ts()}
        self._save_no_touch(chat_key, state)

    def set_group_name(self, chat_key: str, name: str) -> None:
        state = self._state(chat_key)
        state["group_name"] = name
        self._save(chat_key, state)

    def _recall_hint_allowed(self, chat_key: str, text: str, user_id: str) -> bool:
        """H6：回捞提示准入——仅对方先开口的回合 + 每用户冷却。"""
        hours = float(getattr(self.config, "humanize_recall_interval_hours", 72) or 0)
        if hours <= 0:
            return False
        if getattr(self.config, "humanize_recall_on_cold_only", True) and not str(text or "").strip():
            return False
        if not user_id:
            return False
        try:
            last = float(self.sdk.storage.get(RECALL_LAST_PREFIX + str(user_id), 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        return (utils.now_ts() - last) >= hours * 3600

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

# ===== 会话健康体检：体积/残留指标（强化压缩与清理入口的数据面） =====

    def health_of(self, chat_key: str) -> dict:
        """会话健康体检：上下文体量与残留计数（只读不修改）。

        指标：条数/字符量、工具残留(rounds/trace)条数、超长正文条数。
        强化压缩（compact force）会把整段历史浓缩为摘要小作文，这些
        残留随之消失——体检用于排序与前后对比。
        """
        contexts = self.get_contexts(chat_key)
        messages = [c for c in contexts if isinstance(c, dict)]
        chars = sum(len(self._text_of(c.get("content"))) for c in messages)
        residue = sum(1 for c in messages if c.get("rounds") or c.get("trace"))
        oversized = sum(1 for c in messages if len(self._text_of(c.get("content"))) > 2400)
        return {
            "chat_key": chat_key,
            "messages": len(messages),
            "chars": chars,
            "tool_residue": residue,
            "oversized": oversized,
            "healthy": not (residue or oversized or chars > 200_000),
        }

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
        self.todos.clear(chat_key)
        self.user_mutes.clear(chat_key)
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
                    "name": str(state.get("name") or "")
                    or str(state.get("group_name") or "")
                    or str(state.get("user_name") or ""),
                    "persona": state["persona"],
                    "turns": len(state["contexts"]),
                    "updated": state["updated"],
                    "preview": preview,
                    "pinned": bool(state.get("pinned")),
                    "archived": bool(state.get("archived")),
                    "listen_off": bool(state.get("listen_off")),
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
        user_mem_key: str = "",
        persist: bool = True,
        debug: bool = False,
    ) -> dict:


        await self.compact_if_needed(chat_key)
        contexts = self.get_contexts(chat_key)
# 低token模式：显式开关（会话 low_token / 全局 budget_mode）或超限自动进入
# （budget_auto_on_limit）——系统提示跳过重组件、历史窗口收紧、预算装填自动启用；
# 人格与任务连续性部件保留，发言风格不变，省的是输入 token 总量
        from .policy import budget_effective

        low_token = budget_effective(self.sdk, self.config, chat_key)
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
# 纵深防御：seed 里混入"本次输入同文本"的行时剔除——否则实时链路随后
# 再 append 一次，同一消息在会话里出现两份（webui 可见的重复注入）
                current_fp = self._seed_fp_of(text)
                seeded = [
                    row for row in seeded
                    if self._seed_fp_of(str(row.get("content") or "")) != current_fp
                ]
            if seeded:
                contexts = self.seed_contexts(chat_key, seeded)
                seeded_done = bool(contexts)
# 低token模式收紧历史：条数减半 + 单条截 300 字（放在 seed 之后，回填的历史一并收紧）
        if low_token and contexts:
            half = max(1, len(contexts) // 2)
            tightened = []
            for entry in contexts[-half:]:
                if not isinstance(entry, dict):
                    tightened.append(entry)
                    continue
                content = entry.get("content")
                if isinstance(content, list):
# 拷贝再截（storage 读出的对象可能与持久层共享引用）；只截 text part，image_url 结构原样保留
                    entry = dict(entry)
                    entry["content"] = [
                        dict(p, text=str(p.get("text") or "")[:LOW_TOKEN_CONTENT_CHARS])
                        if isinstance(p, dict) and p.get("type") == "text"
                        and len(str(p.get("text") or "")) > LOW_TOKEN_CONTENT_CHARS else p
                        for p in content
                    ]
                elif isinstance(content, str) and len(content) > LOW_TOKEN_CONTENT_CHARS:
                    entry = dict(entry, content=content[:LOW_TOKEN_CONTENT_CHARS])
                tightened.append(entry)
            contexts = tightened
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
            restricted=self._sender_restricted(sender_id, profile_user),
            admin_ids=(self.notify_admin_ids_for(str(profile_user or "").split(":", 1)[0])[:1]
                       if self._sender_restricted(sender_id, profile_user) else None),
            low_token=low_token,
        )
        if recalled:
            lines = "\n".join(f"- {entry.get('content', '')}" for entry in recalled)
            parts.append(SystemPart("memory", texts.t("memory_header") + "\n" + lines))
        # 用户级跨会话记忆（仅私聊传入 user_mem_key 时注入）
        if memory is not None and user_mem_key:
            try:
                user_recalled = memory.recall(
                    user_mem_key, query=self._text_of(text), limit=int(getattr(self.config, "memory_recall", 6)) or 6
                ) or []
            except Exception:
                user_recalled = []
            if user_recalled:
                ulines = "\n".join(f"- {entry.get('content', '')}" for entry in user_recalled)
                parts.append(SystemPart("user_memory", texts.t("user_memory_header") + "\n" + ulines))
# H6 记忆回捞钩子：相关记忆命中且距上次提及超过冷却时，允许自然带一句「记得你」；
# 冷却内/非对方先开口的回合不提旧事（禁止沉默期主动翻旧账）
        if recalled and self._recall_hint_allowed(chat_key, text, sender_id or cross_user_id):
            parts.append(SystemPart("recall_hint", texts.t("recall_hint_note")))
            try:
                self.sdk.storage.set(RECALL_LAST_PREFIX + str(sender_id or cross_user_id), utils.now_ts())
            except Exception:
                pass
        user_msg: dict = {"role": "user", "content": text}
        if images:
            pool = getattr(self.main, "pool", None)
            caps = {}
            try:
                caps = pool.primary_capabilities() if pool else {}
            except Exception:
                caps = {}
            if caps.get("vision") is False:
# 对话路径：识别失败也要给模型一个明确的"看不见"，而不是静默丢图
                described = await pool.describe_images(images, on_error="text") if pool else []
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
# 低token模式自动启用预算装填：上下文是 token 消耗的大头，低token态下按模型窗口装填
# 并对溢出触发压缩（显式配了 tokens 的场景不受影响——显式配置优先于自动行为）
        if mode == "off" and low_token:
            mode = "auto"
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
        pack_stats: dict = {}
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
            pack_stats = packed.stats
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
            "debug": {
                "parts": [
                    {"kind": p.kind, "chars": len(p.text or ""), "required": p.required, "preview": str(p.text or "")[:120]}
                    for p in parts if p.text
                ],
                "packer": pack_stats,
                "pack_enabled": pack_enabled,
                "model_length": model_length,
                "low_token": low_token,
            } if debug else {},
        }

    def _resolve_chat_model(self) -> dict | None:
        """预取本会话主对话将选中的模型（kind="chat"），保证装填与 runner 选型一致。"""
        pool = getattr(self.main, "pool", None)
        resolver = getattr(pool, "resolve_task_model", None)
        if not callable(resolver):
            return None
        try:
            return resolver(TaskSpec(kind="chat", chat_key=chat_key))
        except Exception:
            return None

    @staticmethod
    def _persist_sender(chat_key: str, cross_user_id: str, sender_id: str = "") -> str:
        platform, detail_type, _ = parse_chat_key(chat_key)
        if platform == DASHBOARD_PLATFORM:
            return "dashboard"
# 群聊也持久化发言者 uid（缺失会导致历史消息无法归因）
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
        user_id: str = "",
        skip_append: bool = False,
        origin: str = "chat",
    ) -> str:

        if not skip_append:
            meta: dict = {}
            if model:
                meta["model"] = str(model)
            if isinstance(usage, dict) and usage:
# 只留小体量的 token 计数；聚合口径仍走 record_usage（日用量/成本），条目里只留
# 本条消息的出处，前端/命令侧可查"这条是哪个模型答的、花了多少"
                meta["usage"] = {
                    k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
                    if isinstance(usage.get(k), (int, float))
                }
            self.append(chat_key, "assistant", reply, trace=trace, rounds=rounds, meta=meta or None)
        if usage:
# 用户维度记账（user_daily_budget 配额读 by_user）
            if user_id:
                usage = dict(usage)
                usage["user_id"] = user_id
            self.main.record_usage(chat_key, usage, model, origin=origin)
        overflow = self.trim_overflow(chat_key, keep=max(2, int(getattr(self.config, "context_limit", 30))))
        if overflow:
            self.main.spawn(self._summarize_overflow(chat_key, overflow))
        if title_from and not self.group_name_of(chat_key):
            self.main.spawn(self.title_task(chat_key, title_from, reply))
# 群语气学习（两段式）：首次 30 轮尽快入乡随俗，之后 120 轮才慢刷一次——
# 群风格基本固定（一个月都不变），不用频繁同步（state["group_style_turn"] 防重复触发）
        first = int(getattr(self.config, "group_style_first_turns", 30) or 0)
        refresh = int(getattr(self.config, "group_style_refresh_turns", 120) or 0)
        if (
            first > 0
            and bool(getattr(self.config, "group_style_learn", True))
            and ":group:" in str(chat_key)
        ):
            state = self._state(chat_key)
            turns = int(state.get("turns") or 0)
            last_learned = int(state.get("group_style_turn") or 0)
            if last_learned == 0:
                due = turns >= first
            else:
                due = refresh > 0 and turns - last_learned >= refresh
            if due and turns > 0:
                state["group_style_turn"] = turns
                self._save_no_touch(chat_key, state)
                self.main.spawn(self.learn_group_style(chat_key))
        return reply

    async def _summarize_overflow(self, chat_key: str, removed: list) -> None:
# 高负载降载：满载时跳过压缩——removed 条目仍在上下文里，下轮 trim 会再次触发
        pool = getattr(self.main, "pool", None)
        if pool is not None and callable(getattr(pool, "background_blocked", None)) and pool.background_blocked():
            self.main.logger.debug("background skip: overflow-summary (saturated)")
            return
        summary = await self.compactor.summarize_entries(removed)
        if not summary:
            return
# 分离 <facts> 段（宽松解析，失败不入库）
        clean, facts = extract_facts(summary)
        if facts and getattr(self.config, "facts_extract", True):
            self.append_facts(chat_key, facts)
# 压缩沉淀：关键事实同步进长期记忆（source=auto，随遗忘曲线淡出）——
# 会话 facts/summary 只在本会话生效，跨天回忆检索靠记忆库
        if facts and bool(getattr(self.config, "compact_to_memory", True)):
            memory = getattr(self.main, "memory", None)
            if memory is not None:
                for fact in facts:
                    try:
                        memory.remember(chat_key, fact.split("|", 1)[-1].strip()[:200],
                                        category="auto", importance=3, source="auto")
                    except Exception:
                        pass
# TODO 类 facts 双写 TodoStore（执行面单源）：压缩抽出的待办进清单，
# AI 面板都能看到并推进；画像侧保留 TODO fact 作历史轨迹
        todo_items = [f.split("|", 1)[1].strip() for f in facts if f.startswith("TODO|")]
        if todo_items:
            try:
                for item in todo_items:
                    self.todos.add(chat_key, item)
            except Exception:
                pass
        self.append_summary(chat_key, clean or summary)


    @staticmethod
    def _seed_fp_of(text: str) -> str:
        """seed 去重指纹：剥掉 label_incoming 的发言者标注后取尾部（与裸文本可比）。"""
        s = str(text or "").strip()
        s = _re.sub(r"^\[[^\]]*\]\s*", "", s)
        s = _re.sub(r"^[^\[\n]{1,40}\(\d{5,}\):\s*", "", s)
        s = _re.sub(r"^\(\d{5,}\):\s*", "", s)
        return s[-200:]

    @staticmethod
    def _text_of(content) -> str:
        return utils.content_text(content)
