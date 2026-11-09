from __future__ import annotations

import time

from ErisPulse import sdk
from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import command, message, notice, request
from ErisPulse.loaders import ModuleLoadStrategy

try:
    from ErisPulse.Core.Bases import ModuleMeta
except ImportError:
    ModuleMeta = None

from . import texts, utils
from .chat.cli import CliMixin
from .chat.events import EventsMixin
from .chat.inbox import InboxMixin, _int_or_none, _num_or_none
from .chat.usage import UsageMixin
from .conversation.delivery import Delivery
from .conversation.memory import MemoryStore
from .conversation.service import ConversationService, account_of as _account_of, make_chat_key, parse_chat_key, strip_isolation
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
from .tools_builtin import agent, code, computer, erispulse, knowledge, memory, schedule, selfconfig, skilltools, takumi, todo
from .version import __version__

AUDIT_KEY = "QvQChat:audit"

LOCAL_ORIGINS = ("dashboard", "rpc")


def _master_config_users() -> object:
    """读取框架主人配置原始 users 值（list=全局主人 / dict=按平台）。失败返回 None。"""
    try:
        from ErisPulse.runtime.frame_config import get_master_config

        return (get_master_config() or {}).get("users")
    except Exception:
        return None


def _flatten_masters(data) -> tuple[set[str], dict[str, set[str]]]:
    """递归展平主人表，兼容所有已知形态：

    - list/set：全局主人
    - {"global": [ids]}：全局主人
    - {"platform": [ids]}：平台主人
    - {"platform": {account: [ids]}}：多账户部署下的平台→账户→主人嵌套
      （账户层展开后归并到平台；同一人在多账户只配置一次）
    - 平台键下的散值（非列表）：视为单元素集合
    """
    global_ids: set[str] = set()
    platform_ids: dict[str, set[str]] = {}

    def walk(node, platform: str) -> None:
        if isinstance(node, (list, tuple, set)):
            ids = {str(i) for i in node if str(i).strip()}
            if platform in ("", "global"):
                global_ids.update(ids)
            else:
                platform_ids.setdefault(platform, set()).update(ids)
            return
        if not isinstance(node, dict):
# 散值（int/str）：当作单元素主人列表
            text = str(node).strip()
            if text:
                if platform in ("", "global"):
                    global_ids.add(text)
                else:
                    platform_ids.setdefault(platform, set()).add(text)
            return
        for key, value in node.items():
            name = str(key).strip()
            if name.lower() == "global":
                walk(value, "global")
            elif platform and platform != "global":
                walk(value, platform)  # 已锁定平台（账户层），继续深入
            else:
                walk(value, name)

    walk(data, "")
    return global_ids, platform_ids


def framework_masters() -> tuple[set[str], dict[str, set[str]]]:
    """直接读取框架主人表（不依赖 is_master 的版本行为）。

    返回 (全局主人集合, {平台: 主人集合})。优先用 master.list()（含运行时 add 的
    主人），失败则退回原始配置 users。这样即便旧框架的 is_master 判否/抛错，
    「默认以框架主人为管理员」的语义仍然成立。
    """
    try:
        from ErisPulse.Core import master as master_manager

        data = master_manager.list()
    except Exception:
        data = None
    if isinstance(data, (dict, list)):
        global_ids, platform_ids = _flatten_masters(data)
        if global_ids or platform_ids:
            return global_ids, platform_ids
    users = _master_config_users()
    if isinstance(users, (list, dict)):
        return _flatten_masters(users)
    return set(), {}


def _platform_matches(config_platform: str, actual_platform: str) -> bool:
    """平台名宽容匹配：精确 / 前缀（onebot vs onebot11）/ 通配（onebot*）。"""
    config_platform = str(config_platform or "").strip().lower()
    actual_platform = str(actual_platform or "").strip().lower()
    if not config_platform or not actual_platform:
        return False
    if config_platform == actual_platform:
        return True
    if config_platform.endswith("*") and actual_platform.startswith(config_platform[:-1]):
        return True
    return actual_platform.startswith(config_platform) or config_platform.startswith(actual_platform)


