"""核心侧扩展点：参与决策插件化（qvq.observe / qvq_decision / SpeechBudget / speak）。

契约对端为 QvQStalker 插件（订阅 qvq.observe、提供 qvq_decision、调用 QvQChat.speak）。
"""
import asyncio
import inspect
from dataclasses import MISSING
from types import SimpleNamespace

from ErisPulse import ServiceNotProvidedError

from QvQChat import texts
from QvQChat.Config import GROUP_META, QvQConfig
from QvQChat.Main import Main
from QvQChat.bridge.ecosystem import EcosystemBridge
from QvQChat.dashboard.manager import DashboardManager
from QvQChat.participation import (
    KIND_INTERJECT,
    KIND_PROACTIVE,
    ParticipationManager,
    SpeechBudget,
)

from fakes import FakeChatEvent, FakeMain, FakeRequest, make_config
from test_aggregate import make_main

GROUP_KEY = "onebot11:group:1"


# ==================== 装配辅助 ====================

def _bind(main):
    """make_main 的绑定清单外追加 新方法（_interject）。"""
    static_attr = inspect.getattr_static(Main, "_interject")
    setattr(main, "_interject", static_attr.__get__(main))
    return main


def make_part_main(catalog=None, **overrides):
    overrides.setdefault("aggregate_window", 5.0)# 测试期不真正冲刷聚合
    main = _bind(make_main(**overrides))
    main.participation = ParticipationManager(main)
    return main


def add_provider(main, module="Stalker", decision="speak", score=0.9, reason="插件判定",
                 slow=0.0, capture=None):
    """按 FakeModuleManager catalog 模式伪造带 qvq_decision 服务的生态模块。"""
    entry = {"name": "qvq_decision", "signature": "(ctx: dict) -> dict", "description": "参与决策"}
    catalog = main.sdk.module._catalog
    catalog.setdefault(module, [])
    if entry not in catalog[module]:
        catalog[module].append(entry)

    if slow:

        class SlowProvider:
            async def qvq_decision(self, ctx=None, **_):
                await asyncio.sleep(slow)
                return {"decision": decision, "reason": reason, "score": score, "urgency": "low"}

        main.sdk.module._instances[module] = SlowProvider()
        return main

    def handler(ctx=None, **_):
        if capture is not None:
            capture["ctx"] = ctx
        if isinstance(ctx, dict) and ctx.get("probe"):
            return {"decision": "silent", "reason": "probe ok", "score": 0.0, "urgency": "low"}
        return {"decision": decision, "reason": reason, "score": score, "urgency": "low"}

    main.sdk.module.handlers[(module, "qvq_decision")] = handler
    return main


def add_broken_provider(main, module="Broken"):
    """声明了服务但调用被拒（services 白名单陷阱）/ 异常的模块。"""
    main.sdk.module._catalog.setdefault(module, []).append(
        {"name": "qvq_decision", "signature": "(ctx: dict) -> dict", "description": "未在白名单"}
    )

    def handler(ctx=None, **_):
        raise ServiceNotProvidedError(module, "qvq_decision")

    main.sdk.module.handlers[(module, "qvq_decision")] = handler
    return main


def cancel_pending(main):
    for entry in main._pending.values():
        timer = entry.get("timer")
        if timer is not None:
            timer.cancel()
    main._pending.clear()


def observe_payloads(main):
    return [data for event, data in main.sdk.lifecycle.emitted if event == "qvq.observe"]


def participation_payloads(main):
    return [data for event, data in main.sdk.lifecycle.emitted if event == "qvq.participation"]


# ==================== 提供者发现 ====================

async def test_discover_finds_declared_provider():
    main = make_part_main()
    add_provider(main, "Stalker", decision="silent")
    found = await main.participation.discover()
    assert "Stalker" in found
    assert found["Stalker"]["module"] == "Stalker"
# 探测调用传 {"probe": True}
    probes = [c for c in main.sdk.module.calls if c[:2] == ("Stalker", "qvq_decision")]
    assert probes and probes[0][3].get("ctx") == {"probe": True}


async def test_discover_whitelist_rejection_is_silent():
    main = make_part_main()
    add_broken_provider(main, "Broken")
    add_provider(main, "Stalker", decision="silent")
    found = await main.participation.discover()
    assert "Broken" not in found and "Stalker" in found
# 未声明服务的模块不探测
    main.sdk.module._catalog["Plain"] = [{"name": "other", "signature": "()"}]
    found = await main.participation.discover()
    assert "Plain" not in found


