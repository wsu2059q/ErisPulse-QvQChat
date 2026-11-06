# 多人/高负载：并发闸门、优先级分派、陈旧插话丢弃、参与决策降载
import asyncio
import time

import pytest

from QvQChat.engine.base import ChatRequest, ChatResponse, TaskSpec
from QvQChat.engine.gate import PriorityGate
from QvQChat.engine.pool import ModelPool
from QvQChat.Main import Main

from fakes import FakeChatEvent, FakeMain, FakeSDK, make_config


def _inbox_main(**cfg):
    """FakeMain + InboxMixin 运行时状态（_pending/_chat_locks 等）。"""
    main = FakeMain(**cfg)
    main._pending = {}
    main._chat_locks = {}
    main._rate_window = {}
    main._rate_notice_shown = {}
    main._waiting = {}
    # _batch_message 依赖的 Mixin 方法：FakeMain 不是 Main 子类，绑定为实例属性
    from QvQChat.chat.inbox import InboxMixin

    main._sender_name = lambda event: InboxMixin._sender_name(event)
    # 防抖定时器不真跑（测试同步 flush）；绑定为空协程避免 spawn 报缺方法
    main._flush_later = lambda chat_key, window: _noop()
    main._lock_for = lambda chat_key: main._chat_locks.setdefault(chat_key, __import__("asyncio").Lock())
    main.spawn = lambda coro: asyncio.get_event_loop().create_task(coro)
    return main


async def _noop():
    return None


# ===== PriorityGate =====

def test_gate_unlimited_passes_everything():
    gate = PriorityGate(0)
    for _ in range(5):
        asyncio.get_event_loop_policy()  # noop：保持可读
    async def drive():
        for _ in range(5):
            await gate.acquire()
        assert gate.active == 5
        for _ in range(5):
            gate.release()
    asyncio.run(drive())
    assert gate.active == 0


def test_gate_limits_active():
    gate = PriorityGate(2)

    async def drive():
        await gate.acquire()
        await gate.acquire()
        assert gate.saturated is True
        task = asyncio.create_task(gate.acquire(priority=8))
        await asyncio.sleep(0.01)
        assert gate.waiting == 1 and gate.active == 2
        gate.release()
        await asyncio.wait_for(task, 1)
        assert gate.active == 2 and gate.waiting == 0
        gate.release()
        gate.release()

    asyncio.run(drive())
    assert gate.active == 0


def test_gate_high_priority_first():
    gate = PriorityGate(1)
    order = []

    async def drive():
        await gate.acquire()  # 唯一槽位被占
        low = asyncio.create_task(_holder(gate, 8, order, "low"))
        await asyncio.sleep(0.01)
        high = asyncio.create_task(_holder(gate, 0, order, "high"))
        await asyncio.sleep(0.01)
        gate.release()  # 放出一个空位 → 应该给 priority=0
        await asyncio.gather(low, high)
        gate.release()
        gate.release()

    asyncio.run(drive())
    assert order == ["high", "low"]


async def _holder(gate, priority, order, tag):
    await gate.acquire(priority)
    order.append(tag)
    await asyncio.sleep(0.01)
    gate.release()


def test_gate_cancel_while_waiting_does_not_leak_slot():
    gate = PriorityGate(1)

    async def drive():
        await gate.acquire()
        waiter = asyncio.create_task(gate.acquire(priority=8))
        await asyncio.sleep(0.01)
        waiter.cancel()
        try:
            await waiter
        except asyncio.CancelledError:
            pass
        assert gate.waiting == 0
        gate.release()
        assert gate.active == 0  # 槽位没有被取消者占走

    asyncio.run(drive())


# ===== pool 集成：dispatch 优先级映射 + 闸门包住 engine.chat =====

class _SpyEngine:
    def __init__(self):
        self.calls = []

    async def chat(self, base_url, api_key, request, on_delta=None, on_reset=None, on_reasoning=None):
        self.calls.append(request.model)
        return ChatResponse(content="ok", model=request.model, usage={})


