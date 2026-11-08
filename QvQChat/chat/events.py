"""非消息事件域（Notice/Request）：事件收件箱 + 生态广播 + 受控唤醒。

框架把平台事件归一为 message/notice/request/meta 四类总线（OB12 口径：
type → detail_type → sub_type），此前本模块只接了 message。这里补齐：

- 一律入收件箱：不枚举事件类型，平台私有 detail_type/sub_type 原样保留
  （含平台原始载荷截断），模型用 list_events 工具随时查看
- 生态开放接口：qvq.notice / qvq.request 生命周期广播（外部模块防御式订阅）
- 唤醒默认关：notice 需 notice_listen + notice_types 白名单（档位规则照旧：
  off/lurk 永不醒；被点名的直接互动类在 at_only 也醒）；request 需
  request_auto_handle（AI 以管理员身份用 handle_request 自主决定，结果汇报管理员）
"""
from __future__ import annotations

import json
import time
import traceback

from .. import texts
from ..conversation.service import make_chat_key
from .inbox import _account_suffix_for, is_self_event

# 收件箱容量（每账户保留最近 N 条；storage 持久，重启不丢待处理请求）
EVENT_INBOX_CAP = 100
EVENT_INBOX_KEY = "QvQChat:event_inbox:"

# 通知唤醒限频：每会话每窗口最多 N 次（防戳一戳刷屏烧 token）
NOTICE_RATE_LIMIT = 5
NOTICE_RATE_WINDOW = 60.0