async def test_discover_removes_vanished_provider():
    main = make_part_main()
    add_provider(main, "Stalker", decision="silent")
    await main.participation.discover()
    assert "Stalker" in main.participation.providers
    main.sdk.module.handlers.pop(("Stalker", "qvq_decision"))
    main.sdk.module._catalog["Stalker"] = []
    await main.participation.discover()
    assert "Stalker" not in main.participation.providers


# ==================== 决策问询与聚合 ====================

async def test_decide_returns_none_without_providers():
    main = make_part_main()
    assert await main.participation.decide(GROUP_KEY, FakeChatEvent(text="hi"), "hi") is None


async def test_decide_ctx_payload_contract():
    main = make_part_main()
    captured: dict = {}
    add_provider(main, "Stalker", decision="silent", score=0.1, capture=captured)
    await main.participation.discover()
# 先旁听一条入窗（recent_messages 来源）
    await main.participation._on_observe({
        "chat_key": GROUP_KEY, "sender_id": "u0", "sender_name": "甲", "text": "早上好", "ts": 1.0,
    })
    decision = await main.participation.decide(GROUP_KEY, FakeChatEvent(text="有人知道吗"), "有人知道吗")
    ctx = captured["ctx"]
    assert ctx["chat_key"] == GROUP_KEY
    assert ctx["platform"] == "onebot11"
    assert ctx["group_id"] == "1"
    assert ctx["is_group"] is True
    assert ctx["text"] == "有人知道吗"
    assert ctx["sender_id"] == "u1"
    assert ctx["sender_name"] == "群主"
    assert ctx["at_bot"] is False# 未命中确定性触发才到达这里
    assert ctx["heat_hint"] is None# 插件自维护
    assert isinstance(ctx["recent_messages"], list)
    assert ctx["recent_messages"][-1]["text"] == "早上好"
    assert ctx["replied_recently"] is False
    assert ctx["ts"] > 0
    assert decision["speak"] is False


async def test_decide_first_speak_aggregation():
    main = make_part_main()
    add_provider(main, "Alpha", decision="speak", score=0.9, reason="提问命中")
    add_provider(main, "Beta", decision="silent", score=0.1, reason="模式保守")
    await main.participation.discover()
    decision = await main.participation.decide(GROUP_KEY, FakeChatEvent(text="?"), "?")
    assert decision["speak"] is True
    assert decision["provider"] == "Alpha"
    assert decision["reason"] == "提问命中"
    assert decision["providers_queried"] == ["Alpha", "Beta"]
    assert {r["decision"] for r in decision["results"]} == {"speak", "silent"}


async def test_decide_max_score_threshold():
    main = make_part_main(participation_strategy="max_score")
    add_provider(main, "Alpha", decision="speak", score=0.5, reason="低分插话")
    add_provider(main, "Beta", decision="silent", score=0.99, reason="高分沉默")
    await main.participation.discover()
    decision = await main.participation.decide(GROUP_KEY, FakeChatEvent(text="?"), "?")
# speak 候选最高分 0.5 < 阈值 0.6 → 沉默（silent 侧高分不参与）
    assert decision["speak"] is False
    assert decision["provider"] == "Alpha"
    assert "0.5" in decision["reason"] and "0.6" in decision["reason"]

    main.cfg.participation_score_threshold = 0.4
    decision = await main.participation.decide(GROUP_KEY, FakeChatEvent(text="?"), "?")
    assert decision["speak"] is True and decision["provider"] == "Alpha"


async def test_decide_unanimous_aggregation():
    main = make_part_main(participation_strategy="unanimous")
    add_provider(main, "Alpha", decision="speak")
    add_provider(main, "Beta", decision="silent", reason="未到观察计数")
    await main.participation.discover()
    decision = await main.participation.decide(GROUP_KEY, FakeChatEvent(text="?"), "?")
    assert decision["speak"] is False
    assert decision["reason"] == "未到观察计数"

    main2 = make_part_main(participation_strategy="unanimous")
    add_provider(main2, "Alpha", decision="speak", score=0.7)
    add_provider(main2, "Beta", decision="speak", score=0.9)
    await main2.participation.discover()
    decision = await main2.participation.decide(GROUP_KEY, FakeChatEvent(text="?"), "?")
    assert decision["speak"] is True and decision["provider"] == "Beta"


