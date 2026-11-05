import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from openai import APIStatusError, AuthenticationError, RateLimitError

from QvQChat.Main import Main, tool_allowed
from QvQChat.agent.runner import AgentRunner
from QvQChat.agent.tools import Tool, ToolRegistry
from QvQChat.dashboard.manager import DashboardManager
from QvQChat.engine.base import ChatRequest, ChatResponse, ToolCall
from QvQChat.engine.openai import OpenAIEngine
from QvQChat.conversation.service import ConversationService

from fakes import FakeMain, make_config, make_ctx


def make_harness(**overrides):
    return SimpleNamespace(cfg=make_config(**overrides), logger=FakeMain().logger, _chat_locks={})


def test_lock_same_key_same_object():
    harness = make_harness()
    lock_a = Main._lock_for(harness, "chat1")
    assert Main._lock_for(harness, "chat1") is lock_a
    assert Main._lock_for(harness, "chat2") is not lock_a


async def test_sensitive_read_denied_for_non_admin(tmp_path):
    from QvQChat.tools_builtin import computer

    inside = tmp_path / "w"
    inside.mkdir()
    (inside / "config.toml").write_text("token = 'secret'", encoding="utf-8")
    ctx = make_ctx(work_dirs=[str(inside)])
    out = await computer.read_file(ctx, str(inside / "config.toml"))
    assert "secret" not in out

    admin_ctx = make_ctx(admins=["1"], work_dirs=[str(inside)])
    out = await computer.read_file(admin_ctx, str(inside / "config.toml"))
    assert "secret" in out


def test_engine_retry_on_5xx_then_success():
    engine = OpenAIEngine()
    engine.retry_delays = (0, 0)

    class FakeStatusErr(APIStatusError):
        def __init__(self, status):
            self.status_code = status
            self.message = "err"

    ok_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None), finish_reason="stop")],
        usage=None,
        model="m",
    )

    class FakeCompletions:
        def __init__(self, responses):
            self._responses = list(responses)
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            item = self._responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

    flaky = FakeCompletions([FakeStatusErr(500), FakeStatusErr(503), ok_resp])
    engine._clients[("", "")] = SimpleNamespace(chat=SimpleNamespace(completions=flaky))

    resp = asyncio.run(engine.chat("", "", ChatRequest(messages=[{"role": "user", "content": "hi"}])))
    assert resp.content == "ok" and flaky.calls == 3


def test_engine_auth_error_no_retry():
    engine = OpenAIEngine()
    engine.retry_delays = (0, 0)

    class FakeAuthErr(AuthenticationError):
        def __init__(self):
            self.message = "bad key"

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            raise FakeAuthErr()

    flaky = FakeCompletions()
    engine._clients[("", "")] = SimpleNamespace(chat=SimpleNamespace(completions=flaky))

    from QvQChat.engine.base import EngineError

    try:
        asyncio.run(engine.chat("", "", ChatRequest(messages=[{"role": "user", "content": "hi"}])))
        raise AssertionError("should raise")
    except EngineError:
        pass
    assert flaky.calls == 1


def test_rate_limit_retries():
    engine = OpenAIEngine()
    engine.retry_delays = (0, 0)

    class FakeRateErr(RateLimitError):
        def __init__(self):
            self.message = "rate"

    ok_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None), finish_reason="stop")],
        usage=None,
        model="m",
    )

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise FakeRateErr()
            return ok_resp

    flaky = FakeCompletions()
    engine._clients[("", "")] = SimpleNamespace(chat=SimpleNamespace(completions=flaky))

    resp = asyncio.run(engine.chat("", "", ChatRequest(messages=[{"role": "user", "content": "hi"}])))
    assert resp.content == "ok" and flaky.calls == 2


async def test_context_summarize_on_overflow():
    main = FakeMain()
    manager = ConversationService(main)
    key = "test:private:sum"

    class SumPool:
        async def chat(self, request):
            return type("R", (), {"content": "- 决定用方案A", "usage": {}})()

    main.pool = SumPool()
    for i in range(6):
        manager.append(key, "user", f"旧消息{i}")
    removed = manager.trim_overflow(key, keep=2)
    assert len(removed) == 4
# 收尾摘要：经 compactor.summarize_entries 写入会话摘要
    await manager._summarize_overflow(key, removed)
    assert "方案A" in manager.summary_of(key)

