from types import SimpleNamespace

from QvQChat.conversation.delivery import Delivery, split_paragraphs
from QvQChat.conversation.rhythm import structure_signals

from fakes import FakeLogger, FakeSendChain, FakeSDK, make_config


class FakeForwardEvent:
    def __init__(self, platform="onebot11", sends=("MergeForward", "Text")):
        self._platform = platform
        self._sends = list(sends)

    def get_platform(self):
        return self._platform

    def is_group_message(self):
        return False

    def get_user_id(self):
        return "12345"

    def get_group_id(self):
        return "67890"


def make_harness(**overrides):
    cfg = make_config(**{"forward_threshold": 50, **overrides})
    sdk = FakeSDK()
    sdk.adapter.add("onebot11", FakeSendChain(sends=("MergeForward", "Text")), sends=("MergeForward", "Text"))
    return SimpleNamespace(cfg=cfg, logger=FakeLogger(), sdk=sdk)


def long_text(n):
    return "## 段落\n" + "内容" * n


def tool_trace():
    return [{"tool": "call_module", "arguments": "{}", "output": "installed", "ms": 5}]


def rounds_multi_replies():
    return [
        {"text": "", "tools": tool_trace()},
        {"text": "先说中间发现", "tools": []},
        {"text": "补充一个关键细节", "tools": []},
        {"text": "综上是结论", "tools": []},
    ]


def forward_calls(harness, platform="onebot11"):
    chain = harness.sdk.adapter.get(platform).Send
    return [args for name, args, _ in chain.calls if name == "MergeForward"]


async def test_tool_run_with_multiple_replies_merges():
    harness = make_harness()
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, "综上是结论", tool_trace(), rounds=rounds_multi_replies()) is True
    calls = forward_calls(harness)
    assert calls and len(calls[0][0]) >= 3
    texts = [n["data"]["content"][0]["data"]["text"] for n in calls[0][0]]
    assert any("call_module" in t for t in texts)
    assert any("installed" in t for t in texts)
    assert any("综上是结论" in t for t in texts)


async def test_single_reply_stays_plain_even_with_tools():
    harness = make_harness()
    event = FakeForwardEvent()
    rounds = [{"text": "一个简短的结论", "tools": []}]
    assert await Delivery(harness)._try_forward(event, "一个简短的结论", tool_trace(), rounds=rounds) is False
    assert forward_calls(harness) == []


async def test_consecutive_tools_merge_into_one_node():
    harness = make_harness(forward_min_messages=1)
    event = FakeForwardEvent()
    tools = [
        {"tool": "call_module", "arguments": "{}", "output": "installed", "ms": 5},
        {"tool": "call_module", "arguments": '{"x": 1}', "output": "ok", "ms": 6},
    ]
    rounds = [
        {"text": "", "tools": tools},
        {"text": "完成", "tools": []},
    ]
    assert await Delivery(harness)._try_forward(event, "完成", tools, rounds=rounds) is True
    calls = forward_calls(harness)
    assert calls and len(calls[0][0]) == 2
    tool_node = calls[0][0][0]["data"]["content"][0]["data"]["text"]
    assert tool_node.count("call_module") == 2
    reply_node = calls[0][0][1]["data"]["content"][0]["data"]["text"]
    assert reply_node == "完成"


async def test_tool_and_message_alternate_stay_separate():
    harness = make_harness(forward_min_messages=1)
    event = FakeForwardEvent()
    rounds = [
        {"text": "", "tools": [{"tool": "read_file", "arguments": "{}", "output": "a", "ms": 1}]},
        {"text": "中间说明", "tools": []},
        {"text": "", "tools": [{"tool": "list_dir", "arguments": "{}", "output": "b", "ms": 1}]},
        {"text": "最终结论", "tools": []},
    ]
    trace = [entry for r in rounds for entry in r["tools"]]
    assert await Delivery(harness)._try_forward(event, "最终结论", trace, rounds=rounds) is True
    calls = forward_calls(harness)
    texts = [n["data"]["content"][0]["data"]["text"] for n in calls[0][0]]
    assert len(texts) == 4
    assert "中间说明" in texts[1]
    assert "read_file" in texts[0] and "list_dir" in texts[2]


async def test_platform_blocklist_never_forwards():
    harness = make_harness(no_forward_platforms=["onebot11"])
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, "综上", tool_trace(), rounds=rounds_multi_replies()) is False
    assert forward_calls(harness) == []


async def test_platform_allowlist_gates():
    harness = make_harness(forward_platforms=["yunhu"])
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, "综上", tool_trace(), rounds=rounds_multi_replies()) is False
    harness.sdk.adapter.add("yunhu", FakeSendChain(sends=("MergeForward", "Text")), sends=("MergeForward", "Text"))
    event2 = FakeForwardEvent(platform="yunhu", sends=("MergeForward", "Text"))
    assert await Delivery(harness)._try_forward(event2, "综上", tool_trace(), rounds=rounds_multi_replies()) is True


async def test_platform_without_forward_method_skips():
    harness = make_harness()
    harness.sdk.adapter.add("onebot11", FakeSendChain(), sends=("Text",))
    event = FakeForwardEvent(sends=("Text",))
    assert await Delivery(harness)._try_forward(event, long_text(500), tool_trace(), rounds=rounds_multi_replies()) is False
    assert forward_calls(harness) == []


async def test_any_platform_with_forward_method_works():
    harness = make_harness()
    harness.sdk.adapter.add("yunhu", FakeSendChain(sends=("MergeForward", "Text")), sends=("MergeForward", "Text"))
    event = FakeForwardEvent(platform="yunhu", sends=("MergeForward", "Text"))
    assert await Delivery(harness)._try_forward(event, "综上", tool_trace(), rounds=rounds_multi_replies()) is True
    assert forward_calls(harness, "yunhu")