async def test_decide_provider_timeout_treated_as_silent():
    main = make_part_main(participation_provider_timeout=0.05)
    add_provider(main, "Slow", decision="speak", slow=0.3)
    add_provider(main, "Fast", decision="silent", score=0.2, reason="快速沉默")
    await main.participation.discover()
    decision = await main.participation.decide(GROUP_KEY, FakeChatEvent(text="?"), "?")
    assert decision["speak"] is False# 超时提供者视为 silent
    assert decision["reason"] == "快速沉默"
    slow_result = next(r for r in decision["results"] if r["provider"] == "Slow")
    assert slow_result["decision"] == "silent" and "Slow" in slow_result["reason"]
    assert decision["providers_queried"] == ["Fast", "Slow"]
    assert decision["results"][0]["reason"] == "快速沉默"


async def test_decide_provider_exception_treated_as_silent():
    main = make_part_main()
    main.sdk.module._catalog["Boom"] = [{"name": "qvq_decision", "signature": "(ctx)"}]
    main.sdk.module.handlers[("Boom", "qvq_decision")] = RuntimeError("plugin crashed")
    main.sdk.module._catalog["Fine"] = [{"name": "qvq_decision", "signature": "(ctx)"}]
    main.sdk.module.handlers[("Fine", "qvq_decision")] = lambda ctx=None, **_: "not-a-dict"
# 探测失败（异常/非 dict 返回）→ 两者都不成为提供者
    await main.participation.discover()
    assert "Boom" not in main.participation.providers
    assert "Fine" not in main.participation.providers

# 探测通过但问询时崩溃 → 该提供者视为 silent，不影响其余提供者
    def flaky(ctx=None, **_):
        if isinstance(ctx, dict) and ctx.get("probe"):
            return {"decision": "silent", "reason": "probe ok", "score": 0.0, "urgency": "low"}
        raise RuntimeError("boom at decide")

    main2 = make_part_main()
    main2.sdk.module._catalog["Flaky"] = [{"name": "qvq_decision", "signature": "(ctx)"}]
    main2.sdk.module.handlers[("Flaky", "qvq_decision")] = flaky
    add_provider(main2, "Stable", decision="speak", score=0.8)
    await main2.participation.discover()
    decision = await main2.participation.decide(GROUP_KEY, FakeChatEvent(text="?"), "?")
    assert decision["speak"] is True and decision["provider"] == "Stable"
    flaky_result = next(r for r in decision["results"] if r["provider"] == "Flaky")
    assert flaky_result["decision"] == "silent" and "Flaky" in flaky_result["reason"]


# ==================== SpeechBudget ====================

def test_budget_hourly_limit_and_window_reset():
    budget = SpeechBudget(FakeMain().sdk, make_config(participation_hourly_limit=2, participation_cooldown_seconds=0))
    t0 = 1000.0
    assert budget.allow("g", KIND_INTERJECT, now=t0)[0]
    budget.record("g", KIND_INTERJECT, now=t0)
    assert budget.allow("g", KIND_INTERJECT, now=t0 + 1)[0]
    budget.record("g", KIND_INTERJECT, now=t0 + 1)
    ok, why = budget.allow("g", KIND_INTERJECT, now=t0 + 2)
    assert not ok and why
# 不同群互不影响 / 新小时窗口重置
    assert budget.allow("g2", KIND_INTERJECT, now=t0 + 2)[0]
    assert budget.allow("g", KIND_INTERJECT, now=t0 + 3601)[0]


def test_budget_cooldown():
    budget = SpeechBudget(FakeMain().sdk, make_config(participation_cooldown_seconds=300))
    t0 = 2000.0
    budget.record("g", KIND_INTERJECT, now=t0)
    ok, _ = budget.allow("g", KIND_INTERJECT, now=t0 + 10)
    assert not ok
    assert budget.allow("g", KIND_INTERJECT, now=t0 + 301)[0]


def test_budget_global_daily_limit_only_counts_proactive():
    budget = SpeechBudget(
        FakeMain().sdk,
        make_config(participation_proactive_daily_limit=1, participation_cooldown_seconds=0),
    )
    t0 = 3000.0
    assert budget.allow("g", KIND_PROACTIVE, now=t0)[0]
    budget.record("g", KIND_PROACTIVE, now=t0)
    ok, why = budget.allow("g", KIND_PROACTIVE, now=t0 + 10)
    assert not ok and why
# 插话不计入全局日限（冷却 0）
    assert budget.allow("g", KIND_INTERJECT, now=t0 + 10)[0]
    status = budget.status(now=t0 + 10)
    assert status["proactive_today"] == 1
    assert status["limits"]["proactive_daily_limit"] == 1