class EventsMixin:
    # ---------- 通用辅助 ----------

    @staticmethod
    def _ev_s(event, fn, default: str = "") -> str:
        try:
            return str(fn() or "")
        except Exception:
            return default

    def _event_self_id(self, event) -> str:
        return self._ev_s(event, lambda: event.get_self_account_id())

    def _event_chat_key(self, event) -> str:
        """非消息事件的会话键：有群 id → 群键；否则私聊键（user_id 或 operator_id）。"""
        platform = self._ev_s(event, lambda: event.get_platform())
        suffix = _account_suffix_for(self.cfg, self.sdk, event)
        gid = self._ev_s(event, lambda: event.get_group_id())
        if gid:
            if getattr(self.cfg, "group_isolation", False):
                uid = self._ev_s(event, lambda: event.get_user_id())
                if uid:
                    return make_chat_key(platform, "group", f"{gid}:u{uid}") + suffix
            return make_chat_key(platform, "group", gid) + suffix
        uid = self._ev_s(event, lambda: event.get_user_id()) or self._ev_s(event, lambda: event.get_operator_id())
        return make_chat_key(platform, "private", uid) + suffix

    def _event_sub_type(self, event) -> str:
        try:
            return str(event.get("sub_type") or "")
        except Exception:
            return ""

    def _event_summary(self, event, kind: str) -> str:
        """人类可读事件摘要：只拼通用字段，不枚举平台类型（私有类型原样显示）。"""
        detail = self._ev_s(event, lambda: event.get_detail_type())
        sub = self._event_sub_type(event)
        head = f"【{kind}/{detail}" + (f":{sub}" if sub else "") + "】"
        parts = []
        group = self._ev_s(event, lambda: event.get_group_id())
        user = self._ev_s(event, lambda: event.get_user_id())
        operator = self._ev_s(event, lambda: event.get_operator_id())
        target = self._ev_s(event, lambda: event.get_target_id())
        nick = self._ev_s(event, lambda: event.get_user_nickname())
        comment = self._ev_s(event, lambda: event.get_comment())
        if group:
            parts.append(f"群 {group}")
        if user:
            parts.append(f"用户 {nick}({user})" if nick else f"用户 {user}")
        if operator and operator != user:
            parts.append(f"操作者 {operator}")
        if target and target not in (user, self._event_self_id(event)):
            parts.append(f"目标 {target}")
        if comment:
            parts.append(f"附言：{comment}")
        return head + (" " + " ".join(parts) if parts else "")

    def _event_raw_text(self, event) -> str:
        """平台原始载荷截断保留：模型可借此看懂平台私有拓展字段。"""
        try:
            platform = self._ev_s(event, lambda: event.get_platform())
            raw = event.get(f"{platform}_raw") if hasattr(event, "get") else None
            if raw:
                return json.dumps(raw, ensure_ascii=False, default=str)[:1500]
        except Exception:
            pass
        return ""

    # ---------- 事件收件箱 ----------

    def _inbox_load(self, account: str) -> list:
        if getattr(self, "_event_inbox", None) is None:
            self._event_inbox = {}
        cached = self._event_inbox.get(account)
        if cached is not None:
            return cached
        try:
            stored = self.sdk.storage.get(EVENT_INBOX_KEY + account)
        except Exception:
            stored = None
        entries = stored if isinstance(stored, list) else []
        self._event_inbox[account] = entries
        return entries

    def _inbox_save(self, account: str) -> None:
        entries = self._inbox_load(account)
        if len(entries) > EVENT_INBOX_CAP:
            del entries[:-EVENT_INBOX_CAP]
        try:
            self.sdk.storage.set(EVENT_INBOX_KEY + account, entries)
        except Exception as e:
            self.logger.debug(f"inbox persist failed: {e}")

    def _inbox_add(self, event, kind: str, chat_key: str) -> dict:
        """事件入箱：通用字段平铺 + summary + 平台原始载荷截断。同 id 幂等。"""
        account = self._event_self_id(event) or "default"
        try:
            ts = float(event.get("time") or 0) if hasattr(event, "get") else 0.0
        except Exception:
            ts = 0.0
        entry = {
            "id": ((str(event.get("id") or "") if hasattr(event, "get") else "")
                   or f"{kind}-{int(time.time() * 1000)}"),
            "ts": ts or round(time.time(), 3),
            "kind": kind,
            "detail_type": self._ev_s(event, lambda: event.get_detail_type()),
            "sub_type": self._event_sub_type(event),
            "platform": self._ev_s(event, lambda: event.get_platform()),
            "account": account,
            "chat_key": chat_key,
            "user_id": self._ev_s(event, lambda: event.get_user_id()),
            "operator_id": self._ev_s(event, lambda: event.get_operator_id()),
            "target_id": self._ev_s(event, lambda: event.get_target_id()),
            "group_id": self._ev_s(event, lambda: event.get_group_id()),
            "request_id": "",
            "comment": self._ev_s(event, lambda: event.get_comment()),
            "summary": self._event_summary(event, "通知" if kind == "notice" else "请求"),
            "read": False,
            "raw": self._event_raw_text(event),
        }
        if kind == "request":
            entry["request_id"] = self._ev_s(event, lambda: event.get_request_id())
        entries = self._inbox_load(account)
        if any(e.get("id") == entry["id"] for e in entries):
            return entry
        entries.append(entry)
        self._inbox_save(account)
        return entry

    def _inbox_pick(self, entry: dict, keys: tuple) -> dict:
        return {k: entry.get(k) for k in keys}

    # ---------- Notice 入口 ----------

    async def _on_notice(self, event) -> None:
        try:
            try:
                if event.get("replayed"):
                    return
            except Exception:
                pass
            if is_self_event(self.cfg, self.sdk, event):
                return
            if not self._dup_delivery_gate(event, ""):
                return
            chat_key = self._event_chat_key(event)
            entry = self._inbox_add(event, "notice", chat_key)
# 生态开放接口：qvq.notice 广播（listen_off 与 observe 同语义：群要隐私就静音）
            if not self.sessions.get_flag(chat_key, "listen_off"):
                try:
                    await self.sdk.lifecycle.emit(
                        "qvq.notice",
                        self._inbox_pick(entry, (
                            "id", "ts", "detail_type", "sub_type", "platform", "account",
                            "chat_key", "user_id", "operator_id", "target_id", "group_id",
                            "summary",
                        )),
                    )
                except Exception as e:
                    self.logger.debug(f"emit qvq.notice failed: {e}")
            self._maybe_wake_on_notice(event, chat_key, entry)
        except Exception:
            self.logger.error("on_notice failed:\n" + traceback.format_exc())

    def _notice_type_hit(self, event) -> bool:
        """白名单匹配：接受 detail_type / sub_type / detail:sub / 去平台前缀短名。"""
        wanted = [str(t or "").strip() for t in (getattr(self.cfg, "notice_types", []) or [])]
        wanted = {w for w in wanted if w}
        if not wanted:
            return False
        detail = self._ev_s(event, lambda: event.get_detail_type())
        sub = self._event_sub_type(event)
        platform = self._ev_s(event, lambda: event.get_platform())
        candidates = {detail, sub}
        if detail and sub:
            candidates.add(f"{detail}:{sub}")
        prefix = f"{platform}_"
        if detail.startswith(prefix):
            candidates.add(detail[len(prefix):])
        return bool(candidates & wanted)

    def _notice_rate_ok(self, chat_key: str) -> bool:
        now = time.time()
        if getattr(self, "_notice_rate", None) is None:
            self._notice_rate = {}
        stamps = [t for t in self._notice_rate.get(chat_key, []) if now - t < NOTICE_RATE_WINDOW]
        if len(stamps) >= NOTICE_RATE_LIMIT:
            self._notice_rate[chat_key] = stamps
            return False
        stamps.append(now)
        self._notice_rate[chat_key] = stamps
        return True

    def _maybe_wake_on_notice(self, event, chat_key: str, entry: dict) -> None:
        """通知唤醒（默认全关）：白名单 + 档位 + 限频三道门，命中才进聊天管线。"""
        if not bool(getattr(self.cfg, "notice_listen", False)):
            return
        if not self._notice_type_hit(event):
            return
        mode = self._trigger_mode_of(chat_key)
        if mode in ("off", "lurk"):
            return
