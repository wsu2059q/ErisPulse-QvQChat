"""auto 三选判定（demote/interrupt/queue）+ 排队回执加固 + 会话策略（policy）测试。

覆盖 4.6.4 批次的核心行为：
- demote：旧任务转后台子智能体续跑（探针 + spawn），新消息立即处理，回执一条
- queue：完全静默入队（不再有排队播报二连发）
- _announce_queued 输出加固：思考链混正文时只认 JSON line，绝不回发原文
- listen_allowed：屏蔽/白名单早闸；apply_priority：会话优先级偏移
- live.stale：running 态三重回收护栏（任务已死 / 长时间无事件）
- build_system_parts(low_token)：省流跳过重组件、保留人格与连续性部件
"""

import asyncio

import pytest

from QvQChat.Main import Main
from QvQChat.chat.inbox import _json_line_of
from QvQChat.conversation.policy import (
    PRIORITY_OFFSET,
    apply_priority,
    get_policy,
    listen_allowed,
    set_policy,
)
from QvQChat.dashboard.live import LiveStream

from fakes import FakeChatEvent, FakeMain


def _bind_inbox(main):
    """FakeMain 未继承 InboxMixin：绑定本用例用到的方法。"""
    for name in ("_enqueue_waiting", "_announce_queued", "_handle_auto_decision"):
        setattr(main, name, getattr(Main, name).__get__(main))
    return main


class _Live:
    status = "running"

    def __init__(self, text="做到一半的进度", prompt="帮我写一篇角色设定，越详细越好"):
        self.cancelled = False
        self.text = text
        self.prompt = prompt

    def cancel(self):
        self.cancelled = True


async def _drain(main):
    for task in list(main.spawned):
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2)
        except Exception:
            task.cancel()


# ---------- _json_line_of：思考链剥离 + JSON 提取 ----------


def test_json_line_strips_think_and_extracts():
    raw = '<think>Let me think... {"fake": 1}</think>Here you go: {"line":"马上就好"}'
    assert _json_line_of(raw) == "马上就好"


def test_json_line_garbage_returns_empty():
    assert _json_line_of("I am thinking about the answer... no json here") == ""
    assert _json_line_of("") == ""
    assert _json_line_of(None) == ""


# ---------- _handle_auto_decision：三选收尾 ----------


async def test_demote_moves_task_to_background_and_replies_once():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main._interrupted_notes = {}
    main.live_registry = None
    live = _Live()
    ev = FakeChatEvent(text="帮我查下充值方式", group=False)
    proceed = await Main._handle_auto_decision(
        main, "onebot11:group:1", ev, [{"text": "查充值", "images": []}],
        live, "demote", "角色在后台继续写，先回你这条～",
    )
    assert proceed is True and live.cancelled
# 回执恰好一条（回执合一）
    assert len(ev.replies) == 1
    assert "后台" in ev.replies[0][1]
# 后台子智能体已 spawn：sub: 键 + 探针 running + 子会话收到任务文本
    subs = [t for t in main.spawned]
    assert subs, "demote 应该 spawn 后台续跑任务"
    sub_keys = [k for k in main.sdk.storage._data if k.startswith("QvQChat:subjob:sub:onebot11:group:1:demote:")]
    assert sub_keys, "应有 demote 探针落库"
    probe = main.sdk.storage.get(sub_keys[0], {})
    assert probe.get("status") == "running"
    assert probe.get("parent_chat_key") == "onebot11:group:1"
    await _drain(main)


async def test_queue_decision_is_silent_and_enqueues():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main.cfg.interrupt_mode = "auto"
    live = _Live()
    ev = FakeChatEvent(text="哈哈哈", group=False)
    items = [{"text": "哈哈哈", "images": []}]
    proceed = await Main._handle_auto_decision(main, "k", ev, items, live, "queue", "")
    assert proceed is False and not live.cancelled
