from __future__ import annotations

import asyncio
import base64
import mimetypes
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from ErisPulse import sdk
from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import command, message
from ErisPulse.loaders import ModuleLoadStrategy

try:
    from ErisPulse.Core.Bases import ModuleMeta
except ImportError:
    ModuleMeta = None

from . import texts, utils
from .conversation.delivery import Delivery, strip_output_tag
from .conversation.memory import MemoryStore
from .conversation.service import ConversationService, make_chat_key, parse_chat_key, strip_isolation
from .dashboard.live import bind as live_bind
from .Config import QvQConfig
from .I18n import QvQI18n
from .agent.persona import PersonaManager
from .agent.runner import AgentRunner
from .agent.tools import ToolContext, ToolRegistry
from .bridge.ecosystem import EcosystemBridge
from .bridge.mcp import MCPManager
from .engine.base import ChatRequest
from .engine.pool import ModelPool
from .scheduler import Scheduler
from .skills import SkillManager
from .tools_builtin import agent, code, computer, erispulse, knowledge, memory, schedule, selfconfig, skilltools, takumi
from .version import __version__

AUDIT_KEY = "QvQChat:audit"
AUDIT_LIMIT = 500

CONFIRM_WORDS = {"确认", "確認", "确定", "確定", "是", "confirm", "yes", "y", "ok"}

LOCAL_ORIGINS = ("dashboard", "rpc")


def is_admin_user(config, user_id: str, origin: str = "chat", platform: str = "",
                  master_checker=None) -> bool:
    if origin in LOCAL_ORIGINS:
        return True
    if master_checker is not None:
        try:
            if master_checker(platform, str(user_id)):
                return True
        except Exception:
            pass
    admins = [str(a) for a in (getattr(config, "admins", []) or [])]
    return bool(admins) and str(user_id) in admins


def _match_tool_rules(name: str, rules) -> bool:
    for rule in rules or []:
        rule = str(rule)
        if rule.endswith("*"):
            if name.startswith(rule[:-1]):
                return True
        elif rule == name:
            return True
    return False


def tool_allowed(config, tool, user_id: str, origin: str = "chat",
                 platform: str = "", master_checker=None) -> tuple[bool, str]:
    if is_admin_user(config, user_id, origin, platform, master_checker):
        return True, ""
    deny = (False, texts.t(
        "tool_permission_denied",
        tool=getattr(tool, "name", str(tool)),
        user_id=str(user_id) or "unknown",
        platform=platform or "unknown",
    ))
    if _match_tool_rules(getattr(tool, "name", str(tool)), getattr(config, "admin_tools", None) or []):
        return deny
    if getattr(tool, "access", "admin") == "safe":
        return True, ""
    if _match_tool_rules(getattr(tool, "name", str(tool)), getattr(config, "safe_tools", []) or []):
        return True, ""
    return deny

CAPABILITY_PROMPT = (
    "Sending messages: platforms differ in capabilities. When the user names a target platform "
    "(e.g. send to YunHu/QQ/Telegram), first call list_platforms to inspect that platform's "
    "supported send methods, then decide yourself which method fits the content and context — "
    "prefer Markdown or Html for formatted text, Image/Voice/Video for media, plain Text otherwise. "
    "Note: on QQ-like platforms Markdown is limited (tables and code blocks usually do NOT render) "
    "— keep formatting simple. "
    "send_message picks and downgrades automatically; send_dsl exposes the full chain "
    "(Using / rules / modifiers / any method) when you need explicit control. "
    "By default each paragraph of your reply is delivered to the chat as its own message. "
    "When the merge switch is enabled, a tool run's reply is packaged into a forward message "
    "together with the tool trace instead. After finishing a tool run, do NOT send an extra "
    "summary/recap via send_message, and do not narrate what you just sent "
    "(e.g. \"已把…发到群里\"). "
    "Output control: you can override the auto choice by STARTING your reply with [[转发]] "
    "(force forward card — for reports/results worth reading as a whole) or [[直发]] "
    "(force normal messages — for casual chat). The tag is stripped before sending; use it "
    "only when the automatic choice would be wrong. "
    "Vision: images users send in chat and images returned by tools are provided to you as "
    "image inputs — describe or analyze them directly; local image files are converted "
    "automatically, and if the model rejects images the system retries without them."
)


