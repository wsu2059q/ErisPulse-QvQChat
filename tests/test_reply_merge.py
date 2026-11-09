import asyncio
import time

from QvQChat.Main import Main
from QvQChat.chat.inbox import _RECENT_MSGS
from QvQChat.tools_builtin.erispulse import _request_route_kwargs

from fakes import FakeChatEvent, make_ctx
from test_aggregate import make_main


def make_merge_main(**overrides):
    overrides.setdefault("aggregate_window", 0.05)  # 短聚合窗：回灌后立刻出回合
    main = make_main(**overrides)
    main._merge_timers = {}
    main._last_reply_ts = {}
# make_main 的绑定清单没覆盖合并窗相关方法：unbound 调用前补绑
    for name in ("_batch_message", "_flush_later", "_flush_pending", "_drain_waiting",
                 "_enqueue_waiting", "_announce_queued", "_arm_merge_timer"):
        setattr(main, name, getattr(Main, name).__get__(main))
    return main


async def _wait_for(pred, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        await asyncio.sleep(0.02)
    return False


async def test_flush_holds_during_merge_window():
    """刚回复过的会话：聚合窗口关闭后直接挂等待队列，不开新回合。"""
    main = make_merge_main(reply_merge_window=1.2)
    main._last_reply_ts["onebot11:group:1"] = time.time() - 0.2  # 刚回复 0.2s
    ev = FakeChatEvent(text="再来一条", user_id="u2", at=True)
    await Main._on_message(main, ev)
    # 聚合窗(0.05s)关闭 → flush → 命中合并窗 hold（轮询等调度，防负载抖动）
    held = await _wait_for(lambda: main._waiting.get("onebot11:group:1"))
    assert held, "消息必须挂入等待队列"
    assert not main.captured, "合并窗口内不得开新回合"
    assert "onebot11:group:1" in main._merge_timers
    for task in list(main._merge_timers.values()):  # 清理挂起定时器防 loop 警告
        task.cancel()


async def test_merge_timer_drains_into_single_turn():
    """窗口到点：等待队列整体回灌为一次聚合回合（一个回复）。"""
    main = make_merge_main(reply_merge_window=0.15)
    main._last_reply_ts["onebot11:group:1"] = time.time() - 0.05
    ev1 = FakeChatEvent(text="第一句", user_id="u2", user_name="路人甲", at=True)
    ev2 = FakeChatEvent(text="第二句", user_id="u3", user_name="路人乙", at=True)
    await Main._on_message(main, ev1)
    await asyncio.sleep(0.02)
    await Main._on_message(main, ev2)
    await asyncio.sleep(0.05)
    # 聚合窗口(5s)未到，手动 flush 让两条都进等待队列
    for key in list(main._pending):
        main._pending[key]["timer"] = None
        await Main._flush_pending(main, key)
    assert main._waiting.get("onebot11:group:1"), "两条都应挂入等待队列"
    assert len(main.captured) == 0
    await asyncio.sleep(0.3)  # 合并定时器到点回灌
    await asyncio.sleep(0.2)  # 回灌后聚合窗口走完再处理
    assert main.captured, "窗口到点必须合并回灌为一个回合"
    assert len(main.captured) == 1, "多条消息只开一次回合"
    user_msg = [m for m in main.captured[0]["messages"] if m.get("role") == "user"][-1]
    content = user_msg["content"]
    assert "第一句" in content and "第二句" in content
    # 各自发言人归属保留
    assert "路人甲" in content and "路人乙" in content


async def test_no_merge_window_processes_immediately():
    """reply_merge_window=0（关闭）：回复后立刻可开新回合，不挂队列。"""
    main = make_merge_main(reply_merge_window=0.0)
    main._last_reply_ts["onebot11:group:1"] = time.time()  # 刚回复
    ev = FakeChatEvent(text="直接答", user_id="u2", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.05)
    for key in list(main._pending):
        main._pending[key]["timer"] = None
        await Main._flush_pending(main, key)
    assert not main._waiting.get("onebot11:group:1")
    await asyncio.sleep(0.15)
    assert main.captured, "窗口关闭时消息照常处理"


async def test_drain_waiting_merges_attribution():
    """busy 队列释放：多条排队消息合并为一个聚合条目且发言人归属不串。"""
    main = make_merge_main()
    ev1 = FakeChatEvent(text="排队一", user_id="u2", user_name="甲", at=True)
    ev2 = FakeChatEvent(text="排队二", user_id="u3", user_name="乙", at=True)
    main._waiting["onebot11:group:1"] = [
        (ev1, [{"text": "排队一", "images": [], "sender_id": "u2", "sender_name": "甲"}]),
        (ev2, [{"text": "排队二", "images": [], "sender_id": "u3", "sender_name": "乙"}]),
    ]
    Main._drain_waiting(main, "onebot11:group:1")
    assert not main._waiting.get("onebot11:group:1")
    assert not main._merge_timers.get("onebot11:group:1")
    entry = main._pending["onebot11:group:1"]
    assert len(entry["items"]) == 2
    assert {i["sender_name"] for i in entry["items"]} == {"甲", "乙"}


# ---------- handle_request 类型路由 ----------


def _ctx_with_inbox(entry_account="643319481", entry=None):
    from fakes import FakeMain

    main = FakeMain()
    ctx = make_ctx(main=main, chat_key="snowluma:group:1@643319481")
    ctx.self_id = "643319481"
    main._inbox_load = lambda acct: ([entry] if acct == entry_account else [])
    return ctx, main


def test_route_kwargs_group_invite_from_inbox():
    """群邀请：从收件箱还原 sub_type/group_id，路由到 set_group_add_request。"""
    ctx, _ = _ctx_with_inbox(entry={
        "kind": "request", "request_id": "flag-888", "detail_type": "group",
        "sub_type": "invite", "group_id": "235228131",
    })
    extra = _request_route_kwargs(ctx, "643319481", "flag-888")
    assert extra == {"_request_type": "group", "sub_type": "invite", "group_id": "235228131"}


def test_route_kwargs_friend_request_empty():
    """好友请求：无需类型参数。"""
    ctx, _ = _ctx_with_inbox(entry={
        "kind": "request", "request_id": "flag-1", "detail_type": "private",
        "sub_type": "", "group_id": "",
    })
    extra = _request_route_kwargs(ctx, "643319481", "flag-1")
    assert extra == {}


def test_route_kwargs_explicit_override_and_unknown():
    """AI 显式传参覆盖收件箱；查不到条目但声明了 sub_type 时仍按群路由。"""
    ctx, _ = _ctx_with_inbox(entry_account="643319481", entry={
        "kind": "request", "request_id": "flag-2", "detail_type": "group",
        "sub_type": "add", "group_id": "100",
    })
    extra = _request_route_kwargs(ctx, "643319481", "flag-2", sub_type="invite", group_id="200")
    assert extra == {"_request_type": "group", "sub_type": "invite", "group_id": "200"}
    extra = _request_route_kwargs(ctx, "nobody", "flag-x", sub_type="add")
    assert extra == {"_request_type": "group", "sub_type": "add"}
