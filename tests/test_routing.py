"""难度感知模型路由（V1 启发式，默认关闭）：engine/router.classify 分级 + pool.dispatch 内改写 prefer。

fake 池沿用 test_model_dispatch 模式：cheap(1.0) < smart(10) < plain(30)，
prefer="cheap" 时 dispatch 应命中 p1:cheap。
"""

import time
from types import SimpleNamespace

from QvQChat.engine.base import ChatRequest, ChatResponse, TaskSpec
from QvQChat.engine.pool import ModelPool
from QvQChat.engine.router import classify

from fakes import FakeSDK, make_config

SMALLTALKS = ["嗯嗯", "哈哈哈哈", "好的", "ok", "😂😂👍", "谢谢啦～"]

# 长文 + 代码块 + 分析关键词（>300 字），quality 的复合强信号
QUALITY_TEXT = (
    "请帮我分析下面这段代码为什么会报错，并总结可能的修复方案：\n```\n"
    + ("def run():\n    return value\n" * 15)
    + "```\n报错信息是 NameError: name 'value' is not defined，我想知道原因和规避写法。"
)

# 中庸长度（60-300 字）、无代码/关键词/工具暗示 → balanced
NEUTRAL_TEXT = (
    "今天下午的会议改到三点了，地点在五楼东侧会议室，参会的人比上次多一些，"
    "记得提前十分钟到场，会上主要围绕下个季度的排期和人员安排过一遍，材料我会前发到群里。"
)

# 工具任务暗示 → 至少 balanced（不下探 cheap）
TOOL_HINT_TEXT = "帮我查一下明天北京的天气怎么样，适合出门吗"


def make_pool(**cfg):
    pool = ModelPool(FakeSDK(), make_config(**cfg))
    pool.save_provider(
        {
            "id": "p1",
            "name": "P1",
            "base_url": "https://x/v1",
            "api_key": "k",
            "models": [
                {"id": "plain", "enabled": True, "tool_call": False,
                 "cost": {"input": 10.0, "output": 20.0}},
                {"id": "smart", "enabled": True, "tool_call": True, "vision": True,
                 "cost": {"input": 5.0, "output": 5.0}},
                {"id": "cheap", "enabled": True, "tool_call": True,
                 "cost": {"input": 0.5, "output": 0.5}},
            ],
        }
    )
    return pool


def fake_engine(pool) -> list:
    requested = []

    async def fake_chat(base_url, api_key, scoped, on_delta=None, on_reset=None, on_reasoning=None):
        requested.append(scoped.model)
        return ChatResponse(content="ok", model=scoped.model)

    pool.engine = SimpleNamespace(chat=fake_chat)
    return requested


def req(text: str) -> ChatRequest:
# 带一条前置 system 消息：路由只看首条 user 消息
    return ChatRequest(
        messages=[{"role": "system", "content": "you are a bot"}, {"role": "user", "content": text}]
    )


# ===== classify：纯函数分级 =====


def test_classify_smalltalk_is_cheap():
    for text in SMALLTALKS:
        decision = classify(text)
        assert decision.prefer == "cheap", text
        assert decision.reason


def test_classify_empty_is_cheap():
    assert classify("").prefer == "cheap"
    assert classify(None).prefer == "cheap"


def test_classify_long_code_analysis_is_quality():
    assert len(QUALITY_TEXT) > 300
    decision = classify(QUALITY_TEXT)
    assert decision.prefer == "quality"
    assert "code" in decision.reason
    assert "long message" in decision.reason


def test_classify_inline_code_is_quality():
    assert classify("run `make build` please").prefer == "quality"


def test_classify_neutral_and_tool_hint_are_balanced():
    assert 60 < len(NEUTRAL_TEXT) < 300
    assert classify(NEUTRAL_TEXT).prefer == "balanced"
# 工具暗示保底 balanced（短消息也不下探 cheap）
    assert classify(TOOL_HINT_TEXT).prefer == "balanced"
# 短消息 + 单个分析关键词：升一档到 balanced 而非 quality
    assert classify("帮我总结一下今天的讨论").prefer == "balanced"


# ===== TaskSpec.chat_key 兼容 =====


def test_taskspec_chat_key_default_and_positional_compat():
    assert TaskSpec().chat_key == ""
    assert TaskSpec().prefer == ""
    assert TaskSpec("chat").kind == "chat"
    spec = TaskSpec(kind="chat", needs=None, prefer="", model=None, chat_key="k1")
    assert spec.chat_key == "k1"


# ===== dispatch：开关与改写 =====


async def test_dispatch_routing_disabled_by_default_no_change():
# make_config 未定义 routing_enabled：getattr 兜底 False，零行为变化
    pool = make_pool()
    requested = fake_engine(pool)
    spec = TaskSpec(kind="chat", chat_key="k1")
    resp = await pool.dispatch(spec, req("嗯嗯"))
    assert requested == ["plain"]# 池序第一个，prefer 未被改写
    assert resp.model == "p1:plain"
    assert spec.prefer == ""
    assert pool.routing_stats == {}
    assert not pool.routing_log


async def test_dispatch_routing_enabled_rewrites_to_cheap():
    pool = make_pool(routing_enabled=True, routing_ttl=300)
    requested = fake_engine(pool)
    spec = TaskSpec(kind="chat", chat_key="k1")
    resp = await pool.dispatch(spec, req("嗯嗯"))
