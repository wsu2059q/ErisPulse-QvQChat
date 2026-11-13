"""消息入口域（拆分自 Main.py）：触发判定 / 限频 / 聚合 / 排队 / 冷启动回填。

锁语义：``_flush_pending`` 持 per-chat 锁执行 ``_process_locked``，
与 ``Main.run_prompt`` / ``Main.run_dashboard_chat`` 的 prepare→finalize 段互斥，
防定时任务与聊天并发交错写上下文；这些路径互不嵌套（工具/子代理用独立 chat_key）。
"""
from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import random
import re
import time
import traceback
from pathlib import Path

from .. import texts, utils
from ..agent.tools import ToolContext
from ..conversation.policy import apply_priority, get_policy, listen_allowed
from ..conversation.service import DASHBOARD_PLATFORM, make_chat_key, parse_chat_key, strip_isolation
from ..dashboard.live import bind as live_bind
from ..utils import strip_stray_tags
from ..conversation.delivery import strip_output_tag
from ..engine.base import ChatRequest, TaskSpec
from ..tools_builtin.agent import demote_to_background
from .recovery import INFLIGHT_KEY_PREFIX, RecoveryMixin

CONFIRM_WORDS = {"确认", "確認", "确定", "確定", "是", "confirm", "yes", "y", "ok"}

# cheap 模型的思考链常混在正文里（含多行）：回执/判定解析前必须先剥掉，
# 否则整段思考原样回发到群里就是思考泄露事故
_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)

# 显式停止指令（打断免判定）：任务运行中来一条纯停止词消息，直接作废旧任务，
# 不发三选判定调用（省一次调用，也免得被预算/满载降级吞进队列——"说停"必须是可靠的
# 抢救通道）。整条消息只是停止词的短句才命中，长句里带"停"字不误伤。
_STOP_PHRASE_RE = re.compile(
    r"^[\s，,。！!？?~～*@·]*(?:"
    r"停+|停止|停下|住手|住口|住嘴|闭嘴|打住|"
    r"别说了|别发了|别弄了|别做了|别搞了|"
    r"取消|算了|算了算了|够了|"
    r"stop|cancel|quit"
    r")[\s，,。！!？?~～*·吧啊呀啦嘛哦]*$",
    re.IGNORECASE,
)


def _is_stop_phrase(text: str) -> bool:
    """是否为纯停止指令（用于任务运行中的免判定硬中断）。"""
    return bool(_STOP_PHRASE_RE.match(str(text or "").strip()))


def _json_line_of(raw: str) -> str:
    """剥思考链后从响应里提取 JSON 的 line 字段；拿不到返回空串（调用方走模板回退）。"""
    cleaned = _THINK_RE.sub("", str(raw or ""))
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if not m:
        return ""
    try:
        data = json.loads(m.group(0))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("line") or "").strip()

# 触发规则严格度排序（数值越大越严）：会话级只能收紧不能放宽——全局 at_only 时会话最多 at_only
TRIGGER_RANK = {"all": 0, "at_only": 1, "lurk": 2, "off": 3}


