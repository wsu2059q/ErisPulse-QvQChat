"""后台子智能体生命周期（四段式）：started 事件 / 终态硬头 / 消化轮直发 / 直发身份头。"""
import asyncio
from types import SimpleNamespace

import pytest

import QvQChat.Main as MainMod
from QvQChat.Main import Main
from QvQChat.tools_builtin import agent as agent_tools

from fakes import FakeChatEvent, FakeMain, make_config


class _SubRunner:
    """可编程子智能体 runner：返回固定文本，记录调用。"""

    def __init__(self, text="任务结果正文"):
        self.text = text
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return type("R", (), {"text": self.text, "usage": {}, "tool_trace": [{"tool": "t"}], "rounds": []})()


def _make_ctx(main, chat_key="onebot11:group:1"):
    from QvQChat.agent.tools import ToolContext

    ev = FakeChatEvent(text="", user_id="u1", at=True)
    return ToolContext(
        main=main, sdk=main.sdk, config=main.cfg, chat_key=chat_key,
        session_key=chat_key, platform="onebot11", detail_type="group",
        target_id="1", user_id="u1", event=ev, self_id="bot",
    ), ev


@pytest.mark.asyncio
async def test_background_spawn_emits_started_and_digest_has_head():
    """后台派单：started 事件带 parent/task；回报消化后 reply 以〔后台任务 · 完成〕开头。"""
    main = FakeMain()
    main.spawned = []
    ctx, _ = _make_ctx(main)
    agent_tools.register(main.registry, main)
    tool = main.registry.get("spawn_agent")
    assert tool is not None, "spawn_agent 未注册"
    emitted = []
    main.sdk.lifecycle.emit = _fake_emit(emitted, main)

    runner = _SubRunner("画好了：/app/work/x.png")
    main.runner = runner

    result = await agent_tools.spawn_agent(ctx, task="画雪景水彩图", background=True)
    assert "后台" in result or "background" in result.lower()
    # 等待后台任务与回报消化收敛
# 派发链会串行 spawn 新任务（done → 消化 → run_prompt）：循环收敛直到不再产生新任务
    for _ in range(60):
        pending = [x for x in main.spawned if not x.done()]
        if not pending:
            break
        await asyncio.gather(*pending, return_exceptions=True)
    # started 事件（spawn 排队的异步任务，收敛后断言）
    started = [e for e in emitted if e[0] == "qvq.subagent_started"]
    assert started and started[0][1]["parent_chat_key"] == "onebot11:group:1"
    assert started[0][1]["task"] == "画雪景水彩图"
    # run_prompt 被调且带 notice 硬头（FakeMain.prompts 记录 (chat_key, prompt, kwargs)）
    assert main.prompts, "回报消化未发生"
    kwargs = main.prompts[-1][2]
    notice = kwargs.get("notice") or ""
    # 语言无关：硬头必含任务名（FakeMain 默认 en 环境）
    assert notice and "画雪景水彩图" in notice


def _fake_emit(emitted, main=None):
    async def emit(name, payload=None):
        emitted.append((name, payload))
# 真监听器在 on_load 注册（FakeMain 不跑 on_load）——subagent_done 手动派发给 Main
        if name == "qvq.subagent_done" and main is not None:
# FakeMain 不继承 Main：_on_subagent_done 里 self._digest_subagent 会 AttributeError，
# 直接绑真方法消化（等价于监听器 spawn 的那一跳）：_digest_subagent(parent, data)
            await Main._digest_subagent(main, str((payload or {}).get("parent_chat_key") or ""), payload)
    return emit


@pytest.mark.asyncio
async def test_digest_failed_head():
    """失败回报：硬头为〔后台任务 · 失败〕且带原因。"""
    main = FakeMain()
    await Main._digest_subagent(main, "onebot11:group:1", {
        "sub_key": "sub:x", "task": "抓数据", "status": "error", "error": "boom",
        "answer": "",
    })
    kwargs = main.prompts[-1][2]
    assert "抓数据" in kwargs["notice"] and "boom" in kwargs["notice"]


@pytest.mark.asyncio
async def test_digest_cancelled_head():
    main = FakeMain()
    await Main._digest_subagent(main, "onebot11:group:1", {
        "sub_key": "sub:x", "task": "抓数据", "status": "cancelled", "answer": "",
    })
    kwargs = main.prompts[-1][2]
    assert kwargs["notice"] and "抓数据" in kwargs["notice"]


@pytest.mark.asyncio
async def test_digest_forces_direct_send(monkeypatch):
    """消化轮默认强制直发（from_tools=False），subagent_report_forward=true 时恢复打卡。"""
    main = FakeMain()
    main.runner = _SubRunner("消化后的转告要点")
    main._lock_for = (lambda cache={}: (lambda k: cache.setdefault(k, asyncio.Lock())))()
    main._over_token_limit = lambda key: False
    main._chat_ctx = lambda event, key, origin: SimpleNamespace(
        chat_key=key, origin=origin, sent_log=[],
    )