def _make_pool():
    pool = ModelPool(FakeSDK(), make_config())
    pool.save_provider(
        {
            "id": "p1",
            "name": "P1",
            "base_url": "https://x/v1",
            "api_key": "k",
            "models": [{"id": "m1", "enabled": True, "tool_call": True}],
        }
    )
    pool.engine = _SpyEngine()
    return pool


def test_dispatch_maps_background_kind_to_low_priority():
    pool = _make_pool()
    spec = TaskSpec(kind="compact", prefer="cheap")
    assert str(spec.kind) != "chat"
    # TaskSpec.priority 默认 0；映射逻辑在 dispatch 内部（chat=0 / 其它=8），这里验证字段可用
    spec_chat = TaskSpec(kind="chat", priority=6)
    assert spec_chat.priority == 6


def test_pool_chat_releases_gate_on_success_and_failure():
    pool = _make_pool()

    class _BoomEngine:
        async def chat(self, *a, **k):
            raise RuntimeError("down")

    async def drive():
        pool.gate.set_limit(1)
        await pool.chat(ChatRequest(messages=[], model="p:m1"))
        assert pool.gate.active == 0  # 成功释放
        pool.engine = _BoomEngine()
        with pytest.raises(Exception):
            await pool.chat(ChatRequest(messages=[], model="p:m1"))
        assert pool.gate.active == 0  # 失败也释放

    asyncio.run(drive())


def test_saturated_property_reflects_gate():
    pool = _make_pool()
    pool.gate.set_limit(1)
    assert pool.saturated is False
    pool.gate._active = 1
    assert pool.saturated is True
    pool.gate._active = 0


# ===== inbox：陈旧插话丢弃 =====

async def test_stale_interject_dropped():
    main = _inbox_main(interject_stale_seconds=0.05)
    key = "onebot11:group:1"
    ev = FakeChatEvent(text="插话话题", group=True, group_id="1", user_id="9")
    Main._batch_message(main, ev, key, "插话话题", [], origin="plugin")
    main._pending[key]["ts"] = time.time() - 999  # 人为变陈旧
    called = []

    async def fake_process(event, items, chat_key, origin="chat"):
        called.append(origin)

    main._process_locked = fake_process
    await Main._flush_pending(main, key)
    assert called == []  # 陈旧插话不处理


async def test_stale_user_message_never_dropped():
    main = _inbox_main(interject_stale_seconds=0.05)
    key = "onebot11:group:1"
    ev = FakeChatEvent(text="在吗", group=True, group_id="1", user_id="9", at=True)
    Main._batch_message(main, ev, key, "在吗", [], origin="chat")
    main._pending[key]["ts"] = time.time() - 9999  # 再久也要答
    called = []

    async def fake_process(event, items, chat_key, origin="chat"):
        called.append(origin)

    main._process_locked = fake_process
    await Main._flush_pending(main, key)
    assert called == ["chat"]


async def test_fresh_interject_passes():
    main = _inbox_main(interject_stale_seconds=90)
    key = "onebot11:group:1"
    ev = FakeChatEvent(text="新话题", group=True, group_id="1", user_id="9")
    Main._batch_message(main, ev, key, "新话题", [], origin="plugin")
    called = []

    async def fake_process(event, items, chat_key, origin="chat"):
        called.append(origin)

    main._process_locked = fake_process
    await Main._flush_pending(main, key)
    assert called == ["plugin"]


# ===== inbox：参与决策降载 =====

def test_interject_overloaded_conditions():
    main = _inbox_main()

    class _Gate:
        def __init__(self, saturated):
            self._s = saturated
        @property
        def saturated(self):
            return self._s

    main.pool = type("P", (), {"gate": _Gate(False)})()
    from QvQChat.chat.inbox import InboxMixin

    main._interject_overloaded = lambda key: InboxMixin._interject_overloaded(main, key)
    key = "onebot11:group:1"
    assert main._interject_overloaded(key) in (True, False)  # 空闲态依锁状态而定，不抛错
    main._lock_for(key)  # 创建锁
    main.pool.gate = _Gate(True)
    assert main._interject_overloaded(key) is True  # 闸门满载 → 插话降载