def is_framework_master(user_id: str, platform: str = "") -> bool:
    """是否为框架主人（全局，或本平台的平台主人）。"""
    uid = str(user_id or "")
    if not uid:
        return False
    global_ids, platform_ids = framework_masters()
    if uid in global_ids:
        return True
    for configured, ids in platform_ids.items():
        if uid in ids and _platform_matches(configured, platform):
            return True
    return False


def is_admin_user(config, user_id: str, origin: str = "chat", platform: str = "",
                  master_checker=None, logger=None) -> bool:
    """管理员判定：本地来源 > 框架主人（is_master 或直读主人表）> admins 名单。

    默认没有配置 admins 时，框架主人就是管理员——is_master 若因框架版本/签名
    差异判否，这里直接读主人表兜底，不把判定权交给单一实现。
    """
    if origin in LOCAL_ORIGINS:
        return True
    uid = str(user_id or "")
    if master_checker is not None:
        try:
            if master_checker(platform, uid):
                return True
        except Exception as e:
# 不再静默吞：框架主人判定故障必须可见（限频，避免刷屏）
            _warn_once(logger, f"master_checker failed ({platform}/{uid}): {e}")
    if is_framework_master(uid, platform):
        return True
    admins = [str(a) for a in (getattr(config, "admins", []) or [])]
    return bool(admins) and uid in admins


_WARNED: set[str] = set()


def _warn_once(logger, message: str) -> None:
    key = message[:80]
    if key in _WARNED:
        return
    _WARNED.add(key)
    if logger is not None:
        try:
            logger.warning(message)
        except Exception:
            pass


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


class Main(InboxMixin, EventsMixin, UsageMixin, CliMixin, BaseModule):
    """消息入口/非消息事件/用量/命令逻辑分别拆至 chat/inbox.py、chat/events.py、
    chat/usage.py、chat/cli.py。

    mixin 继承保证全部历史方法名（含 _on_message/_process_locked/record_usage 等）
    仍可通过 getattr_static(Main, name) 在本类上解析到。
    """

    ConfigClass = QvQConfig
    I18nClass = QvQI18n

    def __init__(self):
        self.sdk = sdk
        self.logger = sdk.logger.get_child("QvQChat")
        self.started_at = time.time()  # 运行时长（状态卡）
# 跨账户同消息认领表：指纹 -> (账户, 时间戳, 是否@)，防多账户各跑一份
        self._msg_claims: dict = {}
# bot 连锁计数：chat_key -> 连续兄弟 bot 触发轮数（超限静默等真人）
        self._bot_chain: dict = {}
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
        self.plugin_settings_catalog: dict = {}# qvq_settings 归属标记：{module: title}
        self._chat_locks: dict = {}
        self._pending: dict = {}
        self._waiting: dict = {}
        self._merge_timers: dict = {}
        self._last_reply_ts: dict = {}
        self._proactive_recent: dict = {}
        self._interrupted_notes: dict = {}
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
                {"name": "plugin_config", "description": "读取插件设置（框架 config 中各模块当前存储值，{module: {key: value}}；module 过滤，空返回全部）", "signature": "(module: str = '') -> dict"},
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
# 统一扩展入口：生态模块经 qvq_extensions 贡献的技能/知识只读并入本模块
        if self.skills is not None:
            self.skills.set_external_provider(self.eco.external_skills)
        if self.knowledge is not None:
            self.knowledge.set_external_provider(self.eco.external_knowledge)
# 内置 ErisPulse 文档检索（版本跟随已安装框架，零 MCP 依赖）
        from .bridge.docs import ErisPulseDocs

        self.docs = ErisPulseDocs(self)
# 参与决策（qvq.observe 旁听窗口 + qvq_decision 提供者发现，默认关闭）
        from .participation import ParticipationManager

        self.participation = ParticipationManager(self)
        self.participation.start()
        self.scheduler = Scheduler(self)
        self.delivery = Delivery(self)
        self._register_builtin_tools()
        self._register_handlers()
        self._register_subagent_listener()
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
            docs_info = await self.docs.ensure_synced()
            self.logger.info(f"docs: {docs_info}")
        except Exception as e:
            self.logger.warning(f"docs sync failed: {e}")
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
        todo.register(self.registry, self)
        skilltools.register(self.registry, self)
        agent.register(self.registry, self)
        selfconfig.register(self.registry, self)
        takumi.register(self.registry, self)
        from .tools_builtin import dev as dev_tools, docs as docs_tools, web as web_tools, files as file_tools

        docs_tools.register(self.registry, self)
        web_tools.register(self.registry, self)
        dev_tools.register(self.registry, self)
        file_tools.register(self.registry, self)

    def _register_handlers(self) -> None:
