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
    on_delta, on_reset, on_tool_event, on_reasoning = bind(live)

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
    on_delta, on_reset, on_tool_event, on_reasoning = bind(live)

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
    assert snap["reasoning"] == ""
    assert snap["reply"] == "final"
    assert snap["error"] is None
    assert "started" in snap


def test_reset_clears_segments_and_reindexes():
    """回归：reset 后 segments 必须同步清空，且新 delta 从索引 0 重新发布。"""

    reg = LiveRegistry()
    live = reg.start("s")
    queue = asyncio.Queue()
    live.subscribers.add(queue)
    on_delta, on_reset, on_tool_event, on_reasoning = bind(live)

    async def drive():
        await on_delta("旧输出")
        await on_tool_event({"phase": "start", "step_id": "s0", "name": "t", "arguments": "{}"})
        await on_tool_event({"phase": "end", "step_id": "s0", "name": "t", "output": "ok", "ms": 5})
        await on_reset()
        await on_delta("新输出")

    asyncio.run(drive())
    assert live.segments == [{"type": "text", "text": "新输出"}]
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    deltas = [data for kind, data in events if kind == "delta"]
    assert deltas[-1] == {"t": "新输出", "i": 0}
    assert live.snapshot()["segments"] == [{"type": "text", "text": "新输出"}]


def test_bind_publishes_reasoning_events():
    reg = LiveRegistry()
    live = reg.start("s")
    queue = asyncio.Queue()
    live.subscribers.add(queue)
    on_delta, on_reset, on_tool_event, on_reasoning = bind(live)

    async def drive():
        await on_reasoning("思考A")
        await on_reasoning("思考B")

    asyncio.run(drive())
    assert live.reasoning == "思考A思考B"
    assert live.snapshot()["reasoning"] == "思考A思考B"
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    assert [e[0] for e in events] == ["reasoning", "reasoning"]
    assert events[0][1] == {"t": "思考A"}


def test_reset_clears_reasoning():
    reg = LiveRegistry()
    live = reg.start("s")
    on_delta, on_reset, on_tool_event, on_reasoning = bind(live)

    async def drive():
        await on_reasoning("思考")
        await on_reset()

    asyncio.run(drive())
    assert live.reasoning == ""


def test_partial_record_from_steps_and_segments():
    reg = LiveRegistry()
    live = reg.start("s")
    on_delta, on_reset, on_tool_event, on_reasoning = bind(live)

    async def drive():
        await on_delta("第一轮")
        await on_tool_event({"phase": "start", "step_id": "s0", "name": "search", "arguments": '{"q":"x"}'})
        await on_tool_event({"phase": "end", "step_id": "s0", "name": "search", "output": "结果", "ms": 12})
        await on_delta("，继续")
        await on_tool_event({"phase": "start", "step_id": "s1", "name": "calc", "arguments": "{}"})
        await on_delta("被打断的文本")

    asyncio.run(drive())
    text, trace, rounds = live.partial_record()
    assert text == live.text.strip()
    assert trace == [
        {"tool": "search", "arguments": '{"q":"x"}', "output": "结果", "ms": 12},
        {"tool": "calc", "arguments": "{}", "output": "", "ms": 0},
    ]
    assert len(rounds) == 3
    assert rounds[0]["text"] == "第一轮"
    assert rounds[0]["tools"][0]["tool"] == "search"
    assert rounds[0]["tools"][0]["output"] == "结果"
    assert rounds[1]["text"] == "，继续"
    assert rounds[1]["tools"][0]["tool"] == "calc"
    assert rounds[1]["tools"][0]["output"] == ""
    assert rounds[2] == {"text": "被打断的文本", "tools": []}
