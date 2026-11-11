"""线上事故批量根因修复的回归测试。

- eco 工具"广告在、通道不在"：系统提示词点名的工具 schema 回灌（_reinforce_advertised_tools）
- 工具循环进度话术刷屏：中间发言近重复抑制（_is_near_duplicate）
- 停止指令被预算/队列吞掉：纯停止词免判定硬中断（_is_stop_phrase）
- 模型发明 [recall] 语法自纠：recall_message 真通道
- 会话策略进 AI 自管理面：session_settings 读写 policy 四键 + 用量读回
"""
import json

import pytest

from QvQChat.agent.runner import AgentRunner, _is_near_duplicate
from QvQChat.agent.tools import Tool, ToolRegistry
from QvQChat.chat.inbox import _is_stop_phrase
from QvQChat.tools_builtin import erispulse, selfconfig

from fakes import FakeMain, FakeSendChain, make_ctx


@pytest.fixture(autouse=True)
def _zh_texts():
    from ErisPulse.Core import i18n
    from QvQChat import texts as _texts

    _texts.register_texts()
    i18n.set_language("zh-CN")
    yield
    i18n.reset_language()


def test_stop_phrase():
# 命中：纯停止词（含单个"停"、重复、常见语气词后缀）
    for text in ("停", "停停", "停停停", "停停停！", "停止", "停下吧", "住手", "闭嘴啊",
                 "别发了", "取消", "算了", "够了！", "stop", "Stop!", "cancel", " 停 "):
        assert _is_stop_phrase(text), text
# 不命中：长句里带停字/带其他内容的不是停止指令
    for text in ("停下来聊聊", "停一下，我想起个事", "不停的走", "什么时候停",
                 "停止页", "取消订单的入口在哪", "算了算了还是你说吧"):
        assert not _is_stop_phrase(text), text


def test_progress_near_duplicate():
    seen = ["马上就好喵，正在选图喵"]
    assert _is_near_duplicate("马上就好喵，正在发送", seen)
    assert _is_near_duplicate("马上就好喵正在发送", seen)
    assert not _is_near_duplicate("查到了，服务器在巴黎", seen)
    assert not _is_near_duplicate("", seen)


async def test_duplicate_tool_call_short_circuit():
    """同回合同工具+同参数的调用：上次成功 → 短路不再执行（线上事故：同一条
    send_message 发了三遍）；上次失败 → 允许重试。"""
    from QvQChat.engine.base import ToolCall

    calls = []

    async def handler(ctx, **kwargs):
        calls.append(dict(kwargs))
        return "sent ok"

    main = FakeMain()
    registry = ToolRegistry()
    registry.register(Tool(
        name="send_message",
        description="send",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
        access="safe",
        dedupe_success=True,
    ))
    runner = AgentRunner(object(), registry, main.cfg)
    ctx = make_ctx(main)
    memo: dict[str, str] = {}
    call = ToolCall(call_id="c1", name="send_message", arguments={"text": "再来就再来"})
    out, failed = await runner._run_tool(call, ctx, [], call_memo=memo)
    assert failed is False and out == "sent ok" and len(calls) == 1
# 同参数重复：短路执行（handler 不再被打），提示里带上次输出
    out, failed = await runner._run_tool(call, ctx, [], call_memo=memo)
    assert len(calls) == 1 and failed is False and "duplicate call" in out and "sent ok" in out
# 换参数：正常执行
    out, failed = await runner._run_tool(
        ToolCall(call_id="c2", name="send_message", arguments={"text": "别的"}), ctx, [], call_memo=memo,
    )
    assert len(calls) == 2 and out == "sent ok"
# 上次失败的调用允许重试
    async def flaky(ctx, **kwargs):
        calls.append(dict(kwargs))
        raise RuntimeError("boom")

    registry.register(Tool(
        name="flaky_tool",
        description="flaky",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=flaky,
        access="safe",
    ))
    bad = ToolCall(call_id="c3", name="flaky_tool", arguments={})
    await runner._run_tool(bad, ctx, [], call_memo=memo)
    out, failed = await runner._run_tool(bad, ctx, [], call_memo=memo)
    assert failed is True and len(calls) == 4