async def test_runner_tool_round_callback():
    main = FakeMain()
    registry = ToolRegistry()

    async def echo(ctx, **kwargs):
        return "done"

    registry.register(Tool(
        name="echo",
        description="t",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=echo,
    ))
    rounds = []

    class Pool:
        def __init__(self):
            self.n = 0

        async def chat(self, request, **kwargs):
            self.n += 1
            if self.n == 1:
                return ChatResponse(
                    content="",
                    tool_calls=[ToolCall(call_id="c1", name="echo", arguments={"text": "hi"})],
                )
            return ChatResponse(content="完成")

    runner = AgentRunner(Pool(), registry, main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(
        system="s",
        messages=[{"role": "user", "content": "hi"}],
        ctx=ctx,
        on_tool_round=lambda calls: rounds.append(calls),
    )
    assert result.text == "完成"
    assert rounds == [[{"name": "echo", "arguments": '{"text": "hi"}'}]]


async def test_runner_injects_tool_image_to_model():
    main = FakeMain()
    registry = ToolRegistry()
    seen_messages = []

    async def draw(ctx, **kwargs):
        return json.dumps({"image_path": "/tmp/pic.png"})

    registry.register(Tool(
        name="draw",
        description="t",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=draw,
    ))

    class Pool:
        def __init__(self):
            self.n = 0

        async def chat(self, request, **kwargs):
            self.n += 1
            seen_messages.append(list(request.messages))
            if self.n == 1:
                return ChatResponse(
                    content="",
                    tool_calls=[ToolCall(call_id="c1", name="draw", arguments={})],
                )
            return ChatResponse(content="看到图了")

    runner = AgentRunner(Pool(), registry, main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(
        system="s",
        messages=[{"role": "user", "content": "画图"}],
        ctx=ctx,
    )
    assert result.text == "看到图了"
    followup = seen_messages[1]
    image_msgs = [m for m in followup if m.get("role") == "user" and isinstance(m.get("content"), list)]
    assert image_msgs and any(
        part.get("type") == "image_url" and part["image_url"]["url"] == "/tmp/pic.png"
        for part in image_msgs[0]["content"]
    )


def test_recap_regex_matches_yi_xiang():
    main = FakeMain()
    trace = [{"tool": "send_message", "arguments": "{}", "output": "ok"}]
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("已向群里说明情况：安装命令被拦截。", trace) is True
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("已发送配置说明。", trace) is True
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("这不是复述，是正经回答。", trace) is False


def test_export_import_roundtrip():
    main = FakeMain()
    manager = DashboardManager(main)
    main.pool.save_provider({"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "api_key": "k", "models": [{"id": "deepseek-chat", "enabled": True}]})
    main.personas.save({"id": "custom1", "name": "n", "system": "s"})
    manager.main.memory.remember("c1", "记住我")

    data = asyncio.run(manager.export_data(None))
    assert data["providers"] and data["memory"].get("c1")

    main2 = FakeMain()
    manager2 = DashboardManager(main2)

    class R:
        def __init__(self, d):
            self._d = d

        async def json(self):
            return self._d

    payload = {"data": {"providers": data["providers"], "personas": data["personas"], "memory": data["memory"]}}
    result = asyncio.run(manager2.import_data(R(payload)))
    assert set(["providers", "personas", "memory"]).issubset(set(result["applied"]))
    assert main2.pool.list_models()[0]["model"] == "deepseek-chat"
    assert main2.memory.entries("c1")[0]["content"] == "记住我"


def test_to_model_image_local_file(tmp_path):
    import base64

    main = SimpleNamespace()
    png = tmp_path / "shot.png"
    png.write_bytes(b"\x89PNG fake")
    out = Main._to_model_image(str(png))
    assert out.startswith("data:image/png;base64,")
    assert base64.b64decode(out.split(",", 1)[1]) == b"\x89PNG fake"
    assert Main._to_model_image(str(tmp_path / "nope.png")) == ""
    assert Main._to_model_image("https://example.com/a.png") == "https://example.com/a.png"


def test_engine_strips_images_on_400():
    engine = OpenAIEngine()
    engine.retry_delays = (0, 0)
    captured = []

    ok_resp = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="看到了", tool_calls=None), finish_reason="stop")],
        usage=None,
        model="m",
    )

    class FakeStatusErr(APIStatusError):
        def __init__(self):
            self.status_code = 400
            self.message = "image not supported"

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        async def create(self, **kwargs):
            self.calls += 1
            captured.append(kwargs["messages"])
            if self.calls == 1:
                raise FakeStatusErr()
            return ok_resp

    engine._clients[("", "")] = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    messages = [
        {"role": "user", "content": [
            {"type": "text", "text": "看这张图"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
        ]}
    ]
    resp = asyncio.run(engine.chat("", "", ChatRequest(messages=messages)))
    assert resp.content == "看到了"
    assert engine._has_image_parts(captured[0]) is True
    assert engine._has_image_parts(captured[1]) is False
    assert "看这张图" in captured[1][0]["content"]
