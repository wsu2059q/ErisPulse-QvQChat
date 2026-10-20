from __future__ import annotations

import asyncio
from types import SimpleNamespace

from QvQChat.agent.persona import PersonaManager
from QvQChat.agent.tools import ToolRegistry


class FakeStorage:
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def delete(self, key):
        self._data.pop(key, None)

    def keys(self):
        return list(self._data)


class FakeLogger:
    def __init__(self):
        self.records = []

    def info(self, *args, **kwargs):
        self.records.append(("info", args))

    def warning(self, *args, **kwargs):
        self.records.append(("warning", args))


class FakeModuleManager:
    def __init__(self, catalog=None):
        self._catalog = catalog or {}
        self._instances = {}
        self.calls = []
        self.handlers = {}

    def services(self, module_name=None):
        return self._catalog

    def list_registered(self):
        return list(dict.fromkeys(list(self._instances) + list(self._catalog)))

    async def call(self, module, service, *args, **kwargs):
        self.calls.append((module, service, args, kwargs))
        key = (module, service)
        if key in self.handlers:
            handler = self.handlers[key]
            if callable(handler):
                return handler(**kwargs)
            return handler
        instance = self._instances.get(module)
        if instance is not None and hasattr(instance, service):
            result = getattr(instance, service)(**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        raise RuntimeError(f"module {module} not available")

    def __contains__(self, name):
        return name in self._catalog or name in self._instances

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._instances:
            return self._instances[name]
        try:
            return self._catalog[name]
        except KeyError:
            raise AttributeError(name) from None


class FakeLifecycle:
    def __init__(self):
        self.registered = []
        self.emitted = []

    def register(self, event, handler):
        self.registered.append((event, handler))

    async def emit(self, event, data=None, **kwargs):
        self.emitted.append((event, data))
        return data


class FakeClient:
    def __init__(self):
        self.requests = []
        self.status = 200
        self._json = {}
        self._text = ""
        self._data = b""

    async def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self

    async def json(self, **kwargs):
        return self._json

    async def text(self, encoding=None):
        return self._text

    async def read(self):
        return self._data


class _Pending:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _inner():
            return self._value
        return _inner().__await__()


class FakeSendChain:
    def __init__(self, sends=("Markdown", "Text"), fail_on=()):
        self.calls = []
        self._sends = set(sends)
        self._fail_on = set(fail_on)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name in self._fail_on:
                raise RuntimeError(f"{name} send failed")
            if name in self._sends:
                return _Pending({"status": "ok", "sent": name})
            return self

        return record


class FakeAdapter:
    def __init__(self, chain, sends):
        self.Send = chain
        self._sends = list(sends)

    async def call_api(self, endpoint, **params):
        return {"endpoint": endpoint, **params}

    def Request(self, request_id):
        self._request_calls = [request_id]

        class _Req:
            def __init__(self, outer):
                self._outer = outer

            def accept(self):
                self._outer._request_calls.append("accept")
                return {"accepted": True}

            def reject(self):
                self._outer._request_calls.append("reject")
                return {"accepted": False}

        return _Req(self)


class FakeAdapterManager:
    def __init__(self):
        self._adapters = {}
        self._sends = {}

    def add(self, name, chain, sends=("Markdown", "Text")):
        self._adapters[name] = FakeAdapter(chain, sends)
        self._sends[name] = list(sends)

    def get(self, name):
        return self._adapters.get(name)

    def list_sends(self, name):
        return list(self._sends.get(name, []))

    def list_registered(self):
        return list(self._adapters)


class FakeChatEvent:
    def __init__(self, text="", images=None, platform="onebot11", group=True,
                 group_id="1", user_id="u1", user_name="群主", at=False):
        self._text = text
        self._images = images or []
        self._platform = platform
        self._group = group
        self._gid = group_id
        self._uid = user_id
        self._name = user_name
        self._at = at
        self.replies = []
        self.claimed = False

    def get_alt_message(self):
        return self._text

    def is_group_message(self):
        return self._group

    def is_private_message(self):
        return not self._group

    def is_at_message(self):
        return self._at

    def is_command(self):
        return False

    def get_group_id(self):
        return self._gid

    def get_platform(self):
        return self._platform

    def get_user_id(self):
        return self._uid

    def get_user_nickname(self):
        return self._name

    def get_sender(self):
        return {"nickname": self._name}

    def get_self_account_id(self):
        return "bot"

    def supports(self, method):
        return method == "Text"

    def done(self, *args, **kwargs):
        self.claimed = True

    async def reply(self, content, method="Text"):
        self.replies.append((method, content))

    async def history(self, n):
        return []

    def get(self, key, default=None):
        return default

    def get_message(self):
        segments = []
        for url in self._images:
            segments.append({"type": "image", "data": {"url": url}})
        if self._text:
            segments.append({"type": "text", "data": {"text": self._text}})
        return segments


class FakeInteraction:
    @staticmethod
    def make_key(event):
        return "fake:interaction:key"


class FakeSDK:
    def __init__(self, catalog=None):
        self.storage = FakeStorage()
        self.logger = FakeLogger()
        self.module = FakeModuleManager(catalog)
        self.lifecycle = FakeLifecycle()
        self.client = FakeClient()
        self.adapter = FakeAdapterManager()
        self.interaction = SimpleNamespace(make_key=lambda event: "fake:interaction:key")
        self.config_sets = []
        self.config = SimpleNamespace(setConfig=lambda key, value: self.config_sets.append((key, value)))


def make_config(**overrides):
    base = dict(
        default_model="",
        temperature=0.7,
        max_tokens=0,
        model_failover=True,
        reply_private=True,
        reply_at=True,
        wake_prefixes=[],
        command_prefixes=["#", "/"],
        admins=[],
        admin_tools=[],
        safe_tools=[],
        safe_commands=["ping *"],
        security_level="standard",
        trust_agent=False,
        sensitive_paths=["config", ".env", "*.key", "*.pem", "*.db", "*.sqlite*"],
        self_config=True,
        work_dirs=[],
        command_timeout=30,
        blocked_patterns=[],
        confirm_timeout=60,
        context_limit=30,
        history_seed=20,
        forward_platforms=["*"], no_forward_platforms=[],
        forward_min_messages=2,
        forward_threshold=600,
        context_summary=True,
        context_compress_tokens=128000,
        tool_notice_mode="brief",
        aggregate_window=5.0,
        skills_dir="data/QvQChat/skills",
        skills_disabled=[],
        memory_max=200,
        memory_recall=6,
        tool_timeout=120,
        max_tool_rounds=50,
        max_tool_calls=150,
        disabled_tools=[],
        eco_exclude=["QvQChat"],
        eco_include=[],
        mcp_timeout=30,
        extra_prompts=[],
        owner_only=False,
        task_check_interval=20,
        task_use_cron_module=True,
        view_token="",
        daily_token_limit=0,
        usage_retention_days=14,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class FakeMain:
    def __init__(self, catalog=None, **config_overrides):
        from QvQChat.engine.pool import ModelPool
        from QvQChat.scheduler import Scheduler
        from QvQChat.conversation.service import ConversationService
        from QvQChat.conversation.memory import MemoryStore

        self.sdk = FakeSDK(catalog)
        self.cfg = make_config(**config_overrides)
        self.logger = self.sdk.logger
        self.registry = ToolRegistry()
        self.personas = PersonaManager(self.sdk)
        self.conversations = ConversationService(self)
        self.sessions = self.conversations
        from QvQChat.conversation.delivery import Delivery
        self.delivery = Delivery(self)
        self.memory = MemoryStore(self.sdk, self.cfg)
        self.pool = ModelPool(self.sdk, self.cfg)
        self.scheduler = Scheduler(self)
        from QvQChat.bridge.mcp import MCPManager
        from QvQChat.skills import SkillManager

        self.skills = SkillManager(self.sdk, self.cfg)
        self.mcp = MCPManager(self)
        self.takeover = {}
        self.audits = []
        self.tasks_fired = []
        self.prompts = []

    def is_admin(self, user_id, origin="chat", platform=""):
        from QvQChat.Main import is_admin_user

        return is_admin_user(self.cfg, user_id, origin, platform)

    def audit(self, tool, detail, ctx=None):
        self.audits.append({"tool": tool, "detail": detail})

    def record_usage(self, chat_key, usage):
        from QvQChat.Main import Main

        Main.record_usage(self, chat_key, usage)

    def _usage_today(self):
        from QvQChat.Main import Main

        return Main._usage_today(self)

    def _usage_history(self, days=14):
        from QvQChat.Main import Main

        return Main._usage_history(self, days)

    async def run_task(self, task):
        self.tasks_fired.append(task)

    async def run_prompt(self, chat_key, prompt, **kwargs):
        self.prompts.append((chat_key, prompt, kwargs))
        return "ok"


class FakePool:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def chat(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


CTX_KEYS = {
    "main", "sdk", "config", "chat_key", "session_key", "platform",
    "detail_type", "target_id", "user_id", "event", "origin", "confirmer",
}


def make_ctx(main=None, **overrides):
    from QvQChat.agent.tools import ToolContext

    ctx_fields = {k: v for k, v in overrides.items() if k in CTX_KEYS}
    cfg_fields = {k: v for k, v in overrides.items() if k not in CTX_KEYS}
    if main is None:
        main = FakeMain(**cfg_fields)
    elif cfg_fields:
        data = vars(main.cfg).copy()
        data.update(cfg_fields)
        main.cfg = SimpleNamespace(**data)
    base = dict(
        main=main,
        sdk=main.sdk,
        config=main.cfg,
        chat_key="test:private:1",
        session_key="test:bot:1:1",
        platform="test",
        detail_type="private",
        target_id="1",
        user_id="1",
        event=None,
        origin="chat",
        confirmer=None,
    )
    base.update(ctx_fields)
    return ToolContext(**base)


class FakeRequest:
    def __init__(self, token=None, bearer=None):
        self.headers = {}
        if bearer:
            self.headers["Authorization"] = f"Bearer {bearer}"
        self.query_params = {"token": token} if token else {}