async def test_force_forward_tag_overrides_disabled():
    harness = make_harness(forward_platforms=[])
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, "短回复", [], force=True) is True
    calls = forward_calls(harness)
    assert calls and calls[0][0][-1]["data"]["content"][0]["data"]["text"].endswith("短回复")


async def test_force_plain_blocks_forward():
    harness = make_harness()
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, long_text(500), tool_trace(), force=False) is False
    assert forward_calls(harness) == []


async def test_force_forward_still_needs_forward_method():
    harness = make_harness()
    harness.sdk.adapter.add("yunhu", FakeSendChain(), sends=("Text",))
    event = FakeForwardEvent(platform="yunhu", sends=("Text",))
    assert await Delivery(harness)._try_forward(event, "短", [], force=True) is False


def test_split_paragraphs():
    text = "第一段内容足够长一些一些一些一些。\n\n第二段也很长很长很长很长很长。\n\n第三段收尾。"
    parts = split_paragraphs(text, min_length=10)
    assert len(parts) == 3
    assert split_paragraphs("只有一段", min_length=10) == []


def _split_event(sent):
    class FakeEvent:
        def get_platform(self):
            return "onebot11"

        def is_group_message(self):
            return False

        def get_user_id(self):
            return "1"

        def get_group_id(self):
            return ""

        def supports(self, method):
            return method == "Text"

        async def reply(self, content, method="Text"):
            sent.append(content)

    return FakeEvent()


async def test_deliver_reply_splits_plain_chat():
    sent = []
    harness = make_harness(split_min_length=5, split_delay=0)
    delivery = Delivery(harness)
    text = "甲段内容长一点。" + "\n\n" + "乙段也长一点。"
    await delivery.deliver_reply(_split_event(sent), text, [], force=None)
    assert len(sent) == 2 and sent[0].startswith("甲段")


async def test_deliver_reply_merged_run_sends_nothing_plain():
    sent = []
    harness = make_harness()
    delivery = Delivery(harness)
    await delivery.deliver_reply(_split_event(sent), "综上", tool_trace(), rounds=rounds_multi_replies())
    assert sent == []


async def test_structure_aware_forwards_structured_report():
    harness = make_harness(forward_structure_aware=True)
    event = FakeForwardEvent()
    reply = "## 适配清单\n\n```py\nprint(1)\n```\n\n综上如下。"
    rounds = [{"text": reply, "tools": []}]
# 无工具轮次，但结构化占比高 → 仍走合并转发
    assert await Delivery(harness)._try_forward(event, reply, [], rounds=rounds) is True
    assert forward_calls(harness)


async def test_structure_aware_sends_pure_chatter_direct():
    harness = make_harness(forward_structure_aware=True)
    event = FakeForwardEvent()
    rounds = [
        {"text": "哈哈好呀", "tools": tool_trace()},
        {"text": "那就这样", "tools": []},
        {"text": "晚点聊", "tools": []},
    ]
# 段数达到 min 但纯寒暄无结构 → 直发（旧行为会合并转发）
    assert await Delivery(harness)._try_forward(event, "晚点聊", tool_trace(), rounds=rounds) is False
    assert forward_calls(harness) == []


async def test_structure_aware_multi_part_with_code_still_forwards():
    harness = make_harness(forward_structure_aware=True)
    event = FakeForwardEvent()
    chatter = [
        "今天聊聊天气，有点冷。",
        "最近也没什么特别的事情。",
        "就这样吧，闲聊而已。",
        "再补一句凑数的话。",
        "还有一句没营养的。",
    ]
    reply = "\n".join(chatter[:2]) + "\n```\nok\n```\n" + "\n".join(chatter[2:])
    rounds = [
        {"text": chatter[0], "tools": []},
        {"text": "```\nok\n```", "tools": []},
        {"text": "\n".join(chatter[1:]), "tools": []},
    ]
    sig = structure_signals(rounds, reply)
# 结构占比低于阈值，但段数达标且含代码块 → 仍转发
    assert sig["score"] < 0.4 and sig["has_code"] is True
    assert await Delivery(harness)._try_forward(event, reply, [], rounds=rounds) is True
    assert forward_calls(harness)


async def test_force_tags_keep_priority_over_structure_awareness():
    harness = make_harness(forward_structure_aware=True)
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, "短回复", [], force=True) is True
    assert await Delivery(harness)._try_forward(event, "```py\nx=1\n```", [], force=False, rounds=[{"text": "x", "tools": []}]) is False


async def test_forward_nodes_use_persona_nickname():
    """会话人格配置 nickname → 转发节点显示人格昵称而非机器人自身昵称。"""
    harness = make_harness()
    harness.personas = SimpleNamespace(
        resolve=lambda chat_key: {"id": "p1", "nickname": "阿波"}
    )
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, "综上", tool_trace(), rounds=rounds_multi_replies()) is True
    calls = forward_calls(harness)
    assert calls
    nicknames = {n["data"]["nickname"] for n in calls[0][0]}
    assert nicknames == {"阿波"}

# 未配置 nickname → 回落机器人自身昵称（原行为）
    harness2 = make_harness()
    event2 = FakeForwardEvent()
    assert await Delivery(harness2)._try_forward(event2, "综上", tool_trace(), rounds=rounds_multi_replies()) is True
    calls2 = forward_calls(harness2)
    nicknames2 = {n["data"]["nickname"] for n in calls2[0][0]}
    assert "阿波" not in nicknames2
