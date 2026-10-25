from __future__ import annotations

from ErisPulse import sdk
from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import command, message
from ErisPulse.loaders import ModuleLoadStrategy

try:
    from ErisPulse.Core.Bases import ModuleMeta
except ImportError:
    ModuleMeta = None

from . import texts, utils
from .chat.cli import CliMixin
from .chat.inbox import InboxMixin
from .chat.usage import UsageMixin
from .conversation.delivery import Delivery
from .conversation.memory import MemoryStore
from .conversation.service import ConversationService, make_chat_key, parse_chat_key, strip_isolation
from .dashboard.live import bind as live_bind# noqa: F401 — 兼容引用（本体在 chat/inbox 使用）
from .prompts import CAPABILITY_PROMPT# 本体已迁 prompts.py；导入即保持 QvQChat.Main.CAPABILITY_PROMPT 兼容引用
from .Config import QvQConfig
from .I18n import QvQI18n
from .agent.persona import PersonaManager
from .agent.runner import AgentRunner
from .agent.tools import ToolContext, ToolRegistry
from .bridge.ecosystem import EcosystemBridge
from .bridge.mcp import MCPManager
from .engine.base import ChatRequest# noqa: F401 — 兼容引用（本体在 chat/inbox 使用）
from .engine.base import TaskSpec
from .engine.pool import ModelPool
from .scheduler import Scheduler
from .skills import SkillManager
from .tools_builtin import agent, code, computer, erispulse, knowledge, memory, schedule, selfconfig, skilltools, takumi
from .version import __version__

AUDIT_KEY = "QvQChat:audit"
AUDIT_LIMIT = 500

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
# 主人判定失败时退回 admins 名单（权限兜底语义，不做噪音日志）
            pass
    admins = [str(a) for a in (getattr(config, "admins", []) or [])]
    return bool(admins) and str(user_id) in admins


def _match_tool_rules(name: str, rules) -> bool:
# 收编到 utils.match_pattern（保留本名供既有引用/测试使用）
    return utils.match_pattern(name, rules)


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


class Main(InboxMixin, UsageMixin, CliMixin, BaseModule):
    """消息入口/用量/命令逻辑分别拆至 chat/inbox.py、chat/usage.py、chat/cli.py。

    mixin 继承保证全部历史方法名（含 _on_message/_process_locked/record_usage 等）
    仍可通过 getattr_static(Main, name) 在本类上解析到。
    """

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
        self.participation = None
        self.takeover: dict = {}
        self.plugin_settings_catalog: dict = {}
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
                {"name": "speak", "description": "主动向会话发言（插件主动开口唯一出口，先过输出预算护栏），返回发送文本或拒绝原因", "signature": "(chat_key: str, reason: str = '', prompt: str = '', persona_id: str = '') -> str"},
                {"name": "describe_image", "description": "用视觉模型描述一张图片（表情包收录打标签等场景），返回描述文本", "signature": "(url: str, prompt: str = '') -> str"},
                {"name": "plugin_config", "description": "读取插件设置（qvq_settings 描述符默认值与已存覆盖值合并；module 过滤，空返回全部）", "signature": "(module: str = '') -> dict"},
                {"name": "participation_status", "description": "获取群聊参与决策状态：提供者目录、输出预算现状、最近决策日志", "signature": "() -> dict"},
            ],
        )
        if ModuleMeta is None:
            return info
        return ModuleMeta(**info)

    async def on_load(self, event) -> bool:
        texts.register_texts()
# A2: token 估算配置提前注入（幂等；Compactor/Service/Pool 构造时也会注入）
        from .engine import tokens
        tokens.configure(self.cfg)
        self.pool = ModelPool(self.sdk, self.cfg)
        self.registry = ToolRegistry()
        self.personas = PersonaManager(self.sdk)
        try:
# KV 绑定为权威源；conv state.persona 镜像过期则回填一次
            moved = self.personas.migrate_state_mirror()
            if moved:
                self.logger.info(f"persona binding migration: {moved} session mirrors synced from KV")
        except Exception as e:
            self.logger.debug(f"persona mirror migration failed: {e}")
        self.conversations = ConversationService(self)
        self.sessions = self.conversations
        self.memory = MemoryStore(self.sdk, self.cfg)
        from .conversation.knowledge import KnowledgeBase
        self.knowledge = KnowledgeBase(self.sdk, self.cfg)
        self.skills = SkillManager(self.sdk, self.cfg)
        self.runner = AgentRunner(self.pool, self.registry, self.cfg)
        self.eco = EcosystemBridge(self)
        self.mcp = MCPManager(self)
# 参与决策（qvq.observe 旁听窗口 + qvq_decision 提供者发现，默认关闭）
        from .participation import ParticipationManager

        self.participation = ParticipationManager(self)
        self.participation.start()
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
        except Exception as e:
            self.logger.debug(f"mcp close_all failed: {e}")
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
                except Exception as e:
                    self.logger.debug(f"takeover lease release failed: {e}")
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
        except Exception as e:
# 审计落盘失败不能完全静默
            self.logger.debug(f"audit persist failed: {e}")

    async def run_prompt(self, chat_key: str, prompt: str, persona_id: str = "",
                         origin: str = "task", send: bool = True, user_id: str = "",
                         model: str = "", task_kind: str = "chat") -> str:
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
# A2: task_kind 尾参——runner 暂未暴露 kind，非默认类别先经 TaskSpec 解析
# （cfg.task_models[kind]）得到任务模型，作为显式 model 传给 runner.run
        resolved_model = str(model or "")
        if not resolved_model and task_kind and task_kind != "chat":
            resolver = getattr(self.pool, "resolve_task_model", None)
            if callable(resolver):
                try:
                    resolved_model = str((resolver(TaskSpec(kind=task_kind)) or {}).get("id") or "")
                except Exception as e:
                    self.logger.debug(f"task model resolve failed: {e}")
# 与聊天/面板同一把 per-chat 锁（本方法不与 _process_locked 互相嵌套，无死锁）
        async with self._lock_for(chat_key):
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
                model=(resolved_model or prepared.get("model") or "") or None,
                task_kind=task_kind,
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
        on_reasoning=None,
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
# prepare→finalize 段持 per-chat 锁，与聊天触发/定时任务互斥写上下文
        async with self._lock_for(chat_key):
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
                on_reasoning=on_reasoning,
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
# A2: 任务分派字段透传（task_models[kind] / 显式模型）
        await self.run_prompt(
            chat_key,
            str(task.get("prompt") or ""),
            persona_id=str(task.get("persona") or ""),
            origin=origin,
            user_id=str(task.get("created_by") or ""),
            model=str(task.get("model") or ""),
            task_kind=str(task.get("task_kind") or "chat"),
        )

    async def chat(self, session_id: str, prompt: str, persona: str = "") -> str:
        return await self.run_prompt(session_id, prompt, persona_id=persona, origin="rpc", send=False)

    async def describe_image(self, url: str, prompt: str = "") -> str:
        """用视觉模型描述一张图片（表情包收录打标签等），无视觉能力时返回空串。"""
        if not url:
            return ""
        try:
            descriptions = await self.pool.describe_images([url], prompt=prompt)
            return str(descriptions[0]) if descriptions else ""
        except Exception as e:
            self.logger.warning(f"describe_image failed: {e}")
            return ""

    async def speak(self, chat_key: str, reason: str = "", prompt: str = "",
                    persona_id: str = "", **_) -> str:
        """扩展点 C：插件主动发言唯一出口。

        先过 SpeechBudget（kind="proactive"，全局每日/每群小时/冷却护栏，不可绕过），
        拒绝返回原因文本；通过则记账并走 run_prompt（origin="proactive" 记账可观测）。
        """
        manager = getattr(self, "participation", None)
        budget = getattr(manager, "budget", None) if manager is not None else None
        chat_key = str(chat_key or "")
        if budget is None or not chat_key:
            return texts.t("participate_disabled")

        def _log_proactive(ok: bool, why: str) -> None:
            if manager is not None:
                manager.log_decision({
                    "kind": "proactive",
                    "chat_key": chat_key,
                    "decision": "speak",
                    "reason": why or str(reason or ""),
                    "provider": "",
                    "providers_queried": [],
                    "score": None,
                    "budget_ok": ok,
                    "ts": utils.now_ts(),
                })

        ok, why = budget.allow(chat_key, "proactive")
        if not ok:
            _log_proactive(False, why)
            self.logger.info(f"proactive speak denied ({chat_key}): {why}")
            return why
        budget.record(chat_key, "proactive")
        reply = await self.run_prompt(
            chat_key,
            str(prompt or "") or texts.t("participate_speak_prompt"),
            persona_id=str(persona_id or ""),
            origin="proactive",
            send=True,
        )
        _log_proactive(True, "")
        return reply

    async def plugin_config(self, module: str = "", **_) -> dict:
        """插件设置读取：qvq_settings 描述符默认值 + 已存覆盖值合并；module 过滤。"""
        from .pluginsettings import load_overrides, merge_entry

        catalog = getattr(self, "plugin_settings_catalog", None)
        if not isinstance(catalog, dict):
            catalog = {}
        result = {}
        for name, entry in catalog.items():
            if module and name != module:
                continue
            result[name] = merge_entry(entry if isinstance(entry, dict) else {}, load_overrides(self.sdk, name))
        return result

    async def participation_status(self, **_) -> dict:
        """参与决策观测（提供者目录 + 输出预算现状 + 最近决策环形日志）。"""
        manager = getattr(self, "participation", None)
        if manager is None:
            return {
                "enabled": bool(getattr(self.cfg, "participation_enabled", False)),
                "providers": [],
                "budget": {},
                "decisions": [],
            }
        return manager.status()

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