# prefer 改写为 cheap → resolve_task_model 按 cost 升序命中 p1:cheap
    assert spec.prefer == "cheap"
    assert requested == ["cheap"]
    assert resp.model == "p1:cheap"
# 统计与决策日志
    assert pool.routing_stats == {"cheap": 1}
    entry = pool.routing_log[-1]
    assert entry["chat_key"] == "k1"
    assert entry["prefer"] == "cheap"
    assert entry["reason"]
    assert entry["ts"] <= time.time()
    assert any(level == "debug" for level, _ in pool.sdk.logger.records)


async def test_dispatch_routing_quality_labelled_in_log():
    pool = make_pool(routing_enabled=True, routing_ttl=300)
    requested = fake_engine(pool)
    spec = TaskSpec(kind="chat", chat_key="k1")
    await pool.dispatch(spec, req(QUALITY_TEXT))
# V1 中 quality/balanced 仅作标签（排序仍走池序），但分级结果必须留痕
    assert spec.prefer == "quality"
    assert requested == ["plain"]
    assert pool.routing_stats == {"quality": 1}
    assert pool.routing_log[-1]["prefer"] == "quality"


async def test_dispatch_routing_skips_explicit_constraints():
    pool = make_pool(routing_enabled=True, routing_ttl=300)
    requested = fake_engine(pool)
# 显式 model：不改写
    spec = TaskSpec(kind="chat", model="p1:plain", chat_key="k1")
    await pool.dispatch(spec, req("嗯嗯"))
    assert spec.prefer == "" and requested[-1] == "plain"
# needs 约束池：不改写
    spec = TaskSpec(kind="chat", needs=["tool_call"], chat_key="k1")
    await pool.dispatch(spec, req("嗯嗯"))
    assert spec.prefer == "" and requested[-1] == "smart"
# 已有 prefer：不改写（也不重复统计）
    spec = TaskSpec(kind="chat", prefer="cheap", chat_key="k1")
    await pool.dispatch(spec, req(NEUTRAL_TEXT))
    assert spec.prefer == "cheap" and requested[-1] == "cheap"
# 非 chat 任务（compact 等）不参与路由
    spec = TaskSpec(kind="compact", chat_key="k1")
    await pool.dispatch(spec, req("嗯嗯"))
    assert spec.prefer == "" and requested[-1] == "plain"
    assert pool.routing_stats == {}
    assert not pool.routing_log


async def test_dispatch_routing_multimodal_first_user_text():
    pool = make_pool(routing_enabled=True, routing_ttl=300)
    requested = fake_engine(pool)
    request = ChatRequest(
        messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": [{"type": "text", "text": "嗯嗯"}]},
        ]
    )
    spec = TaskSpec(kind="chat", chat_key="k1")
    await pool.dispatch(spec, request)
    assert spec.prefer == "cheap"
    assert requested == ["cheap"]
# 无文本分片（纯图片）：跳过路由
    spec2 = TaskSpec(kind="chat", chat_key="k2")
    request2 = ChatRequest(
        messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "u"}}]}]
    )
    await pool.dispatch(spec2, request2)
    assert spec2.prefer == ""


# ===== TTL 缓存 =====


async def test_routing_ttl_cache_hit_reuses_classification():
    pool = make_pool(routing_enabled=True, routing_ttl=300)
    fake_engine(pool)
    key = TaskSpec(kind="chat", chat_key="k1")
    await pool.dispatch(key, req(QUALITY_TEXT))
    assert pool.routing_log[-1]["prefer"] == "quality"
# 同会话短时间内换寒暄消息：命中缓存，不重复分级
    await pool.dispatch(TaskSpec(kind="chat", chat_key="k1"), req("嗯嗯"))
    assert pool.routing_log[-1]["prefer"] == "quality"
    assert pool.routing_stats == {"quality": 2}
# 不同会话互不影响
    await pool.dispatch(TaskSpec(kind="chat", chat_key="k2"), req("嗯嗯"))
    assert pool.routing_log[-1]["prefer"] == "cheap"
    assert pool.routing_stats == {"quality": 2, "cheap": 1}


async def test_routing_ttl_expiry_reclassifies():
    pool = make_pool(routing_enabled=True, routing_ttl=300)
    fake_engine(pool)
# 伪造已过期的缓存条目
    pool.routing_cache["k1"] = ("quality", "stale", time.time() - 301)
    spec = TaskSpec(kind="chat", chat_key="k1")
    await pool.dispatch(spec, req("嗯嗯"))
    assert spec.prefer == "cheap"
    assert pool.routing_log[-1]["prefer"] == "cheap"
    assert pool.routing_log[-1]["reason"] != "stale"


async def test_routing_ttl_zero_disables_cache():
    pool = make_pool(routing_enabled=True, routing_ttl=0)
    fake_engine(pool)
    await pool.dispatch(TaskSpec(kind="chat", chat_key="k1"), req(QUALITY_TEXT))
    await pool.dispatch(TaskSpec(kind="chat", chat_key="k1"), req("嗯嗯"))
    assert [e["prefer"] for e in pool.routing_log] == ["quality", "cheap"]


async def test_routing_without_chat_key_classifies_each_dispatch():
    pool = make_pool(routing_enabled=True, routing_ttl=300)
    fake_engine(pool)
    await pool.dispatch(TaskSpec(kind="chat"), req(QUALITY_TEXT))
    await pool.dispatch(TaskSpec(kind="chat"), req("嗯嗯"))
    assert [e["prefer"] for e in pool.routing_log] == ["quality", "cheap"]