def test_budget_persisted_in_storage():
    main = FakeMain()
    budget = SpeechBudget(main.sdk, make_config(participation_hourly_limit=1, participation_cooldown_seconds=0))
    budget.record("g", KIND_INTERJECT, now=4000.0)
    assert main.sdk.storage.get("QvQChat:participation:g") == [4000.0]
# 新实例读同一 storage：预算状态延续
    reborn = SpeechBudget(main.sdk, make_config(participation_hourly_limit=1, participation_cooldown_seconds=0))
    ok, _ = reborn.allow("g", KIND_INTERJECT, now=4000.5)
    assert not ok


def test_budget_daily_resets_next_day():
    budget = SpeechBudget(FakeMain().sdk, make_config(participation_proactive_daily_limit=1))
    day1 = 5000.0
    budget.record("g", KIND_PROACTIVE, now=day1)
    assert not budget.allow("g", KIND_PROACTIVE, now=day1 + 60)[0]
# 次日重置（+24h）
    assert budget.allow("g", KIND_PROACTIVE, now=day1 + 86400)[0]


# ==================== _on_message：qvq.observe 旁听通道 ====================

async def test_observe_payload_fields_and_channel_exists():
    main = make_part_main()# participation 默认关闭，旁听通道仍存在
    ev = FakeChatEvent(text="随便聊聊", at=False)
    await Main._on_message(main, ev)
    payloads = observe_payloads(main)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["chat_key"] == GROUP_KEY
    assert payload["platform"] == "onebot11"
    assert payload["detail_type"] == "group"
    assert payload["group_id"] == "1"
    assert payload["sender_id"] == "u1"
    assert payload["sender_name"] == "群主"
    assert payload["text"] == "随便聊聊"
    assert payload["is_group"] is True
    assert payload["at_bot"] is False
    assert payload["is_command_prefix"] is False
    assert payload["ts"] > 0
# 未触发消息：旁听但不回复
    assert not main._pending and not ev.claimed

# 命令前缀消息不进入旁听通道
    main.sdk.lifecycle.emitted.clear()
    await Main._on_message(main, FakeChatEvent(text="#help"))
    assert observe_payloads(main) == []

# 触发消息（@bot）同样被旁听，at_bot 如实标记
    await Main._on_message(main, FakeChatEvent(text="@bot 在吗", at=True))
    assert observe_payloads(main)[-1]["at_bot"] is True
    cancel_pending(main)


# ==================== _on_message：参与决策插话分支 ====================

async def test_interject_speak_enters_pending_with_plugin_origin():
    main = make_part_main(participation_enabled=True)
    add_provider(main, "Stalker", decision="speak", score=0.9, reason="提问关键词命中")
    await main.participation.discover()
    ev = FakeChatEvent(text="这个问题怎么解？", at=False)
    await Main._on_message(main, ev)
    assert GROUP_KEY in main._pending
    entry = main._pending[GROUP_KEY]
    assert entry["items"] and entry["items"][0]["text"] == "这个问题怎么解？"
    assert entry["origin"] == "plugin"
    assert ev.claimed
# 插话不消耗发送者限频窗口
    assert f"rate:{GROUP_KEY}:u1" not in main._rate_window
# 决策观测：环形日志 + qvq.participation 事件
    logged = main.participation.decisions[-1]
    assert logged["decision"] == "speak" and logged["budget_ok"] is True
    assert logged["provider"] == "Stalker" and logged["providers_queried"] == ["Stalker"]
    events = participation_payloads(main)
    assert events and events[-1]["decision"] == "speak"
    assert events[-1]["budget_ok"] is True and events[-1]["ts"] > 0
    cancel_pending(main)


async def test_interject_silent_or_disabled_keeps_original_behavior():
    main = make_part_main(participation_enabled=False)
    add_provider(main, "Stalker", decision="speak")
    await main.participation.discover()
    await Main._on_message(main, FakeChatEvent(text="插我", at=False))
    assert not main._pending
    assert not main.participation.decisions# decide 根本未被调用

# 开启但提供者沉默 → 照旧 return（仅记观测）
    main.cfg.participation_enabled = True
    main.sdk.module.handlers[("Stalker", "qvq_decision")] = (
        lambda ctx=None, **_: {"decision": "silent", "reason": "保守模式", "score": 0.0, "urgency": "low"}
    )
    await Main._on_message(main, FakeChatEvent(text="再插", at=False))
    assert not main._pending
    assert main.participation.decisions[-1]["decision"] == "silent"
    assert participation_payloads(main)[-1]["decision"] == "silent"