def _num_or_none(value) -> float | None:
    """人格级模型参数覆盖解析：合法正值返回，其余（空/非法/非正）一律 None=不覆盖。"""
    try:
        parsed = float(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _int_or_none(value) -> int | None:
    parsed = _num_or_none(value)
    return int(parsed) if parsed else None

# 同账户重复投递去重窗口（秒）：适配器重试/回声会把同一消息再投一次
DUP_DELIVERY_WINDOW = 6.0

# 限频滑窗字典容量上限（群聊×用户数远达不到，防极端场景只增不减）
RATE_WINDOW_CAP = 512


def is_self_event(cfg, sdk, event) -> bool:
    """H2 自身出站回环判定：sender 等于平台 self_id 或适配器 bot id 即视为回声。"""
    if not bool(getattr(cfg, "humanize_echo_filter", True)):
        return False
    sender = str(event.get_user_id() or "")
    if not sender:
        return False
    for probe in (
        lambda: event.get_self_account_id(),
        lambda: event.get("self_id"),
    ):
        try:
            value = probe()
        except Exception:
            value = None
        if value and str(value) == sender:
            return True
    try:
        adapter = sdk.adapter.get(event.get_platform() or "")
    except Exception:
        adapter = None
    for attr in ("self_id", "bot_id", "get_self_id"):
        value = getattr(adapter, attr, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value and str(value) == sender:
            return True
    return False


# H3 硬打断信号词：短催促/纠错类。纠错词同时触发 H5 撤回
INTERRUPT_URGE_WORDS = ("？", "?", "在吗", "在么", "说话", "理我", "回我", "等等")
RECALL_WORDS = ("撤回", "说错", "发错", "不是这个", "删掉")


def detect_interrupt(text: str, is_at: bool, is_reply: bool,
                     sender_gap: float | None, signals: list) -> tuple[bool, bool]:
    """H3 硬打断判定：返回 (是否打断, 是否纠错需撤回)。

    signals 来自 humanize_interrupt_signals；sender_gap 为该发送者距上一条消息的秒数
    （<=10s 视为连发 burst）。
    """
    enabled = set(str(x) for x in (signals or []) if str(x))
    if not enabled:
        return False, False
    text = str(text or "").strip()
    if "mention" in enabled and is_at:
        return True, False
    if "reply" in enabled and is_reply:
        return True, False
    if "burst" in enabled and sender_gap is not None and 0 < sender_gap <= 10:
        return True, False
    if "urge" in enabled and text and len(text) <= 12:
        if any(w in text for w in INTERRUPT_URGE_WORDS) or any(w in text for w in RECALL_WORDS):
            return True, any(w in text for w in RECALL_WORDS)
    return False, False


def debounce_window(cfg, is_group: bool, is_at: bool) -> float:
    """H2 防抖分级：私聊沿用 aggregate_window；群聊普通消息用群窗口，@ 触发压短。"""
    base = float(getattr(cfg, "aggregate_window", 5.0) or 0)
    if not is_group:
        return base
    group = float(getattr(cfg, "debounce_group_seconds", 2.0) or 0)
    if group <= 0:
        group = base
    if is_at:
        mention = float(getattr(cfg, "debounce_mention_seconds", 1.0) or 0)
        if mention > 0:
            return mention
    return group


# 近期消息指纹：chat_key -> [(sender:text, ts)]（进程内即可：适配器双投递都在本进程）
_RECENT_MSGS: dict[str, list] = {}


def _dup_recent(chat_key: str, sender_id: str, text: str, window: float = 2.0) -> bool:
    """短窗去重：同一会话内同发送者+相同文本在 window 秒内重复到达 → 丢弃。

    针对适配器对多账户同群消息的双投递/重放（毫秒级连发），不影响人类正常复读。
    """
    import hashlib

    key = str(chat_key or "")
    fp = hashlib.sha1(f"{sender_id}\n{text}".encode("utf-8", "replace")).hexdigest()[:16]
    now = time.time()
    recent = _RECENT_MSGS.get(key)
    if recent is None:
        recent = []
        _RECENT_MSGS[key] = recent
    recent[:] = [item for item in recent if now - item[1] < window]
    if any(item[0] == fp for item in recent):
        return True
    recent.append((fp, now))
    if len(_RECENT_MSGS) > 512:
        for k in list(_RECENT_MSGS)[: len(_RECENT_MSGS) - 512]:
            _RECENT_MSGS.pop(k, None)
    return False


def _account_suffix_for(cfg, sdk, event) -> str:
    """单适配器多账户隔离：键追加 @账户 后缀。

    自动探测：仅当该适配器在线机器人 >= 2 且事件携带账户信息时生效——
    单账户安装不加后缀（存量会话/人格/记忆无缝保留）；配置关闭则强制不加。
    模块级函数：宿主以任意对象为 self 的非绑定调用（测试模式）下依旧可用。
    """
    if not getattr(cfg, "account_isolation", True):
        return ""
    platform = ""
    try:
        platform = str(event.get_platform() or "")
        bots = sdk.adapter.list_bots(platform) or {}
        per_platform = bots.get(platform, bots) if isinstance(bots, dict) else {}
        if not isinstance(per_platform, dict) or len(per_platform) < 2:
            return ""
# 账户身份取稳定值：get_self_user_id()（机器人的固定用户 id）优先——
# get_self_account_id() 返回的是框架配置的账户名（如 "Amer"），同一机器人
# 换配置名就漂移，用它会能把同一机器人的历史散成多份会话
        account = ""
        try:
            getter = getattr(event, "get_self_user_id", None)
            if callable(getter):
                account = str(getter() or "")
        except Exception:
            account = ""
        if not account:
            account = str(event.get_self_account_id() or "")
    except Exception:
        return ""
    return f"@{account}" if account else ""




def _seed_text_fingerprint(text: str) -> str:
    """seed 去重指纹：剥掉发言者标注前缀（"昵称(uid): " / "[未记录] "）后取尾部。

    存储里的上下文是标注后的文本、transcript 行是裸文本——不剥标签前缀，
    "裸文本 vs 标注文本" 会被当成两条不同的消息，去重失效。
    """
    s = str(text or "").strip()
    s = re.sub(r"^\[[^\]]*\]\s*", "", s)  # [未记录] 等方括号标注
    s = re.sub(r"^[^\[\n]{1,40}\(\d{5,}\):\s*", "", s)  # 昵称(uid): 
    s = re.sub(r"^\(\d{5,}\):\s*", "", s)  # (uid): 
    return s[-200:]


def _seed_dedupe(rows, contexts) -> list:
    """冷启动回填去重：跳过当前上下文里已存在的相同文本（防止同一条消息既在
    历史又在本次输入中出现两次）。"""
    if not rows:
        return rows
    known = set()
    for message in contexts or []:
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(
                    str(part.get("text") or "") for part in content if isinstance(part, dict)
                )
            text = str(content or "").strip()
            if text:
                known.add(_seed_text_fingerprint(text))
    out = []
    for row in rows:
        text = str((row or {}).get("text") or "").strip()
        if text and _seed_text_fingerprint(text) in known:
            continue
        known.add(_seed_text_fingerprint(text))
        out.append(row)
    return out


# 测试绑定清单：测试把收件箱/命令行 mixin 的方法绑到轻量宿主（FakeMain）上驱动管线。
# 单一来源——新增这类方法时在这里补名字，各测试文件统一引用本常量
INBOX_BOUND_METHODS = (
    "_process_locked", "_chat_ctx", "_sender_name", "_resolve_group_name",
    "_seed_history", "_transcript_rows", "_label_seed_rows", "_group_nicknames",
    "is_admin", "check_tool_permission", "_master_checker",
    "record_usage", "_usage_today", "_prune_usage", "_usage_history",
    "_lock_for", "_batch_message", "_flush_later", "_flush_pending",
    "_live_conflict", "_auto_interrupt_decide", "_handle_auto_decision",
    "_extract_images", "_to_model_image", "_cleanup_takeovers", "_should_trigger",
    "_chat_key_of", "_chat_confirmer", "_rate_allow", "_rate_notice", "_user_quota_allow", "_quota_notice",
    "_maybe_send_opening",
    "_is_command_message", "_command_yields", "_drain_waiting", "_enqueue_waiting", "_trigger_mode_of", "_is_direct_address", "_dup_delivery_gate", "_is_sibling_bot", "_quote_content", "_has_reply_segment", "_quote_targets_me",
    "_sender_muted", "_mutes_note",
    "_on_message", "_announce_queued", "_cmd_agent", "_cmd_persona",
)


class InboxMixin(RecoveryMixin):
    """Main 的消息入口 mixin（组合 RecoveryMixin：实例重启恢复方法随本链挂到 Main）。
    依赖宿主提供 self.sdk / self.cfg / self.logger /
    self.sessions / self.pool / self.runner / self.delivery / self.takeover /
    self._pending / self._waiting / self._chat_locks / self._rate_window /
    self._rate_notice_shown / self.spawn / self.is_admin / self._chat_confirmer 等。"""

    @staticmethod
    def _to_model_image(url: str, max_bytes: int = 5 * 1024 * 1024) -> str:
        if not url or url.startswith(("http://", "https://", "data:")):
            return url
        raw = url[7:] if url.startswith("file://") else url
        try:
            path = Path(raw).expanduser()
            if not path.is_file() or path.stat().st_size > max_bytes:
                return ""
            mime = mimetypes.guess_type(str(path))[0] or "image/png"
            data = base64.b64encode(path.read_bytes()).decode()
            return f"data:{mime};base64,{data}"
        except Exception:
# 本地图片转 base64 失败即放弃该图（降级语义：返回空串由调用方过滤）
            return ""

    async def _quote_content(self, event, limit: int = 300) -> str:
        """提取被引用消息原文：内联 text → 本地 transcript 按 message_id 查 → 适配器 get_msg。

        本地优先的原因：QQ 系 get_msg 对旧消息/跨账户经常失败，而框架 transcript
        （分发前落库）里每条都带 event_id，引用自己刚说过的话一定能查到。
        查到的若是我方消息会标注，模型才能理解"主人是在回复我上一句"。
        """
        platform = str(event.get_platform() or "")
        mid = ""
        try:
            for segment in event.get_message() or []:
                if not isinstance(segment, dict) or segment.get("type") != "reply":
                    continue
                data = segment.get("data") or {}
                raw = str(data.get("text") or "").strip()
                if not raw:
                    content = data.get("content")
                    if isinstance(content, list):
                        raw = "".join(
                            str(seg.get("data", {}).get("text") or "") if isinstance(seg, dict) else str(seg)
                            for seg in content
                        ).strip()
                    elif content:
                        raw = str(content).strip()
                if raw:
                    return raw[:limit]
                mid = str(data.get("id") or data.get("message_id") or "")
                break
        except Exception:
            return ""
        if not mid:
            return ""
# 本地 transcript：按 event_id 精确命中（先查本会话，再全量兜底）
        try:
            transcript = getattr(self.sdk, "transcript", None)
            if transcript is not None and hasattr(transcript, "get"):
                rows = []
                key_fn = getattr(transcript, "session_key_from_event", None)
                if callable(key_fn):
                    try:
                        rows = transcript.get(key_fn(event), 200) or []
                    except Exception:
                        rows = []
                for row in reversed(rows):  # get 按时间升序，从新往旧找
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("event_id") or "") != mid:
                        continue
                    text = str(row.get("text") or "").strip()
                    if not text:
                        break
                    role = str(row.get("role") or "")
                    if role in ("bot", "assistant"):
                        return texts.t("quote_is_own_prev", content=utils.truncate(text, limit))
                    return text[:limit]
        except Exception as e:
            self.logger.debug(f"quote local lookup failed: {e}")
# 兜底：适配器 get_msg（带账户——多账户下不带会落到默认账户查不到）
        if platform:
            try:
                adapter = self.sdk.adapter.get(platform)
                result = None
                if adapter is not None and hasattr(adapter, "call_api"):
                    kwargs = {"message_id": mid}
                    try:
                        account = str(event.get_self_account_id() or "")
                    except Exception:
                        account = ""
                    if account:
                        kwargs["_account_id"] = account
                    result = await adapter.call_api("get_msg", **kwargs)
                payload = result if isinstance(result, dict) else {}
                msg = payload.get("message")
                sender = payload.get("sender") or {}
                nick = ""
                if isinstance(sender, dict):
                    nick = str(sender.get("nickname") or sender.get("card") or "")
                if isinstance(msg, list):
                    text = "".join(
                        str(s.get("data", {}).get("text") or "") if isinstance(s, dict) else str(s)
                        for s in msg
                    ).strip()
                else:
                    text = str(msg or "").strip()
                if not text:
                    text = str(payload.get("raw_message") or "").strip()
                if text:
                    return (f"{nick}：{text}" if nick else text)[:limit]
            except Exception as e:
                self.logger.debug(f"quote fetch failed: {e}")
        return ""

    @staticmethod
    def _has_reply_segment(event) -> bool:
        """消息里是否带引用段（不解析内容，只做廉价前置判断）。"""
        try:
            return any(
                isinstance(seg, dict) and seg.get("type") == "reply"
                for seg in (event.get_message() or [])
            )
        except Exception:
            return False

    async def _quote_targets_me(self, event) -> bool:
        """被引用消息是否本账户所发：引用=艾特（引用谁，谁被点名）。

        先看 reply 段内联的被引用者信息（部分适配器带），拿不到再按
        message_id 走适配器 get_msg 查发送者。查不到一律 False（宁可少触发）。
        """
        platform = str(event.get_platform() or "")
        account = str(event.get_self_account_id() or "")
        mid = ""
        try:
            for segment in event.get_message() or []:
                if not isinstance(segment, dict) or segment.get("type") != "reply":
                    continue
                data = segment.get("data") or {}
                sender = data.get("sender")
                if isinstance(sender, dict):
                    uid = str(sender.get("user_id") or sender.get("id") or "")
                    if uid:
                        return uid == account
                mid = str(data.get("id") or data.get("message_id") or "")
                if mid:
                    break
        except Exception:
            return False
        if not mid or not platform or not account:
            return False
        try:
            adapter = self.sdk.adapter.get(platform)
            if adapter is None or not hasattr(adapter, "call_api"):
                return False
            result = await adapter.call_api("get_msg", message_id=mid)
            payload = result if isinstance(result, dict) else {}
            sender = payload.get("sender")
            uid = ""
            if isinstance(sender, dict):
                uid = str(sender.get("user_id") or "")
            if not uid:
                uid = str(payload.get("user_id") or "")
            return bool(uid) and uid == account
        except Exception as e:
            self.logger.debug(f"quote sender fetch failed: {e}")
            return False

    @staticmethod
    def _extract_images(event) -> list[str]:
        urls: list[str] = []
        try:
            for segment in event.get_message() or []:
                if not isinstance(segment, dict) or segment.get("type") != "image":
                    continue
                data = segment.get("data") or {}
                url = str(data.get("url") or data.get("file") or "")
                if url.startswith(("http://", "https://", "file://", "base64://")):
                    urls.append(url)
        except Exception:
            urls = []
        return urls[:3]

    def _chat_key_of(self, event) -> str:
        platform = event.get_platform() or ""
        suffix = _account_suffix_for(self.cfg, self.sdk, event)
        if event.is_group_message():
            gid = str(event.get_group_id() or "")
            if getattr(self.cfg, "group_isolation", False):
                uid = str(event.get_user_id() or "")
                if uid:
                    return make_chat_key(platform, "group", f"{gid}:u{uid}") + suffix
            return make_chat_key(platform, "group", gid) + suffix
        return make_chat_key(platform, "private", str(event.get_user_id() or "")) + suffix

    def _chat_ctx(self, event, chat_key: str, origin: str = "chat", scene_note: str = "") -> ToolContext:
        from ..conversation.service import strip_account as _strip_account

        platform, detail_type, target_id = parse_chat_key(_strip_account(strip_isolation(chat_key)))
        session_key = ""
        try:
            session_key = self.sdk.interaction.make_key(event)
        except Exception:
            session_key = ""
        self_id = ""
        try:
            self_id = str(event.get_self_account_id() or "") if event is not None else ""
        except Exception:
            self_id = ""
        return ToolContext(
            main=self,
            sdk=self.sdk,
            config=self.cfg,
            chat_key=chat_key,
            session_key=session_key,
            platform=platform,
            detail_type=detail_type,
            target_id=target_id,
            user_id=str(event.get_user_id() or "") if event is not None else "",
            event=event,
            origin=origin,
            confirmer=self._chat_confirmer,
            scene_note=scene_note,
            self_id=self_id,
        )

    def _cleanup_takeovers(self) -> None:
        now = time.time()
        for key in [k for k, v in self.takeover.items() if float(v.get("until", 0)) <= now]:
            entry = self.takeover.pop(key, None)
            lease = (entry or {}).get("lease")
            if lease is not None:
                try:
                    lease.release()
                except Exception as e:
                    self.logger.debug(f"takeover lease release failed: {e}")
# 顺带回收内存态（每条入站消息都会走到这里；同步无 await，回收安全）
# 1) 限频滑窗：窗口已空的键连同提示标记一并清掉
        for key in [
            k for k, w in self._rate_window.items()
            if not w or now - max(w) >= 60
        ]:
            self._rate_window.pop(key, None)
            self._rate_notice_shown.pop(key, None)
# 2) per-chat 锁：仅回收未持有且无等待者的锁
        for key in [k for k, lock in self._chat_locks.items() if not lock.locked()]:
            self._chat_locks.pop(key, None)

    async def _maybe_interrupt(self, event, chat_key: str, text: str) -> None:
        """H3/H5：打断信号检测。仅在本会话确有未发完的分段时生效；纠错词同时撤回上一条。"""
        if not bool(getattr(self.cfg, "humanize_interrupt", True)):
            return
        delivery = getattr(self, "delivery", None)
        if delivery is None:
            return
        now = time.time()
        sender = str(event.get_user_id() or "")
        if not hasattr(self, "_burst_last"):
            self._burst_last = {}
        gap = None
        if sender:
            last = self._burst_last.get(f"{chat_key}:{sender}")
            if last:
                gap = now - last
            self._burst_last[f"{chat_key}:{sender}"] = now
# 仅在防抖窗口内或上一轮分段尚未发完时才打断（护栏，防误伤）
        in_debounce = chat_key in self._pending
        sending = chat_key in getattr(delivery, "_budget_start", {})
        if not (in_debounce or sending):
            return
        try:
            is_reply = any(
                isinstance(seg, dict) and seg.get("type") == "reply"
                for seg in (event.get_message() or [])
            )
        except Exception:
            is_reply = False
        hit, wants_recall = detect_interrupt(
            text,
            bool(event.is_at_message()),
            is_reply,
            gap,
            list(getattr(self.cfg, "humanize_interrupt_signals", []) or []),
        )
        if not hit:
            return
        delivery.interrupt(chat_key)
        self.logger.info(f"hard interrupt triggered for {chat_key}")
        if wants_recall and bool(getattr(self.cfg, "humanize_recall_message", True)):
            await delivery.recall_last(chat_key)

    def _over_token_limit(self, chat_key: str) -> bool:
        """会话是否处于超限态（全局日上限或会话级日限额，任一命中即超）。

        供插话问询、主动发言等可选模型调用的前置闸：超限态下这些"可省调用"
        一律跳过。管理员豁免只作用于用户触发回合的拦截与提示，这里不做身份判断。
        """
        today = time.strftime("%Y-%m-%d")
        data = self.sdk.storage.get(f"QvQChat:usage:{today}", {})
        if not isinstance(data, dict):
            data = {}
        global_limit = int(getattr(self.cfg, "daily_token_limit", 0) or 0)
        if global_limit > 0 and int(data.get("tokens", 0) or 0) >= global_limit:
            return True
        session_limit = int(get_policy(self.sdk, chat_key).get("session_budget") or 0)
        if session_limit > 0:
            by_chat = data.get("by_chat")
            used = int((by_chat or {}).get(chat_key, 0) or 0) if isinstance(by_chat, dict) else 0
            if used >= session_limit:
                return True
        return False

    def _user_quota_allow(self, chat_key: str, sender_id: str, event) -> bool:
        """用户级每日 token 配额：超限拒绝并至多提示一次（管理员豁免）。

        计数在 record_usage 侧（by_user 累加），这里只做门槛判断。
        """
        limit = int(getattr(self.cfg, "user_daily_budget", 0) or 0)
        if limit <= 0 or not sender_id:
            return True
        if self.is_admin(sender_id, "chat", event.get_platform() or ""):
            return True
        today = time.strftime("%Y-%m-%d")
        data = self.sdk.storage.get(f"QvQChat:usage:{today}", {})
        by_user = data.get("by_user") if isinstance(data, dict) else None
        used = int((by_user or {}).get(sender_id, 0) or 0) if isinstance(by_user, dict) else 0
        if used < limit:
            return True
        notice_key = f"QvQChat:usage:user_quota_noticed:{today}:{sender_id}"
        if not self.sdk.storage.get(notice_key, False):
            self.sdk.storage.set(notice_key, True)
            try:
                self.spawn(self._quota_notice(event, limit, used))
            except Exception:
                self.logger.debug("quota notice spawn failed")
        self.logger.info(f"user daily quota exceeded ({chat_key}:{sender_id}): {used}/{limit}")
        return False

    async def _quota_notice(self, event, limit: int, used: int) -> None:
        try:
            await event.reply(texts.t("user_quota_reached", limit=limit, used=used))
        except Exception as e:
            self.logger.debug(f"quota notice reply failed: {e}")

    def _rate_allow(self, chat_key: str, sender_id: str, event) -> bool:
        """群聊 per-user 滑动窗口限频：超限静默丢弃（每窗口至多提示一次），管理员豁免。"""
        limit = int(getattr(self.cfg, "user_rate_limit", 0) or 0)
        if limit <= 0 or not chat_key or ":group:" not in chat_key or not sender_id:
            return True
        if self.is_admin(sender_id, "chat", event.get_platform() or ""):
            return True
        now = time.time()
        key = f"rate:{chat_key}:{sender_id}"
        window = [t for t in self._rate_window.get(key, []) if now - t < 60]
        if len(window) >= limit:
            if not getattr(self, "_rate_notice_shown", {}).get(key):
                self._rate_notice_shown = getattr(self, "_rate_notice_shown", {})
                self._rate_notice_shown[key] = True
                notice_event = event
                self.spawn(self._rate_notice(notice_event))
            return False
        window.append(now)
        self._rate_window[key] = window
        if now - max(window[:-1], default=now) > 120:
            self._rate_notice_shown.pop(key, None)
# 容量上限，超出时优先淘汰已过期键，仍超则按插入序淘汰最旧键
        if len(self._rate_window) > RATE_WINDOW_CAP:
            for stale in [
                k for k, w in self._rate_window.items()
                if not w or now - max(w) >= 60
            ]:
                if len(self._rate_window) <= RATE_WINDOW_CAP:
                    break
                self._rate_window.pop(stale, None)
                self._rate_notice_shown.pop(stale, None)
            while len(self._rate_window) > RATE_WINDOW_CAP:
                stale = next(iter(self._rate_window))
                self._rate_window.pop(stale, None)
                self._rate_notice_shown.pop(stale, None)
        return True

    async def _rate_notice(self, event) -> None:
        try:
            await event.reply(texts.t("rate_limited"))
        except Exception as e:
            self.logger.debug(f"rate limit notice reply failed: {e}")

    def _trigger_mode_of(self, chat_key: str) -> str:
        """生效触发规则：会话覆盖只能比全局更严（取两者中更严格的档）。"""
        g = str(getattr(self.cfg, "trigger_mode", "all") or "all").lower()
        if g not in TRIGGER_RANK:
            g = "all"
        try:
            per = self.sessions.trigger_mode_of(chat_key).lower()
        except Exception:
            per = ""
        if per not in TRIGGER_RANK:
            return g
        return per if TRIGGER_RANK[per] >= TRIGGER_RANK[g] else g

    def _is_direct_address(self, event, text: str, quoted_me: bool = False) -> bool:
        """群里是否被点名：@机器人、命中唤醒前缀，或引用了本账户的消息。"""
        if quoted_me or event.is_at_message():
            return True
        for prefix in getattr(self.cfg, "wake_prefixes", []) or []:
            if prefix and text.startswith(prefix):
                return True
        return False

    def _is_sibling_bot(self, event, sender_id: str) -> bool:
        """发话者是否同后端的其它 bot 账户（平台在册账户且不是本事件自己的账户）。

        别家后端的 bot 框架层面不可见——不做名单登记，是否 bot 由 AI 从行为
        自行判断（提示词认知条款，见 identity_other_agents / judge prompt）。
        """
        sender = str(sender_id or "")
        if not sender:
            return False
        try:
            me = str(event.get_self_account_id() or "")
            if sender == me:
                return False
            platform = str(event.get_platform() or "")
            bots = self.sdk.adapter.list_bots(platform) or {}
            per = bots.get(platform, bots) if isinstance(bots, dict) else {}
            return isinstance(per, dict) and sender in {str(k) for k in per}
        except Exception:
            return False

    def _dup_delivery_gate(self, event, text: str) -> bool:
        """同账户重复投递去重：适配器重试/回声会把同一条消息再投一次。

        只认"真实投递身份"：message_id 或事件时间戳与上一份完全一致才算重复
        （人类重发/连发必然是新 id 新时间戳，不受影响；不同账户各回各的，不在此限）。
        两者都拿不到的事件不做判定（无法区分，宁可不拦）。
        返回 True=继续处理，False=重复投递丢弃。
        """
        account = str(event.get_self_account_id() or "")
        now = time.time()
        mid = str(event.get("message_id") or "") if hasattr(event, "get") else ""
        ts = event.get("time") if hasattr(event, "get") else None
        if not mid and not ts:
            return True
        import re as _re

        fp = "{}:{}:{}:{}".format(
            event.get_platform() or "",
            str(event.get_group_id() or "") if event.is_group_message() else "",
            event.get_user_id() or "",
            _re.sub(r"\s+", "", str(text or ""))[:120],
        )
        identity = mid or f"{fp}@{ts}"
        key = f"{account}:{identity}"
        claims = getattr(self, "_msg_claims", None)
        if claims is None:
            claims = {}
            self._msg_claims = claims
        if len(claims) > 256:
# 值是纯 float 时间戳（见下方写入），不是元组——下标访问会在容量清理时
# 炸掉后续每一条消息（'float' object is not subscriptable，bot 全哑）
            claims = {k: v for k, v in claims.items() if now - v < DUP_DELIVERY_WINDOW}
            self._msg_claims = claims
        seen = claims.get(key)
        if seen and now - seen < DUP_DELIVERY_WINDOW:
            return False
        claims[key] = now
        return True

    def _should_trigger(self, event, chat_key: str, text: str, quoted_me: bool = False) -> bool:
        if chat_key in self.takeover:
            return True
        if event.is_private_message():
            return bool(getattr(self.cfg, "reply_private", True))
        if event.is_group_message():
            if getattr(self.cfg, "reply_at", True) and (event.is_at_message() or quoted_me):
                return True
            for prefix in getattr(self.cfg, "wake_prefixes", []) or []:
                if prefix and text.startswith(prefix):
                    return True
        return False

    def _sender_muted(self, chat_key: str, event) -> bool:
        """用户级屏蔽早闸：管理员豁免；屏蔽中的用户整条消息直接丢弃。"""
        sender_id = str(event.get_user_id() or "")
        if not sender_id:
            return False
        if self.is_admin(sender_id, "chat", event.get_platform() or ""):
            return False
        store = getattr(self.sessions, "user_mutes", None)
        if store is None:
            return False
        return store.get(chat_key, sender_id) is not None

    def _mutes_note(self, chat_key: str) -> str:
        """活跃屏蔽的场景告知：让模型知道哪些人被自己屏蔽、收不到 TA 的消息。"""
        store = getattr(self.sessions, "user_mutes", None)
        if store is None:
            return ""
        entries = store.active(chat_key)
        if not entries:
            return ""
        items = "、".join(
            f"{e.get('user_id')}（{(e.get('reason') or '未记录原因')}）" for e in entries[:8]
        )
        return texts.t("scene_user_mutes", items=items)

    async def _on_message(self, event) -> None:
        try:
            if event.get("replayed"):
                return
# H2 回声过滤：适配器把 bot 自己发出的消息回投成事件时直接丢弃——
# 不参与合并、不作为新触发源、也不进旁听流（否则插件会看到假消息）
            if is_self_event(self.cfg, self.sdk, event):
                return
            text = (event.get_alt_message() or "").strip()
            if self._is_command_message(event, text):
                return
            self._cleanup_takeovers()
            chat_key = self._chat_key_of(event)
# 身份迁移：跨平台/换号后旧键映射到新键——历史/人格/记忆/事实全部跟随
# （映射在路由解析之前应用，映射目标自身仍可再走路由）
            chat_key = self.sessions.resolve_identity(chat_key)
            routed = self.sessions.resolve_route(chat_key)
            if routed:
                chat_key = routed
# mute/白名单早闸：屏蔽会话与白名单外会话整条消息丢弃（回复+旁听都不做）。
# 放在路由解析之后：策略键跟随的是最终会话键；命令消息已在更早的 _is_command_message
# 让路（/qvq unmute 仍可用），走到这里的不会是命令
            if not listen_allowed(self.cfg, self.sdk, chat_key):
                self.logger.debug(f"listen blocked by policy ({chat_key})")
                return
# 用户级屏蔽：被 AI/管理员屏蔽的用户整条丢弃——不旁听、不进 observe、不触发、不进历史。
# 管理员永不被屏蔽；命令消息已在更早的 _is_command_message 让路
            if self._sender_muted(chat_key, event):
                self.logger.debug(f"sender muted by user-mute ({chat_key})")
                return
# H3 硬打断：本会话还有未发完的分段时，新消息命中强信号 → 丢弃剩余段
            try:
                await self._maybe_interrupt(event, chat_key, text)
            except Exception as e:
                self.logger.debug(f"interrupt check failed: {e}")
#  扩展点 A：qvq.observe 旁听通道——命令过滤后、触发判定前广播纯数据载荷
# （含未触发回复的消息，插件借此观察全部群聊；异常吞掉不打断主流程）
# 跨账户同消息仲裁：多账户部署同一条群消息只允许一个账户接手（@ 优先）
            if not self._dup_delivery_gate(event, text):
                return
# 同后端兄弟 bot 判定（拟人化 bot 互聊的前提），observe 载荷带上标记
            sender_id = str(event.get_user_id() or "")
            sibling = self._is_sibling_bot(event, sender_id)
# 隐私开关：会话开了 listen_off 就不向第三方广播本群消息（Stalker/插话随之静音）
            if not self.sessions.get_flag(chat_key, "listen_off"):
                try:
                    is_group = event.is_group_message()
                    await self.sdk.lifecycle.emit(
                        "qvq.observe",
                        {
                            "chat_key": chat_key,
                            "platform": event.get_platform() or "",
                            "detail_type": "group" if is_group else "private",
                            "group_id": str(event.get_group_id() or "") if is_group else "",
                            "sender_id": str(event.get_user_id() or ""),
                            "sender_name": self._sender_name(event),
                            "text": text,
                            "is_group": is_group,
                            "at_bot": bool(event.is_at_message()),
                            "sender_is_bot": sibling,
                            "reply_to_bot": False,
                            "is_command_prefix": False,
                            "images": self._extract_images(event),
                            "is_reply": any(
                                isinstance(seg, dict) and seg.get("type") == "reply"
                                for seg in (event.get_message() or [])
                            ),
                            "reply_message_id": next(
                                (
                                    str(seg.get("data", {}).get("message_id") or "")
                                    for seg in (event.get_message() or [])
                                    if isinstance(seg, dict) and seg.get("type") == "reply"
                                ),
                                "",
                            ),
                            "ts": time.time(),
                        },
                    )
                except Exception as e:
                    self.logger.debug(f"emit qvq.observe failed: {e}")
# bot 互聊（拟人化）：关闭时兄弟 bot 的消息只旁听不响应；
# 开启也只连续陪聊 3 轮就收口，等真人发言重置（防两个 bot 绕圈）
            if sibling and not bool(getattr(self.cfg, "bot_cross_talk", True)):
                return
            if sibling:
                chain = getattr(self, "_bot_chain", None)
                if chain is None:
                    chain = {}
                    self._bot_chain = chain
                count = int(chain.get(chat_key, 0))
                if count >= 3:
                    return
                chain[chat_key] = count + 1
            else:
                chain = getattr(self, "_bot_chain", None)
                if chain is not None and chain.get(chat_key):
                    chain[chat_key] = 0
# 引用=艾特：有人引用本账户的消息等同被点名。懒判定——只在群聊、未被 @
# 且带引用段时才向适配器拉取被引用消息，控制 get_msg 调用频率
            quoted_me = False
            if event.is_group_message() and not event.is_at_message() and self._has_reply_segment(event):
                quoted_me = await self._quote_targets_me(event)
# 触发规则（会话级覆盖全局）：off 不响应 / lurk 只旁听（observe 已发出）/ at_only 群里仅点名
            mode = self._trigger_mode_of(chat_key)
            if mode in ("off", "lurk"):
                return
            if mode == "at_only" and event.is_group_message() and not self._is_direct_address(event, text, quoted_me):
                return
            if not self._should_trigger(event, chat_key, text, quoted_me):
#  扩展点 B：未被 @/前缀命中时问询参与决策提供者（默认关闭），
# speak 则过输出预算后以 origin="plugin" 进入聚合回复，不消耗发送者限频
                manager = getattr(self, "participation", None)
                if (
                    manager is not None
                    and bool(getattr(self.cfg, "participation_enabled", False))
                    and event.is_group_message()
                    and manager.chat_allowed(chat_key)
# 高负载降载：并发闸门满载或本会话正在处理时跳过问询——
# 插话是可选行为，绝不能和用户的直接提问抢资源
                    and not self._interject_overloaded(chat_key)
# 超限且未开自动低token时跳过问询：decide 本身是一次模型调用，
# 插话回合反正会被限额拦截，问询就白花了（开了超限自动进低token则照常问询、插话走便宜链路）
                    and not (
                        self._over_token_limit(chat_key)
                        and not bool(getattr(self.cfg, "budget_auto_on_limit", False))
                    )
                ):
                    decision = await manager.decide(chat_key, event, text)
                    if isinstance(decision, dict):
                        await self._interject(manager, event, chat_key, text, decision)
                return
            if event.is_group_message() and not self.sessions.member_allowed(
                chat_key, str(event.get_user_id() or ""), event.get_platform() or ""
            ):
                return
            event.done()
            sender_for_quota = str(event.get_user_id() or "")
            if not self._user_quota_allow(chat_key, sender_for_quota, event):
                return
            if not self._rate_allow(chat_key, sender_for_quota, event):
                return
            images = self._extract_images(event)
            self._batch_message(event, chat_key, text, images)
        except Exception:
# 完整堆栈：'float' object is not subscriptable 这类信息不带行号没法定位。
# 注意 LoggerChild 无 exception 方法（__getattr__ 会把 .exception 变成子 logger，
# 一调用就是 'LoggerChild' object is not callable）——用 error + format_exc
            self.logger.error("on_message failed:\n" + traceback.format_exc())

    def _command_yields(self) -> list[str]:
        """命令让路前缀表：配置 command_prefixes ∪ 框架命令系统当前配置的前缀。

        本处理器在框架分发器（priority=100）之上运行，is_command() 在我们的优先级
        还未打标——必须按前缀自己让路。框架前缀支持自定义（如 qvqchat），动态读取
        而不是硬编码，部署者改前缀后无需同步本模块配置。长前缀优先匹配。
        """
        prefixes = [str(p) for p in (getattr(self.cfg, "command_prefixes", []) or []) if p]
        try:
            from ErisPulse.Core.Event import command as _command

            fw = getattr(_command, "prefix", "")
            if isinstance(fw, str):
                prefixes.append(fw)
            elif isinstance(fw, (list, tuple)):
                prefixes.extend(str(p) for p in fw)
        except Exception:
            pass
        return sorted({p for p in prefixes if p}, key=len, reverse=True)

    def _is_command_message(self, event, text: str) -> bool:
        """命令消息让路判定：让分发器处理，本处理器不认领不拦截。"""
        if event.is_command():
            return True
        return any(text.startswith(p) for p in self._command_yields())

    def _interject_overloaded(self, chat_key: str) -> bool:
        """插话降载判定：并发闸门满载 / 本会话锁被占 / 本会话有任务在跑。"""
        pool = getattr(self, "pool", None)
        gate = getattr(pool, "gate", None)
        if gate is not None and gate.saturated:
            return True
        if self._lock_for(chat_key).locked():
            return True
        registry = getattr(self, "live_registry", None)
        if registry is not None and registry.busy(chat_key):
            return True
        return False

    async def _interject(self, manager, event, chat_key: str, text: str, decision: dict) -> None:
        """参与决策 speak 后的插话落地：成员准入按会话整体判断 → 输出预算 → 聚合入队。

        预算/准入拒绝不发消息，仅记决策观测（qvq.participation 事件 + 环形日志）。
        """
        budget_ok, budget_reason = True, ""
        if decision.get("speak"):
            sender_id = str(event.get_user_id() or "")
# 成员准入（按会话整体）：白名单非 * 时仅名单内发送者可作为插话由头
            if not self.sessions.member_allowed(chat_key, sender_id, event.get_platform() or ""):
                budget_ok, budget_reason = False, texts.t("participate_member_denied")
            else:
                budget_ok, budget_reason = manager.budget.allow(chat_key, "interject")
                if budget_ok:
                    manager.budget.record(chat_key, "interject")
                    event.done()# 插话由头不消耗发送者 _rate_allow 限额
                    self._batch_message(
                        event, chat_key, text, self._extract_images(event), origin="plugin"
                    )
        entry = {
            "kind": "interject",
            "chat_key": chat_key,
            "decision": "speak" if decision.get("speak") else "silent",
            "reason": budget_reason or str(decision.get("reason") or ""),
            "provider": str(decision.get("provider") or ""),
            "providers_queried": list(decision.get("providers_queried") or []),
            "score": decision.get("score"),
            "budget_ok": budget_ok,
            "ts": time.time(),
        }
        manager.log_decision(entry)
        try:
            await self.sdk.lifecycle.emit(
                "qvq.participation",
                {key: value for key, value in entry.items() if key != "kind"},
            )
        except Exception as e:
            self.logger.debug(f"emit qvq.participation failed: {e}")

    @staticmethod
    def _sender_name(event) -> str:
        try:
            name = event.get_user_nickname()
            if name:
                return str(name)
        except Exception:
            pass
        try:
            sender = event.get_sender()
            if isinstance(sender, dict):
                return str(sender.get("nickname") or sender.get("card") or "")
        except Exception:
            pass
        return ""

    async def _resolve_group_name(self, event, chat_key: str, group_id: str) -> str:
        if not group_id:
            return ""
        name = str(event.get("group_name") or "")
        if name:
            self.sessions.set_group_name(chat_key, name)
            return name
        cached = self.sessions.group_name_of(chat_key)
        if cached:
            return cached
        adapter = self.sdk.adapter.get(event.get_platform() or "")
        if adapter is None:
            return ""
        try:
            info = await adapter.call_api("get_group_info", group_id=group_id)
# 兼容两种形态：有信封（{status, data:{group_name}}）取 data 层，无信封直接取顶层
            payload = info if isinstance(info, dict) else {}
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            name = str(data.get("group_name") or "")
        except Exception as e:
            self.logger.debug(f"get_group_info failed: {e}")
            name = ""
        if name:
            self.sessions.set_group_name(chat_key, name)
        return name

    async def _auto_interrupt_decide(self, chat_key: str, old_live, new_text: str) -> tuple[str, str, str]:
        """auto 模式的三选判定：cheap 模型结合当前任务与新消息给出决定。

        返回 (decision, 理由, 人设化话术)。decision 三选：
        demote=旧任务转后台子智能体续跑、新消息立即处理 / interrupt=旧任务作废 / queue=跑完再处理。
        话术给用户看（"先回你这个，那个排着"），机制术语不外露；queue 的话术留空（完全静默）。
        任何失败回退 ("queue", "fallback", "")——宁可排队也不要误杀正在跑的任务。
        """
# 高负载降载：并发满载时不发判定调用（它本身也是一次模型请求），直接排队——
# 排队本就是安全默认，把并发槽位留给正在跑的任务与用户直答
        pool = getattr(self, "pool", None)
        if pool is not None and callable(getattr(pool, "background_blocked", None)) and pool.background_blocked():
            if bool(getattr(self.cfg, "log_debug", False)):
                self.logger.debug("background skip: interrupt-decide (saturated) -> queue")
            return "queue", "saturated-skip", ""
# 低token模式：判定也是一次模型调用——直接静默入队（旧任务继续跑，忙完合并处理），
# 少一次请求、少一条回执；需要抢救旧任务的用户用 /qvq 命令或直接说停
        if bool(getattr(self.cfg, "budget_mode", False)):
            return "queue", "budget-skip", ""
        try:
            current = utils.truncate(str(old_live.text or "").strip(), 500) or "（工具执行中，暂无输出）"
            incoming = utils.truncate(str(new_text or "").strip(), 400)
# 最近对话上下文：判定必须知道"这条新消息在回应什么/是否在纠正刚才的话"，
# 只看当前任务输出+新消息会把"同意/停/不是这个"之类短回复判错
            recent_lines: list[str] = []
            try:
                for msg in list(self.sessions.get_contexts(chat_key) or [])[-5:]:
                    if not isinstance(msg, dict):
                        continue
                    role = str(msg.get("role") or "")
                    content = msg.get("content")
                    if isinstance(content, list):
                        content = " ".join(
                            str(p.get("text") or "") for p in content if isinstance(p, dict)
                        )
                    text = utils.truncate(str(content or "").strip(), 200)
                    if not text:
                        continue
                    if role in ("bot", "assistant"):
                        recent_lines.append("[bot] " + text)
                    else:
                        sender = str(msg.get("sender_name") or msg.get("sender") or "")
                        recent_lines.append((sender + ": " if sender else "") + text)
            except Exception:
                recent_lines = []
            recent_block = ""
            if recent_lines:
                recent_block = "<recent-chat>\n" + "\n".join(recent_lines) + "\n</recent-chat>\n\n"
            from ..engine.base import ChatRequest, TaskSpec

            request = ChatRequest(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "A bot is mid-task when a NEW user message arrives. Decide ONE of three: "
                            "demote — the new message is an independent request/question unrelated to the "
                            "running task and the task still needs a while: move the old task to a "
                            "background sub-agent and handle the new message right now; "
                            "interrupt — the new message corrects/cancels/asks to stop the running task, "
                            "or answers a question the bot asked (e.g. agreeing to a pending confirmation): "
                            "discard the old task; "
                            "queue — casual chat or something that belongs to the running task itself: "
                            "handle it after the task finishes, no receipt needed. "
                            "Use <recent-chat> to tell what the new message is replying to. "
                            'Reply ONLY with JSON: {"decision":"demote"|"interrupt"|"queue",'
                            '"reason":"short why",'
                            '"line":"one short in-persona sentence telling the user what happens (only for '
                            'demote/interrupt; leave empty for queue, no jargon)"}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            recent_block
                            + "<current-task>\n" + current + "\n</current-task>\n\n"
                            + "<new-message>\n" + incoming + "\n</new-message>"
                        ),
                    },
                ],
                tools=None,
                temperature=0.0,
                max_tokens=160,
            )
            response = await self.pool.dispatch(TaskSpec(kind="compact", prefer="cheap"), request)
            import json as _json
            import re as _re

