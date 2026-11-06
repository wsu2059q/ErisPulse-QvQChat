from types import SimpleNamespace

from QvQChat.agent.toolselect import CORE_TOOLS, ToolSelector, _parse_names

from fakes import FakeLogger, FakeSDK, make_config


def schema(name):
    return {"type": "function", "function": {"name": name, "description": f"{name} desc", "parameters": {}}}


class FakeRunner:
    def __init__(self, reply="[]", fail=False):
        self.pool = SimpleNamespace(sdk=SimpleNamespace(logger=FakeLogger()))
        self.config = make_config()
        self.reply = reply
        self.fail = fail
        self.calls = []

    async def _dispatch(self, kind, request, **kwargs):
        self.calls.append((kind, kwargs))
        if self.fail:
            raise RuntimeError("selector down")
        return SimpleNamespace(content=self.reply)


def make_selector(reply="[]", fail=False, **cfg):
    runner = FakeRunner(reply, fail)
    runner.config = make_config(**cfg)
    return ToolSelector(runner), runner


def test_parse_names_tolerates_fences_and_noise():
    allowed = {"a", "b", "c"}
    assert _parse_names('```json\n["a","b"]\n```', allowed) == ["a", "b"]
    assert _parse_names('Sure: ["a","zzz","a"]', allowed) == ["a"]
    assert _parse_names("no json here", allowed) == []


def test_enabled_modes():
    selector, _ = make_selector(tool_select="auto", tool_select_threshold=5)
    assert selector.enabled(6) is True
    assert selector.enabled(5) is False
    selector_off, _ = make_selector(tool_select="off")
    assert selector_off.enabled(999) is False
    selector_on, _ = make_selector(tool_select="on", tool_select_threshold=999)
    assert selector_on.enabled(1) is True


async def test_select_keeps_core_and_picked():
    selector, runner = make_selector(reply='["web_search"]', tool_select="on")
    schemas = [schema("send_message"), schema("web_search"), schema("run_command"), schema("web_fetch")]
    result = await selector.select("查一下今天新闻", schemas, chat_key="c1")
    names = [s["function"]["name"] for s in result]
    assert "web_search" in names and "send_message" in names
    assert "run_command" not in names
    assert runner.calls and runner.calls[0][0] == "toolselect"


async def test_select_fail_open_on_error():
    selector, _ = make_selector(fail=True, tool_select="on")
    schemas = [schema("a"), schema("b")]
    assert await selector.select("hi", schemas, chat_key="c1") == schemas


async def test_select_fail_open_on_empty_answer():
    selector, _ = make_selector(reply="I cannot help", tool_select="on")
    schemas = [schema("a"), schema("b")]
    assert await selector.select("hi", schemas, chat_key="c1") == schemas


async def test_select_ttl_cache_skips_second_call():
    selector, runner = make_selector(reply='["a"]', tool_select="on", tool_select_ttl=60)
    schemas = [schema("a"), schema("b")]
    await selector.select("hi", schemas, chat_key="c1")
    await selector.select("hi again", schemas, chat_key="c1")
    assert len(runner.calls) == 1


async def test_core_tools_constant():
    assert "send_message" in CORE_TOOLS


def test_apply_always_keeps_eco_tools():
    """动态注入豁免 eco_*：表情包等生态工具不被裁掉（否则模型看不见就永不调用）。"""
    from QvQChat.agent.toolselect import ToolSelector

    schemas = [
        {"type": "function", "function": {"name": n, "description": n}}
        for n in ("send_message", "search_web", "eco_QvQMemes_send_sticker", "tool_a", "tool_b")
    ]
    selected = ToolSelector._apply(schemas, picked=["tool_a"])
    names = {s["function"]["name"] for s in selected}
    assert "eco_QvQMemes_send_sticker" in names  # 没被选中也保留
    assert "tool_b" not in names                 # 未选中的普通工具被裁
