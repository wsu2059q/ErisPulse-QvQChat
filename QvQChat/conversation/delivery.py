from __future__ import annotations

import asyncio
import random
import re
import time

from .. import texts, utils
from ..tools_builtin.erispulse import REPLY_PREFERENCE
from .rhythm import STRUCTURE_FORWARD_RATIO, as_float, as_int, plan_segments, structure_signals
from .visual import build_sections

OUTPUT_TAG_RE = re.compile(r"^\[\[(转发|直发)\]\]\s*")

RECAP_RE = re.compile(r"^(已[经把完成向]|好[的了]|已发送|已发出|done|sent)")

PENDING_KEY_PREFIX = "QvQChat:pending_send:"

# D4：仅对超时/网络类异常做指数退避重试，其余（参数错误/平台不支持等）快速失败
RETRYABLE_EXC = (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError)
RETRYABLE_NAME_HINTS = ("timeout", "timed out", "connection", "network", "temporarily", "unavailable", "reset")


def strip_output_tag(reply: str) -> tuple[str, bool | None]:

    tag = OUTPUT_TAG_RE.match(reply)
    if not tag:
        return reply, None
    return reply[tag.end():].strip(), tag.group(1) == "转发"


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
    }
    patterns = getattr(config, "delivery_profiles", None)
    if isinstance(patterns, dict):
        for pattern, overrides in patterns.items():
            if isinstance(overrides, dict) and match_platform(pattern, platform):
                for key, value in overrides.items():
                    if key in profile:
                        profile[key] = value
    return profile


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

    def profile_for(self, platform: str) -> dict:
        """D2：取平台投递 profile（reply/工具两条路径共用）。"""
        return delivery_profile(self.config, platform)

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
        if force is not True:
            if not self.merges(platform):
                return False
            if not tool_trace and not structure_aware:
                return False
        sections, text_segments = build_sections(rounds, reply, tool_trace)
        if force is not True:
            profile = self.profile_for(platform)
            min_messages = as_int(profile.get("forward_min_messages"), 2)
            if structure_aware:
# D3 结构感知：结构化占比达标、或多段且含代码块/表格才转发；纯寒暄多段直发
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
# 会话人格配置了转发显示名（nickname）则覆盖机器人自身昵称
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

    async def _send_plain(self, event, reply: str) -> bool:
        """单条发送：方法降级 -> 重试 -> 最终失败入待发队列（D4）。返回是否发送成功。"""
        used, _, _ = await dispatch_text(
            self.sdk, self.config,
            lambda name, content: event.reply(content, method=name),
            self._reply_methods(event), reply,
            queue=self._event_queue(event), logger=self.main.logger,
        )
        return bool(used)

    async def _send_split(self, event, reply: str) -> None:
        profile = self.profile_for(str(event.get_platform() or ""))
        segments = plan_segments(reply, profile, rng=self._rng)
        if not segments:
            segments = [(reply, 0.0)]
        segments = await self._emit_deliver_hook(event, segments)
        queue = self._event_queue(event)
        for index, (text, delay) in enumerate(segments):
            if delay > 0:
                await asyncio.sleep(delay)
            if await self._send_plain(event, text):
                continue
# D4：分段中途失败——失败段已入队，剩余段一并入队，不中断已发段
            if queue is not None:
                for rest, _ in segments[index + 1:]:
                    entry = dict(queue)
                    entry.update({"text": rest, "ts": time.time()})
                    enqueue_pending(self.sdk, self.config, queue["chat_key"], entry)
            break

    async def deliver_reply(self, event, reply: str, tool_trace: list, force: bool | None = None,
                            rounds: list | None = None) -> None:

        if self._is_recap(reply, tool_trace):
            self.main.logger.info("reply suppressed as send recap")
            return
        await self._replay_pending(self._event_chat_key(event))
        if await self._try_forward(event, reply, tool_trace, force=force, rounds=rounds):
            return
        profile = self.profile_for(str(event.get_platform() or ""))
        if force is not True and profile.get("reply_split", "paragraph") == "paragraph":
            await self._send_split(event, reply)
            return
        await self._send_plain(event, reply)

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
        used, _, _ = await dispatch_text(
            self.sdk, self.config,
            lambda name, content: getattr(adapter.Send.To(detail_type, target_id), name)(content),
            methods, text, queue=None, logger=self.main.logger,
        )
        if not used:
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
