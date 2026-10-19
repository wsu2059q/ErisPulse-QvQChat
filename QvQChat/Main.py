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
from .session.manager import SessionManager, make_chat_key, parse_chat_key
from .session.store import MemoryStore
from .skills import SkillManager
from .tools_builtin import agent, code, computer, erispulse, memory, schedule, selfconfig, skilltools, takumi
from .version import __version__

AUDIT_KEY = "QvQChat:audit"
AUDIT_LIMIT = 500

OUTPUT_TAG_RE = re.compile(r"^\[\[(转发|直发)\]\]\s*")

CONFIRM_WORDS = {"确认", "確認", "确定", "確定", "是", "confirm", "yes", "y", "ok"}

BASE_SAFE_TOOLS = {
    "send_message",
    "send_dsl",
    "list_platforms",
    "list_takeovers",
    "remember",
    "recall",
    "forget",
    "list_memory",
    "read_file",
    "view_image",
    "list_dir",
    "list_services",
    "create_scheduled_task",
    "list_scheduled_tasks",
    "cancel_scheduled_task",
}

DEFAULT_ADMIN_TOOLS = [
    "run_command",
    "run_python",
    "write_file",
    "call_adapter_api",
    "call_module",
    "takeover_session",
    "release_takeover",
    "eco_*",
    "mcp_*",
]

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


def tool_allowed(config, tool_name: str, user_id: str, origin: str = "chat",
                 platform: str = "", master_checker=None) -> tuple[bool, str]:
    if is_admin_user(config, user_id, origin, platform, master_checker):
        return True, ""
    if tool_name in BASE_SAFE_TOOLS:
        return True, ""
    safe_extra = [str(s) for s in (getattr(config, "safe_tools", []) or [])]
    if _match_tool_rules(tool_name, safe_extra):
        return True, ""
    admin_rules = [str(a) for a in (getattr(config, "admin_tools", None) or DEFAULT_ADMIN_TOOLS)]
    if _match_tool_rules(tool_name, admin_rules):
        return False, texts.t(
            "tool_permission_denied",
            tool=tool_name,
            user_id=str(user_id) or "unknown",
            platform=platform or "unknown",
        )
    return False, texts.t(
        "tool_permission_denied",
        tool=tool_name,
        user_id=str(user_id) or "unknown",
        platform=platform or "unknown",
    )

