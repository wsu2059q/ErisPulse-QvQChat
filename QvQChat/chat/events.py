"""非消息事件域（Notice/Request）：事件收件箱 + 生态广播 + 受控唤醒。

框架把平台事件归一为 message/notice/request/meta 四类总线（OB12 口径：
type → detail_type → sub_type），除 message 外的事件类型也在此统一接入：

- 一律入收件箱：不枚举事件类型，平台私有 detail_type/sub_type 原样保留
  （含平台原始载荷截断），模型用 list_events 工具随时查看
- 生态开放接口：qvq.notice / qvq.request 生命周期广播（外部模块防御式订阅）
- 唤醒默认关：notice 需 notice_listen + notice_types 白名单（档位规则照旧：
  off/lurk 永不醒；被点名的直接互动类在 at_only 也醒）；request 需
  request_auto_handle（AI 以管理员身份用 handle_request 自主决定，结果汇报管理员）
"""
from __future__ import annotations

import asyncio
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

# 入群合并窗口（秒）：同群连续 group_increase 通知合并为一个 AI 回合，一次欢迎
# 整批新人（一批用户同时进群时每条通知各开一个回合，刷屏且消耗
# token）。实际生效窗口 = min(JOIN_AGG_WINDOW, aggregate_window)——不比消息聚合
# 管线更拖（运营方调小 aggregate_window 求快时，入群唤醒同样快）；聚合关（0）
# 时逐条照旧；cfg.join_agg_window 可显式覆盖（含 0=关闭合并）。
JOIN_AGG_WINDOW = 8.0
# 好友申请受理后的私聊静默（秒）：好友申请决策回执发到来源时已经是欢迎，同一
# 用户随后的 friend_increase 类通知在此窗口内不唤醒（同一新人会被
# 欢迎两三句）
FRIEND_GREET_SUPPRESS = 600.0


# ===== 入群/加好友通知治理（模块级纯函数）=====
# 放模块级而不是 mixin 方法：测试宿主（FakeMain）按名单挑选 mixin 方法绑定，
# 新增实例方法在老宿主上不存在——被绑定方法内部调用会 AttributeError，并被
# _on_notice 的兜底 try/except 吞掉，表现为"该醒不醒"的静默回归。


def _ev_str(event, fn, default: str = "") -> str:
    try:
        return str(fn() or "")
    except Exception:
        return default


def _is_join_notice(event) -> bool:
    """入群通知判定：detail/sub_type 含 "increase" 词形且确有群 id（OB12 口径
    detail_type="group_increase"，部分适配器拆成 detail="group" sub="increase"，
    不硬编码平台私有全名，decrease 不含 increase 不误伤）。friend_increase 这类
    无群 id 的通知天然不进合并路径。"""
    if not _ev_str(event, lambda: event.get_group_id()):
        return False
    detail = _ev_str(event, lambda: event.get_detail_type())
    sub = _ev_str(event, lambda: event.get("sub_type"))
    return "increase" in f"{detail} {sub}".lower()


def _join_window(cfg) -> float:
    """生效入群合并窗口：cfg.join_agg_window 显式覆盖优先（0=关闭合并）；
    否则取 min(JOIN_AGG_WINDOW, aggregate_window)——不比消息聚合管线更拖
    （运营方调小 aggregate_window 求快时，入群唤醒同样快），聚合关（0）返回 0。"""
    override = getattr(cfg, "join_agg_window", None)
    if override is not None:
        return max(float(override) or 0.0, 0.0)
    aggregate = float(getattr(cfg, "aggregate_window", JOIN_AGG_WINDOW) or 0)
    if aggregate <= 0:
        return 0.0
    return min(JOIN_AGG_WINDOW, aggregate)


def _friend_greet_hit(main, event) -> bool:
    """私聊会话：该用户刚被受理过好友申请（FRIEND_GREET_SUPPRESS 内）→ 不唤醒，
    决策回执已经是欢迎。群聊会话不受影响；未挂账（无状态字典）恒 False。"""
    if _ev_str(event, lambda: event.get_group_id()):
        return False
    store = getattr(main, "_recent_friend_greeted", None)
    if not store:
        return False
    platform = _ev_str(event, lambda: event.get_platform())
    for uid in (_ev_str(event, lambda: event.get_user_id()),
                _ev_str(event, lambda: event.get_operator_id())):
        if not uid:
            continue
        stamp = store.get(f"{platform}:{uid}")
        if stamp is not None and time.time() - float(stamp) < FRIEND_GREET_SUPPRESS:
            return True
    return False


