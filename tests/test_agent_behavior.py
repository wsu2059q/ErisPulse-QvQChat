"""智能体行为：计划-执行-反思（deep 三段式）+ 工具自愈 + 技能自动习得。"""

from QvQChat import texts
from QvQChat.agent.runner import AgentResult, AgentRunner
from QvQChat.agent.tools import Tool, ToolRegistry
from QvQChat.engine.base import ChatResponse, EngineError, ToolCall
from QvQChat.prompts import CRITIQUE_PROMPT, REFLEXION_PLAN_PROMPT
from QvQChat.tools_builtin import skilltools

from fakes import FakeMain, make_ctx


def make_tool(name, handler=None):
    async def default_handler(ctx, **kwargs):
        return f"echo:{kwargs.get('text', '')}"

    return Tool(
        name=name,
        description="test tool",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler or default_handler,
    )


def user_contents(request) -> list:
    return [
        m.get("content")
        for m in request.messages
        if isinstance(m, dict) and m.get("role") == "user" and isinstance(m.get("content"), str)
    ]


# ===== deep 三段式 =====


class DeepPool:
    """dispatch 假池：compact（规划/审查）与 chat 分开脚本化，记录 (spec, request)。"""

    def __init__(self, plan="1. first step\n2. second step\nDone when: site is up",
                 critique="DONE", chats=None):
        self.plan = plan
        self.critique = critique
        self.chat_responses = list(chats or [])
        self.calls = []
        self._compact_n = 0

    async def dispatch(self, spec, request, **kwargs):
        self.calls.append((spec, request))
        if spec.kind == "compact":
            self._compact_n += 1
            if self._compact_n == 1:
                return ChatResponse(content=self.plan, model="p:cheap", usage={"total_tokens": 1})
            return ChatResponse(content=self.critique, model="p:cheap", usage={"total_tokens": 1})
        return self.chat_responses.pop(0)


def deep_runner(pool, main=None, **cfg):
    main = main or FakeMain(**cfg)
    registry = ToolRegistry()
    registry.register(make_tool("echo"))
    return AgentRunner(pool, registry, main.cfg), main


async def test_deep_plan_injected_and_call_order():
    pool = DeepPool(chats=[ChatResponse(content="done answer", usage={"total_tokens": 2})])
    runner, main = deep_runner(pool)
    result = await runner.run(
        system="SYS", messages=[{"role": "user", "content": "deploy the site"}],
        ctx=make_ctx(main), task_kind="deep",
    )
# 三次调用顺序：PLAN(compact/cheap) → EXECUTE(chat) → CRITIQUE(compact/cheap)
    kinds = [spec.kind for spec, _ in pool.calls]
    assert kinds == ["compact", "chat", "compact"]
    assert pool.calls[0][0].prefer == "cheap" and pool.calls[2][0].prefer == "cheap"
# PLAN 调用：REFLEXION_PLAN_PROMPT 为 system，任务文本进入 user
    plan_request = pool.calls[0][1]
    assert plan_request.messages[0]["content"] == REFLEXION_PLAN_PROMPT
    assert plan_request.tools is None
    assert "deploy the site" in plan_request.messages[-1]["content"]
# 计划注入执行阶段 system 尾部 <task-plan> 块
    exec_request = pool.calls[1][1]
    assert exec_request.messages[0]["content"] == "SYS\n\n<task-plan>\n" + pool.plan + "\n</task-plan>"
    assert result.plan == pool.plan
    assert result.text == "done answer"
# CRITIQUE 调用：CRITIQUE_PROMPT + 计划/回复/trace 摘要
    critique_request = pool.calls[2][1]
    assert critique_request.messages[0]["content"] == CRITIQUE_PROMPT
    payload = critique_request.messages[-1]["content"]
    assert pool.plan in payload and "done answer" in payload and "(no tools used)" in payload
    assert result.critique == "DONE"


async def test_deep_critique_done_no_fix_round():
    pool = DeepPool(critique="DONE — reply covers all steps",
                    chats=[ChatResponse(content="done answer", usage={"total_tokens": 2})])
    runner, main = deep_runner(pool)
    result = await runner.run(system="SYS", messages=[{"role": "user", "content": "do it"}],
                              ctx=make_ctx(main), task_kind="deep")
    assert len(pool.calls) == 3, "DONE 不应触发修正轮"
    assert result.text == "done answer"
    assert result.rounds[-1]["text"] == "done answer"


