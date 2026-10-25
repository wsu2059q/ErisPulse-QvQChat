import asyncio

from QvQChat.conversation.budget import PRIORITY, ContextPacker, SystemPart

from fakes import FakeMain


def big(kind, n, required=False):
    return SystemPart(kind, "字" * n, required=required)


def test_priority_table_order():
    assert [k for k, _ in sorted(PRIORITY.items(), key=lambda kv: kv[1])][0] == "persona"
    assert PRIORITY["persona"] < PRIORITY["capability"] < PRIORITY["scene"] < PRIORITY["summary"]
    assert PRIORITY["summary"] < PRIORITY["facts"] < PRIORITY["memory"] < PRIORITY["kb"]
    assert PRIORITY["kb"] < PRIORITY["skill_full"] < PRIORITY["skill_list"] < PRIORITY["extra"]


def test_pack_drops_low_priority_first():
    packer = ContextPacker()
    parts = [
        SystemPart("persona", "你是助手", required=True),
        SystemPart("capability", "能力说明", required=True),
        SystemPart("scene", "场景"),
        big("extra", 2000),# 优先级最低 → 先丢
        big("kb", 2000),# 其次
    ]
    packed = packer.pack(
        context_length=2000,
        parts=parts,
        history=[{"role": "user", "content": "你好"}],
        user_msg={"role": "user", "content": "在吗"},
        max_output=256,
    )
    stats = packed.stats
    assert stats["dropped"].get("extra") == 1
    assert "你是助手" in packed.system
# 预算 = 2000*0.85 - 256 - 256 = 1188；system 封顶 594
    assert stats["budget"] == 1188
    assert stats["used_system"] <= 594 + 40# 截断标记允许少量开销


def test_pack_required_only_truncated_never_dropped():
    packer = ContextPacker()
    parts = [
        big("persona", 3000, required=True),
        big("capability", 3000, required=True),
    ]
    packed = packer.pack(
        context_length=1000,
        parts=parts,
        history=[],
        user_msg={"role": "user", "content": "hi"},
        max_output=0,
    )
# required 只截不丢：两段都仍在，且带截断标记
    assert "…[truncated]" in packed.system
    assert packed.stats["dropped"] == {}
    assert "字" in packed.system


def test_pack_user_msg_always_kept_and_history_fills_new_to_old():
    packer = ContextPacker()
    history = []
    for i in range(8):
        history.append({"role": "user", "content": f"第{i}轮提问" + "内容" * 60})
        history.append({"role": "assistant", "content": f"第{i}轮回答" + "回复" * 60})
    user_msg = {"role": "user", "content": "最新的问题"}
    packed = packer.pack(
        context_length=1500,
        parts=[SystemPart("persona", "你是助手", required=True)],
        history=history,
        user_msg=user_msg,
        max_output=512,
    )
    messages = packed.messages
    assert messages[-1] is user_msg, "user_msg 必须永远保位"
    assert packed.stats["overflow_turns"] > 0, "小预算下旧轮应被挤掉"
    kept_texts = [m.get("content") for m in messages[:-1]]
    assert "第7轮提问" in str(kept_texts[-2]), "从新到旧装填：最新一轮必须在"
    assert "第0轮提问" not in str(kept_texts), "最旧一轮应被挤掉"
# 装填不溢出时 overflow 为 0
    packed_ok = packer.pack(
        context_length=100000,
        parts=[SystemPart("persona", "你是助手", required=True)],
        history=[{"role": "user", "content": "hi"}],
        user_msg=user_msg,
        max_output=0,
    )
    assert packed_ok.stats["overflow_turns"] == 0
    assert len(packed_ok.messages) == 2


def test_pack_degenerate_budget_passthrough():
    packer = ContextPacker()
    packed = packer.pack(
        context_length=0,
        parts=[SystemPart("persona", "你是助手", required=True)],
        history=[{"role": "user", "content": "hi"}],
        user_msg={"role": "user", "content": "go"},
        max_output=0,
    )
    assert packed.stats.get("degenerate") is True
    assert "你是助手" in packed.system
    assert packed.messages[-1]["content"] == "go"


async def test_prepare_packing_integration():
    main = FakeMain(context_budget_mode="tokens", default_context_length=2000, max_tokens=256)
    spawned = []
    main.spawn = lambda coro: spawned.append(coro)
    manager = main.sessions
    key = "test:private:budget"
    for i in range(10):
        manager.append(key, "user", f"历史问题{i}" + "细节" * 100)
        manager.append(key, "assistant", f"历史回答{i}" + "说明" * 100)
    prepared = await manager.prepare(key, "最新的一条消息")
    assert prepared["user_msg"]["content"] == "最新的一条消息"
    assert prepared["contexts"], "装填后应保留最近若干轮"
    texts = [str(m.get("content")) for m in prepared["contexts"]]
    assert any("历史问题9" in t for t in texts), "最近一轮历史保留"
    assert not any("历史问题0" in t for t in texts), "最旧历史被预算挤出"
# 溢出触发 budget 压缩（spawn 异步执行）
    assert spawned, "装填溢出应 spawn reason=budget 压缩"
    report = await spawned[0]
    assert report.get("reason") == "budget"
# prepare 返回选中的模型（与 runner 选型一致）
    assert "model" in prepared


async def test_prepare_budget_off_keeps_legacy_behavior():
    main = FakeMain()
    manager = main.sessions
    key = "test:private:legacy"
    for i in range(6):
        manager.append(key, "user", f"消息{i}")
    prepared = await manager.prepare(key, "你好")
# off 模式：全部历史照带（发送级轮窗口为 0 不裁剪）
    assert len(prepared["contexts"]) == 6
    assert prepared["user_msg"]["content"] == "你好"