async def _flush_join_buffer(main, chat_key: str) -> None:
    """合并窗口到点：整批入群通知合成一个 stimulus（原摘要的群头部 + 合并名单），
    一次 _batch_message 让 AI 一个回合欢迎所有人（单人同路径，names 只有一个）。
    self-join 不进缓冲（单独走 notice_self_join），不会在这里混批。"""
    await asyncio.sleep(_join_window(main.cfg))
    buffered = (getattr(main, "_join_buffer", None) or {}).pop(chat_key, None)
    if not buffered:
        return
    events = [e for e in (buffered.get("events") or []) if e is not None]
    if not events:
        return
# 限频在 flush 时统一判一次：窗口内多批不逐条计费，超限整批静默（事件已入箱可查）
    if not main._notice_rate_ok(chat_key):
        return
# 名单从各事件的 user/nickname 抽成 "nick(id)"（与摘要口径一致），按 user 去重保序
    labels: list[str] = []
    seen: set = set()
    for ev in events:
        uid = _ev_str(ev, lambda: ev.get_user_id())
        if not uid or uid in seen:
            continue
        seen.add(uid)
        nick = _ev_str(ev, lambda: ev.get_user_nickname())
        labels.append(f"{nick}({uid})" if nick else uid)
    first = events[0]
    detail = _ev_str(first, lambda: first.get_detail_type())
    sub = _ev_str(first, lambda: first.get("sub_type"))
    head = f"【通知/{detail}" + (f":{sub}" if sub else "") + "】"
    group_id = _ev_str(first, lambda: first.get_group_id())
    if group_id:
        head += f" 群 {group_id}"
    main._batch_message(
        first,
        chat_key,
        head + " " + texts.t("notice_join_merged", names="、".join(labels)),
        [],
    )


class EventsMixin:
    # ---------- 通用辅助 ----------

    @staticmethod
    def _ev_s(event, fn, default: str = "") -> str:
        try:
            return str(fn() or "")
        except Exception:
            return default

    def _event_self_id(self, event) -> str:
# 稳定 user_id 优先（与 @账户 会话后缀同口径）；老适配器无该方法时回退配置名，
# 别名机制（_inbox_alias_keys）保证两种口径互相可见
        sid = self._ev_s(event, lambda: event.get_self_user_id())
        return sid or self._ev_s(event, lambda: event.get_self_account_id())

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

    def _inbox_alias_keys(self, account: str) -> list[str]:
        """收件箱账户键别名：user_id ↔ 配置名互换（同一账户两种称呼都能命中）。

        历史包袱：收件箱曾按 get_self_account_id()（配置名，会漂移）存键，
        会话/操作链路统一用稳定 user_id——两套口径对不上时第二账户的
        事件全部"查无此箱"。这里把两个名字都作为候选键。
        """
        keys = [str(account or "default")]
        if str(account or "default") == "default":
            return keys
        try:
            for adapter in self._iter_adapters():
                accounts = getattr(adapter, "accounts", None)
                if not isinstance(accounts, dict):
                    continue
                for acct_name, cfg in accounts.items():
                    bot_id = str(getattr(cfg, "bot_id", "") or "")
                    if not bot_id:
                        continue
                    if bot_id == str(account):
                        keys.append(str(acct_name))
                    elif str(acct_name) == str(account):
                        keys.append(bot_id)
        except Exception:
            pass
        seen: list[str] = []
        for key in keys:
            if key and key not in seen:
                seen.append(key)
        return seen

    def _iter_adapters(self):
        try:
            names = self.sdk.adapter.list_registered()
        except Exception:
            names = []
        for name in names or []:
            adapter = None
            try:
                adapter = self.sdk.adapter.get(str(name))
            except Exception:
                adapter = None
            if adapter is not None:
                yield adapter

    def _inbox_load(self, account: str) -> list:
        if getattr(self, "_event_inbox", None) is None:
            self._event_inbox = {}
        cached = self._event_inbox.get(account)
        if cached is not None:
            return cached
        entries: list = []
        for key in self._inbox_alias_keys(account):
            try:
                stored = self.sdk.storage.get(EVENT_INBOX_KEY + key)
            except Exception:
                stored = None
            if isinstance(stored, list) and stored:
                entries.extend(e for e in stored if isinstance(e, dict))