def _runner_with_eco(access: str = "safe") -> tuple[AgentRunner, FakeMain]:
    async def handler(ctx, **kwargs):
        return "ok"

    main = FakeMain()
    registry = ToolRegistry()
    registry.register(Tool(
        name="eco_QvQMemes_send_sticker",
        description="send a sticker",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
        origin="eco",
        access=access,
    ))
    return AgentRunner(object(), registry, main.cfg), main


def test_reinforce_advertised_tools_restores_channel():
    runner, main = _runner_with_eco()
    ctx = make_ctx(main, admins=["1"], user_id="1")
# 广告在（system 提到工具名）、schema 被裁 → 回灌
    schemas: list = []
    reinforced = runner._reinforce_advertised_tools(
        schemas, "想发表情包可以调 eco_QvQMemes_send_sticker", ctx, None, [],
    )
    assert reinforced == ["eco_QvQMemes_send_sticker"]
    assert schemas[0]["function"]["name"] == "eco_QvQMemes_send_sticker"
# 已在 schema 里的不重复回灌
    reinforced = runner._reinforce_advertised_tools(
        schemas, "eco_QvQMemes_send_sticker", ctx, None, ["eco_QvQMemes_send_sticker"],
    )
    assert reinforced == []
    assert len(schemas) == 1


def test_reinforce_skips_unknown_and_hidden():
    runner, main = _runner_with_eco(access="admin")
# 非管理员：admin 档工具点名也不开通道
    ctx = make_ctx(main, admins=["boss"], user_id="someone")
    schemas: list = []
    reinforced = runner._reinforce_advertised_tools(
        schemas, "调 eco_QvQMemes_send_sticker", ctx, None, [],
    )
    assert reinforced == [] and schemas == []
# 管理员：同一条广告则回灌
    ctx_admin = make_ctx(main, admins=["boss"], user_id="boss")
    reinforced = runner._reinforce_advertised_tools(
        schemas, "调 eco_QvQMemes_send_sticker", ctx_admin, None, [],
    )
    assert reinforced == ["eco_QvQMemes_send_sticker"]
# 已卸载的名字：无从补回也不报错
    reinforced = runner._reinforce_advertised_tools(
        schemas, "eco_Gone_Tool", ctx_admin, None, [],
    )
    assert reinforced == []


async def test_recall_message_tool():
    main = FakeMain()
    main.sdk.adapter.add("test", FakeSendChain())
    registry = ToolRegistry()
    erispulse.register(registry, main)
    assert "recall_message" in {t.name for t in registry.list()}
    ctx = make_ctx(main, chat_key="test:private:9")
# 没有可撤回消息：如实报失败
    out = json.loads(await registry.invoke("recall_message", {}, ctx))
    assert out["ok"] is False
# 有最近发送记录：真撤回（FakeAdapter.call_api 响应 delete_msg）
    main.delivery._last_sent["test:private:9"] = {
        "message_id": -123, "platform": "test", "ts": __import__("time").time(),
    }
    out = json.loads(await registry.invoke("recall_message", {}, ctx))
    assert out["ok"] is True


async def test_session_settings_policy_roundtrip():
    ctx = make_ctx()
    out = json.loads(await selfconfig.session_settings(ctx, action="get"))
    assert out["low_token"] is False and out["session_budget"] == 0
    assert out["priority"] == "normal" and out["muted"] is False
    assert out["usage_today"]["global_tokens"] == 0

    out = json.loads(await selfconfig.session_settings(
        ctx, action="set",
        settings={"low_token": True, "session_budget": 500, "priority": "low"},
    ))
    assert set(out["applied"]) == {"low_token", "session_budget", "priority"}
    out = json.loads(await selfconfig.session_settings(ctx, action="get"))
    assert out["low_token"] is True and out["low_token_active"] is True
    assert out["session_budget"] == 500 and out["priority"] == "low"
    assert out["usage_today"]["session_budget"] == 500

# 字符串布尔容错："false" 不能被 bool() 变成 True
    await selfconfig.session_settings(ctx, action="set", settings={"low_token": "false"})
    out = json.loads(await selfconfig.session_settings(ctx, action="get"))
    assert out["low_token"] is False and out["low_token_active"] is False
