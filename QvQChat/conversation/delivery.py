from __future__ import annotations

import asyncio
import random
import re
import time

from .. import texts, utils
from ..tools_builtin.erispulse import REPLY_PREFERENCE
from ..utils import OUTPUT_TAG_RE, strip_output_tag
from .rhythm import STRUCTURE_FORWARD_RATIO, as_float, as_int, plan_segments, structure_signals
from .visual import build_sections

 
__all__ = [
    "OUTPUT_TAG_RE", "strip_output_tag", "Delivery",
    "split_paragraphs", "match_platform", "delivery_profile",
]

RECAP_RE = re.compile(r"^(已[经把完成向]|好[的了]|已发送|已发出|done|sent)")

PENDING_KEY_PREFIX = "QvQChat:pending_send:"

 
RETRYABLE_EXC = (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)
RETRYABLE_NAME_HINTS = ("timeout", "timed out", "connection", "network", "temporarily", "unavailable", "reset")
 
 
UNDELIVERABLE_HINTS = (
    "不是机器人好友", "recvId值错误", "not friend", "no such user", "user not found",
    "no relation", "blocked", "blacklist", "拉黑", "rejected", "无权限发送", "forbidden",
    "group not found", "群不存在", "已退出", "not in group", "kicked",
)


def split_paragraphs(text: str, min_length: int = 120, max_parts: int = 6) -> list[str]:

    parts = [p.strip() for p in re.split(r"\n{2,}", str(text or "")) if p.strip()]
    if len(parts) <= 1:
        return []
    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1]) < min_length:
            merged[-1] += "\n\n" + part
        else:
            merged.append(part)
    if len(merged) < 2 or sum(len(p) for p in merged) < min_length:
        return []
    if len(merged) > max_parts:
        head = merged[: max_parts - 1]
        head.append("\n\n".join(merged[max_parts - 1:]))
        merged = head
    return merged


def match_platform(pattern: str, platform: str) -> bool:
    """平台通配匹配：与 forward_platforms merges 同语义（* 全匹配 / 前缀* / 精确）。"""
    pattern = str(pattern or "")
    return pattern == "*" or pattern == platform or (pattern.endswith("*") and platform.startswith(pattern[:-1]))


def delivery_profile(config, platform: str) -> dict:
    """D2 平台投递 profile：全局配置默认值 + delivery_profiles 通配命中项覆盖。

    覆盖键覆盖 D1 节奏参数与 reply_split/max_parts/forward_min_messages/forward_threshold。
    """
    profile: dict = {
        "sentence_split": bool(getattr(config, "sentence_split", False)),
        "sentence_max": as_int(getattr(config, "sentence_max", 80), 80),
        "typing_speed": as_float(getattr(config, "typing_speed", 25), 25.0),
        "split_jitter": max(0.0, as_float(getattr(config, "split_jitter", 0.35), 0.35)),
        "total_delay_cap": as_float(getattr(config, "total_delay_cap", 20), 20.0),
        "base_delay": as_float(getattr(config, "split_delay", 1.2), 1.2),
        "min_delay": as_float(getattr(config, "min_delay", 0.5), 0.5),
        "max_delay": as_float(getattr(config, "max_delay", 6.0), 6.0),
        "min_length": as_int(getattr(config, "split_min_length", 120), 120),
        "max_parts": max(1, as_int(getattr(config, "max_parts", 6), 6)),
        "reply_split": str(getattr(config, "reply_split", "paragraph")),
        "forward_min_messages": as_int(getattr(config, "forward_min_messages", 2), 2),
        "forward_threshold": as_int(getattr(config, "forward_threshold", 600), 600),
        "forward_args_chars": as_int(getattr(config, "forward_args_chars", 140), 140) or 140,
        "forward_output_chars": as_int(getattr(config, "forward_output_chars", 500), 500) or 500,
    }
    patterns = getattr(config, "delivery_profiles", None)
    if isinstance(patterns, dict):
        for pattern, overrides in patterns.items():
            if isinstance(overrides, dict) and match_platform(pattern, platform):
                for key, value in overrides.items():
                    if key in profile:
                        profile[key] = value
    return profile