# 先剥思考链再提 JSON：cheap 模型的思考混在正文里，直接正则会捞到思考里的花括号
            cleaned = _THINK_RE.sub("", response.content or "")
            m = _re.search(r"\{[\s\S]*\}", cleaned)
            if m:
                data = _json.loads(m.group(0))
                decision = str(data.get("decision") or "").lower()
                if decision in ("demote", "interrupt", "queue"):
                    self.logger.info(f"auto interrupt decision ({chat_key}): {decision} — {data.get('reason', '')}")
                    return decision, str(data.get("reason") or ""), str(data.get("line") or "").strip()
        except Exception as e:
            self.logger.debug(f"auto interrupt decide failed, fallback queue: {e}")
        return "queue", "fallback", ""

    def _enqueue_waiting(self, chat_key: str, event, items: list, announce: bool = True) -> None:
        queue = self._waiting.setdefault(chat_key, [])
# 回执合一：每条新消息至多一条回执。auto 路径回执由判定话术承担（announce=False 全静默入队）；
# queue 模式只在队列为空的第一条播报（后续静默，反正任务结束后会被合并处理），say_mode=off 也不播
        first = not queue
        queue.append((event, items))
        self.logger.info(f"chat busy, message queued ({chat_key}, {len(queue)} waiting)")
        if announce and first and str(getattr(self.cfg, "interrupt_say_mode", "persona") or "persona") != "off":
            self.spawn(self._announce_queued(chat_key, event, items))

    async def _announce_queued(self, chat_key: str, event, items: list) -> None:
        """排队回执（仅 queue 模式第一条）：cheap 模型生成一句人设化话术。

        只认 JSON 输出并先剥思考链——直接回发响应原文会把 cheap 模型的
        整段思考跟着进了群（思考泄露事故根因）；line 一律截到 80 字，失败回退固定模板。
        """
        incoming = " ".join(str(i.get("text") or "") for i in items if i.get("text"))
        registry = getattr(self, "live_registry", None)
        current = ""
        live = registry.get(chat_key) if registry else None
        if live is not None:
            current = str(live.text or "")[-300:]
        prompt = (
            "机器人正在执行一个未完成的长任务，这条新消息已排入队列、任务完成后就会处理。"
            "任务最近的输出摘要是：" + (current or "（尚无输出）")
            + "。新消息：" + incoming[:150] + "。"
            'Reply ONLY with JSON: {"line":"以机器人自己的口吻写一句话：简单说明正在做什么，'
            '并告知消息已排上、忙完就处理；不调用任何工具"}'
        )
        line = ""
        try:
# A2: 排队播报迁 TaskSpec 分派（kind=announce，成本偏好 cheap），池无 dispatch 时回退 pool.chat
            request = ChatRequest(messages=[{"role": "user", "content": prompt}], max_tokens=120, temperature=0.7)
            dispatch = getattr(self.pool, "dispatch", None)
            if callable(dispatch):
                response = await dispatch(TaskSpec(kind="announce", prefer="cheap"), request)
            else:
                response = await self.pool.chat(request)
            line = _json_line_of(response.content or "")
        except Exception as e:
            self.logger.warning(f"queue announce failed: {e}")
        if not line:
            line = texts.t("interrupt_auto_queue")
        try:
            await event.reply(line[:80])
        except Exception as e:
            self.logger.warning(f"queue announce reply failed: {e}")

    def _drain_waiting(self, chat_key: str) -> None:
        self._merge_timers.pop(chat_key, None)
        queue = self._waiting.pop(chat_key, None)
        if not queue:
            return
# 队列整体合并为一个回合：条目预构建并保留各自发言人归属（逐条 _batch_message
# 会开 N 个连续回合逐条作答——正是"短时多条每条都回"的来源之一）
        merged_items: list = []
        last_event = queue[-1][0]
        for event, items in queue:
            for item in (items or []):
                if isinstance(item, dict):
                    merged_items.append(item)
        if not merged_items:
            return
        self._batch_message(last_event, chat_key, "", [], items=merged_items)

    def _lock_for(self, chat_key: str) -> asyncio.Lock:
        lock = self._chat_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_key] = lock
        return lock

    def _is_self_event(self, event) -> bool:
        """自身出站回环判定：sender 等于平台 self_id 或适配器 bot id 即视为回声。"""
        if not bool(getattr(self.cfg, "humanize_echo_filter", True)):
            return False
        sender = str(event.get_user_id() or "")
        if not sender:
            return False
        for probe in (
            lambda: event.get_self_account_id(),
            lambda: event.get("self_id"),
        ):
            try:
                value = probe()
            except Exception:
                value = None
            if value and str(value) == sender:
                return True
        try:
            adapter = self.sdk.adapter.get(event.get_platform() or "")
        except Exception:
            adapter = None
        for attr in ("self_id", "bot_id", "get_self_id"):
            value = getattr(adapter, attr, None)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = None
            if value and str(value) == sender:
                return True
        return False

    @staticmethod
    def _debounce_window(cfg, is_group: bool, is_at: bool) -> float:
        """H2 防抖分级：私聊沿用 aggregate_window；群聊普通消息用群窗口，@ 触发压短。"""
        base = float(getattr(cfg, "aggregate_window", 5.0) or 0)
        if not is_group:
            return base
        group = float(getattr(cfg, "debounce_group_seconds", 2.0) or 0)
        if group <= 0:
            group = base
        if is_at:
            mention = float(getattr(cfg, "debounce_mention_seconds", 1.0) or 0)
            if mention > 0:
                return mention
        return group

    def _batch_message(self, event, chat_key: str, text: str, images: list,
                       origin: str = "chat", items: list | None = None) -> None:
        entry = self._pending.setdefault(chat_key, {"items": [], "event": event, "timer": None})
