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
    ctx = make_ctx(main, admins=["1"])
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "final answer"
    assert result.tool_trace[0]["tool"] == "echo"
    assert result.usage["total_tokens"] == 8
    loop_request = requests[0]
    assert loop_request.tools and loop_request.messages[0]["role"] == "system"
    followup = requests[1].messages
    assert followup[-2]["role"] == "assistant" and "tool_calls" in followup[-2]
    assert followup[-1]["role"] == "tool" and followup[-1]["tool_call_id"] == "c1"


async def test_runner_delivery_hint_from_mid_run_tag():
    """中间发言开头的 [[转发]] 记录为 run 级投递意图，并从展示文本剥离。"""
    main = FakeMain()
    registry = ToolRegistry()
    registry.register(make_tool())
    requests = []

    class ScriptedPool:
        async def chat(self, request, **kwargs):
            requests.append(request)
            if len(requests) == 1:
                return ChatResponse(
                    content="[[转发]]先查一下",
                    tool_calls=[ToolCall(call_id="c1", name="echo", arguments={"text": "x"})],
                    usage={},
                )
            return ChatResponse(content="最终结论")

    runner = AgentRunner(ScriptedPool(), registry, main.cfg)
    ctx = make_ctx(main, admins=["1"])
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.delivery_hint is True
    assert result.rounds[0]["text"] == "先查一下"
    assert result.text == "最终结论"


async def test_runner_delivery_hint_final_tag_wins():
    """最终回复的标签优先于过程中声明的标签。"""
    main = FakeMain()
    registry = ToolRegistry()
    registry.register(make_tool())
    requests = []

    class ScriptedPool:
        async def chat(self, request, **kwargs):
            requests.append(request)
            if len(requests) == 1:
                return ChatResponse(
                    content="[[转发]]先查一下",
                    tool_calls=[ToolCall(call_id="c1", name="echo", arguments={"text": "x"})],
                    usage={},
                )
            return ChatResponse(content="[[直发]]结论")

    runner = AgentRunner(ScriptedPool(), registry, main.cfg)
    ctx = make_ctx(main, admins=["1"])
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.delivery_hint is False
    assert result.text == "结论"


async def test_runner_limits_output_tag():
    main = FakeMain()
    registry = ToolRegistry()

    class Pool:
        async def chat(self, request, **kwargs):
            return ChatResponse(content="[[直发]]就一句话")

    runner = AgentRunner(Pool(), registry, main.cfg)
    ctx = make_ctx(main, admins=["1"])
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.delivery_hint is False
    assert result.text == "就一句话"


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
    ctx = make_ctx(main, admins=["1"])
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
    ctx = make_ctx(main, admins=["1"])
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
    ctx = make_ctx(main, admins=["1"])
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
    ctx = make_ctx(main, admins=["1"])
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "直接回答"
    request = pool.requests[0]
    assert request.tools, "有能力模型时应保留工具"
    assert request.needs == ["tool_call"]

# 显式指定模型时不加 needs（用户点名的模型不被筛选）
    pool2 = CapabilityPool("yes")
    runner2 = AgentRunner(pool2, make_capability_registry(), main.cfg)
    await runner2.run(
        system="s", messages=[{"role": "user", "content": "hi"}], ctx=make_ctx(main, admins=["1"]), model="m1"
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
    ctx = make_ctx(main, admins=["1"])
    result = await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=ctx)
    assert result.text == "直接回答"
    assert pool.specs and all(isinstance(s, TaskSpec) and s.kind == "chat" for s in pool.specs)


async def test_non_admin_tool_schemas_filtered():
# 非管理员不注入无权调用的工具（与 invoke 期 tool_allowed 同口径），admin 工具不出现在 schema
    main = FakeMain()
    registry = make_capability_registry()
    pool = CapabilityPool("yes")
    runner = AgentRunner(pool, registry, main.cfg)
    await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=make_ctx(main))
    assert pool.requests[0].tools is None


async def test_admin_sees_tool_schemas():
    main = FakeMain()
    registry = make_capability_registry()
    pool = CapabilityPool("yes")
    runner = AgentRunner(pool, registry, main.cfg)
    await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=make_ctx(main, admins=["1"]))
    assert pool.requests[0].tools


async def test_session_block_injected():
# system 尾部追加 <session> 会话上下文（平台/类型/目标/触发者）
    main = FakeMain()
    pool = CapabilityPool("yes")
    runner = AgentRunner(pool, make_capability_registry(), main.cfg)
    await runner.run(system="s", messages=[{"role": "user", "content": "hi"}], ctx=make_ctx(main, admins=["1"]))
    content = pool.requests[0].messages[0]["content"]
    assert content.startswith("s")
    assert "<session>" in content and "platform=test" in content and "</session>" in content