def is_undeliverable(exc: Exception | None) -> bool:
    """目标级不可送达（非网络抖动）：换方法/重试/入队重放都无意义。"""
    if exc is None:
        return False
    name = f"{type(exc).__name__} {exc}".lower()
    return any(hint.lower() in name for hint in UNDELIVERABLE_HINTS)


def is_retryable(exc: Exception | None) -> bool:
    if exc is None:
        return False
    if isinstance(exc, RETRYABLE_EXC):
        return True
    name = f"{type(exc).__name__} {exc}".lower()
    return any(hint in name for hint in RETRYABLE_NAME_HINTS)


def pending_key(chat_key: str) -> str:
    return f"{PENDING_KEY_PREFIX}{chat_key}"


def enqueue_pending(sdk, config, chat_key: str, entry: dict) -> bool:
    """D4：发送最终失败的消息入 KV 待发队列（FIFO，超上限淘汰最旧）。"""
    if sdk is None or not chat_key:
        return False
    key = pending_key(chat_key)
    try:
        data = sdk.storage.get(key, [])
        if not isinstance(data, list):
            data = []
    except Exception:
        return False
    data.append(dict(entry))
    cap = as_int(getattr(config, "pending_send_max", 10), 10)
    if cap > 0 and len(data) > cap:
        data = data[len(data) - cap:]
    try:
        sdk.storage.set(key, data)
    except Exception:
        return False
    return True


async def dispatch_text(sdk, config, sender, methods, text: str,
                        queue: dict | None = None, logger=None) -> tuple[str, object, Exception | None]:
    """统一发送实现（D4 收敛点）：方法降级 ->（仅超时/网络类错误）指数退避重试 -> 仍失败入待发队列。

    sender(method, content) 为单次发送回调，返回平台结果；返回 failed 状态视作失败。
    queue 形如 {"chat_key", "platform", "detail_type", "target_id"}，最终失败时把 text 入队。
    返回 (成功方法名, 平台结果, 最后异常)；全部失败时方法名为空串。
    """
    attempts = [m for m in (methods or []) if m]
    retries = max(0, as_int(getattr(config, "send_retry", 1), 1))
    backoff = max(0.0, as_float(getattr(config, "retry_delay", 1.5), 1.5))
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        if attempt:
            if logger is not None:
                try:
                    logger.info(f"send retry attempt {attempt}: {last_error}")
                except Exception:
                    pass
            if backoff > 0:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))
        for name in attempts:
            content = utils.markdown_to_text(text) if name == "Text" else text
            try:
                result = await sender(name, content)
                if utils._send_failed(result):
                    raise RuntimeError(f"send returned failed status: {result}")
                return name, result, None
            except Exception as e:
                last_error = e
                if logger is not None:
                    try:
                        logger.warning(f"send via {name} failed: {e}")
                    except Exception:
                        pass
                 
                 
                if is_undeliverable(e):
                    if logger is not None:
                        try:
                            logger.warning(f"send undeliverable, aborting all methods: {e}")
                        except Exception:
                            pass
                    return "", None, e
        if not is_retryable(last_error):
            break
    if queue:
        entry = dict(queue)
        entry.update({"text": text, "ts": time.time()})
        if enqueue_pending(sdk, config, entry.get("chat_key", ""), entry) and logger is not None:
            try:
                logger.warning("send failed after retries, message queued as pending")
            except Exception:
                pass
    return "", None, last_error