# origin（chat/plugin）随聚合条目传递，进 ToolContext 记账可观测
        entry.setdefault("origin", origin)
# 入队时间戳：陈旧插话丢弃的依据（首个到达时间，聚合不刷新）
        entry.setdefault("ts", time.time())
        if items is not None:
# 预构建条目（等待队列合并回灌）：各自保留发言人归属，整批进同一回合，
# 首次入箱时已做短窗去重，此处不重复检查
            entry["items"].extend(dict(i) for i in items if isinstance(i, dict))
            entry["event"] = event
        else:
# 短窗去重：多账户同群双投递/适配器重放会在同一会话插入重复文本（用户看到多条重复）。
# 仅在多账户生效（与 @账户 后缀同条件）——单账户场景不做去重，不误伤人类复读
            sender_id = str(event.get_user_id() or "")
# 短窗去重只用于群消息：双投递（同后端多账户各收一条同群消息）只发生在群聊，
# 私聊是点对点无此面；恒开会误吞单账户用户的正常复读
            multi_account = bool(getattr(self.cfg, "account_isolation", True)) or                 bool(_account_suffix_for(self.cfg, self.sdk, event))
            if event.is_group_message() and multi_account and str(text or "").strip()                 and _dup_recent(chat_key, sender_id, str(text)):
                self.logger.debug(f"duplicate incoming dropped ({chat_key})")
                return
            entry["items"].append(
                {
                    "text": text,
                    "images": images,
                    "sender_id": sender_id,
                    "sender_name": self._sender_name(event),
                }
            )
            entry["event"] = event
        if entry["timer"] is None:
            try:
                is_group = event.is_group_message()
            except Exception:
                is_group = False
            try:
                is_at = event.is_at_message()
            except Exception:
                is_at = False
            window = debounce_window(self.cfg, is_group, is_at)
            if window <= 0:
                entry["timer"] = self.spawn(self._flush_pending(chat_key))
            else:
                entry["timer"] = self.spawn(self._flush_later(chat_key, window))

    async def _flush_later(self, chat_key: str, window: float) -> None:
        await asyncio.sleep(window)
        await self._flush_pending(chat_key)

    async def _flush_pending(self, chat_key: str) -> None:
        entry = self._pending.pop(chat_key, None)
        if not entry:
            return
# 陈旧插话丢弃：多人洪流里等到锁时话题早已翻页——插话（origin=plugin）等太久
# 就不追了；用户直接触发（@/前缀/私聊）永不丢弃，再久也要答
        origin = entry.get("origin", "chat")
        if origin == "plugin":
            stale_after = float(getattr(self.cfg, "interject_stale_seconds", 90) or 0)
            if stale_after > 0 and time.time() - float(entry.get("ts") or 0) > stale_after:
                self.logger.debug(f"stale interject dropped ({chat_key})")
                return
# 回复合并窗口：刚回复过的会话先不开新回合——窗口内陆续到达的消息挂入等待队列，
# 窗口走完后合并为一次后续回复（短时多条不逐条应答，防止刷屏式复读轰炸）
        merge_window = float(getattr(self.cfg, "reply_merge_window", 0) or 0)
        if merge_window > 0:
            last = float(self._last_reply_ts.get(chat_key, 0.0) or 0.0)
            remain = merge_window - (time.time() - last)
            if remain > 0:
                queue = self._waiting.setdefault(chat_key, [])
                queue.append((entry["event"], entry["items"]))
                self._arm_merge_timer(chat_key, remain)
                self.logger.info(f"reply merge window holding ({chat_key}, {len(queue)} waiting, {remain:.1f}s left)")
                return
# 长任务冲突判定必须在锁外：per-chat 锁被运行中的任务整轮持有，
# 锁内再看 live 已等任务跑完，auto 判定会失效
        if not await self._live_conflict(chat_key, entry["event"], entry["items"]):
            return
# per-chat 锁真正生效——聚合触发与定时任务/面板并发互斥，防止交错写上下文
        async with self._lock_for(chat_key):
            await self._process_locked(entry["event"], entry["items"], chat_key, origin)

    async def _handle_auto_decision(self, chat_key: str, event, items: list, old_live,
                                    decision: str, line: str, labeled: str = "") -> bool:
        """auto 三选判定（demote/interrupt/queue）的统一收尾：回执 + 旧任务去向。

        返回 True = 现在处理新消息（demote/interrupt）；False = 已静默入队（queue）。
        回执合一：decide 的话术就是唯一回执——queue 完全静默（line 即便非空也丢弃，
        不再叠加排队播报二连发）；demote/interrupt 按 say_mode 决定人设话术还是固定模板。
        """
        if decision == "queue":
# 闲聊或属于任务本身：跑完合并处理即可，静默入队不打扰
            self._enqueue_waiting(chat_key, event, items, announce=False)
            return False
        say_style = str(getattr(self.cfg, "interrupt_say_mode", "persona") or "persona")
        if decision == "demote":
# 让路后台：任务文本取发起时的原始 prompt（live.prompt），缺失才兜底已有输出开头
            task_text = utils.truncate(str(getattr(old_live, "prompt", "") or "").strip(), 800)
            if not task_text:
                task_text = (
                    utils.truncate(str(old_live.text or "").strip(), 200)
                    + "（原任务文本缺失，以下是已产生输出）"
                )
            partial = utils.truncate(str(old_live.text or "").strip(), 1500)
            old_live.cancel()
            try:
                await demote_to_background(
                    main=self, event=event, chat_key=chat_key,
                    task_prompt=texts.t("demote_task_prompt", task=task_text, partial=partial or "（尚无输出）"),
                )
            except Exception as e:
