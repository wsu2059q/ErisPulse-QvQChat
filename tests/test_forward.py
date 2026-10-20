from types import SimpleNamespace

from QvQChat.conversation.delivery import Delivery, split_paragraphs

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
    cfg = make_config(**{"forward_threshold": 50, "forward_enabled": True, **overrides})
    sdk = FakeSDK()
    sdk.adapter.add("onebot11", FakeSendChain(sends=("MergeForward", "Text")), sends=("MergeForward", "Text"))
    return SimpleNamespace(cfg=cfg, logger=FakeLogger(), sdk=sdk)


def long_text(n):
    return "## 段落\n" + "内容" * n


def tool_trace():
    return [{"tool": "call_module", "arguments": "{}", "output": "installed"}]


def forward_calls(harness, platform="onebot11"):
    chain = harness.sdk.adapter.get(platform).Send
    return [args for name, args, _ in chain.calls if name == "MergeForward"]


async def test_disabled_never_forwards():
    harness = make_harness(forward_enabled=False)
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, long_text(500), tool_trace()) is False
    assert forward_calls(harness) == []


async def test_threshold_zero_irrelevant_for_reply():
    harness = make_harness(forward_threshold=0, forward_enabled=True)
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, long_text(500), tool_trace()) is True


async def test_tool_run_reply_forwards_regardless_of_length():
    harness = make_harness()
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, "很短", tool_trace()) is True
    calls = forward_calls(harness)
    assert calls and len(calls[0][0]) >= 2
    texts = [n["data"]["content"][0]["data"]["text"] for n in calls[0][0]]
    from QvQChat import texts as texts_mod

    assert any(texts_mod.t("forward_process_title") in t for t in texts)
    assert any("call_module" in t for t in texts)


async def test_plain_chat_never_forwards():
    harness = make_harness()
    event = FakeForwardEvent()
    assert await Delivery(harness)._try_forward(event, long_text(30), []) is False
    assert await Delivery(harness)._try_forward(event, long_text(60), []) is False
    assert forward_calls(harness) == []


async def test_platform_without_forward_method_skips():
    harness = make_harness()
    harness.sdk.adapter.add("onebot11", FakeSendChain(), sends=("Text",))
    event = FakeForwardEvent(sends=("Text",))
    assert await Delivery(harness)._try_forward(event, long_text(500), tool_trace()) is False
    assert forward_calls(harness) == []


async def test_any_platform_with_forward_method_works():
    harness = make_harness()
    harness.sdk.adapter.add("yunhu", FakeSendChain(sends=("MergeForward", "Text")), sends=("MergeForward", "Text"))
    event = FakeForwardEvent(platform="yunhu", sends=("MergeForward", "Text"))
    assert await Delivery(harness)._try_forward(event, long_text(500), tool_trace()) is True
    assert forward_calls(harness, "yunhu")


async def test_force_forward_tag_overrides_short_and_disabled():
    harness = make_harness(forward_enabled=False)
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
    harness = SimpleNamespace(cfg=make_config(split_min_length=5, split_delay=0), logger=FakeLogger(), sdk=FakeSDK())
    delivery = Delivery(harness)
    text = "甲段内容长一点。" + "\n\n" + "乙段也长一点。"
    await delivery.deliver_reply(_split_event(sent), text, [], force=None)
    assert len(sent) == 2 and sent[0].startswith("甲段")


async def test_deliver_reply_tool_run_never_splits():
    sent = []
    harness = SimpleNamespace(cfg=make_config(split_min_length=10, forward_enabled=False), logger=FakeLogger(), sdk=FakeSDK())
    delivery = Delivery(harness)
    text = "甲段内容长一点。" + "\n\n" + "乙段也长一点。"
    await delivery.deliver_reply(_split_event(sent), text, [{"tool": "x", "arguments": "", "output": ""}])
    assert len(sent) == 1