async def test_interject_group_whitelist_config():
    main = make_part_main(participation_enabled=True, participation_groups=["777"])
    add_provider(main, "Stalker", decision="speak")
    await main.participation.discover()
    await Main._on_message(main, FakeChatEvent(text="非白名单群", at=False))
    assert not main._pending and not main.participation.decisions

    main.cfg.participation_groups = ["1"]# 群号命中
    await Main._on_message(main, FakeChatEvent(text="白名单群", at=False))
    assert GROUP_KEY in main._pending

    main.cfg.participation_groups_exclude = ["onebot11:group:*"]# 黑名单优先
    await Main._on_message(main, FakeChatEvent(text="被排除", at=False))
    assert len(main._pending[GROUP_KEY]["items"]) == 1
    cancel_pending(main)


async def test_interject_member_whitelist_blocks_sender():
    main = make_part_main(participation_enabled=True)
    add_provider(main, "Stalker", decision="speak")
    await main.participation.discover()
    main.sessions.set_members(GROUP_KEY, ["u9"])
    await Main._on_message(main, FakeChatEvent(text="名单外人", at=False))
    assert not main._pending
    logged = main.participation.decisions[-1]
    assert logged["decision"] == "speak" and logged["budget_ok"] is False
    assert logged["reason"] == texts.t("participate_member_denied")

# 名单内成员可作为插话由头
    await Main._on_message(main, FakeChatEvent(text="名单内人", user_id="u9", at=False))
    assert GROUP_KEY in main._pending
    cancel_pending(main)


async def test_interject_budget_rejection_observed():
    main = make_part_main(participation_enabled=True)
    add_provider(main, "Stalker", decision="speak")
    await main.participation.discover()
    main.participation.budget.record(GROUP_KEY, KIND_INTERJECT)# 触发默认 300s 冷却
    ev = FakeChatEvent(text="冷却中插话", at=False)
    await Main._on_message(main, ev)
    assert not main._pending and not ev.claimed
    logged = main.participation.decisions[-1]
    assert logged["budget_ok"] is False and logged["reason"]
    assert participation_payloads(main)[-1]["budget_ok"] is False


async def test_observe_feeds_manager_window_via_lifecycle():
    """manager.start() 订阅 qvq.observe 后，旁听窗口经事件链自动入窗。"""
    main = make_part_main(participation_enabled=True)
    captured: dict = {}
    add_provider(main, "Stalker", decision="silent", capture=captured)
    await main.participation.discover()
    main.participation.start()
    assert "qvq.observe" in [e for e, _ in main.sdk.lifecycle.registered]
    await Main._on_message(main, FakeChatEvent(text="第一条", user_id="u2", user_name="乙", at=False))
    await Main._on_message(main, FakeChatEvent(text="第二条", at=False))
    seen = [m["text"] for m in captured["ctx"]["recent_messages"]]
    assert seen == ["第一条", "第二条"]
    assert captured["ctx"]["recent_messages"][0]["sender_name"] == "乙"


# ==================== speak 服务（扩展点 C） ====================

async def test_speak_passes_budget_and_runs_prompt():
    main = make_part_main()
    main.speak = Main.speak.__get__(main)
    reply = await main.speak(GROUP_KEY, reason="冲动值达标", prompt="主动开场")
    assert reply == "ok"
    assert len(main.prompts) == 1
    chat_key, prompt, kwargs = main.prompts[0]
    assert chat_key == GROUP_KEY and prompt == "主动开场"
    assert kwargs["origin"] == "proactive" and kwargs["send"] is True
    assert main.participation.budget.status()["proactive_today"] == 1
    assert main.participation.decisions[-1]["kind"] == "proactive"
    assert main.participation.decisions[-1]["budget_ok"] is True


async def test_speak_default_prompt_when_empty():
    main = make_part_main()
    main.speak = Main.speak.__get__(main)
    await main.speak(GROUP_KEY)
    assert main.prompts[0][1] == texts.t("participate_speak_prompt")


async def test_speak_budget_denied_returns_reason():
    main = make_part_main(participation_proactive_daily_limit=1)
    main.participation.budget.record(GROUP_KEY, KIND_PROACTIVE)
    main.speak = Main.speak.__get__(main)
    out = await main.speak(GROUP_KEY, reason="r", prompt="p")
    assert out and out != "ok"
    assert not main.prompts
    assert main.participation.decisions[-1]["budget_ok"] is False
    assert main.participation.decisions[-1]["reason"] == out