# FakeMain.run_prompt 是记录 stub（无发送）——digest 要验证真实发送行为，绑真方法
    main.run_prompt = lambda *a, **k: Main.run_prompt(main, *a, **k)
    sent = []

    async def fake_send_segments(platform, detail_type, target_id, segments, from_tools=False, chat_key=""):
        sent.append({"from_tools": from_tools, "segments": [s for _, s in segments]})
        return None

    main.delivery.send_segments = fake_send_segments
    main.spawned = []
    monkeypatch.setattr(MainMod, "strip_output_tag", lambda text: (text, None), raising=False)

    # 默认：notice 非空 → from_tools=False
    await Main._digest_subagent(main, "onebot11:group:1", {
        "sub_key": "sub:x", "task": "t", "status": "done",
        "answer": "结论正文",
    })
    for _ in range(60):
        pending = [x for x in main.spawned if not x.done()]
        if not pending:
            break
        await asyncio.gather(*pending, return_exceptions=True)
    assert sent and sent[-1]["from_tools"] is False
    # 硬头在消息首段（语言无关：任务名 t 在硬头行里，转告正文随其后）
    first_line = sent[-1]["segments"][0].split("\n")[0]
    assert " t" in first_line or first_line.endswith("t")

    # subagent_report_forward=True → from_tools=True
    main.cfg.subagent_report_forward = True
    await Main._digest_subagent(main, "onebot11:group:1", {
        "sub_key": "sub:y", "task": "t2", "status": "done", "answer": "结果 2",
    })
    for _ in range(60):
        pending = [x for x in main.spawned if not x.done()]
        if not pending:
            break
        await asyncio.gather(*pending, return_exceptions=True)
    assert sent[-1]["from_tools"] is True


@pytest.mark.asyncio
async def test_subagent_direct_send_label():
    """子智能体直发：subagent_label_on 开启时首行加身份头；关闭时不加。"""
    main = FakeMain()
    main.cfg.subagent_label_on = True
    ctx, _ = _make_ctx(main)
    ctx.agent_label = "以下为子智能体的进度更新："
    ctx.sent_log = []

    from QvQChat.tools_builtin import erispulse as erispulse_tools
    from fakes import FakeSendChain

    erispulse_tools.register(main.registry, main)
    tool = main.registry.get("send_message")
    assert tool is not None
# 目标平台适配器（send_message 链路需要真 fake chain 出发送结果）
    chain = FakeSendChain(sends=("Markdown", "Text"))
    main.sdk.adapter.add("onebot11", chain, sends=("Markdown", "Text"))
    await tool.handler(ctx, text="后台这边画完了")

    # 发起会话落库条目首行带身份头
    hist = main.conversations.get_contexts("onebot11:group:1")
    last = hist[-1]
    assert ctx.agent_label in str(last["content"])

    # 关闭开关：不加头
    main.cfg.subagent_label_on = False
    await tool.handler(ctx, text="第二条更新")
    hist2 = main.conversations.get_contexts("onebot11:group:1")
    last2 = hist2[-1]
    assert not str(last2["content"]).startswith("以下为子智能体的进度更新：")
    assert "第二条更新" in str(last2["content"])


def test_forward_min_messages_fallback_3():
    """配置/代码漂移修正：forward_min_messages 代码兜底与配置默认一致（3）。"""
    from QvQChat.conversation.delivery import delivery_profile

    profile = delivery_profile(make_config(), "onebot11")
    assert profile["forward_min_messages"] == 3


@pytest.mark.asyncio
async def test_lurker_message_recorded():
    """旁听落库：未触发 bot 的群消息经 _record_lurker_message 进会话历史，
    并出现在后续 prepare 的上下文里（@ 触发时 AI 能看到群里聊过什么）。"""
    main = FakeMain()
    main._sender_name = lambda event: ""
    ctx, _ = _make_ctx(main)
    chat_key = "onebot11:group:1"
    ev1 = FakeChatEvent(text="我们在讨论工作区+命名空间的拆包方案", user_id="u1", at=False)
    ev2 = FakeChatEvent(text="各个小组件都拆成一个个小包", user_id="u1", at=False)
    Main._record_lurker_message(main, ev1, chat_key, str(ev1._text or ""))
    Main._record_lurker_message(main, ev2, chat_key, str(ev2._text or ""))

    hist = main.conversations.get_contexts(chat_key)
    joined = "\n".join(str(c.get("content") or "") for c in hist)
    assert "工作区+命名空间" in joined and "拆成一个个小包" in joined
    assert any(c.get("sender") == "u1" for c in hist if isinstance(c, dict))

    # 后续 @ 触发回合的 prepare 上下文包含旁听消息
    prepared = await main.conversations.prepare(chat_key, "总结一下", persist=False)
    seen = "\n".join(
        str(m.get("content") or "") for m in prepared.get("contexts", []) if isinstance(m, dict)
    )
    assert "拆成一个个小包" in seen
