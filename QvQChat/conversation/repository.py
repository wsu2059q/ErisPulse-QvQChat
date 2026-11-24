"""会话仓库（ConversationService 的存储半区）：状态读写/索引/上下文/身份迁移。

从 service.py 拆出（M6-4）：方法体逐字搬运，语义不变。会话级编排（prepare/
finalize/summary/facts）留在 service，存储面（KV 形状/索引/倒排/身份映射）在此。
通过 back-ref 取 sdk/main；KV 键名与值形状逐字节不变。
"""
from __future__ import annotations

import re as _re

from .. import texts, utils

CONV_PREFIX = "QvQChat:conv:"
ROUTES_KEY = "QvQChat:routes"
IDENTITY_MAP_KEY = "QvQChat:identity_map"
# 会话索引（单键 list[chat_key]，list_sessions/create 免全库 keys() 扫描）
CONV_INDEX_KEY = "QvQChat:conv_index"
# 用户→群会话倒排（recent_user_messages 免全库扫描）
USER_SEEN_PREFIX = "QvQChat:user_seen:"
USER_SEEN_MAX = 20

DASHBOARD_PLATFORM = "dashboard"
# 低token模式（low_token）单条历史截断字数——人格/TODO 等关键提示不在此列，只削历史
LOW_TOKEN_CONTENT_CHARS = 300


def _translation_values(key: str) -> tuple[str, ...]:
    table = texts.STRINGS.get(key, {})
    return tuple(str(value) for value in table.values() if value)


# 历史回填曾把标注写进 assistant 正文，模型会复读；读取时统一清理旧数据
SEED_BOT_PREFIXES = tuple(f"[{value}] " for value in _translation_values("seed_bot_note"))
SEED_HEADER_PREFIXES = tuple(f"{value}\n" for value in _translation_values("seed_history_header"))


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


def strip_account(chat_key: str) -> str:
    """剥离账户隔离后缀（platform:group:123@bot_a → platform:group:123）。

    @账户 后缀只用于会话/人格/记忆隔离；发送目标必须还原成纯 id。
    """
    text = str(chat_key or "")
    return text.rsplit("@", 1)[0] if "@" in text.rsplit(":", 2)[-1] else text


def account_of(chat_key: str) -> str:
    """取账户隔离后缀（无则空串）。"""
    text = str(chat_key or "")
    tail = text.rsplit(":", 2)[-1]
    return tail.rsplit("@", 1)[1] if "@" in tail else ""


class SessionRepository:
    """存储半区：_state/_save/索引/contexts/append/倒排/路由/身份迁移。"""

    def __init__(self, svc):
        self.svc = svc
# 启动后首次访问会话索引时做一次全量对账
        self._index_ready = False

    @property
    def sdk(self):
        return self.svc.sdk

    @property
    def main(self):
        return self.svc.main

    @property
    def config(self):
        return self.svc.config

    async def _state(self, chat_key: str) -> dict:
        return self._normalize_state(await self.sdk.storage.aget(CONV_PREFIX + chat_key, None))

    @staticmethod
    def _normalize_state(raw) -> dict:
        state = raw if isinstance(raw, dict) else {}
        contexts = state.get("contexts")
        if not isinstance(contexts, list):
            contexts = []
        cleaned: list = []
        for entry in contexts:
            if not isinstance(entry, dict):
                cleaned.append(entry)
                continue
            content = entry.get("content")
            if isinstance(content, str):
                for prefix in SEED_HEADER_PREFIXES:
                    if content.startswith(prefix):
                        content = content[len(prefix):]
                        break
                if entry.get("role") == "assistant":
                    for prefix in SEED_BOT_PREFIXES:
                        if content.startswith(prefix):
                            content = content[len(prefix):]
                            break
                entry["content"] = content
            # 空文本条目清洗：assistant 若带 rounds/trace（只调了工具、没说话）必须保留，
            # 否则读取时会被丢掉，导致"刷新后最后一条变回用户发言"、轮次也不对齐
            if (
                entry.get("role") in ("user", "assistant")
                and isinstance(entry.get("content"), str)
                and not entry["content"].strip()
                and not entry.get("rounds")
                and not entry.get("trace")
            ):
                continue
            cleaned.append(entry)
        state["contexts"] = cleaned