async def test_deep_critique_fix_triggers_single_no_tool_round():
    fix = "FIX: add the port number and the deploy log link"
    pool = DeepPool(critique=fix, chats=[
        ChatResponse(content="answer v1", usage={"total_tokens": 2}),
        ChatResponse(content="answer v2", usage={"total_tokens": 2}),
    ])
    runner, main = deep_runner(pool)
    result = await runner.run(system="SYS", messages=[{"role": "user", "content": "do it"}],
                              ctx=make_ctx(main), task_kind="deep")
# 调用序列：plan → execute → critique → 修正轮（有界 1 次，不再复查）
    kinds = [spec.kind for spec, _ in pool.calls]
    assert kinds == ["compact", "chat", "compact", "chat"]
    fix_request = pool.calls[3][1]
    assert fix_request.tools is None, "修正轮不携带工具"
    assert fix_request.messages[-1]["role"] == "user"
    assert "add the port number" in fix_request.messages[-1]["content"]
    assert fix_request.messages[-2] == {"role": "assistant", "content": "answer v1"}
    assert result.text == "answer v2"
    assert result.critique == fix
    assert result.rounds[-1]["text"] == "answer v2"
# usage 聚合了全部四次调用
    assert result.usage["total_tokens"] == 1 + 2 + 1 + 2


async def test_deep_unrecognized_critique_treated_as_done():
    pool = DeepPool(critique="I think the reply looks fine overall.",
                    chats=[ChatResponse(content="answer v1", usage={"total_tokens": 2})])
    runner, main = deep_runner(pool)
    result = await runner.run(system="SYS", messages=[{"role": "user", "content": "do it"}],
                              ctx=make_ctx(main), task_kind="deep")
    assert len(pool.calls) == 3, "无法识别的审查输出不触发修正轮"
    assert result.text == "answer v1"


async def test_plain_chat_does_not_trigger_deep_phases():
    pool = DeepPool(chats=[ChatResponse(content="plain reply", usage={"total_tokens": 2})])
    runner, main = deep_runner(pool)
    result = await runner.run(system="SYS", messages=[{"role": "user", "content": "hi"}], ctx=make_ctx(main))
    assert len(pool.calls) == 1 and pool.calls[0][0].kind == "chat"
    assert "<task-plan>" not in pool.calls[0][1].messages[0]["content"]
    assert result.plan == "" and result.critique == ""
    assert result.text == "plain reply"


async def test_deep_with_legacy_pool_falls_back_to_chat():
    class LegacyPool:
        def __init__(self):
            self.requests = []
            self.responses = [
                ChatResponse(content="1. legacy plan", usage={"total_tokens": 1}),
                ChatResponse(content="legacy answer", usage={"total_tokens": 2}),
                ChatResponse(content="DONE", usage={"total_tokens": 1}),
            ]

        async def chat(self, request, **kwargs):
            self.requests.append(request)
            return self.responses.pop(0)

    pool = LegacyPool()
    runner, main = deep_runner(pool)
    result = await runner.run(system="SYS", messages=[{"role": "user", "content": "do it"}],
                              ctx=make_ctx(main), task_kind="deep")
    assert len(pool.requests) == 3
    assert "<task-plan>\n1. legacy plan\n</task-plan>" in pool.requests[1].messages[0]["content"]
    assert result.plan == "1. legacy plan" and result.text == "legacy answer"


async def test_deep_degrades_gracefully_when_phases_fail():
    class BrokenCompactPool:
        def __init__(self):
            self.chat_calls = 0

        async def dispatch(self, spec, request, **kwargs):
            if spec.kind == "compact":
                raise EngineError("no cheap model")
            self.chat_calls += 1
            return ChatResponse(content="direct answer", usage={"total_tokens": 3})

    pool = BrokenCompactPool()
    runner, main = deep_runner(pool)
    result = await runner.run(system="SYS", messages=[{"role": "user", "content": "do it"}],
                              ctx=make_ctx(main), task_kind="deep")
    assert result.plan == "" and result.critique == "" and result.text == "direct answer"


# ===== 工具自愈 =====


def boom_tool():
    async def handler(ctx, **kwargs):
        raise ValueError("kaputt")

    return make_tool("boom", handler)


def flaky_tool(fail_on=(1, 3, 4)):
    state = {"n": 0}

    async def handler(ctx, **kwargs):
        state["n"] += 1
        if state["n"] in fail_on:
            raise ValueError("nope")
        return "ok"

    return make_tool("flaky", handler)


