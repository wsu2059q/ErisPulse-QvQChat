"""跨会话用户画像（ProfileStore）+ 固化循环 + 记忆透明可控测试。"""
import asyncio
import time

from QvQChat import texts
from QvQChat.chat.cli import CliMixin
from QvQChat.conversation.budget import PRIORITY
from QvQChat.conversation.profile import PROFILE_PREFIX, ProfileStore
from QvQChat.dashboard.api_sessions import SessionsApiMixin
from QvQChat.dashboard.manager import DashboardManager
from QvQChat.engine.base import ChatResponse, TaskSpec
from QvQChat.scheduler import Scheduler

from fakes import FakeChatEvent, FakeMain


def _put_profile(main, user_key: str, traits=None, preferences=None, facts=None) -> None:
    main.sdk.storage.set(
        PROFILE_PREFIX + user_key,
        {
            "traits": [{"text": t, "ts": time.time()} for t in (traits or [])],
            "preferences": [{"text": p, "ts": time.time()} for p in (preferences or [])],
            "facts": [{"text": f, "ts": time.time()} for f in (facts or [])],
            "updated": time.time(),
        },
    )


class DistillPool:
    """记录 dispatch 规格并返回固定 traits/preferences 提炼结果。"""

    def __init__(self, content: str):
        self.content = content
        self.specs: list[TaskSpec] = []

    async def dispatch(self, spec, request):
        self.specs.append(spec)
        return ChatResponse(content=self.content)

    async def chat(self, request, **kwargs):
        return ChatResponse(content=self.content)


class BoomingPool:
    async def chat(self, request, **kwargs):
        raise RuntimeError("llm down")


def _seed_user_sessions(main) -> str:
    """u1 在两个群发言（建 user_seen 倒排）+ 群 facts + 记忆条目，返回 user_key。"""
    svc = main.conversations
    g1, g2 = "onebot11:group:1", "onebot11:group:2"
    svc.append_user(g1, "(u1): 大家好", sender_id="u1")
    svc.append_user(g2, "(u1): 又见面了", sender_id="u1")
    svc.append_facts(g1, ["PREFERENCE|喜欢蓝色", "ENTITY|张三"])
    svc.append_facts(g2, ["PREFERENCE|喜欢蓝色，深色的那种", "TODO|周五交报告"])
    main.memory.remember(g1, "用户是资深 Python 工程师", importance=5)
    main.memory.remember(g1, "低重要度逐会话记忆", importance=2)
    main.memory.remember("global", "回复要简洁", importance=3)
    return "onebot11:u1"


# ===== consolidate：聚合 / 去重 / LLM 提炼 =====


async def test_consolidate_aggregates_and_dedupes():
    main = FakeMain()
    user_key = _seed_user_sessions(main)
    main.pool = DistillPool(
        "<traits>\n- 张三是资深 Python 工程师\n</traits>\n<preferences>\n- 喜欢蓝色（深色）\n</preferences>"
    )
    report = await main.conversations.profile.consolidate(user_key)

    assert report["changed"] is True
    specs = main.pool.specs
    assert specs and specs[0].kind == "compact" and specs[0].prefer == "cheap"

    profile = main.conversations.profile.get(user_key)
    traits = [t["text"] for t in profile["traits"]]
    prefs = [p["text"] for p in profile["preferences"]]
    facts = [f["text"] for f in profile["facts"]]
    assert "张三是资深 Python 工程师" in traits
    assert "喜欢蓝色（深色）" in prefs
# 跨会话 facts 聚合：包含式归并后偏好类只留更完整一条
    pref_facts = [f for f in facts if f.startswith("PREFERENCE|")]
    assert len(pref_facts) == 1 and "深色" in pref_facts[0]
    assert "ENTITY|张三" in facts and "TODO|周五交报告" in facts
# 私聊会话（onebot11:private:u1）也是聚合候选，但无 facts 不报错
    assert isinstance(profile["updated"], float)