# facts 列表懒迁移
        if not isinstance(state.get("facts"), list):
            state["facts"] = []
        state.setdefault("persona", None)
        state.setdefault("updated", 0.0)
        return state

    async def _save(self, chat_key: str, state: dict) -> None:
        state["updated"] = utils.now_ts()
        limit = max(2, int(getattr(self.config, "context_limit", 30))) * 2
        state["contexts"] = state["contexts"][-limit:]
        await self.sdk.storage.aset(CONV_PREFIX + chat_key, state)
        await self._index_add(chat_key)

    async def _save_no_touch(self, chat_key: str, state: dict) -> None:
        limit = max(2, int(getattr(self.config, "context_limit", 30))) * 2
        state["contexts"] = state["contexts"][-limit:]
        await self.sdk.storage.aset(CONV_PREFIX + chat_key, state)
        await self._index_add(chat_key)

# ===== 会话索引（单键 list[chat_key]，免全库 keys() 扫描） =====

    def _index_load(self) -> list[str] | None:
        """读索引；损坏/缺失返回 None（调用方回退 keys() 扫描自愈）。"""
        data = self.sdk.storage.get(CONV_INDEX_KEY, None)
        if not isinstance(data, list):
            return None
        return [str(k) for k in data if isinstance(k, str) and k]

    def _index_save(self, keys: list[str]) -> None:
        self.sdk.storage.set(CONV_INDEX_KEY, keys)

    async def _index_add(self, chat_key: str) -> None:
        """会话键落盘时同步维护索引（去重）。索引损坏时先全量对账，防止单键索引覆盖其余会话。"""
        index = await self.a_index_load()
        if index is None:
            index = await self.rebuild_index()
        if chat_key in index:
            return
        await self.a_index_save(index + [chat_key])

    async def _index_remove(self, chat_key: str) -> None:
        index = self._index_load()
        if index is None or chat_key not in index:
            return
        self._index_save([k for k in index if k != chat_key])

    async def rebuild_index(self) -> list[str]:
        """全量对账：keys() 扫描 vs 索引差集修复（首访一次；索引缺失/失同步时自愈）。"""
        scanned = sorted(
            key[len(CONV_PREFIX):]
            for key in await self.sdk.storage.aget_all_keys()
            if isinstance(key, str) and key.startswith(CONV_PREFIX)
        )
        index = await self.a_index_load()
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
        await self.a_index_save(scanned)
        self._index_ready = True
        return scanned

    async def _session_keys(self) -> list[str]:
        """取会话键全集：索引优先；首访全量对账一次；索引损坏回退全表扫描并自愈。"""
        if not self._index_ready:
            await self.rebuild_index()
        index = await self.a_index_load()
        if index is not None:
            return index
        self.main.logger.debug("conv_index unreadable, falling back to storage scan")
        scanned = sorted(
            key[len(CONV_PREFIX):]
            for key in await self.sdk.storage.aget_all_keys()
            if isinstance(key, str) and key.startswith(CONV_PREFIX)
        )
        await self.a_index_save(scanned)
        return scanned