CAPABILITY_PROMPT = (
    "Sending messages: platforms differ in capabilities. When the user names a target platform "
    "(e.g. send to YunHu/QQ/Telegram), first call list_platforms to inspect that platform's "
    "supported send methods, then decide yourself which method fits the content and context — "
    "prefer Markdown or Html for formatted text, Image/Voice/Video for media, plain Text otherwise. "
    "Note: on QQ-like platforms Markdown is limited (tables and code blocks usually do NOT render) "
    "— keep formatting simple. "
    "send_message picks and downgrades automatically; send_dsl exposes the full chain "
    "(Using / rules / modifiers / any method) when you need explicit control. "
    "The system automatically packages the reply of a tool run — any run in which you called "
    "tools — into a forward message together with the tool trace; casual chat without tools is "
    "sent as normal messages regardless of length. After finishing a tool run, do NOT send an "
    "extra summary/recap via send_message, and do not narrate what you just sent "
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
        self.runner = None
        self.eco = None
        self.mcp = None
        self.scheduler = None
        self.dashboard = None
        self.takeover: dict = {}
        self._chat_locks: dict = {}
        self._pending: dict = {}

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
        self.sessions = SessionManager(self.sdk, self.cfg)
        self.memory = MemoryStore(self.sdk, self.cfg)
        self.skills = SkillManager(self.sdk, self.cfg)
        self.runner = AgentRunner(self.pool, self.registry, self.cfg)
        self.eco = EcosystemBridge(self)
        self.mcp = MCPManager(self)
        self.scheduler = Scheduler(self)
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
        schedule.register(self.registry, self)
        skilltools.register(self.registry, self)
        agent.register(self.registry, self)
        selfconfig.register(self.registry, self)
        takumi.register(self.registry, self)

    def _register_handlers(self) -> None:
        message.on_message(priority=50)(self._on_message)
        command("agent", help="QvQChat")(self._cmd_agent)
        if "agent" not in getattr(command, "commands", {}):
            self.logger.warning("command 'agent' was not registered")

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

    @staticmethod
    def _chat_key_of(event) -> str:
        platform = event.get_platform() or ""
        if event.is_group_message():
            return make_chat_key(platform, "group", str(event.get_group_id() or ""))
        return make_chat_key(platform, "private", str(event.get_user_id() or ""))

    def _chat_ctx(self, event, chat_key: str) -> ToolContext:
        platform, detail_type, target_id = parse_chat_key(chat_key)
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
            if not self._should_trigger(event, chat_key, text):
                return
            event.done()
            images = self._extract_images(event)
            self._batch_message(event, chat_key, text, images)
        except Exception as e:
            self.logger.warning(f"on_message failed: {e}")

    def _reply_methods(self, event) -> list:
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

    @staticmethod
    def _is_recap(reply: str, tool_trace: list) -> bool:
        if not tool_trace or not any(t.get("tool") == "send_message" for t in tool_trace):
            return False
        text = reply.strip()
        if len(text) > 150:
            return False
        return bool(re.match(r"^(已[经把完成向]|好[的了]|已发送|已发出|done|sent)", text))

    async def _try_forward(self, event, reply: str, tool_trace: list, force: bool | None = None) -> bool:
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
        if force is not True:
            # 打包与否看运行方式，不看文本长度：用了工具的长任务回复转合并转发，纯对话不转
            if not getattr(self.cfg, "forward_enabled", True):
                return False
            if not tool_trace:
                return False
        sections: list = []
        if tool_trace:
            lines = []
            for entry in tool_trace[:10]:
                lines.append(f"{entry.get('tool', '')}({utils.truncate(str(entry.get('arguments', '')), 80)})")
                output = utils.truncate(str(entry.get("output", "")), 200).replace("\n", " ")
                lines.append(texts.t("forward_result", output=output))
            if lines:
                sections.append(texts.t("forward_process_title") + "\n" + "\n".join(lines))
        sections += utils.split_reply_sections(reply)
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
            # 自适应打包：适配器实现 Forward(nodes) 即支持（合并转发/富文本折叠由适配器决定），
            # 未实现或发送失败返回 ""，走普通文本发送兜底
            used = await utils.deliver_forward(adapter, detail_type, target_id, sections, sends)
        except Exception as e:
            self.logger.warning(f"forward send failed, fallback to normal reply: {e}")
            return False
        if used:
            return True
        return False

    def _lock_for(self, chat_key: str) -> asyncio.Lock:
        lock = self._chat_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_key] = lock
        return lock

    def _usage_today(self) -> dict:
        data = self.sdk.storage.get(f"QvQChat:usage:{time.strftime('%Y-%m-%d')}", {})
        return data if isinstance(data, dict) else {}

    def record_usage(self, chat_key: str, usage: dict) -> None:
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
                }
            )
        return history

    def _lock_for(self, chat_key: str) -> asyncio.Lock:
        lock = self._chat_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_key] = lock
        return lock

    def _batch_message(self, event, chat_key: str, text: str, images: list) -> None:
        # 聚合窗口：首条消息到达后等待 aggregate_window 秒，窗口内后续消息合并为一次请求
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
            persona = self.personas.resolve(chat_key)
            system = self._build_system(persona, scene, chat_key=chat_key)
            recalled = self.memory.recall(chat_key, query=combined_text or labeled, limit=int(getattr(self.cfg, "memory_recall", 6)))
            if recalled:
                lines = "\n".join(f"- {entry.get('content', '')}" for entry in recalled)
                system += "\n\nRelated memories:\n" + lines
            # 统一管道：平台侧运行也注册进 LiveRegistry，网页端可实时观看/取消
            # busy 时中断旧任务，新任务带中断上下文 —— 必须先于取上下文完成，
            # 否则中断提示写不进本次请求
            interrupted_note = ""
            live = None
            registry = getattr(self, "live_registry", None)
            if registry is not None:
                old_live = registry.get(chat_key)
                if old_live and old_live.status == "running" and old_live.text.strip():
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
            await self._compress_context_if_needed(chat_key)
            contexts = self.sessions.get_contexts(chat_key)
            if interrupted_note:
                contexts.append({"role": "user", "content": interrupted_note})
            if not contexts:
                contexts = await self._seed_history(event)
                if not is_group and sender_id:
                    cross = self.sessions.recent_user_messages(sender_id, exclude_chat_key=chat_key)
                    if cross:
                        lines: list = []
                        for item in cross:
                            lines.append(f"[来自 {item['label']}]")
                            lines.append(item["content"])
                        contexts.append(
                            {
                                "role": "user",
                                "content": texts.t("cross_session_header") + "\n" + "\n".join(lines),
                            }
                        )
                contexts = self.sessions.seed_contexts(chat_key, contexts)
            images = [
                converted
                for raw in all_images
                for converted in [self._to_model_image(raw)]
                if converted
            ]
            user_msg: dict = {"role": "user", "content": labeled}
            if images:
                parts: list = [{"type": "text", "text": labeled}]
                parts += [{"type": "image_url", "image_url": {"url": url}} for url in images]
                user_msg["content"] = parts
            self.sessions.append_user(chat_key, user_msg["content"], sender_id=sender_id if is_group else "")
            limit = int(getattr(self.cfg, "daily_token_limit", 0) or 0)
            if limit:
                used_today = int(self._usage_today().get("tokens", 0) or 0)
                if used_today >= limit and not self.is_admin(sender_id, "chat", event.get_platform() or ""):
                    await event.reply(texts.t("daily_limit_reached", used=used_today, limit=limit))
                    return
            async def on_tool_round(calls):
                # 仅 all 模式发工具明细；brief 模式以 AI 发言代替，不打断
                if getattr(self.cfg, "tool_notice_mode", "brief") != "all":
                    return
                labels = [
                    f"{call['name']}({call['arguments']})" if call["arguments"] else call["name"]
                    for call in calls[:3]
                ]
                suffix = " …" if len(calls) > 3 else ""
                await event.reply(texts.t("processing_notice", tools="、".join(labels) + suffix))

            async def on_intermediate(speech):
                # 仅 all 模式发阶段性发言；brief 由 AI 通过 send_message 工具主动播报
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
                # 网页端停止：半截回复落库并按完成收尾
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
            self.record_usage(chat_key, result.usage)
            reply = result.text.strip()
            force_forward: bool | None = None
            tag = OUTPUT_TAG_RE.match(reply)
            if tag:
                force_forward = tag.group(1) == "转发"
                reply = reply[tag.end():].strip()
            reply = reply or texts.t("no_reply_content")
            self.sessions.append(chat_key, "assistant", reply, trace=result.tool_trace, rounds=getattr(result, "rounds", None))
            try:
                await self.sdk.lifecycle.emit(
                    "qvq.replied",
                    {"chat_key": chat_key, "reply": reply, "tools": len(result.tool_trace)},
                )
            except Exception:
                pass
            if self._is_recap(reply, result.tool_trace):
                self.logger.info("reply suppressed as send recap")
                return
            if await self._try_forward(event, reply, result.tool_trace, force=force_forward):
                return
            last_error: Exception | None = None
            for method in self._reply_methods(event):
                content = utils.markdown_to_text(reply) if method == "Text" else reply
                try:
                    await event.reply(content, method=method)
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
            if last_error is not None:
                self.logger.warning(f"reply failed: {last_error}")
            overflow = self.sessions.trim_overflow(chat_key, keep=max(2, int(getattr(self.cfg, "context_limit", 30))))
            if overflow and getattr(self.cfg, "context_summary", True):
                self.spawn(self._summarize_context(chat_key, overflow))
        except Exception as e:
            self.logger.warning(f"process failed: {e}")

    @staticmethod
    def _estimate_tokens(text) -> int:
        """粗估 token 数：中文约 1.5 字/token，混合文本按 2 字符/token 计。"""
        return len(str(text or "")) // 2

    def _context_tokens(self, contexts: list) -> int:
        return sum(self._estimate_tokens(m.get("content") if isinstance(m, dict) else m) for m in contexts)

    async def _compress_context_if_needed(self, chat_key: str) -> None:
        """请求前压缩：估算上下文超过阈值时，把旧消息压缩为摘要（同步执行，确保本次请求生效）。"""
        limit = int(getattr(self.cfg, "context_compress_tokens", 12000) or 0)
        if limit <= 0 or not getattr(self.cfg, "context_summary", True):
            return
        contexts = self.sessions.get_contexts(chat_key)
        if self._context_tokens(contexts) <= limit:
            return
        # 从最旧开始裁一半（至少保留最近 8 条），压缩为摘要
        keep = max(8, len(contexts) // 2)
        overflow = contexts[:-keep] if keep < len(contexts) else []
        if not overflow:
            return
        try:
            await self._summarize_context(chat_key, overflow)
            self.sessions.replace_contexts(chat_key, contexts[-keep:])
            self.logger.info(f"context compressed: {chat_key} (-{len(overflow)} msgs)")
        except Exception as e:
            self.logger.warning(f"context compress failed: {e}")

    async def _summarize_context(self, chat_key: str, removed: list) -> None:
        try:
            transcript = "\n".join(
                f"{m.get('role')}: {str(m.get('content'))[:200]}"
                for m in removed
                if isinstance(m, dict)
            )
            response = await self.pool.chat(
                ChatRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Summarize the following conversation excerpt into concise bullet "
                                "points in the same language as the content. Keep names, ids, "
                                "decisions and unresolved questions."
                            ),
                        },
                        {"role": "user", "content": transcript[:6000]},
                    ]
                )
            )
            text = (response.content or "").strip()
            if text:
                self.sessions.append_summary(chat_key, text)
        except Exception as e:
            self.logger.warning(f"context summarize failed: {e}")

    def _build_system(self, persona: dict, scene: str = "", chat_key: str = "") -> str:
        system = persona["system"] + "\n" + utils.time_line()
        if scene:
            system += "\n" + scene
        if chat_key:
            summary = self.sessions.summary_of(chat_key)
            if summary:
                system += "\nEarlier conversation summary (older than recent messages):\n" + summary
        system += "\n" + CAPABILITY_PROMPT
        system += "\n" + texts.t("system_brevity")
        skills = [s for s in self.skills.list_skills() if s.get("enabled")] if self.skills else []
        if skills:
            lines = "\n".join(f"- {s['name']}: {s.get('description') or ''}" for s in skills)
            system += "\n\n<skills>\n" + texts.t("skills_system_note") + "\n" + lines + "\n</skills>"
        for line in getattr(self.cfg, "extra_prompts", []) or []:
            line = str(line).strip()
            if line:
                system += "\n" + line
        return system

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
        platform, detail_type, target_id = parse_chat_key(chat_key)
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
        await self._compress_context_if_needed(chat_key)
        persona = self.personas.get(persona_id) if persona_id else self.personas.resolve(chat_key)
        system = self._build_system(persona)
        messages: list = []
        # 定时/后台任务：告诉 AI 内容要用 send_message 自行投递，投递过就不再补发总结
        if send and platform:
            messages.append({"role": "system", "content": texts.t("task_run_note")})
        messages.append({"role": "user", "content": prompt})
        result = await self.runner.run(
            system=system,
            messages=messages,
            ctx=ctx,
            persona_tools=persona.get("tools"),
        )
        reply = result.text.strip() or texts.t("no_reply_content")
        if send and platform:
            # AI 已在本运行中向该目标投递过内容（如日报本身）→ 总结段不再补发，避免双发
            delivered = any(
                sent_platform == platform and sent_type == detail_type and sent_id == target_id
                for sent_platform, sent_type, sent_id in ctx.sent_log
            )
            if not delivered:
                # 打包与否看运行方式：用了工具的任务投递转合并转发，纯文本回答普通发送
                await self._send_segments(
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
        platform, detail_type, target_id = parse_chat_key(chat_key)
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
        await self._compress_context_if_needed(chat_key)
        persona = self.personas.get(persona_id) if persona_id else self.personas.resolve(chat_key)
        system = self._build_system(persona, chat_key=chat_key)
        recalled = self.memory.recall(chat_key, query=text, limit=int(getattr(self.cfg, "memory_recall", 6)))
        if recalled:
            lines = "\n".join(f"- {entry.get('content', '')}" for entry in recalled)
            system += "\n\nRelated memories:\n" + lines
        for name in skill_names or []:
            skill = self.skills.get_skill(str(name))
            if not skill:
                continue
            system += (
                "\n\n<active-skill name=\"" + str(name) + "\">\n"
                + utils.truncate(str(skill.get("body") or ""), 8000)
                + "\n</active-skill>"
            )
        tools_hint = [str(t) for t in (mcp_tools or []) if str(t)]
        if tools_hint:
            system += "\n\n" + texts.t("dashboard_mcp_hint", tools=", ".join(tools_hint))
        contexts = self.sessions.get_contexts(chat_key)
        user_msg: dict = {"role": "user", "content": text}
        if images:
            parts: list = [{"type": "text", "text": text}] if text else []
            parts += [{"type": "image_url", "image_url": {"url": url}} for url in images[:3]]
            user_msg["content"] = parts
        self.sessions.append_user(chat_key, user_msg["content"], sender_id="dashboard")
        result = await self.runner.run(
            system=system,
            messages=contexts + [user_msg],
            ctx=ctx,
            persona_tools=persona.get("tools"),
            model=model or None,
            temperature=temperature,
            on_delta=on_delta,
            on_reset=on_reset,
            on_tool_event=on_tool_event,
        )
        self.record_usage(chat_key, result.usage)
        reply = result.text.strip() or texts.t("no_reply_content")
        self.sessions.append(chat_key, "assistant", reply, trace=result.tool_trace, rounds=getattr(result, "rounds", None))
        overflow = self.sessions.trim_overflow(chat_key, keep=max(2, int(getattr(self.cfg, "context_limit", 30))))
        if overflow and getattr(self.cfg, "context_summary", True):
            self.spawn(self._summarize_context(chat_key, overflow))
        if not self.sessions.group_name_of(chat_key):
            self.spawn(self._title_task(chat_key, text, reply))
        return reply

    async def _title_task(self, chat_key: str, user_text: str, reply: str) -> None:
        """为无名字的会话用模型生成一个短标题（失败静默）。"""
        from .engine.base import ChatRequest

        try:
            resp = await self.pool.chat(ChatRequest(
                messages=[
                    {"role": "system", "content": texts.t("title_system")},
                    {"role": "user", "content": utils.truncate(user_text, 200) + "\n---\n" + utils.truncate(reply, 300)},
                ],
                max_tokens=48,
                temperature=0.3,
            ))
            title = (resp.content or "").strip().strip("\"“”‘’。.!!??")
            title = title.splitlines()[0][:40] if title else ""
            if title:
                self.sessions.set_group_name(chat_key, title)
        except Exception as e:
            self.logger.warning(f"title generation failed: {e}")

    async def resolve_session_names(self, sessions: list[dict]) -> None:
        """后台尽力解析会话显示名（群名/昵称），写入缓存供下次列表使用。"""
        for session in sessions[:20]:
            chat_key = str(session.get("chat_key") or "")
            if session.get("name") or not chat_key:
                continue
            platform = str(session.get("platform") or "")
            detail_type = str(session.get("detail_type") or "")
            target_id = str(session.get("target_id") or "")
            if platform == "dashboard" or not platform or not target_id:
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
                        self.sessions.set_group_name(chat_key, name)
                else:
                    for endpoint in ("get_stranger_info", "get_user_info"):
                        try:
                            info = await asyncio.wait_for(adapter.call_api(endpoint, user_id=target_id), 6)
                        except Exception:
                            continue
                        if isinstance(info, dict):
                            name = str(info.get("nickname") or info.get("card") or "")
                            if name:
                                break
                    if name:
                        self.sessions.set_user_name(chat_key, name)
            except Exception:
                continue

    async def run_task(self, task: dict) -> None:
        target_type = str(task.get("target_type") or "user")
        detail_type = "group" if target_type == "group" else "private"
        chat_key = make_chat_key(str(task.get("platform") or ""), detail_type, str(task.get("target_id") or ""))
        # 权限随创建者：框架/网页创建的任务以主人身份运行；聊天端创建的沿用创建者身份
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

    async def _send_segments(self, platform: str, detail_type: str, target_id: str, segments,
                             from_tools: bool = False) -> None:
        adapter = self.sdk.adapter.get(platform)
        if adapter is None:
            self.logger.warning(texts.t("adapter_not_found", platform=platform))
            return
        target_type = detail_type if detail_type in ("group", "channel") else "user"
        try:
            sends = list(self.sdk.adapter.list_sends(platform))
        except Exception:
            sends = []
        # 打包与否看运行方式，不看文本长度：工具长任务的投递转合并转发，纯文本回答普通发送
        if getattr(self.cfg, "forward_enabled", True) and from_tools:
            try:
                # 自适应打包：onebot11 走专用 forward 端点→Raw_ob12；其它平台 HTML 卡片/Markdown；全败走下方普通文本
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
                self.logger.warning(f"forward send failed, fallback: {e}")
        for delay, segment in segments:
            if delay > 0:
                await asyncio.sleep(delay)
            methods = [erispulse.pick_send_method(sends)]
            if "Text" not in methods:
                methods.append("Text")
            sent = False
            for name in methods:
                content = utils.markdown_to_text(segment) if name == "Text" else segment
                try:
                    await getattr(adapter.Send.To(target_type, target_id), name)(content)
                    sent = True
                    break
                except Exception as e:
                    self.logger.warning(f"send via {name} failed: {e}")
            if not sent:
                self.logger.warning(f"send to {platform}/{target_type}/{target_id} failed")
                return

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