# 完全静默：queue 不发任何回执（line 即便非空也丢弃）
    assert ev.replies == []
    assert main._waiting.get("k")


async def test_interrupt_decision_stores_note_and_replies():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main._interrupted_notes = {}
    live = _Live()
    ev = FakeChatEvent(text="停！别写了", group=False)
    proceed = await Main._handle_auto_decision(main, "k", ev, [{"text": "停", "images": []}],
                                               live, "interrupt", "")
    assert proceed is True and live.cancelled
    assert len(ev.replies) == 1
    assert "做到一半的进度" in main._interrupted_notes["k"]


async def test_demote_with_empty_line_falls_back_to_template():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main._interrupted_notes = {}
    live = _Live()
    ev = FakeChatEvent(text="在吗", group=False)
    await Main._handle_auto_decision(main, "k", ev, [{"text": "在吗", "images": []}],
                                     live, "demote", "")
    assert len(ev.replies) == 1  # 模板回退仍是恰好一条


async def test_demote_failure_does_not_block_new_message():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main._interrupted_notes = {}

    async def _boom(**kwargs):
        raise RuntimeError("spawn failed")

    import QvQChat.chat.inbox as inbox_mod
    orig = inbox_mod.demote_to_background
    inbox_mod.demote_to_background = _boom
    try:
        live = _Live()
        ev = FakeChatEvent(text="新消息", group=False)
        proceed = await Main._handle_auto_decision(main, "k", ev, [{"text": "新消息", "images": []}],
                                                   live, "demote", "")
        assert proceed is True and live.cancelled
    finally:
        inbox_mod.demote_to_background = orig


# ---------- _announce_queued 输出加固（思考泄露根因） ----------


async def test_announce_never_sends_raw_reasoning(monkeypatch=None):
    main = _bind_inbox(FakeMain())
    main._waiting = {}
    main._interrupted_notes = {}

    class _Resp:
        content = (
            "You are simulating a scenario where a robot is executing a long task. "
            'The task output is: 「角色设定」... So I need to write in Chinese... '
            'Reply ONLY with JSON: {"line":"正在写角色设定，你的消息排上了，忙完就处理"}'
        )

    class _Pool:
        async def dispatch(self, spec, request):
            return _Resp()

    main.pool = _Pool()
    ev = FakeChatEvent(text="好了没", group=False)
    await Main._announce_queued(main, "k", ev, [{"text": "好了没", "images": []}])
    assert len(ev.replies) == 1
    sent = ev.replies[0][1]
    assert "simulating" not in sent, "思考链绝不能外露"
    assert len(sent) <= 80, "回执必须截断到 80 字内"
    assert "排上" in sent or "排" in sent


async def test_announce_falls_back_to_template_on_garbage():
    main = _bind_inbox(FakeMain())
    main._waiting = {}

    class _Resp:
        content = "（模型抽风，输出整段废话没有 JSON）" * 10

    class _Pool:
        async def dispatch(self, spec, request):
            return _Resp()

    main.pool = _Pool()
    ev = FakeChatEvent(text="在吗", group=False)
    await Main._announce_queued(main, "k", ev, [{"text": "在吗", "images": []}])
    assert len(ev.replies) == 1
    assert "废话" not in ev.replies[0][1]  # 模板回退，非原文


async def test_enqueue_announces_only_for_first_message():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    announcements = []

    async def _fake_announce(chat_key, event, items):
        announcements.append(chat_key)

    main._announce_queued = _fake_announce
    ev = FakeChatEvent(text="第一条", group=False)
    Main._enqueue_waiting(main, "k", ev, [{"text": "第一条", "images": []}])
    await asyncio.sleep(0)  # spawn 的播报任务是异步执行的，让一拍再断言
    assert announcements == ["k"]  # 第一条播报
    Main._enqueue_waiting(main, "k", ev, [{"text": "第二条", "images": []}])
    await asyncio.sleep(0)
    assert announcements == ["k"]  # 后续静默
    Main._enqueue_waiting(main, "k2", ev, [{"text": "auto 路径", "images": []}], announce=False)
    await asyncio.sleep(0)
    assert announcements == ["k"]  # auto 路径不播报