# ===== 索引异步门面（事件循环内的调用走这里；同步版留给启动/迁移路径） =====

    async def a_index_load(self) -> list[str] | None:
        data = await self.sdk.storage.aget(CONV_INDEX_KEY, None)
        if not isinstance(data, list):
            return None
        return [str(k) for k in data if isinstance(k, str) and k]

    async def a_index_save(self, keys: list[str]) -> None:
        await self.sdk.storage.aset(CONV_INDEX_KEY, keys)

    async def a_index_add(self, chat_key: str) -> None:
        """a_save 路径的索引维护（去重）；索引缺失时以单键索引落盘（首次会话场景）。"""
        index = await self.a_index_load()
        if index is None:
            index = [chat_key]
        elif chat_key not in index:
            index = index + [chat_key]
        else:
            return
        await self.a_index_save(index)

    async def a_index_remove(self, chat_key: str) -> None:
        index = await self.a_index_load()
        if index is None or chat_key not in index:
            return
        await self.a_index_save([k for k in index if k != chat_key])

    async def a_session_keys(self) -> list[str]:
        """list_sessions 专用：索引优先；首访全量对账一次；索引缺失/损坏回退
        全表键扫描并写回自愈（与同步 _session_keys 同款语义，走异步存储 API）。"""
        index = await self.a_index_load()
        if index is not None and self._index_ready:
            return index
        scanned = sorted(
            key[len(CONV_PREFIX):]
            for key in await self.sdk.storage.aget_all_keys()
            if isinstance(key, str) and key.startswith(CONV_PREFIX)
        )
        if index is None or sorted(index) != scanned:
            await self.a_index_save(scanned)
            self._index_ready = True
            return scanned
        self._index_ready = True
        return index

    async def a_state(self, chat_key: str) -> dict | None:
        raw = await self.sdk.storage.aget(CONV_PREFIX + chat_key, None)
        return self._normalize_state(raw) if isinstance(raw, dict) else None

    async def a_user_seen(self, uid: str) -> list[dict] | None:
        """读倒排（异步）；损坏/缺失返回 None（调用方回退全表扫描）。"""
        data = await self.sdk.storage.aget(USER_SEEN_PREFIX + uid, None)
        if not isinstance(data, list):
            return None
        return [item for item in data if isinstance(item, dict) and isinstance(item.get("chat_key"), str) and item["chat_key"]]


    async def get_contexts(self, chat_key: str) -> list:
        return list((await self._state(chat_key))["contexts"])

    async def replace_contexts(self, chat_key: str, contexts: list) -> None:
        state = await self._state(chat_key)
        state["contexts"] = list(contexts)
        await self._save(chat_key, state)

    async def seed_contexts(self, chat_key: str, seed: list) -> list:
        state = await self._state(chat_key)
        if state["contexts"]:
            return list(state["contexts"])
        state["contexts"] = list(seed)
        await self._save(chat_key, state)
        return list(seed)

    async def append(self, chat_key: str, role: str, content, trace: list | None = None, rounds: list | None = None, meta: dict | None = None) -> None:
        state = await self._state(chat_key)
        entry: dict = {"role": role, "content": content, "ts": utils.now_ts()}
        if meta:
            entry["meta"] = dict(meta)
# rounds 已含同轮的工具明细与正文，trace 再存一份是纯冗余（前端有 rounds 时不读 trace）——不双写
        if trace and not rounds:
            entry["trace"] = list(trace)
        if rounds:
# persist_thinking=False 时剥离 think 块（省存储；历史不显示已思考）
            if not getattr(self.config, "persist_thinking", True):
                rounds = [{k: v for k, v in r.items() if k in ("text", "tools")} if isinstance(r, dict) else r for r in rounds]
            entry["rounds"] = list(rounds)
            if bool(getattr(self.config, "log_debug", False)):
                logger = getattr(self.main, "logger", None)
                if logger is not None:
                    shape = [
                        {"len": len(r.get("text") or ""), "tools": len(r.get("tools") or []),
                         "think": len(r.get("think") or "")} for r in rounds if isinstance(r, dict)
                    ]
                    logger.debug(f"persist assistant ({chat_key}): rounds={shape} trace={'dropped' if trace else 'n/a'}")
        state["contexts"].append(entry)
        await self._save(chat_key, state)

    async def append_user(self, chat_key: str, content, sender_id: str = "") -> None:

        state = await self._state(chat_key)
        entry: dict = {"role": "user", "content": content, "ts": utils.now_ts()}
        if sender_id:
            entry["sender"] = sender_id
        state["contexts"].append(entry)
        state["turns"] = int(state.get("turns") or 0) + 1
        await self._save(chat_key, state)
        if sender_id:
            await self._user_seen_record(sender_id, chat_key, self.svc._text_of(content))

    async def pop_last_exchange(self, chat_key: str) -> str:
        """F2 重新生成：弹出末尾的 assistant 与其前一条 user 消息，返回该 user 文本。

        末条非 assistant（如进行中/异常残留）时不动，返回空串。
        """
        state = await self._state(chat_key)
        contexts = state["contexts"]
        if not contexts or contexts[-1].get("role") != "assistant":
            return ""
        contexts.pop()
        text = ""
        if contexts and contexts[-1].get("role") == "user":
            text = self.svc._text_of(contexts[-1].get("content"))
            contexts.pop()
        await self._save(chat_key, state)
        return text

    async def pop_last_user_if(self, chat_key: str, text: str) -> bool:
        """末条上下文为内容匹配的 user 消息时弹出并保存（悬空恢复防重复；仅动末条）。

        多模态 content（parts 列表）按文本部分拼接比对；不匹配/末条非 user 一律不动。
        """
        state = await self._state(chat_key)
        contexts = state["contexts"]
        if not contexts:
            return False
        entry = contexts[-1]
        if not isinstance(entry, dict) or entry.get("role") != "user":
            return False
        if self.svc._text_of(entry.get("content")) != str(text or ""):
            return False
        contexts.pop()
        await self._save(chat_key, state)
        return True