# 降级失败不阻断新消息处理：旧任务已取消，日志留痕便于排查
                self.logger.warning(f"demote to background failed ({chat_key}): {e}")
        else:
# interrupt：中断上下文留给即将开始的新回合（模型知道上一轮做到哪被叫停了）
            current = str(getattr(old_live, "text", "") or "").strip()
            if current:
                if not hasattr(self, "_interrupted_notes"):
                    self._interrupted_notes = {}
                self._interrupted_notes[chat_key] = texts.t(
                    "interrupted_note", content=utils.truncate(current, 500)
                )
            old_live.cancel()
            self.logger.info(f"live task interrupted for new message ({chat_key}): mode=auto")
# 回执（demote/interrupt 才发）：off 静默 / plain 固定模板 / persona 优先话术、空则回退模板
        if say_style != "off":
            reply = line if (say_style != "plain" and line) else texts.t(
                "interrupt_auto_demote" if decision == "demote" else "interrupt_auto_stop"
            )
            if reply:
                try:
                    await event.reply(reply)
                except Exception:
                    pass
        return True

    async def _live_conflict(self, chat_key: str, event, items: list) -> bool:
        """任务运行中收到新消息：按 interrupt_mode 决定让路（demote/interrupt）还是排队。

        返回 True = 现在就该处理这条消息（无任务或已让路）；
        返回 False = 已排入等待队列，等当前任务结束后合并处理。
        """
        registry = getattr(self, "live_registry", None)
        live = registry.get(chat_key) if registry is not None else None
        if live is None or live.status != "running":
            return True
# 显式停止词最先判定：任何 interrupt_mode（含 queue）下"停停停"都必须打断——
# 队列模式把停止词也排进队等于没有停止通道；免判定还省一次模型调用
        incoming_text = " ".join(str(i.get("text") or "") for i in items if isinstance(i, dict) and i.get("text"))
        if _is_stop_phrase(incoming_text):
            current = str(getattr(live, "text", "") or "").strip()
            if current:
                if not hasattr(self, "_interrupted_notes"):
                    self._interrupted_notes = {}
                self._interrupted_notes[chat_key] = texts.t(
                    "interrupted_note", content=utils.truncate(current, 500)
                )
            live.cancel()
            self.logger.info(f"live task interrupted by stop phrase ({chat_key})")
            return True
        mode = str(getattr(self.cfg, "interrupt_mode", "auto") or "auto")
        if mode == "queue":
            self._enqueue_waiting(chat_key, event, items)
            return False
        if mode == "auto":
            incoming = " ".join(str(i.get("text") or "") for i in items if isinstance(i, dict) and i.get("text"))
            decision, _why, line = await self._auto_interrupt_decide(chat_key, live, incoming)
            return await self._handle_auto_decision(chat_key, event, items, live, decision, line, labeled=incoming)
# interrupt 模式（纯中断）：cancel + interrupted_note，语义保持现状
        current = str(getattr(live, "text", "") or "").strip()
        if current:
            if not hasattr(self, "_interrupted_notes"):
                self._interrupted_notes = {}
            self._interrupted_notes[chat_key] = texts.t(
                "interrupted_note", content=utils.truncate(current, 500)
            )
        live.cancel()
        self.logger.info(f"live task interrupted for new message ({chat_key}): mode={mode}")
        return True

    def _arm_merge_timer(self, chat_key: str, delay: float) -> None:
        """合并窗定时器：到点把等待队列回灌为一个聚合回合。已有定时器则续用（消息继续挂队）。"""
        if chat_key in self._merge_timers:
            return

        async def _merge_fire() -> None:
            self._merge_timers.pop(chat_key, None)
            self._drain_waiting(chat_key)

        self._merge_timers[chat_key] = self.spawn(_merge_fire())

    async def _process_locked(self, event, items: list, chat_key: str, origin: str = "chat") -> None:
        try:
# H3 响应预算：从生成开始计时，发送层据此降级打字延迟
            try:
                self.delivery.begin_budget(chat_key, float(getattr(self.cfg, "humanize_budget_seconds", 7.0) or 0))
            except Exception:
                pass
            ctx = self._chat_ctx(event, chat_key, origin)
# 群判定兜底：通知/请求事件（如群内戳一戳）没有 is_group_message 的会话语义，
# 但带 group_id——按群场景处理（is_private_message 排除假 group_id 的私聊桩）
            is_group = event.is_group_message() or (
                not event.is_private_message() and bool(str(event.get_group_id() or ""))
            )
            sender_id = str(event.get_user_id() or "")
            sender_name = self._sender_name(event)
            group_id = str(event.get_group_id() or "") if is_group else ""
            if getattr(self.cfg, "owner_only", False) and not self.is_admin(sender_id, "chat", event.get_platform() or ""):
                await event.reply(texts.t("owner_only_msg"))
                return
            scene = ""
            if is_group:
                group_name = await self._resolve_group_name(event, chat_key, group_id)
                if group_name:
                    scene = texts.t("scene_group", name=group_name, id=group_id)
                elif group_id:
                    scene = texts.t("scene_group_noid", id=group_id)
                if getattr(self.cfg, "scene_platform_prefix", True):
                    scene = texts.t("scene_platform_line", platform=str(event.get_platform() or "")) + scene
                scene += texts.t("scene_speaker_note")
# 触发来源认知：插件插话（origin=plugin）不是"有人在跟你说话"——否则模型会当成被点名
                if origin == "plugin":
                    scene += texts.t("scene_plugin_trigger", name=sender_name or sender_id, id=sender_id)
                else:
                    # 发言者认知：明确"当前说话的人"，防止把历史对话者误认成当前发言者
                    scene += texts.t("scene_group_attribution", name=sender_name or sender_id, id=sender_id)
                    # 提及感知 + 拟人语气：@ 命中是分内问答，未 @（旁听/插件插话）要像群友随口接话
                    if event.is_at_message():
                        scene += texts.t("scene_at_direct")
                    else:
                        scene += texts.t("scene_at_narrate")
                # 引用回复认知：优先注入被引原文，提取不到再退回泛化提示
                if any(isinstance(seg, dict) and seg.get("type") == "reply" for seg in (event.get_message() or [])):
                    quoted = await self._quote_content(event)
                    if quoted:
                        scene += texts.t("scene_quote_content", content=quoted)
                    else:
                        scene += texts.t("scene_quote_note")
# 场景注记随 ctx 走：spawn_agent 时注入子智能体（群名/发言人/触发方式）
                ctx.scene_note = scene
# 群语气画像：后台学习出的本群说话风格（很小的一段，低token也不影响语气一致性）
                group_style = self.sessions.group_style_of(chat_key)
                if group_style:
                    scene += texts.t("scene_group_style", style=group_style)
                if getattr(self.cfg, "group_isolation", False):
                    scene += texts.t("scene_isolation_note")
            else:
                if sender_name:
                    scene = texts.t("scene_private", name=sender_name, id=sender_id)
# 活跃屏蔽告知（群/私聊都注入）：模型知道自己屏蔽了谁，且收不到 TA 的消息
            mutes_note = self._mutes_note(chat_key)
            if mutes_note:
                scene += mutes_note
# 非消息事件来源注记（通知/请求唤醒的回合）：让模型知道这不是用户发言
            ev_type = ""
            try:
                ev_type = str(event.get_type() or "")
            except Exception:
                ev_type = ""
            if ev_type and ev_type != "message":
                scene += texts.t("scene_notice_trigger", summary=self._event_summary(event, ev_type))
                ctx.scene_note = scene
# 本账户身份认知：多账户部署下让 AI 明确"现在说话的这个账户是谁"，
# @ 的 id 与自己 user_id 不同时知道是在喊别人（防代替回应/认错历史）。
# 放在 scene 全部组装完之后、统一写回 ctx（群聊分支的赋值在更早处）
            try:
                getter = getattr(event, "get_self_user_id", None)
                self_uid = str(getter() or "") if callable(getter) else ""
                self_acct = str(event.get_self_account_id() or "")
                self_nick = str(event.get_user_nickname() or "")
                if self_uid or self_acct:
                    scene += texts.t("scene_self_identity", user_id=self_uid or "-", nickname=self_nick or "-", account=self_acct or "-")
            except Exception:
                pass
            ctx.scene_note = scene
            combined_text = "\n".join(str(i.get("text") or "") for i in items if i.get("text"))
            try:
                await self.sdk.lifecycle.emit(
                    "qvq.message",
                    {
                        "chat_key": chat_key,
                        "platform": event.get_platform() or "",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "text": combined_text,
                        "is_group": is_group,
                        "merged": len(items) > 1,
                    },
                )
            except Exception as e:
                self.logger.debug(f"emit qvq.message failed: {e}")
            labeled_parts = []
            all_images: list = []
            for item in items:
                item_text = str(item.get("text") or "")
                if item_text:
                    labeled_parts.append(
                        self.sessions.label_incoming(
                            item_text,
                            sender_id=item["sender_id"] if is_group else "",
                            sender_name=item["sender_name"] if is_group else "",
                        )
                    )
                for image in item.get("images") or []:
                    if len(all_images) < 3:
                        all_images.append(image)
            labeled = "\n".join(labeled_parts)
            images = [
                converted
                for raw in all_images
                for converted in [self._to_model_image(raw)]
                if converted
            ]
            limit = int(getattr(self.cfg, "daily_token_limit", 0) or 0)
            session_budget = int(get_policy(self.sdk, chat_key).get("session_budget") or 0)
            if limit or session_budget:
                used_today = int(self._usage_today().get("tokens", 0) or 0)
                by_chat_today = (self._usage_today().get("by_chat") or {})
                used_session = int(by_chat_today.get(chat_key, 0) or 0)
                admin = self.is_admin(sender_id, "chat", event.get_platform() or "")
                global_over = limit > 0 and used_today >= limit and not admin
                session_over = session_budget > 0 and used_session >= session_budget and not admin
                auto_budget = bool(getattr(self.cfg, "budget_auto_on_limit", False))
                if (global_over or session_over) and not auto_budget:
# 语义分档：插件插话（origin=plugin）是智能体主动发起的——超限态下静默跳过，
# 既不消耗也不给群友回"到达上限"；用户自己触发的回合才拦截并提示（每天每会话至多一次）。
# budget_auto_on_limit 开启时不拦截：超限自动转入低token模式继续对话（见 budget_effective）
                    if origin == "plugin":
                        self.logger.info(f"over token limit, plugin turn skipped ({chat_key})")
                        return
                    notice_key = f"QvQChat:usage:limit_noticed:{time.strftime('%Y-%m-%d')}:{chat_key}"
                    if not self.sdk.storage.get(notice_key, False):
                        self.sdk.storage.set(notice_key, True)
                        if session_over and not global_over:
                            await event.reply(texts.t("session_limit_reached", used=used_session, limit=session_budget))
                        else:
                            await event.reply(texts.t("daily_limit_reached", used=used_today, limit=limit))
                    return
# 锁外中断判定留下的上下文（旧任务被叫停时做到哪）
            interrupted_note = ""
            if getattr(self, "_interrupted_notes", None) is not None:
                interrupted_note = self._interrupted_notes.pop(chat_key, "") or ""
            live = None
            registry = getattr(self, "live_registry", None)
            if registry is not None:
                old_live = registry.get(chat_key)
                if old_live and old_live.status == "running" and old_live.text.strip():
                    mode = str(getattr(self.cfg, "interrupt_mode", "auto") or "auto")
                    if mode == "queue":
                        self._enqueue_waiting(chat_key, event, items)
                        return
                    if mode == "auto":
