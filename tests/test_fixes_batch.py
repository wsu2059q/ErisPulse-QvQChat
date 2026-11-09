import asyncio
from types import SimpleNamespace

from QvQChat.Main import Main

from fakes import FakeChatEvent, FakeMain, FakeRequestEvent, make_ctx


def _bind_inbox(main):
    """FakeMain 未继承 InboxMixin：绑定本用例用到的方法。"""
    for name in ("_enqueue_waiting", "_announce_queued"):
        setattr(main, name, getattr(Main, name).__get__(main))
    return main


# ---------- 审计落盘 ----------


async def test_audit_persists_to_storage():
    main = FakeMain()
    Main.audit(main, "run_python_sdk", {"bytes": 12})
    entries = main.sdk.storage.get("QvQChat:audit", [])
    assert len(entries) == 1
    assert entries[0]["tool"] == "run_python_sdk"
    Main.audit(main, "run_python", {"bytes": 3})
    assert len(main.sdk.storage.get("QvQChat:audit", [])) == 2


# ---------- 引用消息本地注入 ----------


def _main_with_transcript(rows):
    main = FakeMain()
    main.sdk.transcript = SimpleNamespace(
        get=lambda key, n=200: list(rows),
        session_key_from_event=lambda ev: "k",
    )
    return main


async def test_quote_prefers_local_transcript_and_marks_own_bot_message():
    main = _main_with_transcript([
        {"role": "user", "text": "之前的用户消息", "event_id": "m1"},
        {"role": "bot", "text": "要进我就受理，不要我就把它拒掉~", "event_id": "m2"},
    ])
    ev = FakeChatEvent(text="同意", reply_message_id="m2", group=False)
    quoted = await Main._quote_content(main, ev)
    assert "要进我就受理" in quoted
    assert ("你自己之前发的消息" in quoted) or ("you yourself sent earlier" in quoted)  # 标注为 bot 自己的话


async def test_quote_local_user_message_plain():
    main = _main_with_transcript([
        {"role": "user", "text": "这条是用户说的", "event_id": "u9"},
    ])
    ev = FakeChatEvent(text="这是啥", reply_message_id="u9", group=False)
    quoted = await Main._quote_content(main, ev)
    assert quoted == "这条是用户说的"


async def test_quote_falls_back_empty_without_any_source():
    main = _main_with_transcript([])
    ev = FakeChatEvent(text="?", reply_message_id="missing", group=False)
    assert await Main._quote_content(main, ev) == ""


# ---------- 任务运行中：排队 vs 中断插入 ----------


class _Live:
    status = "running"

    def __init__(self, text="做到一半的进度"):
        self.cancelled = False
        self.text = text

    def cancel(self):
        self.cancelled = True


class _Registry:
    def __init__(self, live):
        self._live = live

    def get(self, key):
        return self._live


async def test_live_conflict_interrupt_mode_cancels_and_notes():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main.cfg.interrupt_mode = "interrupt"
    live = _Live()
    main.live_registry = _Registry(live)
    ev = FakeChatEvent(text="先停一下，我问个别的事", group=False)
    proceed = await Main._live_conflict(main, "k", ev, [{"text": "先停一下", "images": []}])
    assert proceed is True and live.cancelled
    assert "做到一半的进度" in main._interrupted_notes["k"]


async def test_live_conflict_queue_mode_enqueues():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main.cfg.interrupt_mode = "queue"
    live = _Live()
    main.live_registry = _Registry(live)
    ev = FakeChatEvent(text="好的", group=False)
    proceed = await Main._live_conflict(main, "k", ev, [{"text": "好的", "images": []}])
    assert proceed is False and not live.cancelled
    assert main._waiting.get("k")


async def test_live_conflict_auto_mode_queues_or_interrupts():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main.cfg.interrupt_mode = "auto"
    live = _Live()
    main.live_registry = _Registry(live)

    async def decide_queue(chat_key, live_obj, text):
        return "queue", "minor"

    async def decide_interrupt(chat_key, live_obj, text):
        return "interrupt", "urgent"

    main._auto_interrupt_decide = decide_queue
    ev = FakeChatEvent(text="顺便说一句", group=False)
    assert await Main._live_conflict(main, "k", ev, [{"text": "顺便说一句", "images": []}]) is False
    assert main._waiting.get("k") and not live.cancelled

    main._waiting = {}
    main._auto_interrupt_decide = decide_interrupt
    assert await Main._live_conflict(main, "k2", ev, [{"text": "这个更重要", "images": []}]) is True
    assert live.cancelled


async def test_live_conflict_no_running_task_proceeds():
    main = FakeMain()
    main._pending = {}
    main.live_registry = _Registry(_Live())
    main.live_registry._live.status = "idle"
    ev = FakeChatEvent(text="hi", group=False)
    assert await Main._live_conflict(main, "k", ev, [{"text": "hi", "images": []}]) is True


# ---------- 请求决策持久化 ----------


async def test_request_decision_turn_is_persisted():
    main = FakeMain()
    captured = {}

    async def fake_run_prompt(chat_key, prompt, **kwargs):
        captured["kwargs"] = kwargs
        return "主人要受理吗"

    main.run_prompt = fake_run_prompt
    entry = {"platform": "onebot11", "summary": "群邀请", "comment": "",
             "request_id": "flag-1"}
    main.sessions._admin_ids_for = lambda platform: ["10001"]
    await Main._request_decision(main, FakeRequestEvent(user_id="u1", account="bot"), entry)
    assert captured["kwargs"].get("persist") is True  # 决策回合进历史，主人回复才有上下文


# ---------- 瘦身 ----------


async def test_storage_slim_strips_old_tool_detail_and_truncates():
    from QvQChat.dashboard.manager import DashboardManager

    main = FakeMain()
    main.cfg.context_limit = 6
    manager = DashboardManager(main)
    old_rounds = [{"text": "x" * 50, "tools": [{"name": "t", "result": "y" * 500}]}]
    contexts = []
    for i in range(12):
        contexts.append({"role": "assistant", "content": "z" * 3000, "rounds": old_rounds})
    main.sdk.storage.set("QvQChat:conv:c1", {"contexts": contexts})
    result = await manager.storage_slim(SimpleNamespace(query_params={}))
    assert result["ok"] and result["sessions"] == 1
    saved = main.sdk.storage.get("QvQChat:conv:c1")["contexts"]
    # 最近 6 条保持原样
    assert saved[-1].get("rounds") == old_rounds and len(saved[-1]["content"]) == 3000
    # 更早的条目丢工具明细并截断
    assert saved[0].get("rounds") is None
    assert len(saved[0]["content"]) < 3000 and "瘦身截断" in saved[0]["content"]


# ---------- call_api 账户字段名探测 ----------


def test_account_kwarg_prefers_underscore_param():
    from QvQChat.tools_builtin.erispulse import _account_kwarg_of

    class Underscore:
        async def call_api(self, endpoint, _account_id=None, **params):
            pass

    class Standard:
        async def call_api(self, endpoint, **params):
            pass

    assert _account_kwarg_of(Underscore()) == "_account_id"
    assert _account_kwarg_of(Standard()) == "account_id"