async def test_consolidate_llm_failure_keeps_raw_items():
    main = FakeMain()
    user_key = _seed_user_sessions(main)
    main.pool = BoomingPool()

    await main.conversations.profile.consolidate(user_key)
    profile = main.conversations.profile.get(user_key)
    traits = [t["text"] for t in profile["traits"]]
    prefs = [p["text"] for p in profile["preferences"]]
# 兜底分类：PREFERENCE| → preferences；ENTITY/TODO/memory → traits
    assert any("深色" in p for p in prefs)
    assert "ENTITY|张三" in traits
    assert "用户是资深 Python 工程师" in traits# 逐会话 importance>=4 的 memory 参与
    assert "回复要简洁" in traits# global scope memory 参与
    assert all("低重要度" not in t for t in traits)# importance<4 的逐会话记忆不参与


# ===== 衰减 =====


async def test_consolidate_decays_stale_traits():
    main = FakeMain(profile_decay_days=30)
    main.pool = BoomingPool()# 无源可提炼 → 走兜底（空），旧条目按 ts 衰减
    stale_ts = time.time() - 40 * 86400
    main.sdk.storage.set(
        PROFILE_PREFIX + "onebot11:u1",
        {
            "traits": [
                {"text": "过时的特点", "ts": stale_ts},
                {"text": "新鲜的特点", "ts": time.time() - 3600},
            ],
            "preferences": [],
            "facts": [],
            "updated": stale_ts,
        },
    )
    report = await main.conversations.profile.consolidate("onebot11:u1")
    traits = [t["text"] for t in main.conversations.profile.get("onebot11:u1")["traits"]]
    assert "过时的特点" not in traits, "40 天未强化的 traits 应被淘汰"
    assert "新鲜的特点" in traits
    assert report["decayed"] == 1


async def test_consolidate_reinforcement_survives_decay():
    main = FakeMain(profile_decay_days=30)
    g1 = "onebot11:group:1"
    svc = main.conversations
    svc.append_user(g1, "(u1): 我喜欢蓝色", sender_id="u1")
    svc.append_facts(g1, ["PREFERENCE|喜欢蓝色"])
    main.pool = BoomingPool()# 兜底：PREFERENCE| 归 preferences

    stale_ts = time.time() - 40 * 86400
    main.sdk.storage.set(
        PROFILE_PREFIX + "onebot11:u1",
        {
            "traits": [{"text": "PREFERENCE|喜欢蓝色", "ts": stale_ts}],
            "preferences": [],
            "facts": [],
            "updated": stale_ts,
        },
    )
    await svc.profile.consolidate("onebot11:u1")
    texts_all = [
        *[t["text"] for t in svc.profile.get("onebot11:u1")["traits"]],
        *[p["text"] for p in svc.profile.get("onebot11:u1")["preferences"]],
    ]
    assert "PREFERENCE|喜欢蓝色" in texts_all, "被新事实强化的条目应存活（ts 刷新）"


async def test_decay_disabled_keeps_stale():
    main = FakeMain(profile_decay_days=0)
    main.pool = BoomingPool()
    stale_ts = time.time() - 400 * 86400
    main.sdk.storage.set(
        PROFILE_PREFIX + "onebot11:u1",
        {"traits": [{"text": "老条目", "ts": stale_ts}], "preferences": [], "facts": [], "updated": stale_ts},
    )
    await main.conversations.profile.consolidate("onebot11:u1")
    assert [t["text"] for t in main.conversations.profile.get("onebot11:u1")["traits"]] == ["老条目"]


# ===== digest 与条目上限 =====