class Delivery:


    def __init__(self, main, rng=None):
        self.main = main
        self.sdk = main.sdk
        self.config = main.cfg
        self._identity: dict = {}
        self._rng = rng or random
        self._replay_tried: set[str] = set()
 
        self._budget_start: dict[str, float] = {}
 
        self._interrupted: set[str] = set()
 
        self._last_sent: dict[str, dict] = {}

    def begin_budget(self, chat_key: str, seconds: float) -> None:
        """H3：生成本轮回复前记时；seconds<=0 表示不启用预算。"""
        if not chat_key:
            return
        if seconds and seconds > 0:
            self._budget_start[chat_key] = time.time()
        else:
            self._budget_start.pop(chat_key, None)

    def end_budget(self, chat_key: str) -> None:
        self._budget_start.pop(chat_key, None)

    def budget_left(self, chat_key: str) -> float | None:
        """剩余预算秒数；无预算返回 None。"""
        start = self._budget_start.get(chat_key)
        if start is None:
            return None
        budget = as_float(getattr(self.config, "humanize_budget_seconds", 7.0), 7.0)
        return budget - (time.time() - start)

    def interrupt(self, chat_key: str) -> None:
        """H3 硬打断：丢弃该会话未发送的分段（已发出的照发不撤）。"""
        if chat_key:
            self._interrupted.add(chat_key)

    def take_interrupt(self, chat_key: str) -> bool:
        if chat_key in self._interrupted:
            self._interrupted.discard(chat_key)
            return True
        return False

    async def _sleep_interruptible(self, chat_key: str, seconds: float) -> None:
        """H3：分段间延迟可被硬打断提前唤醒。"""
        deadline = time.time() + max(0.0, seconds)
        while True:
            remain = deadline - time.time()
            if remain <= 0 or chat_key in self._interrupted:
                return
            await asyncio.sleep(min(0.2, remain))

    async def recall_last(self, chat_key: str) -> bool:
        """H5 撤回最近一条机器人消息（平台不支持/超时静默失败）。"""
        info = self._last_sent.get(chat_key)
        if not info or not info.get("message_id"):
            return False
        if time.time() - float(info.get("ts") or 0) > 120:
            return False
        adapter = self.sdk.adapter.get(str(info.get("platform") or ""))
        call_api = getattr(adapter, "call_api", None)
        if not callable(call_api):
            return False
        try:
            await call_api("delete_msg", message_id=info["message_id"])
            self._last_sent.pop(chat_key, None)
            self.main.logger.info(f"recalled last message for {chat_key}")
            return True
        except Exception as e:
            self.main.logger.debug(f"recall failed for {chat_key}: {e}")
            return False

    def profile_for(self, platform: str) -> dict:
        """D2：取平台投递 profile（reply/工具两条路径共用）。"""
        return delivery_profile(self.config, platform)

    def quote_enabled(self) -> bool:
        """常规回复是否引用触发消息（reply_quote 开关；平台无 Reply 修饰时框架自动跳过引用）。"""
        return str(getattr(self.config, "reply_quote", "on") or "on") == "on"

    def merges(self, platform: str) -> bool:
        if platform in [b for b in [str(x) for x in (getattr(self.config, "no_forward_platforms", []) or [])] if platform == b or (b.endswith("*") and platform.startswith(b[:-1]))]:
            return False
        for a in [str(x) for x in (getattr(self.config, "forward_platforms", ["*"]) or ["*"])]:
            if a == "*" or platform == a or (a.endswith("*") and platform.startswith(a[:-1])):
                return True
        return False

    async def bot_identity(self, platform: str) -> tuple[str, str]:
        """机器人自己的 (账号, 昵称)：转发节点显示自己，而不是虚构身份。"""
        if platform in self._identity:
            return self._identity[platform]
        user_id, nickname = "", ""
        adapter = self.sdk.adapter.get(platform)
        if adapter is not None:
            for endpoint in ("get_login_info", "get_self_info"):
                try:
                    info = await adapter.call_api(endpoint)
                except Exception:
                    continue
                if isinstance(info, dict):
                    user_id = str(info.get("user_id") or info.get("id") or "")
                    nickname = str(info.get("nickname") or info.get("name") or "")
                if user_id or nickname:
                    break
        self._identity[platform] = (user_id, nickname)
        return user_id, nickname

    def _reply_methods(self, event) -> list:
        from ..tools_builtin import erispulse

        methods = []
        for name in erispulse.REPLY_PREFERENCE:
            try:
                if event.supports(name):
                    methods.append(name)
            except Exception:
                continue
        if "Text" not in methods:
            methods.append("Text")
        return methods

    @staticmethod
    def _is_recap(reply: str, tool_trace: list) -> bool:
        if not tool_trace or not any(t.get("tool") == "send_message" for t in tool_trace):
            return False
        return bool(len(reply.strip()) <= 150 and RECAP_RE.match(reply.strip()))

    def _event_chat_key(self, event) -> str:
        """事件 -> 会话键（与 Main._chat_key_of 同格式，含群隔离后缀）。"""
        platform = str(event.get_platform() or "")
        if event.is_group_message():
            gid = str(event.get_group_id() or "")
            if getattr(self.config, "group_isolation", False):
                uid = str(event.get_user_id() or "")
                if uid:
                    return f"{platform}:group:{gid}:u{uid}"
            return f"{platform}:group:{gid}"
        return f"{platform}:private:{str(event.get_user_id() or '')}"

    def _event_queue(self, event) -> dict | None:
        platform = str(event.get_platform() or "")
        detail_type = "group" if event.is_group_message() else "user"
        target_id = str((event.get_group_id() if detail_type == "group" else event.get_user_id()) or "")
        if not target_id:
            return None
        return {
            "chat_key": self._event_chat_key(event),
            "platform": platform,
            "detail_type": detail_type,
            "target_id": target_id,
        }

    async def _emit_deliver_hook(self, event, segments: list[tuple[str, float]]) -> list[tuple[str, float]]:
        """qvq.deliver hook：分段计算后、发送前广播，订阅方可改写 segments/delays。

        载荷：{chat_key, platform, segments: [(text, delay)...], delays: [float...]}；
        返回 dict 时按其中的 segments 改写（支持 (text, delay) 元组或 {text, delay} 字典项）。
        任何异常吞掉，按原 segments 继续发送。
        """
        payload = {
            "chat_key": self._event_chat_key(event),
            "platform": str(event.get_platform() or ""),
            "segments": [(str(t), float(d)) for t, d in segments],
            "delays": [float(d) for _, d in segments],
        }
        try:
            result = await self.sdk.lifecycle.emit("qvq.deliver", payload)
        except Exception:
            return segments
        if isinstance(result, dict):
            raw = result.get("segments")
            if isinstance(raw, list) and raw:
                rewritten: list[tuple[str, float]] = []
                for item in raw:
                    if isinstance(item, dict):
                        text, delay = item.get("text"), item.get("delay", 0)
                    elif isinstance(item, (list, tuple)) and len(item) == 2:
                        text, delay = item
                    else:
                        continue
                    if str(text or ""):
                        rewritten.append((str(text), max(0.0, as_float(delay, 0.0))))
                if rewritten:
                    return rewritten
        return segments

    async def _try_forward(self, event, reply: str, tool_trace: list, force: bool | None = None,
                           rounds: list | None = None) -> bool:
        if force is False:
            return False
        platform = event.get_platform() or ""
        adapter = self.sdk.adapter.get(platform)
        if adapter is None:
            return False
        try:
            sends = list(self.sdk.adapter.list_sends(platform))
        except Exception:
            sends = []
        structure_aware = bool(getattr(self.config, "forward_structure_aware", False))
        profile = self.profile_for(platform)
        if force is not True:
            if not self.merges(platform):
                return False
            if not tool_trace and not structure_aware:
                return False
        sections, text_segments = build_sections(
            rounds, reply, tool_trace,
            include_trace=not bool(getattr(self.config, "forward_exclude_trace", False)),
 
 
            exclude_final_reply=bool(getattr(self.config, "forward_external_reply", True))
            and bool(str(reply or "").strip()),
            args_chars=as_int(profile.get("forward_args_chars"), 140) or None,
            output_chars=as_int(profile.get("forward_output_chars"), 180) or None,
        )
        if force is not True:
            min_messages = as_int(profile.get("forward_min_messages"), 2)
            if structure_aware:
 
                sig = structure_signals(rounds, reply)
                structured = (
                    sig["score"] >= STRUCTURE_FORWARD_RATIO
                    or (min_messages and text_segments >= min_messages and (sig["has_code"] or sig["has_table"]))
                )
                if not structured:
                    return False
            elif min_messages and text_segments < min_messages:
                return False
        if not sections:
            return False
        detail_type = "group" if event.is_group_message() else "user"
        if detail_type == "group":
            target_id = str(event.get_group_id() or "")
        else:
            target_id = str(event.get_user_id() or "")
        if not target_id:
            return False
        try:
            user_id, bot_nickname = await self.bot_identity(platform)
 
            nickname = bot_nickname
            personas = getattr(self.main, "personas", None)
            if personas is not None:
                try:
                    persona = personas.resolve(self._event_chat_key(event))
                    persona_nick = str((persona or {}).get("nickname") or "")
                except Exception:
                    persona_nick = ""
                if persona_nick:
                    nickname = persona_nick
            used = await utils.deliver_forward(adapter, detail_type, target_id, sections, sends,
                                               nickname=nickname, user_id=user_id)
        except Exception as e:
            self.main.logger.warning(f"forward send failed, fallback to normal reply: {e}")
            return False
        return bool(used)

    async def _send_plain(self, event, reply: str, quote: bool = False) -> bool:
        """单条发送：方法降级 -> 重试 -> 最终失败入待发队列（D4）。返回是否发送成功。

        quote=True 时引用回复触发消息（event.reply 原生支持，平台无 Reply 修饰自动跳过）。
        """
        used, result, _ = await dispatch_text(
            self.sdk, self.config,
            lambda name, content: event.reply(content, method=name, quote=quote),
            self._reply_methods(event), reply,
            queue=self._event_queue(event), logger=self.main.logger,
        )
        if used:
 
            message_id = self._extract_message_id(result)
            if message_id is not None:
                queue = self._event_queue(event) or {}
                self._last_sent[str(queue.get("chat_key") or self._event_chat_key(event))] = {
                    "platform": str(event.get_platform() or ""),
                    "message_id": message_id,
                    "ts": time.time(),
                }
        return bool(used)

    @staticmethod
    def _extract_message_id(result) -> object | None:
        if isinstance(result, dict):
            for key in ("message_id", "messageId"):
                if result.get(key) is not None:
                    return result[key]
            data = result.get("data")
            if isinstance(data, dict) and data.get("message_id") is not None:
                return data["message_id"]
        if isinstance(result, (int, str)) and result:
            return result
        return getattr(result, "message_id", None)

    async def _send_split(self, event, reply: str, quote: bool = False) -> None:
        profile = self.profile_for(str(event.get_platform() or ""))
        segments = plan_segments(reply, profile, rng=self._rng)
        if not segments:
            segments = [(reply, 0.0)]
        segments = await self._emit_deliver_hook(event, segments)
        queue = self._event_queue(event)
        chat_key = str((queue or {}).get("chat_key") or self._event_chat_key(event))
 
        left = self.budget_left(chat_key)
        if left is not None:
            needed = sum(max(0.0, d) for _, d in segments)
            if left <= 0:
                segments = [("\n\n".join(t for t, _ in segments), 0.0)]
            elif needed > left:
                segments = [(t, d / 2 if d > 0 else 0.0) for t, d in segments]
        for index, (text, delay) in enumerate(segments):
            if delay > 0:
                await self._sleep_interruptible(chat_key, delay)
 
            if self.take_interrupt(chat_key):
                self.main.logger.info(f"reply interrupted, dropped {len(segments) - index} segment(s)")
                break
            if await self._send_plain(event, text, quote=quote and index == 0):
                continue
 
            if queue is not None:
                for rest, _ in segments[index + 1:]:
                    entry = dict(queue)
                    entry.update({"text": rest, "ts": time.time()})
                    enqueue_pending(self.sdk, self.config, queue["chat_key"], entry)
            break

    async def deliver_reply(self, event, reply: str, tool_trace: list, force: bool | None = None,
                            rounds: list | None = None) -> None:
        try:
            if self._is_recap(reply, tool_trace):
                self.main.logger.info("reply suppressed as send recap")
                return
            await self._replay_pending(self._event_chat_key(event))
            quote = self.quote_enabled()
            if await self._try_forward(event, reply, tool_trace, force=force, rounds=rounds):
 
 
                if bool(getattr(self.config, "forward_external_reply", True)) and str(reply or "").strip():
                    profile = self.profile_for(str(event.get_platform() or ""))
                    if force is not True and profile.get("reply_split", "paragraph") == "paragraph":
                        await self._send_split(event, reply, quote=quote)
                    else:
                        await self._send_plain(event, reply, quote=quote)
                return
            profile = self.profile_for(str(event.get_platform() or ""))
            if force is not True and profile.get("reply_split", "paragraph") == "paragraph":
                await self._send_split(event, reply, quote=quote)
                return
            await self._send_plain(event, reply, quote=quote)
        finally:
            self.end_budget(self._event_chat_key(event))

    async def _replay_pending(self, chat_key: str) -> bool:
        """D4 失败重放：顺带尝试重放队首一条；失败保留队列（每个 chat_key 每进程只试一次）。"""
        if not chat_key or chat_key in self._replay_tried:
            return False
        self._replay_tried.add(chat_key)
        try:
            data = self.sdk.storage.get(pending_key(chat_key), []) or []
        except Exception:
            return False
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            return False
        entry = data[0]
        platform = str(entry.get("platform") or "")
        detail_type = str(entry.get("detail_type") or "user")
        target_id = str(entry.get("target_id") or "")
        text = str(entry.get("text") or "")
        adapter = self.sdk.adapter.get(platform) if platform else None
        if adapter is None or not target_id or not text:
            return False
        try:
            sends = list(self.sdk.adapter.list_sends(platform))
        except Exception:
            sends = []
        methods = [m for m in REPLY_PREFERENCE if not sends or m in sends]
        if "Text" not in methods:
            methods.append("Text")
        used, _, last_error = await dispatch_text(
            self.sdk, self.config,
            lambda name, content: getattr(adapter.Send.To(detail_type, target_id), name)(content),
            methods, text, queue=None, logger=self.main.logger,
        )
        if not used:
             
            if is_undeliverable(last_error):
                try:
                    self.sdk.storage.set(pending_key(chat_key), data[1:])
                    self.main.logger.warning(
                        f"pending send dropped (undeliverable target {platform}/{detail_type}/{target_id}): {last_error}"
                    )
                except Exception:
                    pass
            return False
        try:
            self.sdk.storage.set(pending_key(chat_key), data[1:])
        except Exception:
            pass
        self.main.logger.info(f"replayed pending send for {chat_key}")
        return True

    async def replay_pending(self, chat_key: str) -> bool:
        """公开重放入口（可供电平启动/定时任务调用；不占用"每进程一次"名额）。"""
        self._replay_tried.discard(chat_key)
        return await self._replay_pending(chat_key)

    async def send_segments(self, platform: str, detail_type: str, target_id: str, segments,
                            from_tools: bool = False, chat_key: str = "") -> None:
        adapter = self.sdk.adapter.get(platform)
        if adapter is None:
            self.main.logger.warning(texts.t("adapter_not_found", platform=platform))
            return
        target_type = detail_type if detail_type in ("group", "channel") else "user"
        try:
            sends = list(self.sdk.adapter.list_sends(platform))
        except Exception:
            sends = []
        if self.merges(platform) and from_tools:
            try:
                used = await utils.deliver_forward(
                    adapter,
                    target_type,
                    target_id,
                    [segment for _, segment in segments],
                    sends,
                )
                if used:
                    return
            except Exception as e:
                self.main.logger.warning(f"forward send failed, fallback: {e}")
        methods = [m for m in ("Markdown", "Html", "Text") if not sends or m in sends]
        if "Text" not in methods:
            methods.append("Text")
        queue = {
            "chat_key": chat_key or f"{platform}:{target_type}:{target_id}",
            "platform": platform,
            "detail_type": target_type,
            "target_id": target_id,
        }
        for delay, segment in segments:
            if delay and delay > 0:
                await asyncio.sleep(delay)
            used, _, _ = await dispatch_text(
                self.sdk, self.config,
                lambda name, content: getattr(adapter.Send.To(target_type, target_id), name)(content),
                methods, segment, queue=queue, logger=self.main.logger,
            )
            if not used:
                self.main.logger.warning(f"send to {platform}/{target_type}/{target_id} failed, queued")
                return
