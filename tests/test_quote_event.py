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


def _name_stub(main, responses):
    async def _call(endpoint, **params):
        if endpoint in responses:
            return responses[endpoint]
        return {}

    main.sdk.adapter._adapters["onebot11"] = SimpleNamespace(call_api=_call)


async def test_resolve_session_names_strips_account_and_reads_data():
    """命名任务：复合 id 先 strip_account 再发；昵称从信封 data 层取。"""
    main = make_main()
    calls = []

    async def _call(endpoint, **params):
        calls.append((endpoint, params.get("user_id") or params.get("group_id")))
        if endpoint == "get_stranger_info":
            return {"status": "ok", "retcode": 0, "data": {"nickname": "小白", "user_id": 1}}
        return {}

    main.sdk.adapter._adapters["onebot11"] = SimpleNamespace(call_api=_call)
    sessions = [{
        "chat_key": "onebot11:private:3838648009@643319481",
        "platform": "onebot11", "detail_type": "private",
        "target_id": "3838648009@643319481", "name": "",
    }]
    from QvQChat.conversation.service import strip_account

    assert strip_account("onebot11:private:3838648009@643319481") == "onebot11:private:3838648009"
    await main.sessions.resolve_session_names(sessions)
    assert calls and calls[0][1] == "3838648009", calls  # 复合后缀已剥离
    assert sessions[0]["name"] == "小白" or main.sessions._state(
        "onebot11:private:3838648009@643319481").get("user_name") == "小白"


async def test_group_name_reads_envelope_data():
    """群名解析兼容信封：group_name 在 data 层也能取到（走真实 _resolve_group_name）。"""
    from QvQChat.chat.inbox import InboxMixin

    main = make_main()
    _name_stub(main, {"get_group_info": {"status": "ok", "data": {"group_name": "测试群"}}})
    info = await main.sdk.adapter.get("onebot11").call_api("get_group_info", group_id="1")
    data = info.get("data") if isinstance(info.get("data"), dict) else info
    assert data.get("group_name") == "测试群"
    ev = FakeChatEvent(text="x", group=True, group_id="1")
    name = await InboxMixin._resolve_group_name(main, ev, "onebot11:group:1", "1")
    assert name == "测试群"