async def test_speak_without_manager_denies():
    main = make_part_main()
    main.participation = None
    main.speak = Main.speak.__get__(main)
    assert await main.speak(GROUP_KEY) == texts.t("participate_disabled")


# ==================== participation_status 与 Dashboard ====================

async def test_participation_status_shape():
    main = make_part_main(participation_enabled=True)
    add_provider(main, "Stalker", decision="silent")
    await main.participation.discover()
    main.participation.log_decision({"kind": "interject", "decision": "silent"})
    status = await Main.participation_status.__get__(main)()
    assert status["enabled"] is True
    assert [p["module"] for p in status["providers"]] == ["Stalker"]
    assert status["decisions"][-1]["decision"] == "silent"
    assert "limits" in status["budget"]


async def test_participation_status_without_manager():
    main = make_part_main()
    main.participation = None
    status = await Main.participation_status.__get__(main)()
    assert status["providers"] == [] and status["decisions"] == []


async def test_dashboard_participation_route_and_endpoint():
    main = make_part_main()
    add_provider(main, "Stalker", decision="silent")
    await main.participation.discover()
    main.participation_status = Main.participation_status.__get__(main)
    manager = DashboardManager(main)
    res = await manager.participation_get(FakeRequest())
    assert res["enabled"] is False
    assert [p["module"] for p in res["providers"]] == ["Stalker"]
    assert "budget" in res and "decisions" in res

    class FakeRouter:
        def __init__(self):
            self.routes = []

        def register_http_route(self, module, path, handler, methods=None):
            self.routes.append((module, tuple(methods or ()), path))

    main.sdk.router = FakeRouter()
    main.sdk.Dashboard = SimpleNamespace(register_view=lambda **_: None)
    DashboardManager(main).register()
    assert ("QvQChat", ("GET",), "/api/qvq/participation") in main.sdk.router.routes


# ==================== 生态桥热刷新挂钩 ====================

async def test_ecosystem_refresh_triggers_discover():
    main = make_part_main()
    add_provider(main, "Stalker", decision="silent")
    bridge = EcosystemBridge(main)
    await bridge.refresh()
    assert "Stalker" in main.participation.providers
# 模块卸载（目录清空）→ 防抖刷新后提供者移除
    main.sdk.module._catalog["Stalker"] = []
    await bridge.refresh()
    assert "Stalker" not in main.participation.providers


async def test_ecosystem_refresh_without_participation_tolerated():
    main = make_part_main()
    main.participation = None
    bridge = EcosystemBridge(main)
    info = await bridge.refresh()
    assert info["modules"] == 0


# ==================== 配置组 ====================

def test_participation_config_group_and_defaults():
    assert GROUP_META["participation"]["order"] < GROUP_META["access"]["order"]
    fm = QvQConfig.field_map()
    expected = {
        "participation_enabled": (False, "participation", 1),
        "participation_groups": ([], "participation", 2),
        "participation_groups_exclude": ([], "participation", 3),
        "participation_strategy": ("first_speak", "participation", 4),
        "participation_score_threshold": (0.6, "participation", 5),
        "participation_hourly_limit": (8, "participation", 6),
        "participation_cooldown_seconds": (300, "participation", 7),
        "participation_provider_timeout": (2, "participation", 8),
        "participation_proactive_daily_limit": (3, "participation", 9),
    }
    for key, (default, group, order) in expected.items():
        assert key in fm, key
        f = fm[key]
        ui = (f.metadata or {}).get("ui") or {}
        assert ui.get("group") == group and ui.get("order") == order, key
        actual = f.default_factory() if f.default_factory is not MISSING else f.default
        assert actual == default, key
    ui = (fm["participation_strategy"].metadata or {}).get("ui") or {}
    assert ui.get("options") == ["first_speak", "max_score", "unanimous"]
# select 成员校验 / bool 拒收字符串 / 默认关闭
    assert QvQConfig.coerce("participation_strategy", "bogus")[0] is False
    assert QvQConfig.coerce("participation_enabled", True) == (True, True, None)
    assert QvQConfig.coerce("participation_enabled", "true")[0] is False
    ok, v, _ = QvQConfig.coerce("participation_hourly_limit", "5")
    assert ok and v == 5