# 多别名合并后按时间排序去重（同 id 只留最新）
        dedup: dict[str, dict] = {}
        for entry in entries:
            dedup[str(entry.get("id") or "")] = entry
        entries = sorted(dedup.values(), key=lambda e: float(e.get("ts") or 0))
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
        """通知唤醒（默认全关）：白名单 + 档位 + 限频三道门，命中才进聊天管线。

        入群/加好友通知治理：
        - 自己入群：不发"新人来了"的普通 stimulus，改发 notice_self_join 场景注记
          （AI 不知情会跟着"欢迎欢迎"，实际是自己进了群）
        - 他人入群：合并窗口内同群连续通知合并为一个回合，一次欢迎整批（防刷屏）
        - 好友静默：刚受理过好友申请的用户，10 分钟内私聊通知不再唤醒

        注意：本方法只能调用"既有"的 mixin 方法——测试宿主（FakeMain）按名单挑
        方法绑定，新增实例方法在老宿主上不存在（AttributeError 会被 _on_notice
        吞掉、静默不醒）。新逻辑全部放模块级函数（见上方定义）。
        """
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
        if _friend_greet_hit(self, event):
            return
        if _is_join_notice(event):
            if self._ev_s(event, lambda: event.get_user_id()) == self._event_self_id(event):
# 自己进群：由人格决定打招呼或安静，绝不能当"新人来了"欢迎
                if not self._notice_rate_ok(chat_key):
                    return
                self._batch_message(event, chat_key, texts.t("notice_self_join"), [])
                return
            if _join_window(self.cfg) <= 0:
# 合并被显式关闭（join_agg_window/aggregate_window 为 0）：逐条照旧，不缓冲
                if not self._notice_rate_ok(chat_key):
                    return
                self._batch_message(
                    event,
                    chat_key,
                    texts.t("notice_stimulus", summary=entry.get("summary") or ""),
                    [],
                )
                return
# 他人入群：先过门（上面）再入合并缓冲，限频挪到 flush 统一判，一次欢迎整批
            buffer_map = getattr(self, "_join_buffer", None)
            if buffer_map is None:
                buffer_map = self._join_buffer = {}
            buffered = buffer_map.get(chat_key)
            if buffered is None:
                buffer_map[chat_key] = {
                    "events": [event],
                    "timer": self.spawn(_flush_join_buffer(self, chat_key)),
                }
            else:
                buffered["events"].append(event)
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
# spawn 不 await：决策是完整 AI 回合（含工具，可达数十秒），内联等待会拖住
# 事件链（线上观察到 _on_request 阻塞 46.8s，连带 SQLite 写入排队 database locked）
                self.spawn(self._request_decision(event, entry))
            else:
                self.logger.info(f"request received (auto handle off): {entry.get('summary')}")
        except Exception:
            self.logger.error("on_request failed:\n" + traceback.format_exc())

    async def _request_decision(self, event, entry: dict) -> None:
        """AI 自主处理请求：决策回合以管理员身份跑（handle_request 自带 admin 护栏）。

        回执两路：群请求的决策发到**事件来源群**（申请人/邀请人看得到受理进度，
        仅私聊管理员时群里无人知道受理进度）；管理员私聊同步一份询问
        （操作权在管理员，handle_request 有 admin 护栏）。未配置管理员只入箱。
        """
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
        group_id = str(entry.get("group_id") or "")
# 群请求 → 来源群也收决策回执（与管理员私聊同一份决策文本）
        source_chat = ""
        if group_id:
            source_chat = make_chat_key(platform, "group", group_id) + suffix
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
# persist=True：决策提问进管理员会话历史——否则主人回"同意"时智能体没有上下文，
# 不知道在同意哪个请求
                persist=True,
            )
        except Exception:
            self.logger.error("request decision failed:\n" + traceback.format_exc())
            return
        reply = str(reply or "").strip()
        if not reply:
            return
# 好友申请决策回合正常完成 → 记"已打招呼"时刻：handle_request 的受理结果发生在
# AI 工具回合内部，这里拿不到确切结论，按"正常完成=已处理"挂账（后续拿得到
# 结果再收紧）。只记好友申请（无群 id；群请求没有这个私聊欢迎面）。随后
# friend_increase 类通知 10 分钟内不唤醒——决策回执已发到来源，同一新人不再
# 被欢迎两三句。顺手清掉过期挂账，防字典随时间无限膨胀
        user_id = str(entry.get("user_id") or "")
        if not group_id and user_id:
            if getattr(self, "_recent_friend_greeted", None) is None:
                self._recent_friend_greeted = {}
            now = time.time()
            self._recent_friend_greeted[f"{platform}:{user_id}"] = now
            self._recent_friend_greeted = {
                key: stamp for key, stamp in self._recent_friend_greeted.items()
                if now - float(stamp) < FRIEND_GREET_SUPPRESS
            }
        if source_chat:
            try:
                await self.delivery.send_segments(platform, "group", group_id, [(0.0, reply)],
                                                  from_tools=False, chat_key=source_chat)
            except Exception as e:
                self.logger.debug(f"request group report send failed: {e}")
        try:
            await self.delivery.send_segments(platform, "private", admin_id, [(0.0, reply)],
                                              from_tools=False, chat_key=admin_chat)
        except Exception as e:
            self.logger.debug(f"request report send failed: {e}")
