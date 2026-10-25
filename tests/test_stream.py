import asyncio
import json
from types import SimpleNamespace

import pytest

from QvQChat.engine.base import ChatRequest
from QvQChat.engine.openai import OpenAIEngine, _ThinkDeltaFilter


def _delta(content=None, tool_calls=None, reasoning=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls, reasoning_content=reasoning)


def _chunk(delta=None, usage=None, model="m1", finish=None):
    choice = SimpleNamespace(delta=delta, finish_reason=finish)
    return SimpleNamespace(choices=[choice], usage=usage, model=model)


def _tool_delta(index, id=None, name=None, arguments=None):
    fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, function=fn)


class FakeStream:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        self._iter = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        pass


class FakeCompletions:
    def __init__(self, chunks):
        self._chunks = chunks
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(self._chunks)


class FakeCompletionsFail:
    def __init__(self, status_error):
        self.calls = []
        self._error = status_error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        raise self._error


class _FakeHttpResponse:
    def __init__(self, status):
        self.status_code = status
        self.headers = {}
        self.request = SimpleNamespace(method="POST", url="https://x/v1/chat/completions")
        self.is_closed = True
        self.is_stream_consumed = True


def _status_error(status):
    from openai import APIStatusError

    return APIStatusError("err", response=_FakeHttpResponse(status), body=None)


def _engine_with(chunks):
    engine = OpenAIEngine()
    completions = FakeCompletions(chunks)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    engine._clients[("", "")] = client
    return engine, completions


def test_think_filter_suppresses_block():
    flt = _ThinkDeltaFilter()
    assert flt.feed("你好<think>") == "你好"
    assert flt.feed("secret stuff") == ""
    assert flt.feed("</think>世界") == "世界"


def test_think_filter_split_tags():
    flt = _ThinkDeltaFilter()
    out = flt.feed("abc<th")
    out += flt.feed("ink>x</thi")
    out += flt.feed("nk>def")
    assert out == "abcdef"


@pytest.mark.asyncio
async def test_stream_chat_emits_deltas_and_tools():
    chunks = [
        _chunk(delta=_delta(content="你好")),
        _chunk(delta=_delta(content="<think>内部</think>！")),
        _chunk(
            delta=_delta(
                tool_calls=[
                    _tool_delta(0, id="call_1", name="list_dir"),
                    _tool_delta(1, id="call_2", name="run_command"),
                ]
            )
        ),
        _chunk(delta=_delta(tool_calls=[_tool_delta(0, arguments='{"path"'), _tool_delta(1, arguments='{"cmd"')]))
,
        _chunk(delta=_delta(tool_calls=[_tool_delta(0, arguments=': "/app"}'), _tool_delta(1, arguments=': "ls"}')])),
        _chunk(delta=_delta(), usage=SimpleNamespace(prompt_tokens=3, completion_tokens=5, total_tokens=8), finish="tool_calls"),
    ]
    engine, completions = _engine_with(chunks)
    deltas = []
    resp = await engine.chat(
        "", "", ChatRequest(messages=[{"role": "user", "content": "hi"}], model="m"),
        on_delta=deltas.append,
    )
    assert deltas == ["你好", "！"]
    assert resp.content == "你好！"
    assert [tc.name for tc in resp.tool_calls] == ["list_dir", "run_command"]
    assert resp.tool_calls[0].arguments == {"path": "/app"}
    assert resp.tool_calls[1].arguments == {"cmd": "ls"}
    assert resp.usage["total_tokens"] == 8
    assert completions.calls[0]["stream"] is True
    assert completions.calls[0]["stream_options"] == {"include_usage": True}


@pytest.mark.asyncio
async def test_stream_drops_stream_options_on_400():
    error = _status_error(400)

    engine = OpenAIEngine()
    completions = FakeCompletionsFail(error)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    engine._clients[("", "")] = client

    async def ok_create(**kwargs):
        if "stream_options" in kwargs:
            raise error
        return FakeStream([_chunk(delta=_delta(content="ok"), finish="stop")])

    completions.create = ok_create
    deltas = []
    resp = await engine.chat(
        "", "", ChatRequest(messages=[{"role": "user", "content": "hi"}], model="m"),
        on_delta=deltas.append,
    )
    assert resp.content == "ok"
    assert deltas == ["ok"]


