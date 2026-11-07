"""引用原文拉取（get_msg 回退）与 get_current_event 内置工具。"""

import asyncio
from types import SimpleNamespace

from QvQChat.Main import Main
from QvQChat.tools_builtin.erispulse import get_current_event

from fakes import FakeChatEvent, FakeMain, make_ctx


def make_main():
    from test_aggregate import make_main as base

    return base(aggregate_window=0.01)


class ReplyEvent(FakeChatEvent):
    """带 reply 段的事件（多数适配器形态：reply 段只有 id，无内联文本）。"""

    def __init__(self, *a, quoted_id="M-OLD", inline="", **kw):
        super().__init__(*a, **kw)
        self._quoted_id = quoted_id
        self._inline = inline

    def get_message(self):
        segs = [{"type": "reply", "data": {"id": self._quoted_id}}]
        if self._inline:
            segs[0]["data"]["text"] = self._inline
        segs.append({"type": "text", "data": {"text": self._text}})
        return segs


def _with_get_msg(main, payload):
    async def _call(endpoint, **params):
        if endpoint == "get_msg":
            return payload
        return {}

    main.sdk.adapter._adapters["onebot11"] = SimpleNamespace(call_api=_call)


async def test_quote_inline_text_used_directly():
    main = make_main()
    ev = ReplyEvent(text="那现在呢", inline="我说 OW1 自研引擎加服务端仅一处", at=True)
    text = await Main._quote_content(main, ev)
    assert "OW1 自研引擎" in text


async def test_quote_fetched_via_get_msg():
    main = make_main()
    _with_get_msg(main, {
        "message": [{"type": "text", "data": {"text": "这事我只听过半截喵"}}],
        "sender": {"nickname": "小Iris"},
    })
    ev = ReplyEvent(text="那现在呢", quoted_id="M-OLD", at=True)
    text = await Main._quote_content(main, ev)
    assert "小Iris" in text and "半截" in text


async def test_quote_fetch_failure_returns_empty():
    main = make_main()
    ev = ReplyEvent(text="那现在呢", quoted_id="M-OLD", at=True)
    text = await Main._quote_content(main, ev)
    assert text == ""  # 无适配器可拉：回退空（scene_quote_note 兜底）


async def test_scene_includes_quote_content():
    main = make_main()
    _with_get_msg(main, {
        "message": [{"type": "text", "data": {"text": "引用原文内容XYZ"}}],
        "sender": {"nickname": "路人"},
    })
    ev = ReplyEvent(text="那这个呢", quoted_id="M-OLD", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.3)
    system = main.captured[0]["system"] if main.captured else ""
    assert "引用原文内容XYZ" in system


def test_get_current_event_returns_segments():
    main = make_main()
    ev = ReplyEvent(text="那现在呢", quoted_id="M-OLD", at=True)
    ctx = make_ctx(main, event=ev)
    out = asyncio.run(get_current_event(ctx))
    assert "M-OLD" in out and "那现在呢" in out and "reply" in out


def test_get_current_event_without_event():
    main = make_main()
    ctx = make_ctx(main, event=None)
    out = asyncio.run(get_current_event(ctx))
    assert out  # 返回提示文本而非报错