def test_digest_limit_and_truncation():
    main = FakeMain(profile_inject=3)
    store = ProfileStore(main)
    _put_profile(
        main,
        "onebot11:u1",
        traits=["特点" + str(i) for i in range(10)],
        preferences=["偏好A"],
        facts=["ENTITY|张三"],
    )
    lines = store.digest("onebot11:u1")
    assert len(lines) == 3
    assert all(line.startswith("[trait] ") for line in lines)

    long_trait = "长" * 300
    _put_profile(main, "onebot11:u2", traits=[long_trait])
    lines = store.digest("onebot11:u2", limit=8)
    assert len(lines) == 1 and len(lines[0]) <= len("[trait] ") + 160


def test_profile_max_caps_categories():
    main = FakeMain(profile_max=2)
    store = ProfileStore(main)
    store._save("onebot11:u1", {"traits": [{"text": f"t{i}", "ts": 1.0} for i in range(5)],
                                "preferences": [], "facts": [], "updated": 1.0})
    profile = store.get("onebot11:u1")
    assert [t["text"] for t in profile["traits"]] == ["t3", "t4"], "超限保最新"


def test_clear_returns_removed_count():
    main = FakeMain()
    _put_profile(main, "onebot11:u1", traits=["a"], preferences=["b"], facts=["c"])
    store = ProfileStore(main)
    assert store.clear("onebot11:u1") == 3
    assert store.get("onebot11:u1")["traits"] == []
    assert store.clear("onebot11:u1") == 0


# ===== active_user_keys（近期活跃） =====


def test_active_user_keys_from_user_seen():
    main = FakeMain()
    svc = main.conversations
    svc.append_user("onebot11:group:1", "(u1): hi", sender_id="u1")
    svc.append_user("onebot11:group:2", "(u2): hi", sender_id="u2")
# u3 很久没说话
    main.sdk.storage.set(
        "QvQChat:user_seen:u3",
        [{"chat_key": "onebot11:group:3", "ts": time.time() - 48 * 3600, "head": ""}],
    )
    keys = ProfileStore(main).active_user_keys(within_hours=24)
    assert "onebot11:u1" in keys and "onebot11:u2" in keys
    assert all(not k.endswith(":u3") for k in keys)


# ===== budget PRIORITY =====


def test_priority_profile_between_facts_and_memory():
    assert PRIORITY["facts"] < PRIORITY["profile"] < PRIORITY["memory"]
    assert PRIORITY["profile"] == 4.5


# ===== service 注入 =====


def test_build_system_parts_injects_profile():
    main = FakeMain()
    svc = main.conversations
    key = "onebot11:group:1"
    svc.append_facts(key, ["ENTITY|张三"])
    _put_profile(main, "onebot11:u1", traits=["熟悉 Python"], preferences=["喜欢简洁"])
    persona = main.personas.resolve(key)

    parts = svc.build_system_parts(persona, chat_key=key, profile_user="onebot11:u1")
    kinds = [p.kind for p in parts]
    assert "profile" in kinds
    assert kinds.index("facts") < kinds.index("profile")
    part = next(p for p in parts if p.kind == "profile")
    assert "[trait] 熟悉 Python" in part.text and "[pref] 喜欢简洁" in part.text

# 无 profile_user / 功能关闭时不注入
    assert "profile" not in [p.kind for p in svc.build_system_parts(persona, chat_key=key)]
    main.cfg.profile_enabled = False
    assert "profile" not in [
        p.kind for p in svc.build_system_parts(persona, chat_key=key, profile_user="onebot11:u1")
    ]


async def test_prepare_passes_profile_user_into_system():
    main = FakeMain()
    svc = main.conversations
    key = "onebot11:private:u1"
    _put_profile(main, "onebot11:u1", traits=["夜猫子"])
    prepared = await svc.prepare(key, "在吗", profile_user="onebot11:u1", persist=False)
    assert "[trait] 夜猫子" in prepared["system"]


# ===== /qvq memories 命令 =====


class CliEvent(FakeChatEvent):
    def __init__(self, args="", **kw):
        super().__init__(**kw)
        self._args = args

    def get_command_args(self):
        return self._args