@pytest.mark.asyncio
async def test_stream_reset_callback_invoked_on_image_fallback():
    error = _status_error(415)

    async def create(**kwargs):
        if any(isinstance(p, list) for m in kwargs["messages"] if isinstance(m.get("content"), list) for p in [m["content"]]) and kwargs.get("messages", [{}])[0].get("content") and isinstance(kwargs["messages"][0]["content"], list):
            raise error
        return FakeStream([_chunk(delta=_delta(content="ok"), finish="stop")])

    engine = OpenAIEngine()
    completions = SimpleNamespace(create=create)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    engine._clients[("", "")] = client

    resets = []
    deltas = []
    resp = await engine.chat(
        "", "",
        ChatRequest(
            messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,x"}}, {"type": "text", "text": "hi"}]}],
            model="m",
        ),
        on_delta=deltas.append,
        on_reset=lambda: resets.append(1),
    )
    assert resp.content == "ok"
    assert resets == [1]
    assert deltas == ["ok"]


@pytest.mark.asyncio
async def test_pool_passes_stream_callbacks():
    from QvQChat.engine.pool import ModelPool

    captured = {}

    class Pool(ModelPool):
        async def chat(self, request, on_delta=None, on_reset=None):
            captured["on_delta"] = on_delta
            captured["on_reset"] = on_reset
            return await super().chat(request, on_delta=on_delta, on_reset=on_reset)

    class FakeSdkStorage:
        def get(self, key, default=None):
            return default

        def set(self, key, value):
            pass

    pool = ModelPool.__new__(ModelPool)
    pool.engine = OpenAIEngine()
    pool.sdk = SimpleNamespace(storage=FakeSdkStorage())
    pool.config = SimpleNamespace(default_model="", model_failover=False, temperature=0.7, max_tokens=64)
    pool.providers = [
        {
            "id": "p1",
            "name": "P1",
            "base_url": "",
            "api_key": "",
            "models": [{"id": "m", "enabled": True}],
        }
    ]
    pool.list_providers = lambda: pool.providers
    pool.list_models = lambda: [
        {"id": "p1:m", "provider": "p1", "provider_name": "P1", "base_url": "", "api_key": "",
         "model": "m", "temperature": None, "max_tokens": None}
    ]

    completions = FakeCompletions([_chunk(delta=_delta(content="hi"), finish="stop")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    pool.engine._clients[("", "")] = client

    deltas = []
    resp = await pool.chat(
        ChatRequest(messages=[{"role": "user", "content": "x"}], model="p1:m"),
        on_delta=deltas.append,
        on_reset=lambda: None,
    )
    assert resp.content == "hi"
    assert deltas == ["hi"]


def test_think_filter_keeps_reasoning_and_flushes_unclosed():
    flt = _ThinkDeltaFilter()
    assert flt.feed("<think>很长") == ""
    assert flt.take_reasoning() == ""
    assert flt.feed("的思考内容，尚未闭合") == ""
    assert flt.take_reasoning() != ""
    leftover = flt.flush()
    assert leftover == ""
    reasoning = flt.take_reasoning()
    assert reasoning# 未闭合的思考不再被丢弃
    assert "的思考内容" in reasoning or "尚未闭合" in reasoning


def test_think_filter_reasoning_complete_when_closed():
    flt = _ThinkDeltaFilter()
    out = flt.feed("<think>秘密</think>正文")
    assert out == "正文"
    assert flt.take_reasoning() == "秘密"
    assert flt.take_reasoning() == ""


@pytest.mark.asyncio
async def test_stream_chat_forwards_reasoning_content_deltas():
    chunks = [
        _chunk(delta=_delta(content="答案", reasoning="推理过程")),
        _chunk(delta=_delta(reasoning="继续推理")),
    ]
    engine, _ = _engine_with(chunks)
    deltas, reasonings = [], []

    resp = await engine.chat(
        "",
        "",
        ChatRequest(messages=[{"role": "user", "content": "q"}], model="m1"),
        on_delta=deltas.append,
        on_reasoning=reasonings.append,
    )
    assert resp.content == "答案"
    assert deltas == ["答案"]
    assert "".join(reasonings) == "推理过程继续推理"


@pytest.mark.asyncio
async def test_stream_chat_flushes_unclosed_think_to_reasoning():
    chunks = [
        _chunk(delta=_delta(content="<think>思考中")),
        _chunk(delta=_delta(content="，继续思考"), finish="stop"),
    ]
    engine, _ = _engine_with(chunks)
    deltas, reasonings = [], []

    resp = await engine.chat(
        "",
        "",
        ChatRequest(messages=[{"role": "user", "content": "q"}], model="m1"),
        on_delta=deltas.append,
        on_reasoning=reasonings.append,
    )
    assert resp.content is None# 正文为空但思考完整可见
    assert deltas == []
    assert "".join(reasonings) == "思考中，继续思考"
