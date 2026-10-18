import asyncio

from QvQChat.dashboard.live import LiveRegistry, bind


def test_registry_start_busy_and_replace():
    reg = LiveRegistry()
    assert reg.get("s1") is None
    assert not reg.busy("s1")
    live = reg.start("s1")
    assert reg.busy("s1")
    live.status = "done"
    assert not reg.busy("s1")
    # 重新发起覆盖旧记录
    live2 = reg.start("s1")
    assert live2 is not live
    assert reg.get("s1") is live2


def test_bind_writes_text_and_steps_and_publishes():
    reg = LiveRegistry()
    live = reg.start("s1")
    import asyncio

    queue = asyncio.Queue()
    live.subscribers.add(queue)
    on_delta, on_reset, on_tool_event = bind(live)

    async def drive():
        await on_delta("你好")
        await on_tool_event({"phase": "start", "step_id": "s0", "name": "t", "arguments": "{}"})
        await on_tool_event({"phase": "end", "step_id": "s0", "name": "t", "output": "ok", "ms": 5})
        await on_reset()
        await on_delta("重试")

    asyncio.run(drive())
    assert live.text == "重试"
    assert live.steps == []
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    kinds = [e[0] for e in events]
    assert kinds == ["delta", "tool", "tool", "reset", "delta"]


def test_bind_end_matches_step_id():
    reg = LiveRegistry()
    live = reg.start("s")
    on_delta, on_reset, on_tool_event = bind(live)

    async def drive():
        await on_tool_event({"phase": "start", "step_id": "a", "name": "x", "arguments": ""})
        await on_tool_event({"phase": "start", "step_id": "b", "name": "y", "arguments": ""})
        await on_tool_event({"phase": "end", "step_id": "a", "name": "x", "output": "", "ms": 1})

    asyncio.run(drive())
    assert live.steps[0]["end"]["step_id"] == "a"
    assert "end" not in live.steps[1]


def test_snapshot_shape():
    reg = LiveRegistry()
    live = reg.start("s")
    live.text = "abc"
    live.reply = "final"
    live.status = "done"
    snap = live.snapshot()
    assert snap["session"] == "s"
    assert snap["status"] == "done"
    assert snap["text"] == "abc"
    assert snap["reply"] == "final"
    assert snap["error"] is None
    assert "started" in snap