def tool_call_pool(script):
    """script: 每轮一项——("call", 工具名) 表示该轮发起工具调用，纯字符串表示最终回复；记录每个请求。"""

    class Pool:
        def __init__(self):
            self.requests = []
            self._i = 0

        async def chat(self, request, **kwargs):
            self.requests.append(request)
            item = script[self._i]
            self._i += 1
            if isinstance(item, str):
                return ChatResponse(content=item, usage={"total_tokens": 1})
            _, name = item
            return ChatResponse(
                content="",
                tool_calls=[ToolCall(call_id=f"c{self._i}", name=name, arguments={})],
                usage={"total_tokens": 1},
            )

    return Pool()


def heal_hint(name, errors):
    return texts.t("tool_selfheal_hint", name=name, errors="\n".join(f"- {e}" for e in errors))


async def test_self_heal_hint_after_two_consecutive_failures():
    main = FakeMain()
    registry = ToolRegistry()
    registry.register(boom_tool())
    pool = tool_call_pool([("call", "boom"), ("call", "boom"), "all done"])
    runner = AgentRunner(pool, registry, main.cfg)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "go"}], ctx=make_ctx(main))
    assert result.text == "all done"
# 第二次连续失败发生在第 2 轮——提示注入到第 3 轮请求的上下文
    err = texts.t("tool_error", name="boom", error="ValueError: kaputt")
    expected = heal_hint("boom", [err, err])
    third = user_contents(pool.requests[2])
    assert expected in third, f"自愈提示未注入：{third}"
# 第 2 轮请求（仅一次失败后）不应有提示
    assert expected not in user_contents(pool.requests[1])


async def test_self_heal_counter_resets_on_success():
    main = FakeMain()
    registry = ToolRegistry()
    registry.register(flaky_tool())# 第 1/3/4 次失败，第 2 次成功
    pool = tool_call_pool([("call", "flaky"), ("call", "flaky"), ("call", "flaky"), ("call", "flaky"), "final"])
    runner = AgentRunner(pool, registry, main.cfg)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "go"}], ctx=make_ctx(main))
    assert result.text == "final"
    err = texts.t("tool_error", name="flaky", error="ValueError: nope")
    expected = heal_hint("flaky", [err, err])
# 第 2 次失败前有一次成功 → 计数清零，只在第 4 次失败（连续第 2 次）后注入一次
    all_hints = [c for req in pool.requests for c in user_contents(req) if c == expected]
    assert all_hints == [expected], "自愈提示应恰好出现一次（成功清零后重新计满两次）"
    assert expected in user_contents(pool.requests[4])


async def test_self_heal_disabled_by_switch():
    main = FakeMain(tool_self_heal=False)
    registry = ToolRegistry()
    registry.register(boom_tool())
    pool = tool_call_pool([("call", "boom"), ("call", "boom"), "final"])
    runner = AgentRunner(pool, registry, main.cfg)
    result = await runner.run(system="s", messages=[{"role": "user", "content": "go"}], ctx=make_ctx(main))
    assert result.text == "final"
    err = texts.t("tool_error", name="boom", error="ValueError: kaputt")
    expected = heal_hint("boom", [err, err])
    for request in pool.requests:
        assert expected not in user_contents(request), "开关关闭时不应注入自愈提示"


async def test_invoke_meta_error_signal():
# invoke 错误语义不变（返回文案），meta["error"]=True 供 runner 判定；权限拒绝不计失败
    registry = ToolRegistry()
    registry.register(boom_tool())
    ctx = make_ctx()
    meta = {}
    out = await registry.invoke("boom", {}, ctx, meta=meta)
    assert "kaputt" in out and meta.get("error") is True
    meta2 = {}
    await registry.invoke("nope", {}, ctx, meta=meta2)
    assert meta2.get("error") is True
# 不传 meta 时行为与旧签名完全一致
    assert "kaputt" in await registry.invoke("boom", {}, ctx)


# ===== 技能自动习得 =====


async def test_save_skill_tool_metadata_and_persistence():
    main = FakeMain()
    registry = ToolRegistry()
    skilltools.register(registry, main)
    tool = registry.get("save_skill")
    assert tool is not None
    assert tool.access == "admin" and tool.danger is True
    assert set(tool.parameters.get("required") or []) == {"name", "description", "content"}
    ctx = make_ctx(main)
    out = await registry.invoke(
        "save_skill",
        {"name": "deploy-site", "description": "部署站点流程", "content": "1. run_command git pull\n2. run_command npm run build"},
        ctx,
    )
    assert "deploy-site" in out
    stored = main.sdk.storage.get("QvQChat:skills", {})
    assert stored["deploy-site"]["description"] == "部署站点流程"
    skill = main.skills.get_skill("deploy-site")
    assert skill is not None and skill["source"] == "dashboard" and "git pull" in skill["body"]