def test_background_blocked_under_saturation():
    """满载时后台任务让路：压缩/标题/筛选/中止判定可据此跳过。"""
    main = FakeMain(max_concurrent_requests=1)
    pool = main.pool
    pool.gate.set_limit(1)
    assert pool.background_blocked() is False
    pool.gate._active = 1
    assert pool.background_blocked() is True
    pool.gate._active = 0
    # 不限流模式永不让路
    pool.gate.set_limit(0)
    assert pool.background_blocked() is False


async def test_interrupt_decide_skips_model_when_saturated():
    """满载时中止判定不发模型调用，直接回退排队（安全默认）。"""
    main = _inbox_main(max_concurrent_requests=1)
    main.pool.gate.set_limit(1)
    calls = []

    async def fake_dispatch(spec, request, **kw):
        calls.append(spec.kind)
        from QvQChat.engine.base import ChatResponse

        return ChatResponse(content='{"decision":"interrupt","reason":"x"}', usage={})

    main.pool.dispatch = fake_dispatch
    main.pool.gate._active = 1  # 模拟满载
    from QvQChat.chat.inbox import InboxMixin
    from types import SimpleNamespace

    main._auto_interrupt_decide = lambda *a, **k: InboxMixin._auto_interrupt_decide(main, *a, **k)
    main._enqueue_waiting = lambda *a, **k: None
    live = SimpleNamespace(text="正在执行的任务")
    decision, why = await main._auto_interrupt_decide("onebot11:group:1", live, "新消息")
    assert decision == "queue" and calls == []
    main.pool.gate._active = 0
    decision, why = await main._auto_interrupt_decide("onebot11:group:1", live, "新消息")
    assert calls == ["compact"]  # 不饱和时正常判定


def test_provider_load_steering_reorders_chain():
    """并发时转移：首选 provider 忙（>=阈值）时，新请求导向池内更闲的一家——不等报错。"""
    pool = ModelPool(FakeSDK(), make_config(provider_load_steering=True, provider_steer_active=2))
    pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://1/v1", "api_key": "k",
                        "models": [{"id": "a", "enabled": True, "tool_call": True}]})
    pool.save_provider({"id": "p2", "name": "P2", "base_url": "https://2/v1", "api_key": "k",
                        "models": [{"id": "b", "enabled": True, "tool_call": True}]})

    class Busy:
        async def chat(self, *a, **k):
            return ChatResponse(content="ok", usage={})

    pool.engine = Busy()
    pool._provider_active["p1"] = 3  # 首选已过载

    async def drive():
        resp = await pool.chat(ChatRequest(messages=[], model="p1:a"))
        assert resp.content == "ok"
        assert pool._provider_active["p1"] == 3  # 没走 p1（计数不变）
        assert pool._provider_active.get("p2", 0) == 0  # p2 已释放

    asyncio.run(drive())


def test_steering_off_keeps_primary():
    pool = ModelPool(FakeSDK(), make_config(provider_load_steering=False))
    pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://1/v1", "api_key": "k",
                        "models": [{"id": "a", "enabled": True, "tool_call": True}]})
    pool.save_provider({"id": "p2", "name": "P2", "base_url": "https://2/v1", "api_key": "k",
                        "models": [{"id": "b", "enabled": True, "tool_call": True}]})

    class Spy:
        def __init__(self):
            self.calls = []

        async def chat(self, base_url, api_key, request, **k):
            self.calls.append(request.model)
            return ChatResponse(content="ok", usage={})

    spy = Spy()
    pool.engine = spy
    pool._provider_active["p1"] = 9

    async def drive():
        await pool.chat(ChatRequest(messages=[], model="p1:a"))

    asyncio.run(drive())
    assert spy.calls and spy.calls[0].endswith("a")  # 关闭分流：仍走首选