# AI 三选判定：回执与旧任务去向统一走 _handle_auto_decision（与锁外 _live_conflict 同一套逻辑）
                        decision, _why, line = await self._auto_interrupt_decide(chat_key, old_live, labeled)
                        if not await self._handle_auto_decision(chat_key, event, items, old_live, decision, line, labeled):
                            return
# 中断注记由 helper 写入 _interrupted_notes（与锁外路径同一条管道），这里取回直用
                        if getattr(self, "_interrupted_notes", None):
                            interrupted_note = self._interrupted_notes.pop(chat_key, "") or interrupted_note
                    else:
                        old_live.cancel()
                        interrupted_note = texts.t(
                            "interrupted_note",
                            content=utils.truncate(old_live.text.strip(), 500),
                        )
                live = registry.start(chat_key)
                live.task = asyncio.current_task()
# 任务发起时的原始文本：auto demote 让路时靠它把旧任务转交后台续跑
                live.prompt = labeled
                on_delta, on_reset, on_tool_event, on_reasoning = live_bind(live)
            else:
                on_delta = on_reset = on_tool_event = on_reasoning = None
            prepared = await self.sessions.prepare(
                chat_key,
                labeled,
                images=images,
                scene=scene,
                seed_provider=lambda: self._seed_history(event, chat_key),
                cross_user_id=("" if is_group else sender_id),
                sender_id=sender_id,
                profile_user=(f"{event.get_platform()}:{sender_id}" if sender_id else ""),
            )
            system = prepared["system"]
            contexts = prepared["contexts"]
            user_msg = prepared["user_msg"]
            persona = prepared["persona"]
# 人格级模型参数覆盖（留空=跟模型/全局默认）
            p_temp = _num_or_none(persona.get("temperature"))
            p_maxtok = _num_or_none(persona.get("max_tokens"))
# 首次接触且未发过开场白 → await 先发开场白再进 runner（时序保证）
            await self._maybe_send_opening(event, chat_key, prepared, persona)
            if interrupted_note:
                contexts.append({"role": "user", "content": interrupted_note})
            async def on_tool_round(calls):
                if getattr(self.cfg, "tool_notice_mode", "brief") != "all":
                    return
                labels = [
                    f"{call['name']}({call['arguments']})" if call["arguments"] else call["name"]
                    for call in calls[:3]
                ]
                suffix = " …" if len(calls) > 3 else ""
                await event.reply(texts.t("processing_notice", tools="、".join(labels) + suffix))

            speech_sent = False
            last_speech = ""# 最近一条已投递阶段发言的规范化文本（同回合去重：复述跳过/双胞胎跳过）

            async def on_intermediate(speech):
# 对话风格：off 静默 / first_last 只投第一句开场（其后阶段发言静默，最终结论走正常回复）/
# brief 及以上全部投递。speech_sent 防重：同一轮多次发言只算一次
                nonlocal speech_sent, last_speech
                mode = getattr(self.cfg, "tool_notice_mode", "brief")
                if mode == "off" or (mode == "first_last" and speech_sent):
                    return
                text = utils.truncate(str(speech).strip(), 1200)
# 阶段发言同样不能带假媒体：模型写「[语音] 喵？…」「[表情包]」假装发过媒体、
# 「（语音已发）」假宣告会从这里原样发出，先清扫再投递
                try:
                    text = utils.strip_fake_media_prefix(utils.strip_fake_media_claims(text))
                except Exception as e:
                    self.logger.debug(f"fake media strip failed: {e}")
                if not text:
                    return
# 同回合去重：规范化后与上一条已投递阶段发言相同 → 跳过（模型每轮工具重试
# 都复述同一句话时，brief 档会连发 N 遍）
                normalized = utils.collapse_spaces(text)
                if normalized and normalized == last_speech:
                    return
                try:
# 走投递层单条发送（方法降级+重试链）：裸 event.reply 在部分适配器上不生效，
# 且失败无信号——这正是"普通消息能发、第一句发不出"的根因
                    ok = await self.delivery._send_plain(event, text)
                    if ok:
                        speech_sent = True
                        last_speech = normalized
                    if bool(getattr(self.cfg, "log_debug", False)):
                        self.logger.debug(f"intermediate speech delivered={ok} ({len(text)} chars, mode={mode})")
                except Exception as e:
# 投递失败必须留痕，不能无声消失
                    self.logger.warning(f"intermediate speech send failed: {e}")

# 悬空回复标记：生成开始落盘（记录将送入模型的 labeled 文本），实例崩溃重启后
# 据此重跑该轮；完成/异常/取消均在 finally 清除，保证正常路径无残留
            self.sdk.storage.set(
                INFLIGHT_KEY_PREFIX + chat_key,
                {"text": labeled, "origin": origin, "ts": time.time()},
            )
            try:
                try:
# 会话策略叠加闸门优先级：插话让位于用户直接提问（0=直答 / 6=插话），
# mute 之外还有 low/high 档会话在满载时的让位/抢先（数值小者先拿并发空位）
# 人格级覆盖：prefill 开场白 + temperature/max_tokens（聊天链路无显式参数，人格即覆盖层）
                    policy = get_policy(self.sdk, chat_key)
# 低token生效态（会话 low_token / 超限自动进入）→ chat 回合显式 prefer cheap：
# runner 内只认全局 budget_mode，会话级与自动态在此传入（显式档位不被自动档覆盖）
                    budget_pref = "cheap" if (
                        policy.get("low_token")
                        or (bool(getattr(self.cfg, "budget_auto_on_limit", False)) and self._over_token_limit(chat_key))
                    ) else ""
                    run_coro = self.runner.run(
                        system=system,
                        messages=contexts + [user_msg],
                        ctx=ctx,
                        persona_tools=persona.get("tools"),
                        on_tool_round=on_tool_round,
                        on_intermediate=on_intermediate,
                        on_delta=on_delta,
                        on_reset=on_reset,
                        on_tool_event=on_tool_event,
                        on_reasoning=on_reasoning,
                        priority=apply_priority(policy, 6 if origin == "plugin" else 0),
                        prefer=budget_pref,
                        prefill=str(persona.get("prefill") or ""),
                        temperature=p_temp,
                        max_tokens=int(p_maxtok) if p_maxtok else None,
                    )
# 回合超时（0=关闭）：卡死任务到点收束放行会话，别让整轮锁被永远占着
                    _turn_timeout = float(getattr(self.cfg, "turn_timeout", 0) or 0)
                    result = await asyncio.wait_for(run_coro, timeout=_turn_timeout or None)
                except asyncio.CancelledError:
                    if live is not None:
                        partial, partial_trace, partial_rounds = live.partial_record()
                        if partial:
                            self.sessions.append(chat_key, "assistant", partial, trace=partial_trace, rounds=partial_rounds)
                        live.reply = partial or None
                        live.status = "done"
                        live.publish("done", {"reply": partial, "session": chat_key})
                        live.publish("end", {"status": live.status})
                    raise
                except asyncio.TimeoutError:
# 超时与中断同路收束：部分输出落库、live 置终态（stale 护栏不再判其"忙碌"），
# 异常继续上抛由外层 except 给 chat 来源回错误提示
                    saved = False
                    if live is not None:
                        partial, partial_trace, partial_rounds = live.partial_record()
                        if partial:
                            self.sessions.append(chat_key, "assistant", partial, trace=partial_trace, rounds=partial_rounds)
                            saved = True
                        live.reply = partial or None
                        live.status = "done"
                        live.publish("done", {"reply": partial, "session": chat_key})
                        live.publish("end", {"status": live.status})
                    self.logger.warning(f"turn timeout after {_turn_timeout}s ({chat_key}), partial saved={saved}")
                    raise
                finally:
                    if live is not None:
                        if live.status == "running":
                            live.status = "done"
                        live.publish("end", {"status": live.status})
                if live is not None:
                    live.reply = result.text.strip()
                    live.status = "done"
                    live.publish("done", {"reply": live.reply, "session": chat_key})
                reply, force_forward = strip_output_tag(result.text.strip())
                reply = strip_stray_tags(reply)
# 标签合并：最终回复自身的标签 > 运行过程中任一段发言声明的标签 > None（自动规则）
                if force_forward is None:
                    force_forward = getattr(result, "delivery_hint", None)
# H4 输出过滤器：复述→重 roll 一次；句数超限/结尾硬造反问→就地截断
                if bool(getattr(self.cfg, "humanize_filter_enabled", False)):
                    try:
                        from ..conversation.rhythm import filter_reply

                        reply, action = filter_reply(
                            reply,
                            combined_text,
                            int(getattr(self.cfg, "humanize_filter_max_sentences", 3) or 3),
                        )
                        if action == "parrot":
                            self.logger.info("reply filter: parrot detected, rerolling once")
                            retry = await self.runner.run(
                                system=system,
                                messages=contexts
                                + [user_msg, {"role": "assistant", "content": reply}]
                                + [{"role": "user", "content": texts.t("parrot_retry_note")}],
                                ctx=ctx,
                                persona_tools=persona.get("tools"),
                            )
# 重 roll 输出同样清扫残留标签（[[直发]]/单括号形态不能原样发出）
                            retry_reply, _ = strip_output_tag(retry.text.strip())
                            retry_reply = utils.strip_stray_tags(retry_reply)
                            retry_reply, _2 = filter_reply(
                                retry_reply, "", int(getattr(self.cfg, "humanize_filter_max_sentences", 3) or 3)
                            )
                            if retry_reply.strip():
                                reply = retry_reply.strip()
                                result = retry
                    except Exception as e:
                        self.logger.debug(f"reply filter failed: {e}")
# 元文本剥离：模型把思考/策略写进正文首段时自动剥掉（默认开，独立于 humanize filter）
                if bool(getattr(self.cfg, "meta_strip", True)):
                    try:
                        reply = utils.strip_meta_section(reply)
                    except Exception as e:
                        self.logger.debug(f"meta strip failed: {e}")
# 假媒体标记：模型不调 TTS 工具自己写「[语音] xxx」假装发过语音——剥标记留正文；
# 「（语音已发）」这类整行假声明一并剥掉（语音没真发出去却宣告已发）
                try:
                    reply = utils.strip_fake_media_prefix(reply)
                    reply = utils.strip_fake_media_claims(reply)
                except Exception as e:
                    self.logger.debug(f"fake media strip failed: {e}")
# 同回合去重：最终回复与最后一条已投递阶段发言规范化后相同 → 阶段发言已代表过它，
# 不重复投递最终条（"阶段发言+最终回复"双胞胎）；会话历史与回执广播照常
                duplicate_final = bool(last_speech) and utils.collapse_spaces(reply) == last_speech
# 静默终局：模型自主跳过（[[不回复]]）或清理后为空 → 不发送、不写占位进上下文
# （占位文案刷屏事故+污染历史；usage 照记）。空回复带模型名记 warning——
# "配了新模型之后一直空回复"的排障起点
                skip_reply = utils.is_skip_reply(reply)
                if skip_reply or not reply.strip():
                    if skip_reply:
                        self.logger.info(f"skip reply requested by model ({chat_key})")
                    else:
                        self.logger.warning(
                            f"empty reply after cleanup (model={getattr(result, 'model', '')}, tools={len(result.tool_trace)}), skipped sending ({chat_key})"
                        )
                    self.sessions.finalize(chat_key, "", trace=result.tool_trace, rounds=getattr(result, "rounds", None), usage=result.usage, model=getattr(result, "model", ""), user_id=sender_id, skip_append=True)
                    self._drain_waiting(chat_key)
                    return
                reply = reply or texts.t("no_reply_content")
                self.sessions.finalize(chat_key, reply, trace=result.tool_trace, rounds=getattr(result, "rounds", None), usage=result.usage, model=getattr(result, "model", ""), user_id=sender_id)
                try:
# 隐私开关：listen_off 时回执事件也不出群
                    if not self.sessions.get_flag(chat_key, "listen_off"):
                        await self.sdk.lifecycle.emit(
                            "qvq.replied",
                            {"chat_key": chat_key, "reply": reply, "tools": len(result.tool_trace)},
                        )
                except Exception as e:
                    self.logger.debug(f"emit qvq.replied failed: {e}")
                if duplicate_final:
# 内容已随阶段发言发到群里：跳过最终投递（pending 重放顺延到下一条回复，无碍）
                    self.logger.debug("final reply duplicates last intermediate speech, skipped")
                else:
                    await self.delivery.deliver_reply(event, reply, result.tool_trace, force=force_forward, rounds=getattr(result, "rounds", None), origin=origin)
# 记录回复时间：回复合并窗口的起点（窗口内后续消息合并为一次后续回复）
                self._last_reply_ts[chat_key] = time.time()
                self._drain_waiting(chat_key)
            finally:
# 删除失败必须当场暴露并重试：残留标记会在下次重启被恢复例程重放成"自动重发"
                try:
                    self.sdk.storage.delete(INFLIGHT_KEY_PREFIX + chat_key)
                except Exception as e:
                    self.logger.warning(f"inflight marker delete failed ({chat_key}): {e}")
                    try:
                        self.sdk.storage.delete(INFLIGHT_KEY_PREFIX + chat_key)
                    except Exception as e2:
                        self.logger.error(f"inflight marker delete retry failed ({chat_key}): {e2}")
        except Exception as e:
            # 失败通知按来源区分：用户主动触发（chat/dashboard 等才收完整错误）；
            # 被动触发（plugin 插话等）用户没有发起消息，默认静默只记日志，避免错误刷屏
            self.logger.warning(f"process failed (origin={origin}): {e}")
# 中止现场落库：取消/超时分支已各自落部分输出，这里兜住其余异常（模型连坏/
# 基础设施炸）——把已产生的输出与工具轨迹存进会话，下一轮模型与面板都看得到
# "上一回合走到哪、为什么断"；无输出时也留一条中止标记（用户消息已由 prepare 落库，
# 缺 assistant 侧会让下一轮历史缺半边）
            failed_live = locals().get("live")
            if failed_live is not None and chat_key:
                try:
                    partial, partial_trace, partial_rounds = failed_live.partial_record()
                    if partial or partial_trace:
                        self.sessions.append(chat_key, "assistant", partial, trace=partial_trace, rounds=partial_rounds)
                    else:
                        self.sessions.append(chat_key, "assistant", texts.t("turn_aborted_note", error=utils.truncate(str(e), 120)))
                except Exception as save_err:
                    self.logger.debug(f"partial save on failure failed: {save_err}")
            if origin == "plugin" and not bool(getattr(self.cfg, "notify_on_passive_failure", False)):
                return
            try:
# 回合超时的 str(e) 是空串，直接套 run_failed 会回一条近空消息——用专用文案
                if isinstance(e, asyncio.TimeoutError):
                    await event.reply(texts.t(
                        "run_timeout",
                        seconds=int(float(getattr(self.cfg, "turn_timeout", 0) or 0)),
                    ))
                else:
                    await event.reply(texts.t("run_failed", error=utils.truncate(str(e), 200)))
            except Exception as inner:
                self.logger.debug(f"run_failed notice reply failed: {inner}")

    async def _maybe_send_opening(self, event, chat_key: str, prepared: dict, persona: dict) -> None:
        """首次接触开场白：prepare 标记 first_contact 且未发过 → 随机一条 await 直发。

        防重靠会话 state 的 opening_sent 标记；Dashboard 平台不触发；
        seed 回填发生时默认不触发（opening_on_seed=True 才发）；
        发送成功后停 0.8s 再返回，让主回复与开场白保持拟人间隔。
        """
        try:
            if not prepared.get("first_contact"):
                return
            if not getattr(self.cfg, "opening_enabled", True):
                return
            if prepared.get("seeded") and not getattr(self.cfg, "opening_on_seed", False):
                return
            if str(event.get_platform() or "") == DASHBOARD_PLATFORM:
                return
            if self.sessions.get_flag(chat_key, "opening_sent"):
                return
            opening = [str(o).strip() for o in (persona.get("opening") or []) if str(o or "").strip()]
            if not opening:
                return
            text = utils.truncate(
                str(random.choice(opening)),
                max(1, int(getattr(self.cfg, "opening_max_len", 200) or 200)),
            )
            await event.reply(text)
            self.sessions.set_flags(chat_key, {"opening_sent": True})
            await asyncio.sleep(0.8)
        except Exception as e:
            self.logger.debug(f"opening send failed: {e}")

    async def _seed_history(self, event, chat_key: str = "") -> list:
        """冷启动回填：优先取带 sender 的收件箱记录并逐条标注发言者，避免历史对话者被误认成当前发言者。

        关键剔除：框架 transcript 在消息分发**之前**就落库——当前这条触发消息
        必然也在 rows 里；不剔掉它，seed 写入后实时链路再 append 一次，
        同一条消息就在会话里出现两份（webui 可见的重复注入根因）。
        """
        limit = int(getattr(self.cfg, "history_seed", 20) or 0)
        if limit <= 0:
            return []
        try:
            rows = self._transcript_rows(event, limit)
        except Exception as e:
            self.logger.debug(f"transcript rows fetch failed: {e}")
            rows = []
        current_mid = ""
        current_text = ""
        try:
            current_mid = str(event.get("message_id") or "") if hasattr(event, "get") else ""
        except Exception:
            current_mid = ""
        try:
            current_text = str(event.get_alt_message() or "").strip()
        except Exception:
            current_text = ""
        if current_mid or current_text:
            filtered = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
                if current_mid and str(meta.get("message_id") or "") == current_mid:
                    continue
# 兜底：transcript 行可能缺 message_id——文本精确一致也视为当前消息
                if current_text and str(row.get("text") or "").strip() == current_text:
                    continue
                filtered.append(row)
            rows = filtered
        rows = _seed_dedupe(rows, self.sessions.get_contexts(chat_key)) if chat_key else rows
        if not rows:
# 降级：框架收件箱不可用时走 event.history（无 sender，统一标注为未记录）
            try:
                history = await event.history(limit)
            except Exception:
                return []
            rows = [
                {"role": str(e.get("role") or ""), "text": str(e.get("text") or ""), "sender": ""}
                for e in (history or [])
                if isinstance(e, dict)
# 降级路径同样剔除当前消息（文本一致即剔）
                if str(e.get("text") or "").strip() != current_text
            ]
        return await self._label_seed_rows(event, rows)

    def _transcript_rows(self, event, limit: int) -> list:
        """按框架收件箱会话键（群聊=群级）过滤近期记录，保留 sender 字段。

        群级键无账户维度——多账户部署下账户 B 收到的消息也会出现在
        账户 A 的回填里，按 meta.self_id 过滤只保留本账户收到的。
        """
        transcript = getattr(self.sdk, "transcript", None)
        recent = getattr(transcript, "recent", None)
        if not callable(recent):
            return []
        platform = str(event.get_platform() or "")
        try:
            is_group = event.is_group_message()
        except Exception:
            is_group = False
        target = str(event.get_group_id() or "") if is_group else str(event.get_user_id() or "")
        if not platform or not target:
            return []
        base_key = f"{platform}:{'group' if is_group else 'private'}:{target}"
        try:
            rows = recent(7 * 24 * 3600, limit=max(500, limit * 25))
        except Exception:
            return []
        picked = [r for r in (rows or []) if isinstance(r, dict) and r.get("session_key") == base_key]
        try:
            self_id = str(event.get_self_user_id() or event.get_self_account_id() or "")
        except Exception:
            self_id = ""
        if self_id:
            filtered = []
            for row in picked:
                meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
                row_self = str(meta.get("self_id") or "")
# 仅当行带 self_id 且与当前账户不同才剔除（旧数据无该字段时保守保留）
                if row_self and row_self != self_id:
                    continue
                filtered.append(row)
            picked = filtered
        return picked[-limit:] if len(picked) > limit else picked

    async def _label_seed_rows(self, event, rows: list) -> list:
        unknown_note = texts.t("seed_unknown_speaker")
        try:
            is_group = event.is_group_message()
        except Exception:
            is_group = False
        senders: list[str] = []
        for row in rows:
            sid = str(row.get("sender") or "")
            if row.get("role") == "user" and sid and sid not in senders:
                senders.append(sid)
        names: dict[str, str] = {}
        if is_group and senders:
            names = await self._group_nicknames(
                str(event.get_platform() or ""), str(event.get_group_id() or ""), senders[:8]
            )
        seeded: list = []
        for row in rows:
            text = str(row.get("text") or "")
            if not text:
                continue
            if row.get("role") == "bot":
# 机器人历史直接作为 assistant 内容；不要内联标签，否则模型会把它当成自己的话复读
                seeded.append({"role": "assistant", "content": text})
            elif row.get("role") == "user":
                sid = str(row.get("sender") or "")
                if sid:
                    name = str(names.get(sid) or "")
                    label = f"{name}({sid})" if name else f"({sid})"
                    seeded.append({"role": "user", "content": f"{label}: {text}"})
                else:
                    seeded.append({"role": "user", "content": f"[{unknown_note}] {text}"})
            else:
                seeded.append({"role": "assistant", "content": text})
        return seeded

    async def _group_nicknames(self, platform: str, group_id: str, uids: list) -> dict:
        """uid→群昵称批量反查，storage 缓存 7 天；失败返回空（标注退化为 (uid):）。"""
        if not platform or not group_id or not uids:
            return {}
        cache_key = f"QvQChat:nick:{platform}:{group_id}"
        cache = self.sdk.storage.get(cache_key, {})
        cache = cache if isinstance(cache, dict) else {}
        now = time.time()
        names: dict[str, str] = {}
        missing: list[str] = []
        for uid in uids:
            hit = cache.get(uid)
            if isinstance(hit, dict) and hit.get("name") and now - float(hit.get("ts") or 0) < 7 * 24 * 3600:
                names[uid] = str(hit["name"])
            else:
                missing.append(uid)
        adapter = self.sdk.adapter.get(platform) if missing else None
        if adapter is not None:

            async def fetch(uid: str) -> tuple[str, str]:
                try:
                    info = await asyncio.wait_for(
                        adapter.call_api("get_group_member_info", group_id=group_id, user_id=uid), 5
                    )
# 信封兼容：昵称在 data 层（{status, data:{card, nickname}}），无信封则取顶层
                    payload = info if isinstance(info, dict) else {}
                    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
                    return uid, str(data.get("card") or data.get("nickname") or "")
                except Exception:
                    return uid, ""

            for uid, name in await asyncio.gather(*[fetch(uid) for uid in missing]):
                if name:
                    names[uid] = name
                    cache[uid] = {"name": name, "ts": now}
            self.sdk.storage.set(cache_key, cache)
        return names

    async def _chat_confirmer(self, ctx: ToolContext, text: str, timeout: int) -> bool:
        event = ctx.event
        if event is None:
            return False
        try:
            await event.reply(text)
            reply = await event.wait_reply(timeout=timeout)
            if reply is None:
                return False
            answer = (reply.get_alt_message() or "").strip().lower()
            return answer in CONFIRM_WORDS
        except Exception as e:
            self.logger.warning(f"confirm failed: {e}")
            return False