# ===== 用户→群会话倒排（recent_user_messages 免全库扫描） =====

    def _user_seen(self, uid: str) -> list[dict] | None:
        """读倒排；损坏/缺失返回 None（调用方回退旧全扫）。"""
        data = self.sdk.storage.get(USER_SEEN_PREFIX + uid, None)
        if not isinstance(data, list):
            return None
        return [item for item in data if isinstance(item, dict) and isinstance(item.get("chat_key"), str) and item["chat_key"]]

    async def _user_seen_record(self, uid: str, chat_key: str, head: str) -> None:
        """uid → 最近发言的群会话（新在前、去重、上限 USER_SEEN_MAX）。仅记群会话。"""
        if ":group:" not in chat_key:
            return
        seen = await self.a_user_seen(uid) or []
        rest = [item for item in seen if item.get("chat_key") != chat_key]
        entry = {"chat_key": chat_key, "ts": utils.now_ts(), "head": utils.truncate(str(head or ""), 60)}
        await self.sdk.storage.aset(USER_SEEN_PREFIX + uid, ([entry] + rest)[:USER_SEEN_MAX])

    async def reset(self, chat_key: str) -> None:
        state = await self._state(chat_key)
        state["contexts"] = []
        state["summary"] = ""
        state["facts"] = []
        state["turns"] = 0
        state["compacted_at_turn"] = 0
        await self._save(chat_key, state)

    async def edit_message(self, chat_key: str, index: int, content: str, attachments: list | None = None) -> bool:
        contexts = await self.get_contexts(chat_key)
        if not (0 <= index < len(contexts)):
            return False
        entry = contexts[index]
        if isinstance(attachments, list):
            entry["content"] = self.svc.rebuild_user_content(content, attachments)
        elif isinstance(entry.get("content"), list):
            kept = [p for p in entry["content"] if isinstance(p, dict) and p.get("type") != "text"]
            merged = ([{"type": "text", "text": content}] + kept) if content else kept
            entry["content"] = merged or content
        else:
            entry["content"] = content
        await self.replace_contexts(chat_key, contexts)
        return True

    async def delete_message(self, chat_key: str, index: int) -> bool:
        contexts = await self.get_contexts(chat_key)
        if not (0 <= index < len(contexts)):
            return False
        contexts.pop(index)
        await self.replace_contexts(chat_key, contexts)
        return True

    async def rewind_to(self, chat_key: str, index: int) -> tuple[bool, str]:
        """回滚到第 index 条之前（删除该条及其之后所有消息）。

        用于"编辑并重新发送"：把被编辑的那条及其回答一起丢弃，返回原文供前端预填重发，
        避免旧回答残留在上下文里造成重复/矛盾。
        """
        contexts = await self.get_contexts(chat_key)
        if not (0 <= index < len(contexts)):
            return (False, "")
        text = self.svc._text_of(contexts[index].get("content"))
        await self.replace_contexts(chat_key, contexts[:index])
        return (True, text)

    async def trim_overflow(self, chat_key: str, keep: int) -> list:
        state = await self._state(chat_key)
        contexts = state["contexts"]
        if len(contexts) <= keep:
            return []
        removed = contexts[: len(contexts) - keep]
        state["contexts"] = contexts[-keep:]
        await self._save(chat_key, state)
        return removed


    async def set_persona(self, chat_key: str, persona_id: str | None) -> None:
        state = await self._state(chat_key)
        state["persona"] = persona_id
        await self._save_no_touch(chat_key, state)

    async def persona_of(self, chat_key: str) -> str | None:
        return (await self._state(chat_key))["persona"]

    async def set_name(self, chat_key: str, name: str) -> str:
        """F2 会话手动改名（空串清除自定义名，回落显示规则）。"""
        state = await self._state(chat_key)
        state["name"] = str(name or "")
        await self._save_no_touch(chat_key, state)
        return state["name"]

    async def set_flags(self, chat_key: str, flags: dict | None = None, pinned: bool | None = None, archived: bool | None = None) -> None:
        """置会话标记。兼容旧签名（pinned/archived 关键字）；起支持任意布尔标记 dict
（如 {"opening_sent": True}），供开场白防重等状态写入。"""
        state = await self._state(chat_key)
        if pinned is not None:
            state["pinned"] = bool(pinned)
        if archived is not None:
            state["archived"] = bool(archived)
        if flags:
            for name, value in flags.items():
                state[str(name)] = bool(value)
        await self._save_no_touch(chat_key, state)

    async def get_flag(self, chat_key: str, name: str) -> bool:
        """读会话布尔标记（缺省 False），与 set_flags 的 dict 形态配对。"""
        return bool((await self._state(chat_key)).get(name))

    async def set_trigger(self, chat_key: str, mode: str) -> None:
        """会话级触发规则覆盖（all 视为未覆盖，删除覆盖回退全局）。"""
        state = await self._state(chat_key)
        mode = str(mode or "").strip().lower()
        if mode in ("", "all"):
            state.pop("trigger_mode", None)
        elif mode in ("at_only", "lurk", "off"):
            state["trigger_mode"] = mode
        await self._save_no_touch(chat_key, state)

    async def trigger_mode_of(self, chat_key: str) -> str:
        """会话触发规则覆盖值（"" 表示未覆盖，跟随全局）；设置弹窗存于 ui。"""
        ui = (await self._state(chat_key)).get("ui")
        if isinstance(ui, dict):
            mode = str(ui.get("trigger_mode") or "").strip().lower()
            if mode in ("at_only", "lurk", "off", "all"):
                return "" if mode == "all" else mode
        return str((await self._state(chat_key)).get("trigger_mode") or "")

