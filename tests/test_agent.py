import asyncio

from QvQChat import texts
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


class CapabilityPool:
    """带能力查询的假池：capability_status 返回固定状态，chat 记录请求。"""

    def __init__(self, status="no"):
        self.status = status
        self.requests = []

    def capability_status(self, need):
        return self.status

    def has_model(self, needs=None):
        return self.status == "yes"

    async def chat(self, request, **kwargs):
        self.requests.append(request)
        return ChatResponse(content="直接回答", model="fake")


def make_capability_registry():
    registry = ToolRegistry()
    registry.register(make_tool())
    return registry


async def test_tools_fallback_strip_default():
# 全池明确无 tool_call：默认 strip——去工具 + system 追加降级提示，仍产出回复
    main = FakeMain()
    pool = CapabilityPool("no")
    runner = AgentRunner(pool, make_capability_registry(), main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "直接回答"
    request = pool.requests[0]
    assert request.tools is None, "strip 分支不应携带工具"
    note = texts.t("tools_degraded_note")
    assert note[:10] in request.messages[0]["content"], "system 应追加降级提示"


async def test_tools_fallback_strict_raises():
    from QvQChat.engine.base import EngineError

    main = FakeMain(tools_fallback="strict")
    runner = AgentRunner(CapabilityPool("no"), make_capability_registry(), main.cfg)
    ctx = make_ctx(main)
    try:
        await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
        raise AssertionError("strict 分支应抛错")
    except EngineError as e:
        assert "tool" in str(e)


async def test_tools_fallback_off_keeps_tools():
# off：旧行为——照常带工具
    main = FakeMain(tools_fallback="off")
    pool = CapabilityPool("no")
    runner = AgentRunner(pool, make_capability_registry(), main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "直接回答"
    request = pool.requests[0]
    assert request.tools, "off 分支应保留工具"
    assert texts.t("tools_degraded_note")[:10] not in request.messages[0]["content"]


async def test_toolcall_needs_added_when_pool_capable():
# 池内有 tool_call 模型：请求 needs 含 tool_call，工具保留
    main = FakeMain()
    pool = CapabilityPool("yes")
    runner = AgentRunner(pool, make_capability_registry(), main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "直接回答"
    request = pool.requests[0]
    assert request.tools, "有能力模型时应保留工具"
    assert request.needs == ["tool_call"]

# 显式指定模型时不加 needs（用户点名的模型不被筛选）
    pool2 = CapabilityPool("yes")
    runner2 = AgentRunner(pool2, make_capability_registry(), main.cfg)
    await runner2.run(
        system="s", messages=[{"role": "user", "content": "hi"}], ctx=make_ctx(main), model="m1"
    )
    assert pool2.requests[0].needs is None
    assert pool2.requests[0].tools


async def test_runner_dispatch_used_when_available():
# 池支持 dispatch 时主循环走 dispatch(kind="chat")
    from QvQChat.engine.base import TaskSpec

    class DispatchPool(CapabilityPool):
        def __init__(self):
            super().__init__("unknown")
            self.specs = []

        async def dispatch(self, spec, request, **kwargs):
            self.specs.append(spec)
            return await self.chat(request, **kwargs)

    main = FakeMain()
    pool = DispatchPool()
    runner = AgentRunner(pool, make_capability_registry(), main.cfg)
    ctx = make_ctx(main)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "直接回答"
    assert pool.specs and all(isinstance(s, TaskSpec) and s.kind == "chat" for s in pool.specs)