class CliHost(CliMixin, FakeMain):
    def _chat_key_of(self, event):
        if event.is_group_message():
            return f"{event.get_platform()}:group:{event.get_group_id()}"
        return f"{event.get_platform()}:private:{event.get_user_id()}"


def _cli_host(**cfg) -> CliHost:
    host = CliHost(**cfg)
    host.cfg.admins = ["u1"]
    host.scheduler = Scheduler(host)
    return host


async def test_qvq_memories_displays_overview():
    host = _cli_host()
    chat_key = "onebot11:group:1"
    host.conversations.append_facts(chat_key, ["ENTITY|张三"])
    host.memory.remember(chat_key, "用户喜欢蓝色")
    _put_profile(host, "onebot11:u1", traits=["熟悉 Python"])

    event = CliEvent(args="memories", user_id="u1", group=True, group_id="1")
    await host._cmd_agent(event)
    reply = event.replies[0][1]
    assert texts.t("memories_memory_count", count=1) in reply
    assert texts.t("memories_facts_count", count=1) in reply
    assert "用户喜欢蓝色" in reply
    assert "熟悉 Python" in reply, "画像全文应展示"
    assert "onebot11:u1" in reply


async def test_qvq_memories_clear_requires_admin_and_confirm():
    host = _cli_host()
    _put_profile(host, "onebot11:u1", traits=["a"], preferences=["b"], facts=["c"])
    host.conversations.append_facts("onebot11:group:1", ["ENTITY|张三"])
    host.memory.remember("onebot11:group:1", "m")

# 非管理员
    event = CliEvent(args="memories clear profile confirm", user_id="stranger", group=True, group_id="1")
    await host._cmd_agent(event)
    assert texts.t("needs_admin") in event.replies[0][1]

# 管理员但缺 confirm
    event = CliEvent(args="memories clear profile", user_id="u1", group=True, group_id="1")
    await host._cmd_agent(event)
    assert texts.t("memories_clear_need_confirm") in event.replies[0][1]
    assert host.conversations.profile.get("onebot11:u1")["traits"], "未确认不得清空"

# 未知目标
    event = CliEvent(args="memories clear nonsense confirm", user_id="u1", group=True, group_id="1")
    await host._cmd_agent(event)
    assert texts.t("memories_clear_usage") in event.replies[0][1]


async def test_qvq_memories_clear_graded():
    host = _cli_host()
    chat_key = "onebot11:group:1"
    _put_profile(host, "onebot11:u1", traits=["a"], preferences=["b"], facts=["c"])
    host.conversations.append_user(chat_key, "(u1): hi", sender_id="u1")
    host.conversations.append_facts(chat_key, ["ENTITY|张三", "TODO|交报告"])
    host.memory.remember(chat_key, "记忆1")
    host.memory.remember(chat_key, "记忆2")

    event = CliEvent(args="memories clear facts confirm", user_id="u1", group=True, group_id="1")
    await host._cmd_agent(event)
    assert texts.t("memories_cleared", target="facts", count=2) in event.replies[0][1]
    assert host.conversations.facts_of(chat_key) == []
    assert host.memory.entries(chat_key), "清 facts 不得动 memory"

    event = CliEvent(args="memories clear memory confirm", user_id="u1", group=True, group_id="1")
    await host._cmd_agent(event)
    assert texts.t("memories_cleared", target="memory", count=2) in event.replies[0][1]
    assert host.memory.entries(chat_key) == []

    event = CliEvent(args="memories clear profile confirm", user_id="u1", group=True, group_id="1")
    await host._cmd_agent(event)
    assert texts.t("memories_cleared", target="profile", count=3) in event.replies[0][1]
    assert host.conversations.profile.get("onebot11:u1")["traits"] == []


# ===== scheduler：固化定时任务 =====


