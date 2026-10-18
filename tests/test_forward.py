from types import SimpleNamespace

from QvQChat.Main import Main

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


def forward_calls(harness, platform="onebot11"):
    chain = harness.sdk.adapter.get(platform).Send
    return [args for name, args, _ in chain.calls if name == "MergeForward"]


async def test_disabled_never_forwards():
    harness = make_harness(forward_enabled=False)
    event = FakeForwardEvent()
    assert await Main._try_forward(harness, event, long_text(500), [{"tool": "x", "arguments": "", "output": ""}]) is False
    assert forward_calls(harness) == []


async def test_threshold_zero_disables():
    harness = make_harness(forward_threshold=0)
    event = FakeForwardEvent()
    assert await Main._try_forward(harness, event, long_text(500), []) is False


async def test_task_reply_forwards_at_threshold_with_trace():
    harness = make_harness()
    event = FakeForwardEvent()
    trace = [{"tool": "call_module", "arguments": "{}", "output": "installed"}]
    assert await Main._try_forward(harness, event, long_text(40), trace) is True
    calls = forward_calls(harness)
    assert calls and len(calls[0][0]) >= 2
    texts = [n["data"]["content"][0]["data"]["text"] for n in calls[0][0]]
    from QvQChat import texts as texts_mod

    assert any(texts_mod.t("forward_process_title") in t for t in texts)
    assert any("call_module" in t for t in texts)


async def test_task_reply_short_stays_normal():
    harness = make_harness()
    event = FakeForwardEvent()
    assert await Main._try_forward(harness, event, "很短", [{"tool": "ping", "arguments": "", "output": "pong"}]) is False
    assert forward_calls(harness) == []


async def test_plain_chat_needs_double_threshold():
    harness = make_harness()
    event = FakeForwardEvent()
    assert await Main._try_forward(harness, event, long_text(30), []) is False
    assert forward_calls(harness) == []
    assert await Main._try_forward(harness, event, long_text(60), []) is True
    assert forward_calls(harness)


async def test_platform_without_forward_method_skips():
    harness = make_harness()
    harness.sdk.adapter.add("onebot11", FakeSendChain(), sends=("Text",))
    event = FakeForwardEvent(sends=("Text",))
    assert await Main._try_forward(harness, event, long_text(500), []) is False
    assert forward_calls(harness) == []


async def test_any_platform_with_forward_method_works():
    """转发能力跟随适配器的 Forward 方法（list_sends 探测），不再限定平台白名单。"""
    harness = make_harness()
    harness.sdk.adapter.add("yunhu", FakeSendChain(sends=("MergeForward", "Text")), sends=("MergeForward", "Text"))
    event = FakeForwardEvent(platform="yunhu", sends=("MergeForward", "Text"))
    assert await Main._try_forward(harness, event, long_text(500), []) is True
    assert forward_calls(harness, "yunhu")


async def test_force_forward_tag_overrides_short_and_disabled():
    harness = make_harness(forward_enabled=False)
    event = FakeForwardEvent()
    assert await Main._try_forward(harness, event, "短回复", [], force=True) is True
    calls = forward_calls(harness)
    assert calls and calls[0][0][-1]["data"]["content"][0]["data"]["text"].endswith("短回复")


async def test_force_plain_blocks_forward():
    harness = make_harness()
    event = FakeForwardEvent()
    assert await Main._try_forward(harness, event, long_text(500), [{"tool": "x", "arguments": "", "output": ""}], force=False) is False
    assert forward_calls(harness) == []


async def test_force_forward_still_needs_forward_method():
    harness = make_harness()
    harness.sdk.adapter.add("yunhu", FakeSendChain(), sends=("Text",))
    event = FakeForwardEvent(platform="yunhu", sends=("Text",))
    assert await Main._try_forward(harness, event, "短", [], force=True) is False