# 置顶消息处理器（高于框架命令分发器的 priority=100）：分工是"让路 + 认领"——
# 命令前缀消息不认领直接放行给下方分发器；自己接手回复的消息处理完即 event.done()
# 认领（_on_message 内），其它模块就不会对同一条消息再答一遍
        message.on_message(priority=99999)(self._on_message)
# 非消息事件总线：通知/请求入收件箱并按配置唤醒/决策（高优先级先见事件，
# 不主动 event.done 认领——通知/请求没有命令分发器竞争）
        notice.on_notice(priority=99998)(self._on_notice)
        request.on_request(priority=99998)(self._on_request)
        for name in ("qvq", "agent", "qvqchat"):
            command(name, help="QvQChat")(self._cmd_agent)
        registered = getattr(command, "commands", {})
        missing = [n for n in ("qvq", "agent") if n not in registered]
        if missing:
            self.logger.warning(f"commands not registered: {', '.join(missing)}")

    def _register_subagent_listener(self) -> None:
        """后台子智能体完成事件 → 结果插回主会话（发起时 spawn 的那个群/私聊）。"""
        lifecycle = getattr(self.sdk, "lifecycle", None)
        if lifecycle is None:
            return
        lifecycle.register("qvq.subagent_done", self._on_subagent_done)

    def _on_subagent_done(self, data) -> None:
# 事件链立刻返回：插回消化在独立任务里跑（emit 等全部处理器完成才返回，
# 不 spawn 会拖住后台子智能体收尾）
        if not isinstance(data, dict):
            return
        parent = str(data.get("parent_chat_key") or "")
        if not parent:
            return
        self.spawn(self._digest_subagent(parent, data))

    async def _digest_subagent(self, parent_chat_key: str, data: dict) -> None:
        task = str(data.get("task") or "")
        answer = str(data.get("answer") or "")
        sub_key = str(data.get("sub_key") or "")
        prompt = texts.t("subagent_report_prompt", task=utils.truncate(task, 200),
                         answer=utils.truncate(answer, 3500), session=sub_key)
        try:
            await self.run_prompt(parent_chat_key, prompt, origin="proactive",
                                  persist=True, scene=texts.t("scene_subagent_report"))
        except Exception as e:
            self.logger.warning(f"subagent digest failed: {type(e).__name__}: {e}")

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
        return is_admin_user(self.cfg, user_id, origin, platform, self._master_checker(), self.logger)

    def diagnose_admin(self, user_id: str, origin: str = "chat", platform: str = "") -> dict:
        """管理员判定诊断：框架版本/主人配置形态/各判定分支结果（whoami 命令与排障用）。"""
        framework_version = ""
        try:
            from importlib.metadata import version as _pkg_version

            framework_version = _pkg_version("ErisPulse")
        except Exception:
            try:
                import ErisPulse as _ep

                framework_version = str(getattr(_ep, "__version__", "") or "")
            except Exception:
                framework_version = "unknown"
        users = _master_config_users()
        global_ids, platform_ids = framework_masters()
        master_call = None
        master_error = ""
        try:
            master_call = bool(self._master_checker()(platform, str(user_id)))
        except Exception as e:
            master_error = str(e)
        admins = [str(a) for a in (getattr(self.cfg, "admins", []) or [])]
        uid = str(user_id)
        return {
            "framework_version": framework_version,
            "user_id": uid,
            "platform": str(platform or ""),
            "origin": str(origin or ""),
            "is_admin": self.is_admin(user_id, origin, platform),
            "master_is_master": master_call,
            "master_error": master_error,
            "master_users_shape": "list(global)" if isinstance(users, list) else ("dict(per-platform)" if isinstance(users, dict) else "missing"),
            "master_users": users if isinstance(users, (list, dict)) else None,
            # 直读主人表的判定（不依赖 is_master）：whoami 里能直接看出是哪条路径放行
            "framework_global_masters": sorted(global_ids),
            "framework_platform_masters": {k: sorted(v) for k, v in platform_ids.items()},
            "framework_master_matched": is_framework_master(uid, platform),
            "admins": admins,
            "admins_matched": bool(admins) and uid in admins,
        }

    def check_tool_permission(self, tool, ctx) -> tuple[bool, str]:
# 必须传 Tool 对象本体：tool_allowed 靠 getattr(tool, "access", "admin") 判 safe，
# 传 tool.name 字符串会让所有 safe 工具在调用期被当成 admin（普通用户连联网搜索都被拒）
        return tool_allowed(self.cfg, tool, ctx.user_id, ctx.origin, ctx.platform, self._master_checker())

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
            limit = int(getattr(self.cfg, "audit_limit", 5000) or 0)
            if limit > 0:
                entries = entries[-limit:]
# 写回存储（此前组装完 entries 直接丢弃——审计页永远为空）
            self.sdk.storage.set(AUDIT_KEY, entries)
        except Exception as e:
# 审计落盘失败不能完全静默
            self.logger.debug(f"audit persist failed: {e}")

    async def run_prompt(self, chat_key: str, prompt: str, persona_id: str = "",
                         origin: str = "task", send: bool = True, user_id: str = "",
                         model: str = "", task_kind: str = "chat", scene: str = "",
                         temperature: float | None = None, persist: bool = False) -> str:
        from .conversation.service import strip_account as _strip_account

        platform, detail_type, target_id = parse_chat_key(_strip_account(strip_isolation(chat_key)))
# 多账户：会话键 @账户 后缀还原出发送账户（工具主动发送要绑对 bot）
        self_id = ""
        if "@" in str(chat_key).rsplit(":", 2)[-1]:
            self_id = str(chat_key).rsplit("@", 1)[1] or ""
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
            self_id=self_id,
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
            prepared = await self.sessions.prepare(chat_key, prompt, persona_id=persona_id, persist=persist, scene=scene)
            messages: list = []
            if send and platform:
                messages.append({"role": "system", "content": texts.t("task_run_note")})
            messages.extend(prepared["contexts"] + [prepared["user_msg"]])
# 人格级覆盖（温度优先级：显式调用参数 > 人格 > 模型 > 全局）
            persona = prepared["persona"]
            p_temp = _num_or_none(persona.get("temperature")) if temperature is None else temperature
            p_maxtok = _int_or_none(persona.get("max_tokens"))
            result = await self.runner.run(
                system=prepared["system"],
                messages=messages,
                ctx=ctx,
                persona_tools=persona.get("tools"),
                model=(resolved_model or prepared.get("model") or "") or None,
                temperature=p_temp,
                max_tokens=p_maxtok,
                task_kind=task_kind,
# 并发闸门让步：用户直答(0) > 插话(6) > 定时/后台任务(8)——
# 任务永远排队不丢失，但饱和时绝不和用户的直接提问抢槽位
                priority=(6 if origin in ("plugin", "proactive") else (8 if origin in ("task", "dashboard", "rpc") else 0)),
                prefill=str(persona.get("prefill") or ""),
            )
# 投递意图标签（[[转发]]/[[直发]]，含单括号变体）剥离：任务场景无转发卡语义，
# 标签只当文本清扫；force 语义丢弃走自动规则
            reply = utils.strip_output_tag(result.text.strip())[0]
            reply = utils.strip_stray_tags(reply).strip() or texts.t("no_reply_content")
# persist=True（插回式调用，如后台子智能体汇报消化）：问答双方都落会话，
# 下轮对话 AI 才记得"汇报过什么、自己怎么消化的"；一次性任务调用保持 False 不留痕
            if persist:
                self.sessions.finalize(
                    chat_key, reply,
                    trace=result.tool_trace, rounds=getattr(result, "rounds", None),
                    usage=getattr(result, "usage", None),
                    model=(resolved_model or prepared.get("model") or ""),
                )
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
# 带会话键：delivery 层据此还原 @账户 绑定发送账户（缺省静默落默认账户=张冠李戴）
                        chat_key=chat_key,
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
        from .conversation.service import strip_account as _strip_account

        platform, detail_type, target_id = parse_chat_key(_strip_account(strip_isolation(chat_key)))