# ===== 会话成员白名单与跨会话路由 =====

    async def routes(self) -> dict:
        data = await self.sdk.storage.aget(ROUTES_KEY, {})
        return {k: str(v) for k, v in data.items() if isinstance(k, str) and v} if isinstance(data, dict) else {}

    async def save_routes(self, routes: dict) -> None:
        await self.sdk.storage.aset(ROUTES_KEY, {str(k): str(v) for k, v in (routes or {}).items() if v})

    async def resolve_route(self, chat_key: str) -> str:
        """消息来源 key → 目标会话 key；群隔离 key 先精确匹配再回落到群 base key"""
        routes = await self.routes()
        if not routes:
            return ""
        if chat_key in routes:
            return routes[chat_key]
        base = strip_isolation(chat_key)
        if base != chat_key:
            return routes.get(base, "")
        return ""

# ===== 身份迁移（跨平台/换号保历史）：旧会话键 → 新会话键 的映射别名 =====
# 场景：onebot11 迁到 snowluma、换号、复合 id 变化——旧键数据不搬，
# 入站事件在键生成后按映射改写，历史/人格/记忆/事实全部自动跟到新身份。

    async def identity_map(self) -> dict:
        data = await self.sdk.storage.aget(IDENTITY_MAP_KEY, {})
        return {k: str(v) for k, v in data.items() if isinstance(k, str) and v} if isinstance(data, dict) else {}

    async def set_identity(self, source: str, target: str) -> None:
        """绑定身份映射：source 键的事件此后按 target 会话处理。"""
        source, target = str(source or "").strip(), str(target or "").strip()
        if not source or not target or source == target:
            return
        mapping = await self.identity_map()
        mapping[source] = target
        await self.sdk.storage.aset(IDENTITY_MAP_KEY, mapping)

    async def remove_identity(self, source: str) -> bool:
        mapping = await self.identity_map()
        if str(source or "") in mapping:
            mapping.pop(str(source), None)
            await self.sdk.storage.aset(IDENTITY_MAP_KEY, mapping)
            return True
        return False

    async def resolve_identity(self, chat_key: str) -> str:
        """跟随身份映射（含链式，环安全）：返回最终会话键；无映射原样返回。"""
        seen = set()
        current = str(chat_key or "")
        while current not in seen:
            seen.add(current)
            nxt = (await self.identity_map()).get(current, "")
            if not nxt or nxt == current:
                break
            current = nxt
        return current

    async def migrate_identity(self, source: str, target: str, mode: str = "alias") -> dict:
        """身份迁移：把 source 的对话身份并入 target，支持三种模式。

        - alias    仅映射：source 事件此后按 target 处理，两边历史都不动
        - merge    合并：source 的上下文/事实/记忆并入 target（按时间排序、去重），
                   旧键状态原地保留（撤销映射即回退），随后建立映射
        - overwrite 覆盖：target 的上下文/事实先备份进回收站，再用 source 的替换，
                   随后建立映射

        返回摘要 {ok, mode, contexts, facts, memories, backup}。
        """
        source, target = str(source or "").strip(), str(target or "").strip()
        mode = str(mode or "alias").strip().lower()
        if not source or not target or source == target:
            return {"ok": False, "error": "source/target 必填且不能相同"}
        if mode not in ("alias", "merge", "overwrite"):
            return {"ok": False, "error": f"未知模式：{mode}"}

        summary: dict = {"ok": True, "mode": mode, "contexts": 0, "facts": 0, "memories": 0, "backup": ""}
        src_state = await self._state(source)
        tgt_state = await self._state(target)

        if mode in ("merge", "overwrite"):
            if mode == "overwrite":