async def test_spawn_agent_inherits_user_context():
    """子智能体权限/发送能力跟随发起用户：platform/detail_type/target_id/event 继承。"""
    main = FakeMain()
    registry = ToolRegistry()
    registry.register(make_tool())
    captured = {}

    class Pool:
        async def chat(self, request, **kwargs):
            return ChatResponse(content="子任务完成", usage={})

    from QvQChat.tools_builtin import agent as agent_tool

    real_runner = agent_tool.AgentRunner

    class SpyRunner(real_runner):
        def __init__(self, pool, registry, config):
            super().__init__(pool, registry, config)

        async def run(self, *, system, messages, ctx, **kwargs):
            captured["platform"] = ctx.platform
            captured["detail_type"] = ctx.detail_type
            captured["target_id"] = ctx.target_id
            captured["user_id"] = ctx.user_id
            captured["event"] = ctx.event
            captured["origin"] = ctx.origin
            captured["scene"] = getattr(ctx, "scene_note", "")
            captured["system"] = system
            from QvQChat.agent.runner import AgentResult

            return AgentResult(text="子任务完成")

    agent_tool.AgentRunner = SpyRunner
    try:
        main.registry = registry
        parent_ctx = make_ctx(main, admins=["1"])
        parent_ctx.chat_key = "onebot11:group:67890"
        parent_ctx.platform = "onebot11"
        parent_ctx.detail_type = "group"
        parent_ctx.target_id = "67890"
        parent_ctx.event = object()
        parent_ctx.scene_note = "平台：onebot11 群：测试群"
        main.sessions.append("onebot11:group:67890", "user", "樱城の心: 帮我导出记录")
        result = await agent_tool.spawn_agent(parent_ctx, task="导出群记录")
        assert "子任务完成" in result
        assert captured["platform"] == "onebot11"
        assert captured["detail_type"] == "group"
        assert captured["target_id"] == "67890"
        assert captured["event"] is parent_ctx.event
        assert captured["scene"] == "平台：onebot11 群：测试群"
        assert "<scene>" in captured["system"]
        assert "<recent-chat>" in captured["system"]
        assert "樱城の心" in captured["system"]
    finally:
        agent_tool.AgentRunner = real_runner


async def test_spawn_agent_no_nested_spawn():
    main = FakeMain()
    from QvQChat.tools_builtin import agent as agent_tool
    from QvQChat import texts

    ctx = make_ctx(main, admins=["1"])
    ctx.chat_key = "sub:onebot11:group:1:abcd1234"
    result = await agent_tool.spawn_agent(ctx, task="x")
    assert "cannot spawn" in result.lower()


async def test_spawn_agent_forwards_sub_tool_events():
    """子智能体内部步骤透传到父直播流：带 agent=sub 标记与 sub: 前缀的 step_id。"""
    main = FakeMain()
    from QvQChat.tools_builtin import agent as agent_tool
    from QvQChat.agent.runner import AgentResult

    seen = []

    def parent_hook(evt):
        seen.append(evt)

    real_runner = agent_tool.AgentRunner

    class HookRunner(real_runner):
        async def run(self, *, system, messages, ctx, **kwargs):
            hook = kwargs.get("on_tool_event")
            if hook is not None:
                hook({"phase": "start", "step_id": "s0", "name": "web_fetch", "arguments": "{}"})
                hook({"phase": "end", "step_id": "s0", "name": "web_fetch", "output": "ok", "ms": 5})
            return AgentResult(text="完成")

    agent_tool.AgentRunner = HookRunner
    try:
        ctx = make_ctx(main, admins=["1"])
        ctx.chat_key = "onebot11:group:1"
        ctx.on_tool_event = parent_hook
        out = await agent_tool.spawn_agent(ctx, task="抓页面")
        assert "完成" in out
        assert len(seen) == 2
        assert seen[0]["agent"] == "sub"
        assert seen[0]["step_id"] == "sub:s0"
        assert seen[1]["phase"] == "end"
        assert seen[1]["step_id"] == "sub:s0"
    finally:
        agent_tool.AgentRunner = real_runner


async def test_spawn_agent_without_hook_stays_silent():
    """没有直播回调（命令行/群聊路径）时不报错、不产生事件。"""
    main = FakeMain()
    from QvQChat.tools_builtin import agent as agent_tool
    from QvQChat.agent.runner import AgentResult

    real_runner = agent_tool.AgentRunner

    class HookRunner(real_runner):
        async def run(self, *, system, messages, ctx, **kwargs):
            assert kwargs.get("on_tool_event") is None
            return AgentResult(text="完成")

    agent_tool.AgentRunner = HookRunner
    try:
        ctx = make_ctx(main, admins=["1"])
        ctx.chat_key = "onebot11:group:1"
        out = await agent_tool.spawn_agent(ctx, task="x")
        assert "完成" in out
    finally:
        agent_tool.AgentRunner = real_runner