# ---------- policy：屏蔽 / 白名单 / 优先级 ----------


def test_policy_mute_gate_blocks_message():
    main = FakeMain()
    set_policy(main.sdk, "onebot11:group:1", muted=True)
    assert listen_allowed(main.cfg, main.sdk, "onebot11:group:1") is False
    assert listen_allowed(main.cfg, main.sdk, "onebot11:group:2") is True


def test_policy_whitelist_mode():
    main = FakeMain()
    main.cfg.chat_listen_mode = "whitelist"
    main.cfg.chat_whitelist = ["onebot11:group:100", "qqmail:"]
    assert listen_allowed(main.cfg, main.sdk, "onebot11:group:100") is True
    assert listen_allowed(main.cfg, main.sdk, "onebot11:group:200") is False
    assert listen_allowed(main.cfg, main.sdk, "qqmail:private:x") is True  # 前缀匹配
# 名单为空 = 全拒
    main.cfg.chat_whitelist = []
    assert listen_allowed(main.cfg, main.sdk, "onebot11:group:100") is False


def test_apply_priority_offsets():
    assert apply_priority({"priority": "low"}, 0) == 0 + PRIORITY_OFFSET["low"]
    assert apply_priority({"priority": "high"}, 6) == 4  # 插话在 high 会话也能提前
    assert apply_priority({"priority": "high"}, 0) == -2
    assert apply_priority({"priority": "normal"}, 0) == 0
    assert apply_priority({"priority": "low"}, 8) == 9  # 钳制上限


def test_set_policy_normalizes_invalid():
    main = FakeMain()
    policy = set_policy(main.sdk, "k", priority="ultra", muted="yes")
    assert policy["priority"] == "normal"
    assert policy["muted"] is True
    assert get_policy(main.sdk, "k") == policy


# ---------- live.stale：running 态回收护栏 ----------


async def test_live_stale_running_guards():
    import time
    stream = LiveStream(session="s")
    assert stream.stale() is False  # 新鲜 running 不回收
# 任务已死但注册表没跟上 → 回收
    stream.task = asyncio.ensure_future(asyncio.sleep(0))
    await stream.task
    assert stream.task.done() and stream.stale() is True
# 长时间无任何事件 → 回收
    stream2 = LiveStream(session="s2")
    stream2.updated = time.time() - 601
    assert stream2.stale() is True
# done 态按原 RETAIN 逻辑
    stream3 = LiveStream(session="s3")
    stream3.status = "done"
    assert stream3.stale() is False  # 刚结束仍保留（前端还要看结果）


# ---------- 省流模式：build_system_parts 跳过重组件 ----------


def test_build_system_parts_low_token_skips_heavy_parts():
    main = FakeMain()
    main.knowledge.add("恐龙", "霸王龙生活于白垩纪晚期。", triggers=["恐龙"])  # kb 命中才有 kb 部件
    persona = {"id": "p1", "name": "测试", "system": "你是测试。"}
    kb = ["给我讲讲恐龙的知识"]
    full = main.sessions.build_system_parts(
        persona, chat_key="onebot11:group:1", scene="s", kb_texts=kb, kb_query="恐龙",
    )
    slim = main.sessions.build_system_parts(
        persona, chat_key="onebot11:group:1", scene="s", kb_texts=kb, kb_query="恐龙", low_token=True,
    )
    kinds_full = {p.kind for p in full}
    kinds_slim = {p.kind for p in slim}
    assert "kb" in kinds_full and "kb" not in kinds_slim
    assert "skill_list" not in kinds_slim
    for kind in ("persona", "capability"):
        assert kind in kinds_slim  # 人格与能力认知不能省