def test_ensure_profile_task_registers_interval_task():
    main = FakeMain()
    scheduler = Scheduler(main)
    task = scheduler.ensure_profile_task()
    assert task is not None
    assert task["task_kind"] == "profile_consolidate"
    assert task["schedule"] == {"type": "interval", "seconds": 6 * 3600}
    assert any(t["task_kind"] == "profile_consolidate" for t in scheduler.list())
    assert scheduler.ensure_profile_task() is None, "幂等：不重复注册"


def test_ensure_profile_task_disabled():
    main = FakeMain(profile_enabled=False)
    assert Scheduler(main).ensure_profile_task() is None
    main2 = FakeMain(profile_consolidate_hours=0)
    assert Scheduler(main2).ensure_profile_task() is None


async def test_tick_fires_profile_task_and_consolidates():
    main = FakeMain()
    scheduler = Scheduler(main)
    scheduler.ensure_profile_task()
    _seed_user_sessions(main)
    tasks = scheduler.list()
    tasks[0]["next_run"] = time.time() - 10
    main.sdk.storage.set("QvQChat:tasks", tasks)
    main.pool = BoomingPool()# LLM 失败 → 兜底路径也能固化

    await scheduler._tick()
    assert main.tasks_fired == [], "画像任务不得走 run_prompt"
    profile = main.conversations.profile.get("onebot11:u1")
    assert profile["traits"] or profile["facts"], "固化循环应产出画像"
    assert any(t["task_kind"] == "profile_consolidate" for t in scheduler.list()), "interval 任务保留"


async def test_profile_fire_skips_failed_users():
    main = FakeMain()
    scheduler = Scheduler(main)

    class FlakyProfile:
        def __init__(self):
            self.calls = []

        def active_user_keys(self, within_hours=24.0):
            return ["a:1", "b:2"]

        async def consolidate(self, user_key):
            self.calls.append(user_key)
            if user_key == "a:1":
                raise RuntimeError("boom")

    flaky = FlakyProfile()
    main.conversations._profile = flaky
    done = await scheduler._fire_profile_consolidate()
    assert flaky.calls == ["a:1", "b:2"], "单用户失败不影响其余用户"
    assert done == 1


# ===== dashboard：memory 端点扩展 + profile 清空 =====


class SessionsHost(SessionsApiMixin):
    _query = staticmethod(DashboardManager._query)

    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk


class ApiRequest:
    def __init__(self, query=None, body=None):
        self.query_params = query or {}
        self._body = body or {}

    async def json(self):
        return self._body


async def test_memory_get_returns_session_profile():
    main = FakeMain()
    svc = main.conversations
    chat_key = "onebot11:group:1"
    svc.append_user(chat_key, "(u1): hi", sender_id="u1")
    svc.append(chat_key, "assistant", "hello")
    _put_profile(main, "onebot11:u1", traits=["熟悉 Python"])

    host = SessionsHost(main)
    data = await host.memory_get(ApiRequest(query={"chat_key": chat_key}))
    assert data["profile_user"] == "onebot11:u1"
    assert [t["text"] for t in data["profile"]["traits"]] == ["熟悉 Python"]
    assert data["entries"] == main.memory.entries(chat_key)


async def test_memory_get_without_chat_key_returns_latest_profile():
    main = FakeMain()
    _seed_user_sessions(main)
    _put_profile(main, "onebot11:u1", traits=["T1"])
    host = SessionsHost(main)
    data = await host.memory_get(ApiRequest())
    assert data["scopes"], "作用域列表保留"
    assert data["profile_user"] == "onebot11:u1"
    assert data["profile"]["traits"][0]["text"] == "T1"


async def test_profile_clear_endpoint():
    main = FakeMain()
    _put_profile(main, "onebot11:u1", traits=["a"])
    host = SessionsHost(main)
    data = await host.profile_clear(ApiRequest(body={"user_key": "onebot11:u1"}))
    assert data["ok"] is True and data["removed"] == 1
    assert main.conversations.profile.get("onebot11:u1")["traits"] == []

    status, code = await host.profile_clear(ApiRequest(body={"user_key": ""}))
    assert code == 400
