import asyncio

from QvQChat.agent.runner import AgentRunner
from QvQChat.agent.tools import Tool, ToolContext, ToolRegistry
from QvQChat.engine.base import ChatResponse, ToolCall

from fakes import FakeMain, make_ctx


def make_tool(name="echo", handler=None):
    async def default_handler(ctx, **kwargs):
        return f"echo:{kwargs.get('text', '')}"

    return Tool(
        name=name,
        description="test tool",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler or default_handler,
    )


def test_registry_schemas_and_whitelist():
    registry = ToolRegistry()
    registry.register(make_tool("alpha"))
    registry.register(make_tool("beta"))
    registry.register(make_tool("eco_X_y"))
    schemas = registry.llm_schemas()
    assert {s["function"]["name"] for s in schemas} == {"alpha", "beta", "eco_X_y"}
    limited = registry.llm_schemas(whitelist=["eco_*"])
    assert [s["function"]["name"] for s in limited] == ["eco_X_y"]
    disabled = registry.llm_schemas(disabled=["eco_*"])
    assert {s["function"]["name"] for s in disabled} == {"alpha", "beta"}


def test_registry_unregister_prefix_and_count():
    registry = ToolRegistry()
    registry.register(make_tool("eco_a"))
    registry.register(make_tool("eco_b"))
    registry.register(make_tool("keep"))
    assert registry.unregister_prefix("eco_") == 2
    assert registry.count_by_origin() == {"builtin": 1}


async def test_invoke_success_and_missing():
    registry = ToolRegistry()
    registry.register(make_tool())
    ctx = make_ctx()
    assert await registry.invoke("echo", {"text": "hi"}, ctx) == "echo:hi"
    assert "nope" in await registry.invoke("nope", {}, ctx)


async def test_invoke_timeout_and_error():
    async def slow(ctx, **kwargs):
        await asyncio.sleep(0.5)

    async def boom(ctx, **kwargs):
        raise ValueError("kaputt")

    registry = ToolRegistry()
    registry.register(make_tool("slow", slow))
    registry.register(make_tool("boom", boom))
    ctx = make_ctx()
    out = await registry.invoke("slow", {}, ctx, timeout=0.05)
    assert "slow" in out
    out = await registry.invoke("boom", {}, ctx)
    assert "kaputt" in out


async def test_runner_tool_loop():
    main = FakeMain()
    registry = ToolRegistry()
    registry.register(make_tool())
    requests = []

    class ScriptedPool:
        async def chat(self, request, **kwargs):
            requests.append(request)
            if len(requests) == 1:
                return ChatResponse(
                    content="",
                    tool_calls=[ToolCall(call_id="c1", name="echo", arguments={"text": "hello"})],
                    usage={"total_tokens": 5},
                )
            return ChatResponse(content="final answer", usage={"total_tokens": 3})

    runner = AgentRunner(ScriptedPool(), registry, main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "final answer"
    assert result.tool_trace[0]["tool"] == "echo"
    assert result.usage["total_tokens"] == 8
    loop_request = requests[0]
    assert loop_request.tools and loop_request.messages[0]["role"] == "system"
    followup = requests[1].messages
    assert followup[-2]["role"] == "assistant" and "tool_calls" in followup[-2]
    assert followup[-1]["role"] == "tool" and followup[-1]["tool_call_id"] == "c1"


async def test_runner_forces_final_answer_at_limit():
    main = FakeMain(max_tool_rounds=1, max_tool_calls=1)
    registry = ToolRegistry()
    registry.register(make_tool())

    class AlwaysTools:
        def __init__(self):
            self.n = 0

        async def chat(self, request, **kwargs):
            self.n += 1
            if not request.tools:
                return ChatResponse(content="gave up properly")
            return ChatResponse(
                content="",
                tool_calls=[ToolCall(call_id=f"c{self.n}", name="echo", arguments={})],
            )

    runner = AgentRunner(AlwaysTools(), registry, main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "gave up properly"


async def test_tool_context_confirm_without_confirmer():
    ctx = ToolContext()
    assert await ctx.confirm("x") is False
