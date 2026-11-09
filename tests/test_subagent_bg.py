import asyncio
from types import SimpleNamespace

from QvQChat.Main import Main
from QvQChat.tools_builtin import agent as agent_tool

from fakes import FakeMain, make_ctx


def _group_ctx(main):
    ctx = make_ctx(main, admins=["1"])
    ctx.chat_key = "onebot11:group:9"
    ctx.platform = "onebot11"
    ctx.detail_type = "group"
    ctx.target_id = "9"
    return ctx


class _SpyRunner:
    calls: list = []

    def __init__(self, pool, registry, config):
        pass

    async def run(self, *, system, messages, ctx, **kwargs):
        from QvQChat.agent.runner import AgentResult

        _SpyRunner.calls.append({"system": system, "ctx": ctx, "kwargs": kwargs})
        return AgentResult(text="后台结果完成")


async def _bg_spawn(main, **tool_kwargs):
    """spawn_agent(background=True) + 收敛后台任务；返回 (工具返回文案, 探针)。"""
    ctx = _group_ctx(main)
    note = await agent_tool.spawn_agent(ctx, task="慢慢查资料", background=True, **tool_kwargs)
    await asyncio.gather(*main.spawned)
    index = main.sdk.storage.get(agent_tool.SUBJOB_INDEX_KEY, [])
    assert len(index) == 1
    probe = main.sdk.storage.get(agent_tool.SUBJOB_PREFIX + index[0], None)
    return note, probe


# 文案随 locale 变化（测试环境 en）：用会话键等 locale 无关锚点断言
def _note_has(note: str) -> bool:
    return "onebot11:group:9" in note


async def test_background_spawn_runs_and_probes_done(monkeypatch=None):
    real = agent_tool.AgentRunner
    agent_tool.AgentRunner = _SpyRunner
    _SpyRunner.calls = []
    try:
        main = FakeMain()
        note, probe = await _bg_spawn(main)
        assert _note_has(note)
        assert probe["status"] == "done"
        assert probe["parent_chat_key"] == "onebot11:group:9"
        # 子会话有任务与结果双方
        ctxs = main.sessions.get_contexts(probe["sub_key"])
        texts = [str(m.get("content")) for m in ctxs]
        assert any("慢慢查资料" in t for t in texts)
        assert any("后台结果完成" in t for t in texts)
    finally:
        agent_tool.AgentRunner = real


async def test_background_emits_done_event():
    real = agent_tool.AgentRunner
    agent_tool.AgentRunner = _SpyRunner
    _SpyRunner.calls = []
    try:
        main = FakeMain()
        await _bg_spawn(main)
        done = [d for e, d in main.sdk.lifecycle.emitted if e == "qvq.subagent_done"]
        assert done and done[0]["parent_chat_key"] == "onebot11:group:9"
        assert "后台结果完成" in done[0]["answer"]
    finally:
        agent_tool.AgentRunner = real


async def test_background_error_marks_probe_no_emit():
    real = agent_tool.AgentRunner

    class BoomRunner(_SpyRunner):
        async def run(self, *, system, messages, ctx, **kwargs):
            raise RuntimeError("boom")

    agent_tool.AgentRunner = BoomRunner
    try:
        main = FakeMain()
        _, probe = await _bg_spawn(main)
        assert probe["status"] == "error"
        assert not [d for e, d in main.sdk.lifecycle.emitted if e == "qvq.subagent_done"]
    finally:
        agent_tool.AgentRunner = real


async def test_foreground_still_waits_inline():
    """不传 background 维持原语义：内联等待并返回答案全文。"""
    real = agent_tool.AgentRunner
    agent_tool.AgentRunner = _SpyRunner
    _SpyRunner.calls = []
    try:
        main = FakeMain()
        ctx = _group_ctx(main)
        out = await agent_tool.spawn_agent(ctx, task="快活")
        assert "后台结果完成" in out
        assert "keep chatting" not in out  # 前台文案没有“转后台”提示
        assert not main.spawned  # 无后台任务
        assert not main.sdk.storage.get(agent_tool.SUBJOB_INDEX_KEY, [])
    finally:
        agent_tool.AgentRunner = real


async def test_on_subagent_done_spawns_digest_with_persist():
    main = FakeMain()
    setattr(main, "_digest_subagent", Main._digest_subagent.__get__(main))
    Main._on_subagent_done(main, {
        "sub_key": "sub:onebot11:group:9:abcd",
        "parent_chat_key": "onebot11:group:9",
        "task": "慢慢查资料",
        "answer": "查到了：答案 42",
        "ms": 1200,
    })
    await asyncio.gather(*main.spawned)
    assert main.prompts, "插回消化必须发起 run_prompt"
    chat_key, prompt, kwargs = main.prompts[-1]
    assert chat_key == "onebot11:group:9"
    assert "查到了：答案 42" in prompt and "慢慢查资料" in prompt
    assert kwargs.get("origin") == "proactive"
    assert kwargs.get("persist") is True


async def test_on_subagent_done_ignores_bad_payload():
    main = FakeMain()
    Main._on_subagent_done(main, None)
    Main._on_subagent_done(main, {"answer": "x"})  # 无 parent_chat_key
    Main._on_subagent_done(main, {"parent_chat_key": ""})
    assert not main.prompts and not main.spawned


async def test_recover_subjobs_marks_interrupted():
    main = FakeMain()
    agent_tool._subjob_probe(main, "sub:onebot11:group:1:dead", {
        "sub_key": "sub:onebot11:group:1:dead",
        "parent_chat_key": "onebot11:group:1",
        "task": "残留任务",
        "status": "running",
        "started": 0,
    })
    agent_tool.recover_subjobs(main)
    probe = main.sdk.storage.get(agent_tool.SUBJOB_PREFIX + "sub:onebot11:group:1:dead", None)
    assert probe["status"] == "interrupted"
    # 已完成的探针不动
    agent_tool._subjob_probe(main, "sub:k2", {"status": "done"})
    agent_tool.recover_subjobs(main)
    assert main.sdk.storage.get(agent_tool.SUBJOB_PREFIX + "sub:k2")["status"] == "done"


async def test_run_prompt_persist_writes_both_sides():
    """persist=True：问答双方都进会话；persist=False（默认）不留痕。"""
    main = FakeMain()
    main._chat_locks = {}

    class R:
        async def run(self, **kwargs):
            return SimpleNamespace(text="插回的消化结论", usage={}, tool_trace=[], rounds=[])

    main.runner = R()
    setattr(main, "run_prompt", Main.run_prompt.__get__(main))
    setattr(main, "_lock_for", Main._lock_for.__get__(main))
    chat_key = "onebot11:group:9"
    await main.run_prompt(chat_key, "后台汇报内容", origin="proactive", send=False, persist=True)
    texts = [str(m.get("content")) for m in main.sessions.get_contexts(chat_key)]
    assert any("后台汇报内容" in t for t in texts)
    assert any("插回的消化结论" in t for t in texts)
    # 默认 persist=False：一次性调用不留痕
    await main.run_prompt(chat_key, "一次性任务提示", origin="task", send=False)
    texts2 = [str(m.get("content")) for m in main.sessions.get_contexts(chat_key)]
    assert not any("一次性任务提示" in t for t in texts2)