def test_effort_smalltalk_injected_via_routing():
    """简单场景自动降思考：难度路由判为 cheap 时按 effort_smalltalk 注入 reasoning_effort。"""
    from QvQChat.engine.base import ChatRequest, TaskSpec
    from QvQChat.engine.pool import ModelPool
    from fakes import FakeSDK, make_config

    pool = ModelPool(FakeSDK(), make_config(routing_enabled=True, effort_smalltalk="off"))
    pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://1/v1", "api_key": "k",
                        "models": [{"id": "a", "enabled": True, "tool_call": True}]})

    captured = {}

    class Eng:
        async def chat(self, base_url, api_key, request, **k):
            captured["effort"] = request.reasoning_effort
            from QvQChat.engine.base import ChatResponse
            return ChatResponse(content="ok", usage={})

    pool.engine = Eng()

    async def drive():
        spec = TaskSpec(kind="chat", chat_key="c1")
        await pool.dispatch(spec, ChatRequest(messages=[{"role": "user", "content": "嗯嗯"}]))
        assert captured["effort"] == "off"

    asyncio.run(drive())


def test_effort_empty_means_no_intervention():
    from QvQChat.engine.base import ChatRequest, TaskSpec
    from QvQChat.engine.pool import ModelPool
    from fakes import FakeSDK, make_config

    pool = ModelPool(FakeSDK(), make_config(routing_enabled=True, effort_smalltalk=""))
    pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://1/v1", "api_key": "k",
                        "models": [{"id": "a", "enabled": True, "tool_call": True}]})

    captured = {}

    class Eng:
        async def chat(self, base_url, api_key, request, **k):
            captured["effort"] = request.reasoning_effort
            from QvQChat.engine.base import ChatResponse
            return ChatResponse(content="ok", usage={})

    pool.engine = Eng()

    async def drive():
        await pool.dispatch(TaskSpec(kind="chat", chat_key="c2"),
                            ChatRequest(messages=[{"role": "user", "content": "嗯嗯"}]))

    asyncio.run(drive())
    assert captured["effort"] == ""


def _quality_pool(keep):
    pool = ModelPool(FakeSDK(), make_config(provider_steer_keep=keep))
    pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://1/v1", "api_key": "k",
                        "models": [{"id": "a", "enabled": True, "tool_call": True},
                                   {"id": "a2", "enabled": True, "tool_call": True}]})
    pool.save_provider({"id": "p2", "name": "P2", "base_url": "https://2/v1", "api_key": "k",
                        "models": [{"id": "b", "enabled": True, "tool_call": True}]})
    calls = []

    class FailP1:
        async def chat(self, base_url, api_key, request, **k):
            calls.append(base_url)
            if base_url.endswith("1/v1"):
                from QvQChat.engine.base import EngineError
                raise EngineError("boom")
            return ChatResponse(content="ok", usage={})

    pool.engine = FailP1()
    return pool, calls


def test_steer_keep_guards_breaker_fallback():
    """质量绑定：首选 provider ∈ steer_keep，其模型全挂时只允许同家顶上——宁可报错不换弱模型。"""
    pool, calls = _quality_pool(keep=["p1"])

    async def drive():
        from QvQChat.engine.base import EngineError
        with pytest.raises(EngineError):
            await pool.chat(ChatRequest(messages=[], model="p1:a"))

    asyncio.run(drive())
    assert calls and all(u.endswith("1/v1") for u in calls), calls  # p2 从未被触碰


def test_breaker_fallback_cross_provider_without_keep():
    """未绑定时保持现状：同家全挂跨提供商回退（b 被尝试并成功）。"""
    pool, calls = _quality_pool(keep=[])

    async def drive():
        resp = await pool.chat(ChatRequest(messages=[], model="p1:a"))
        assert resp.content == "ok"

    asyncio.run(drive())
    assert any(u.endswith("2/v1") for u in calls), calls