# 覆盖前进回收站（可一键恢复），沿用 manager 的 trash 存储约定
                import secrets as _secrets

                token = _secrets.token_urlsafe(9)
                self.sdk.storage.set(
                    "QvQChat:trash:" + token,
                    {"kind": "session", "payload": {"chat_key": target, "state": tgt_state}, "ts": utils.now_ts()},
                )
                summary["backup"] = token
                tgt_state["contexts"] = [e for e in (src_state.get("contexts") or []) if isinstance(e, dict)]
                tgt_state["facts"] = [str(f) for f in (src_state.get("facts") or [])]
                summary["contexts"] = len(tgt_state["contexts"])
                summary["facts"] = len(tgt_state["facts"])
            else:
# 合并：上下文按 (role, content) 去重后按时间排序（跨平台时钟不一致，
# 同一句话 ts 不同也算同一条）；事实并集保序并套上限
                seen_ctx = set()
                merged_ctx: list = []
                for entry in (tgt_state.get("contexts") or []) + (src_state.get("contexts") or []):
                    if not isinstance(entry, dict):
                        continue
                    key = (entry.get("role"), str(entry.get("content") or ""))
                    if key in seen_ctx:
                        continue
                    seen_ctx.add(key)
                    merged_ctx.append(entry)
                merged_ctx.sort(key=lambda e: float(e.get("ts") or 0))
                tgt_state["contexts"] = merged_ctx
                summary["contexts"] = len(merged_ctx)

                facts_max = int(getattr(self.config, "facts_max", 100) or 100)
                seen_f: set[str] = set()
                merged_facts: list[str] = []
                for fact in (tgt_state.get("facts") or []) + (src_state.get("facts") or []):
                    text = str(fact).strip()
                    if not text or text in seen_f:
                        continue
                    seen_f.add(text)
                    merged_facts.append(text)
                tgt_state["facts"] = merged_facts[-facts_max:]
                summary["facts"] = len(tgt_state["facts"])

# 记忆合并（content 归一化去重、按时间排序、套 memory_max）
            mem = getattr(self.main, "memory", None)
            if mem is not None:
                tgt_entries = list(await mem.entries(target))
                seen_n = {mem._normalized(e.get("content", "")) for e in tgt_entries}
                merged_m = list(tgt_entries)
                for entry in await mem.entries(source):
                    normalized = mem._normalized(entry.get("content", ""))
                    if not normalized or normalized in seen_n:
                        continue
                    seen_n.add(normalized)
                    merged_m.append(dict(entry))
                merged_m.sort(key=lambda e: e.get("ts", 0))
                max_items = int(getattr(self.config, "memory_max", 200) or 200)
                if len(merged_m) > max_items:
                    merged_m = merged_m[-max_items:]
                await mem._save(target, merged_m)
                summary["memories"] = len(merged_m)
            await self._save_no_touch(target, tgt_state)

# 最后建立映射：source 的事件此后按 target 处理（旧键数据原地保留，撤销映射即回退）
        await self.set_identity(source, target)
        return summary