class Main(BaseModule):

    ConfigClass = QvQConfig
    I18nClass = QvQI18n

    def __init__(self):
        self.sdk = sdk
        self.logger = sdk.logger.get_child("QvQChat")
        self.pool = None
        self.registry = None
        self.personas = None
        self.sessions = None
        self.memory = None
        self.knowledge = None
        self.runner = None
        self.eco = None
        self.mcp = None
        self.scheduler = None
        self.dashboard = None
        self.takeover: dict = {}
        self._chat_locks: dict = {}
        self._pending: dict = {}
        self._waiting: dict = {}
        self._rate_window: dict = {}
        self._rate_notice_shown: dict = {}

    @staticmethod
    def get_load_strategy() -> ModuleLoadStrategy:
        return ModuleLoadStrategy(lazy_load=False, priority=50)

    @staticmethod
    def get_meta():
        info = dict(
            name="QvQChat",
            description="ErisPulse 通用智能体：消息收发、生态服务、代码执行、电脑操作、定时任务",
            version=__version__,
            group="智能",
            tags=["agent", "ai", "llm"],
            services=[
                {"name": "chat", "description": "与智能体对话（只返回文本），session_id 为 platform:detail_type:target_id"},
                {"name": "run_prompt", "description": "运行一段提示词并可将结果发送到目标会话"},
                {"name": "get_status", "description": "获取运行状态摘要"},
            ],
        )
        if ModuleMeta is None:
            return info
        return ModuleMeta(**info)

    async def on_load(self, event) -> bool:
        texts.register_texts()
        self.pool = ModelPool(self.sdk, self.cfg)
        self.registry = ToolRegistry()
        self.personas = PersonaManager(self.sdk)
        self.conversations = ConversationService(self)
        self.sessions = self.conversations
        self.memory = MemoryStore(self.sdk, self.cfg)
        from .conversation.knowledge import KnowledgeBase
        self.knowledge = KnowledgeBase(self.sdk, self.cfg)
        self.skills = SkillManager(self.sdk, self.cfg)
        self.runner = AgentRunner(self.pool, self.registry, self.cfg)
        self.eco = EcosystemBridge(self)
        self.mcp = MCPManager(self)
        self.scheduler = Scheduler(self)
        self.delivery = Delivery(self)
        self._register_builtin_tools()
        self._register_handlers()
        self._register_dashboard()
        self._register_home_entry()
        self.eco.start()
        self.spawn(self._startup())
        return True

    async def on_unload(self, event) -> bool:
        try:
            await self.mcp.close_all()
        except Exception:
            pass
        for entry in self._pending.values():
            timer = entry.get("timer")
            if timer is not None:
                timer.cancel()
        self._pending.clear()
        for entry in list(self.takeover.values()):
            lease = entry.get("lease")
            if lease is not None:
                try:
                    lease.release()
                except Exception:
                    pass
        self.takeover.clear()
        return True

    async def on_config_update(self, old, new) -> None:
        return

    async def _startup(self) -> None:
        try:
            info = await self.eco.refresh()
            self.logger.info(f"ecosystem bridge: {info}")
        except Exception as e:
            self.logger.warning(f"ecosystem refresh failed: {e}")
        try:
            for info in await self.mcp.connect_all():
                self.logger.info(f"mcp: {info}")
        except Exception as e:
            self.logger.warning(f"mcp connect failed: {e}")
        try:
            await self.scheduler.start()
        except Exception as e:
            self.logger.warning(f"scheduler start failed: {e}")

    def _register_builtin_tools(self) -> None:
        erispulse.register(self.registry, self)
        computer.register(self.registry, self)
        code.register(self.registry, self)
        memory.register(self.registry, self)
        knowledge.register(self.registry, self)
        schedule.register(self.registry, self)
        skilltools.register(self.registry, self)
        agent.register(self.registry, self)
        selfconfig.register(self.registry, self)
        takumi.register(self.registry, self)

    def _register_handlers(self) -> None:
        message.on_message(priority=50)(self._on_message)
        for name in ("qvq", "agent"):
            command(name, help="QvQChat")(self._cmd_agent)
        registered = getattr(command, "commands", {})
        missing = [n for n in ("qvq", "agent") if n not in registered]
        if missing:
            self.logger.warning(f"commands not registered: {', '.join(missing)}")

    def _register_dashboard(self) -> None:
        from .dashboard.live import LiveRegistry

        self.live_registry = LiveRegistry()
        try:
            if "Dashboard" not in self.sdk.module:
                self.logger.info("Dashboard module not present, view skipped")
                return
            from .dashboard.manager import DashboardManager

            self.dashboard = DashboardManager(self)
            self.dashboard.register()
        except Exception as e:
            self.logger.warning(f"dashboard register failed: {e}")

    def _register_home_entry(self) -> None:
        try:
            from .dashboard.manager import ICON_SVG

            self.sdk.router.register_home_entry(
                name={"i18n": "QvQChat.home.entry", "default": "QvQChat"},
                url="/QvQChat/view",
                icon_svg=ICON_SVG,
            )
        except Exception as e:
            self.logger.warning(f"home entry register failed: {e}")

    def is_admin(self, user_id: str, origin: str = "chat", platform: str = "") -> bool:
        return is_admin_user(self.cfg, user_id, origin, platform, self._master_checker())

    def check_tool_permission(self, tool, ctx) -> tuple[bool, str]:
        return tool_allowed(self.cfg, tool.name, ctx.user_id, ctx.origin, ctx.platform, self._master_checker())

    def _master_checker(self):
        def checker(platform: str, user_id: str) -> bool:
            from ErisPulse.Core import master

            return bool(master.is_master(platform or "", str(user_id)))

        return checker

    def audit(self, tool: str, detail: dict, ctx=None) -> None:
        try:
            entries = self.sdk.storage.get(AUDIT_KEY, [])
            if not isinstance(entries, list):
                entries = []
            entries.append(
                {
                    "ts": utils.now_ts(),
                    "tool": tool,
                    "detail": detail,
                    "chat_key": getattr(ctx, "chat_key", "") if ctx is not None else "",
                    "origin": getattr(ctx, "origin", "") if ctx is not None else "",
                    "user_id": str(getattr(ctx, "user_id", "") or ""),
                }
            )
            self.sdk.storage.set(AUDIT_KEY, entries[-AUDIT_LIMIT:])
        except Exception:
            pass

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
            return ""

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
            pass
        return urls[:3]

    def _chat_key_of(self, event) -> str:
        platform = event.get_platform() or ""
        if event.is_group_message():
            gid = str(event.get_group_id() or "")
            if getattr(self.cfg, "group_isolation", False):
                uid = str(event.get_user_id() or "")
                if uid:
                    return make_chat_key(platform, "group", f"{gid}:u{uid}")
            return make_chat_key(platform, "group", gid)
        return make_chat_key(platform, "private", str(event.get_user_id() or ""))

    def _chat_ctx(self, event, chat_key: str) -> ToolContext:
        platform, detail_type, target_id = parse_chat_key(strip_isolation(chat_key))
        session_key = ""
        try:
            session_key = self.sdk.interaction.make_key(event)
        except Exception:
            session_key = ""
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
            origin="chat",
            confirmer=self._chat_confirmer,
        )

    def _cleanup_takeovers(self) -> None:
        now = time.time()
        for key in [k for k, v in self.takeover.items() if float(v.get("until", 0)) <= now]:
            entry = self.takeover.pop(key, None)
            lease = (entry or {}).get("lease")
            if lease is not None:
                try:
                    lease.release()
                except Exception:
                    pass

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
        return True

    async def _rate_notice(self, event) -> None:
        try:
            await event.reply(texts.t("rate_limited"))
        except Exception:
            pass

    def _should_trigger(self, event, chat_key: str, text: str) -> bool:
        if chat_key in self.takeover:
            return True
        if event.is_private_message():
            return bool(getattr(self.cfg, "reply_private", True))
        if event.is_group_message():
            if getattr(self.cfg, "reply_at", True) and event.is_at_message():
                return True
            for prefix in getattr(self.cfg, "wake_prefixes", []) or []:
                if prefix and text.startswith(prefix):
                    return True
        return False

    async def _on_message(self, event) -> None:
        try:
            if event.get("replayed"):
                return
            text = (event.get_alt_message() or "").strip()
            if event.is_command():
                return
            for prefix in getattr(self.cfg, "command_prefixes", []) or []:
                if prefix and text.startswith(prefix):
                    return
            self._cleanup_takeovers()
            chat_key = self._chat_key_of(event)
            routed = self.sessions.resolve_route(chat_key)
            if routed:
                chat_key = routed
            if not self._should_trigger(event, chat_key, text):
                return
            if event.is_group_message() and not self.sessions.member_allowed(
                chat_key, str(event.get_user_id() or ""), event.get_platform() or ""
            ):
                return
            event.done()
            if not self._rate_allow(chat_key, str(event.get_user_id() or ""), event):
                return
            images = self._extract_images(event)
            self._batch_message(event, chat_key, text, images)
        except Exception as e:
            self.logger.warning(f"on_message failed: {e}")

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
            name = str((info or {}).get("group_name") or "")
        except Exception:
            name = ""
        if name:
            self.sessions.set_group_name(chat_key, name)
        return name

    def _usage_today(self) -> dict:
        data = self.sdk.storage.get(f"QvQChat:usage:{time.strftime('%Y-%m-%d')}", {})
        return data if isinstance(data, dict) else {}

    def record_usage(self, chat_key: str, usage: dict, model: str = "") -> None:
        try:
            today = time.strftime("%Y-%m-%d")
            key = f"QvQChat:usage:{today}"
            data = self.sdk.storage.get(key, {})
            if not isinstance(data, dict):
                data = {}
            tokens = int(usage.get("total_tokens", 0) or 0)
            data["tokens"] = int(data.get("tokens", 0) or 0) + tokens
            data["calls"] = int(data.get("calls", 0) or 0) + 1
            by_chat = data.get("by_chat")
            if not isinstance(by_chat, dict):
                by_chat = {}
            by_chat[chat_key] = int(by_chat.get(chat_key, 0) or 0) + tokens
            data["by_chat"] = by_chat
            if model:
                by_model = data.get("by_model")
                if not isinstance(by_model, dict):
                    by_model = {}
                entry = by_model.get(model)
                entry = {"tokens": 0, "in": 0, "out": 0} if not isinstance(entry, dict) else entry
                entry["tokens"] = int(entry.get("tokens", 0) or 0) + tokens
                entry["in"] = int(entry.get("in", 0) or 0) + int(usage.get("prompt_tokens", 0) or 0)
                entry["out"] = int(entry.get("out", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)
                by_model[model] = entry
                data["by_model"] = by_model
            self.sdk.storage.set(key, data)
            self._prune_usage(today)
        except Exception:
            pass

    def _prune_usage(self, today: str) -> None:
        days = int(getattr(self.cfg, "usage_retention_days", 14) or 0)
        if days <= 0:
            return
        try:
            cutoff = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days)
        except ValueError:
            return
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith("QvQChat:usage:"):
                date_part = key.rsplit(":", 1)[-1]
                try:
                    if datetime.strptime(date_part, "%Y-%m-%d") < cutoff:
                        self.sdk.storage.delete(key)
                except ValueError:
                    continue

    def _usage_history(self, days: int = 14) -> list[dict]:
        history = []
        for offset in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
            data = self.sdk.storage.get(f"QvQChat:usage:{date}", {})
            history.append(
                {
                    "date": date,
                    "tokens": int((data or {}).get("tokens", 0) or 0) if isinstance(data, dict) else 0,
                    "calls": int((data or {}).get("calls", 0) or 0) if isinstance(data, dict) else 0,
                    "by_chat": (data or {}).get("by_chat", {}),
                    "by_model": (data or {}).get("by_model", {}),
                }
            )
        return history

    def _enqueue_waiting(self, chat_key: str, event, items: list) -> None:
        queue = self._waiting.setdefault(chat_key, [])
        queue.append((event, items))
        self.logger.info(f"chat busy, message queued ({chat_key}, {len(queue)} waiting)")
        self.spawn(self._announce_queued(chat_key, event, items))

    async def _announce_queued(self, chat_key: str, event, items: list) -> None:
        incoming = " ".join(str(i.get("text") or "") for i in items if i.get("text"))
        registry = getattr(self, "live_registry", None)
        current = ""
        live = registry.get(chat_key) if registry else None
        if live is not None:
            current = str(live.text or "")[-300:]
        prompt = (
            "机器人正在执行一个未完成的长任务。任务最近的输出摘要是："
            + (current or "（尚无输出）")
            + "。此时收到新消息：" + incoming[:150] + "。"
            "请以机器人自己的口吻输出一句话：简单说明当前在做什么，并告诉对方这条新消息已排入队列、"
            "任务完成后就会处理。只输出这一句话，不要调用任何工具。"
        )
        reply = ""
        try:
            response = await self.pool.chat(
                ChatRequest(messages=[{"role": "user", "content": prompt}], max_tokens=80, temperature=0.7)
            )
            reply = (response.content or "").strip()
        except Exception as e:
            self.logger.warning(f"queue announce failed: {e}")
        if not reply:
            return
        try:
            await event.reply(reply)
        except Exception as e:
            self.logger.warning(f"queue announce reply failed: {e}")

    def _drain_waiting(self, chat_key: str) -> None:
        queue = self._waiting.pop(chat_key, None)
        if not queue:
            return
        for event, items in queue:
            self._batch_message(event, chat_key, items)

    def _lock_for(self, chat_key: str) -> asyncio.Lock:
        lock = self._chat_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_key] = lock
        return lock

    def _batch_message(self, event, chat_key: str, text: str, images: list) -> None:
        entry = self._pending.setdefault(chat_key, {"items": [], "event": event, "timer": None})
        entry["items"].append(
            {
                "text": text,
                "images": images,
                "sender_id": str(event.get_user_id() or ""),
                "sender_name": self._sender_name(event),
            }
        )
        entry["event"] = event
        if entry["timer"] is None:
            window = float(getattr(self.cfg, "aggregate_window", 5.0) or 0)
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
        await self._process_locked(entry["event"], entry["items"], chat_key)

    async def _process(self, event, text: str) -> None:
        chat_key = self._chat_key_of(event)
        async with self._lock_for(chat_key):
            await self._process_locked(event, text, chat_key)

    async def _process_locked(self, event, items: list, chat_key: str) -> None:
        try:
            ctx = self._chat_ctx(event, chat_key)
            is_group = event.is_group_message()
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
                scene += texts.t("scene_speaker_note")
            else:
                if sender_name:
                    scene = texts.t("scene_private", name=sender_name, id=sender_id)
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
            except Exception:
                pass
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
            if limit:
                used_today = int(self._usage_today().get("tokens", 0) or 0)
                if used_today >= limit and not self.is_admin(sender_id, "chat", event.get_platform() or ""):
                    await event.reply(texts.t("daily_limit_reached", used=used_today, limit=limit))
                    return
            interrupted_note = ""
            live = None
            registry = getattr(self, "live_registry", None)
            if registry is not None:
                old_live = registry.get(chat_key)
                if old_live and old_live.status == "running" and old_live.text.strip():
                    # queue：当前任务后台继续，新消息排到任务完成后处理；interrupt：取消旧任务
                    if str(getattr(self.cfg, "interrupt_mode", "queue")) == "queue":
                        self._enqueue_waiting(chat_key, event, items)
                        return
                    old_live.cancel()
                    interrupted_note = texts.t(
                        "interrupted_note",
                        content=utils.truncate(old_live.text.strip(), 500),
                    )
                live = registry.start(chat_key)
                live.task = asyncio.current_task()
                on_delta, on_reset, on_tool_event = live_bind(live)
            else:
                on_delta = on_reset = on_tool_event = None
            prepared = await self.sessions.prepare(
                chat_key,
                labeled,
                images=images,
                scene=scene,
                seed_provider=lambda: self._seed_history(event),
                cross_user_id=("" if is_group else sender_id),
            )
            system = prepared["system"]
            contexts = prepared["contexts"]
            user_msg = prepared["user_msg"]
            persona = prepared["persona"]
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

            async def on_intermediate(speech):
                if getattr(self.cfg, "tool_notice_mode", "brief") != "all":
                    return
                text = utils.truncate(str(speech).strip(), 1200)
                if text:
                    await event.reply(text)

            try:
                result = await self.runner.run(
                    system=system,
                    messages=contexts + [user_msg],
                    ctx=ctx,
                    persona_tools=persona.get("tools"),
                    on_tool_round=on_tool_round,
                    on_intermediate=on_intermediate,
                    on_delta=on_delta,
                    on_reset=on_reset,
                    on_tool_event=on_tool_event,
                )
            except asyncio.CancelledError:
                if live is not None:
                    partial = live.text.strip()
                    if partial:
                        self.sessions.append(chat_key, "assistant", partial)
                    live.reply = partial or None
                    live.status = "done"
                    live.publish("done", {"reply": partial, "session": chat_key})
                    live.publish("end", {"status": live.status})
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
            reply = reply or texts.t("no_reply_content")
            self.sessions.finalize(chat_key, reply, trace=result.tool_trace, rounds=getattr(result, "rounds", None), usage=result.usage, model=getattr(result, "model", ""))
            try:
                await self.sdk.lifecycle.emit(
                    "qvq.replied",
                    {"chat_key": chat_key, "reply": reply, "tools": len(result.tool_trace)},
                )
            except Exception:
                pass
            await self.delivery.deliver_reply(event, reply, result.tool_trace, force=force_forward, rounds=getattr(result, "rounds", None))
            self._drain_waiting(chat_key)
        except Exception as e:
            self.logger.warning(f"process failed: {e}")
            try:
                await event.reply(texts.t("run_failed", error=utils.truncate(str(e), 200)))
            except Exception:
                pass

    async def _seed_history(self, event) -> list:
        try:
            history = await event.history(int(getattr(self.cfg, "history_seed", 20)))
            return [
                {"role": "user" if entry.get("role") == "user" else "assistant", "content": str(entry.get("text") or "")}
                for entry in history
                if entry.get("text")
            ]
        except Exception:
            return []

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

    async def run_prompt(self, chat_key: str, prompt: str, persona_id: str = "",
                         origin: str = "task", send: bool = True, user_id: str = "") -> str:
        platform, detail_type, target_id = parse_chat_key(strip_isolation(chat_key))
        ctx = ToolContext(
            main=self,
            sdk=self.sdk,
            config=self.cfg,
            chat_key=chat_key,
            platform=platform,
            detail_type=detail_type,
            target_id=target_id,
            user_id=user_id,
            origin=origin,
        )
        prepared = await self.sessions.prepare(chat_key, prompt, persona_id=persona_id, persist=False)
        messages: list = []
        if send and platform:
            messages.append({"role": "system", "content": texts.t("task_run_note")})
        messages.extend(prepared["contexts"] + [prepared["user_msg"]])
        result = await self.runner.run(
            system=prepared["system"],
            messages=messages,
            ctx=ctx,
            persona_tools=prepared["persona"].get("tools"),
        )
        reply = result.text.strip() or texts.t("no_reply_content")
        if send and platform:
            delivered = any(
                sent_platform == platform and sent_type == detail_type and sent_id == target_id
                for sent_platform, sent_type, sent_id in ctx.sent_log
            )
            if not delivered:
                await self.delivery.send_segments(
                    platform,
                    detail_type,
                    target_id,
                    [(0.0, reply)],
                    from_tools=bool(result.tool_trace),
                )
        return reply

    async def run_dashboard_chat(
        self,
        chat_key: str,
        text: str,
        *,
        images: list[str] | None = None,
        skill_names: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        persona_id: str = "",
        model: str = "",
        temperature: float | None = None,
        on_delta=None,
        on_reset=None,
        on_tool_event=None,
    ) -> str:
        platform, detail_type, target_id = parse_chat_key(strip_isolation(chat_key))
        ctx = ToolContext(
            main=self,
            sdk=self.sdk,
            config=self.cfg,
            chat_key=chat_key,
            platform=platform,
            detail_type=detail_type,
            target_id=target_id,
            user_id="dashboard",
            origin="dashboard",
        )
        prepared = await self.sessions.prepare(
            chat_key,
            text,
            images=images,
            persona_id=persona_id,
            active_skills=skill_names,
            mcp_tools=mcp_tools,
        )
        result = await self.runner.run(
            system=prepared["system"],
            messages=prepared["contexts"] + [prepared["user_msg"]],
            ctx=ctx,
            persona_tools=prepared["persona"].get("tools"),
            model=model or None,
            temperature=temperature,
            on_delta=on_delta,
            on_reset=on_reset,
            on_tool_event=on_tool_event,
        )
        reply = result.text.strip() or texts.t("no_reply_content")
        self.sessions.finalize(chat_key, reply, trace=result.tool_trace, rounds=getattr(result, "rounds", None), usage=result.usage, model=getattr(result, "model", ""), title_from=text)
        return reply

    async def run_task(self, task: dict) -> None:
        target_type = str(task.get("target_type") or "user")
        detail_type = "group" if target_type == "group" else "private"
        chat_key = make_chat_key(str(task.get("platform") or ""), detail_type, str(task.get("target_id") or ""))
        origin = str(task.get("origin") or "dashboard")
        if origin in ("task", ""):
            origin = "dashboard"
        await self.run_prompt(
            chat_key,
            str(task.get("prompt") or ""),
            persona_id=str(task.get("persona") or ""),
            origin=origin,
            user_id=str(task.get("created_by") or ""),
        )

    async def _cmd_agent(self, event) -> None:
        try:
            event.done()
            raw = (event.get_command_args() or "").strip()
            tokens = raw.split() if raw else []
            sub = tokens[0].lower() if tokens else ""
            chat_key = self._chat_key_of(event)
            user_id = str(event.get_user_id() or "")
            if sub in ("", "help", "帮助", "幫助"):
                await event.reply(texts.t("cmd_help"))
            elif sub in ("reset", "重置"):
                self.sessions.reset(chat_key)
                await event.reply(texts.t("reset_done"))
            elif sub in ("persona", "人格"):
                await self._cmd_persona(event, chat_key, tokens)
            elif sub in ("tasks", "任务", "任務"):
                tasks = self.scheduler.list()
                if not tasks:
                    await event.reply(texts.t("task_list_empty"))
                else:
                    lines = [
                        f"[{t.get('id')}] {t.get('name', '')} → {utils.format_ts(float(t.get('next_run', 0)))} :: {str(t.get('prompt', ''))[:40]}"
                        for t in tasks
                    ]
                    await event.reply("\n".join(lines))
            elif sub in ("compact", "压缩", "壓縮"):
                report = await self.sessions.compact_now(chat_key)
                await event.reply(texts.t("compact_done", actions=", ".join(report.get("actions") or ["noop"])))
            elif sub in ("status", "状态", "狀態"):
                counts = self.registry.count_by_origin()
                await event.reply(
                    texts.t(
                        "status_line",
                        models=len(self.pool.list_models()),
                        tools=sum(counts.values()),
                        eco=counts.get("eco", 0),
                        sessions=len(self.sessions.list_sessions()),
                        tasks=len(self.scheduler.list()),
                    )
                )
            elif sub in ("takeover", "接管"):
                if not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                minutes = 10
                if len(tokens) >= 2:
                    try:
                        minutes = max(1, int(tokens[1]))
                    except ValueError:
                        minutes = 10
                result = await erispulse.takeover_session(self._chat_ctx(event, chat_key), duration_minutes=minutes)
                await event.reply(result)
            elif sub in ("release", "释放", "釋放"):
                result = await erispulse.release_takeover(self._chat_ctx(event, chat_key))
                await event.reply(result)
            else:
                await event.reply(texts.t("cmd_unknown"))
        except Exception as e:
            self.logger.warning(f"agent command failed: {e}")

    async def _cmd_persona(self, event, chat_key: str, tokens: list) -> None:
        if len(tokens) >= 2:
            pid = tokens[1]
            persona = self.personas.get(pid)
            if persona.get("id") == pid:
                self.personas.bind(chat_key, pid)
                self.sessions.set_persona(chat_key, pid)
                await event.reply(texts.t("persona_set", id=pid))
            else:
                await event.reply(texts.t("persona_unknown", id=pid))
            return
        lines = []
        for persona in self.personas.list():
            mark = " *" if persona.get("builtin") else ""
            lines.append(f"{persona.get('id')}  {persona.get('name', '')}{mark}")
        await event.reply("\n".join(lines))

    async def chat(self, session_id: str, prompt: str, persona: str = "") -> str:
        return await self.run_prompt(session_id, prompt, persona_id=persona, origin="rpc", send=False)

    async def get_status(self) -> dict:
        counts = self.registry.count_by_origin()
        return {
            "version": __version__,
            "models": len(self.pool.list_models()),
            "tools": counts,
            "sessions": len(self.sessions.list_sessions()),
            "tasks": len(self.scheduler.list()),
            "eco": dict(self.eco.info),
            "extensions": self.eco.extensions_status(),
            "mcp": self.mcp.status(),
            "security_level": getattr(self.cfg, "security_level", "standard"),
            "trust_agent": bool(getattr(self.cfg, "trust_agent", False)),
        }