# 被点名的直接互动（如戳的是本账户）视同被 @：at_only 也醒；环境类通知只在 all 醒
        direct = bool(entry.get("target_id")) and entry.get("target_id") == self._event_self_id(event)
        if mode == "at_only" and not direct:
            return
        if not self._notice_rate_ok(chat_key):
            return
        self._batch_message(
            event,
            chat_key,
            texts.t("notice_stimulus", summary=entry.get("summary") or ""),
            [],
        )

    # ---------- Request 入口 ----------

    async def _on_request(self, event) -> None:
        try:
            try:
                if event.get("replayed"):
                    return
            except Exception:
                pass
            if is_self_event(self.cfg, self.sdk, event):
                return
            if not self._dup_delivery_gate(event, ""):
                return
            chat_key = self._event_chat_key(event)
            entry = self._inbox_add(event, "request", chat_key)
# 生态开放接口：qvq.request 恒广播（请求是冲着 bot 来的，不挂 listen_off）
            try:
                await self.sdk.lifecycle.emit(
                    "qvq.request",
                    self._inbox_pick(entry, (
                        "id", "ts", "detail_type", "sub_type", "platform", "account",
                        "chat_key", "user_id", "group_id", "request_id", "comment",
                        "summary",
                    )),
                )
            except Exception as e:
                self.logger.debug(f"emit qvq.request failed: {e}")
            if bool(getattr(self.cfg, "request_auto_handle", False)):
                await self._request_decision(event, entry)
            else:
                self.logger.info(f"request received (auto handle off): {entry.get('summary')}")
        except Exception:
            self.logger.error("on_request failed:\n" + traceback.format_exc())

    async def _request_decision(self, event, entry: dict) -> None:
        """AI 自主处理请求：以管理员身份跑决策回合（handle_request 自带 admin 护栏），
        决策文本汇报到管理员私聊；未配置管理员则只入箱不决策。"""
        platform = str(entry.get("platform") or "")
        try:
            admin_ids = [str(a) for a in (self.sessions._admin_ids_for(platform) or [])]
        except Exception:
            admin_ids = []
        if not admin_ids:
            self.logger.info("request_auto_handle on but no admins configured; logged only")
            return
        admin_id = admin_ids[0]
        suffix = _account_suffix_for(self.cfg, self.sdk, event)
        admin_chat = make_chat_key(platform, "private", admin_id) + suffix
        summary = str(entry.get("summary") or "")
        try:
            reply = await self.run_prompt(
                admin_chat,
                texts.t(
                    "request_handle_prompt",
                    summary=summary,
                    comment=str(entry.get("comment") or "(无)"),
                    request_id=str(entry.get("request_id") or "(缺失)"),
                    platform=platform,
                ),
                origin="task",
                send=False,
                user_id=admin_id,
                scene=texts.t("scene_request_trigger", summary=summary),
            )
        except Exception:
            self.logger.error("request decision failed:\n" + traceback.format_exc())
            return
        reply = str(reply or "").strip()
        if not reply:
            return
        try:
            await self.delivery.send_segments(platform, "private", admin_id, [(0.0, reply)],
                                              from_tools=False, chat_key=admin_chat)
        except Exception as e:
            self.logger.debug(f"request report send failed: {e}")