async def test_save_skill_rejects_empty_name_and_content():
    main = FakeMain()
    registry = ToolRegistry()
    skilltools.register(registry, main)
    ctx = make_ctx(main)
    out = await registry.invoke("save_skill", {"name": " ", "description": "d", "content": "c"}, ctx)
    assert out == texts.t("skills_name_required")
    out = await registry.invoke("save_skill", {"name": "x", "description": "d", "content": ""}, ctx)
    assert "save_skill" in out


def test_propose_from_run_draft_shape():
    main = FakeMain()
    result = AgentResult(
        text="部署完成，站点已上线\n详细信息见日志",
        tool_trace=[
            {"tool": "run_command", "arguments": '{"cmd": "git pull"}', "output": "ok"},
            {"tool": "run_command", "arguments": '{"cmd": "npm run build"}', "output": "ok"},
            {"tool": "send_message", "arguments": "{}", "output": "sent"},
        ],
    )
    draft = main.skills.propose_from_run("帮我 deploy 新版本", result)
    assert draft is not None
    assert draft["name"] == "deploy"
    assert draft["description"] == "部署完成，站点已上线"
    assert len(draft["steps"]) == 3
    assert draft["steps"][0].startswith("1. 调用 run_command")
    assert "git pull" in draft["steps"][0]
    assert draft["steps"][2].startswith("3. 调用 send_message")
# 不落盘
    assert main.sdk.storage.get("QvQChat:skills", {}) == {}


def test_propose_from_run_none_cases():
    main = FakeMain()
# 无工具调用 → None
    assert main.skills.propose_from_run("plain task", AgentResult(text="ok")) is None
# 无用户文本 → None
    assert main.skills.propose_from_run("", AgentResult(text="ok", tool_trace=[{"tool": "t", "arguments": "", "output": ""}])) is None
# 同名技能已存在 → None（不重复提议）
    result = AgentResult(
        text="done",
        tool_trace=[{"tool": "run_command", "arguments": "", "output": "ok"}],
    )
    assert main.skills.propose_from_run("please deploy it", result)["name"] == "deploy"
    main.skills.save_skill("deploy", "existing", "body")
    assert main.skills.propose_from_run("please deploy it", result) is None


def test_propose_from_run_name_fallback_without_ascii_words():
    main = FakeMain()
    result = AgentResult(
        text="完成",
        tool_trace=[{"tool": "run_command", "arguments": "", "output": "ok"}],
    )
    draft = main.skills.propose_from_run("帮我部署网站", result)
    assert draft is not None
    assert draft["name"] == "task-run_command"
    assert draft["description"] == "完成"


# ===== 配置与提示词常量 =====


def test_config_new_tool_switches():
    from QvQChat.Config import QvQConfig

    assert QvQConfig.field_map()["tool_self_heal"] is not None
    assert QvQConfig.field_map()["skill_induct"] is not None
    assert QvQConfig.__dataclass_fields__["tool_self_heal"].default is True
    assert QvQConfig.__dataclass_fields__["skill_induct"].default is True
    ui = (QvQConfig.__dataclass_fields__["tool_self_heal"].metadata or {}).get("ui") or {}
    assert ui["group"] == "tools" and ui["order"] == 6 and ui["widget"] == "switch"
    ui = (QvQConfig.__dataclass_fields__["skill_induct"].metadata or {}).get("ui") or {}
    assert ui["group"] == "tools" and ui["order"] == 7 and ui["widget"] == "switch"


def test_texts_new_keys_have_five_languages():
    for key in ("tool_selfheal_hint", "skill_saved", "deep_fix_note"):
        entry = texts.STRINGS[key]
        assert set(entry) == {"zh-CN", "zh-TW", "en", "ja", "ru"}, key
        assert "{name}" in entry["en"] or "{fixes}" in entry["en"] or key == "deep_fix_note"


def test_skill_offer_note_is_standalone_constant():
# SKILL_OFFER_NOTE 为独立常量（注入接线由 service 侧按 skill_induct 决定）
    from QvQChat.prompts import CAPABILITY_PROMPT, SKILL_OFFER_NOTE

    assert "save_skill" in SKILL_OFFER_NOTE and "记住这个做法" in SKILL_OFFER_NOTE
    assert SKILL_OFFER_NOTE not in CAPABILITY_PROMPT