# 多账户：会话键 @账户 后缀还原出发送账户
        self_id = ""
        if "@" in str(chat_key).rsplit(":", 2)[-1]:
            self_id = str(chat_key).rsplit("@", 1)[1] or ""
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
            self_id=self_id,
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
# 人格级覆盖（显式面板指定优先于人格）
                temperature=temperature if temperature is not None else _num_or_none(prepared["persona"].get("temperature")),
                max_tokens=_int_or_none(prepared["persona"].get("max_tokens")),
                on_delta=on_delta,
                on_reset=on_reset,
                on_tool_event=on_tool_event,
                on_reasoning=on_reasoning,
                prefill=str(prepared["persona"].get("prefill") or ""),
            )
            reply = utils.strip_stray_tags(result.text.strip()) or texts.t("no_reply_content")
            self.sessions.finalize(chat_key, reply, trace=result.tool_trace, rounds=getattr(result, "rounds", None), usage=result.usage, model=getattr(result, "model", ""), title_from=text)
        return reply

    async def run_task(self, task: dict) -> None:
        target_type = str(task.get("target_type") or "user")
        detail_type = "group" if target_type == "group" else "private"
        chat_key = make_chat_key(str(task.get("platform") or ""), detail_type, str(task.get("target_id") or ""))
# 多账户身份：任务必须以创建它时所在的 bot 账户执行——account 字段优先，
# 兼容存量任务回退创建时的 chat_key 后缀。不加后缀发送会静默落到适配器默认账户
# （"配了 Amer 的定时任务由另一个账号发出"的根因）。
        account = str(task.get("account") or "") or _account_of(str(task.get("chat_key") or ""))
        if account and f"@{account}" not in chat_key:
            chat_key = f"{chat_key}@{account}"
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
# 主动唤醒场景：明确"没人对你说话"，否则模型会把引导语当成有人在提问
        scene = texts.t("scene_proactive", reason=str(reason or "").strip() or texts.t("scene_proactive_noreason"))
# 重复话题抑制：列出本会话最近主动发言（30 分钟内），明令不再翻旧账——
# 否则模型从 summary/facts 里捡最显眼的旧话题反复自说自话（自己说的又进上下文，自激循环）
        import time as _time

        now = _time.time()
        recent = [
            txt for ts, txt in (self._proactive_recent.get(chat_key) or ())
            if now - ts < 1800
        ]
        if recent:
            scene = scene + "\n" + texts.t("scene_proactive_recent", recent=utils.truncate(" / ".join(recent[-5:]), 400))
        reply = await self.run_prompt(
            chat_key,
            str(prompt or "") or texts.t("participate_speak_prompt"),
            persona_id=str(persona_id or ""),
            origin="proactive",
            send=True,
            scene=scene,
        )
        if str(reply or "").strip() not in ("", ".", "。", "-"):
            self._proactive_recent.setdefault(chat_key, []).append((now, utils.truncate(str(reply).strip(), 120)))
            del self._proactive_recent[chat_key][:-8]
        _log_proactive(True, "")
        return reply

    async def plugin_config(self, module: str = "", **_) -> dict:
        """插件设置读取：框架 config 各模块当前存储值（{module: {key: value}}）；module 过滤。

        不合并默认值——默认值由插件自身 ConfigClass 行为承担，这里只透传 sdk.config 现值；
        归属以 plugin_settings_catalog（qvq_settings 标记）为准。
        """
        catalog = getattr(self, "plugin_settings_catalog", None)
        if not isinstance(catalog, dict):
            catalog = {}
        result = {}
        for name in catalog:
            if module and name != module:
                continue
            try:
                values = self.sdk.config.getConfig(name)
            except Exception:
                values = None
            result[name] = dict(values) if isinstance(values, dict) else {}
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
