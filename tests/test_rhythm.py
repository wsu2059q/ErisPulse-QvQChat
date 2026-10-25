import asyncio
from types import SimpleNamespace

import pytest

from QvQChat.conversation.delivery import (
    Delivery,
    delivery_profile,
    dispatch_text,
    enqueue_pending,
    is_retryable,
    pending_key,
)
from QvQChat.conversation.rhythm import (
    STRUCTURE_FORWARD_RATIO,
    forward_score,
    plan_segments,
    split_sentences,
    structure_signals,
)

from fakes import FakeMain, FakeSendChain


class FixedRng:
    """固定随机源：uniform 恒返回 factor（即延迟抖动乘数），保证确定性。"""

    def __init__(self, factor: float = 1.0):
        self.factor = factor
        self.calls: list[tuple[float, float]] = []

    def uniform(self, low: float, high: float) -> float:
        self.calls.append((low, high))
        return self.factor


class FakePlainEvent:
    """reply 路径测试事件：仅支持 Text，可注入失败次数与异常类型。"""

    def __init__(self, fail_times: int = 0, exc: Exception | None = None):
        self.fail_times = fail_times
        self.exc = exc if exc is not None else asyncio.TimeoutError("send timeout")
        self.attempts = 0
        self.sent: list[str] = []

    def get_platform(self):
        return "onebot11"

    def is_group_message(self):
        return False

    def get_user_id(self):
        return "u9"

    def get_group_id(self):
        return ""

    def supports(self, method):
        return method == "Text"

    async def reply(self, content, method="Text"):
        self.attempts += 1
        if self.fail_times > 0:
            self.fail_times -= 1
            raise self.exc
        self.sent.append(content)


BASE_PROFILE = {
    "sentence_split": False,
    "sentence_max": 80,
    "typing_speed": 10.0,
    "split_jitter": 0.0,
    "total_delay_cap": 100.0,
    "base_delay": 1.0,
    "min_delay": 0.0,
    "max_delay": 100.0,
    "min_length": 5,
    "max_parts": 6,
}


def make_delivery(**config):
    main = FakeMain(**config)
    return main.delivery, main


# ---------- D1 plan_segments ----------

def test_plan_segments_paragraphs_with_typing_delay():
    text = "A" * 30 + "\n\n" + "B" * 40
    segs = plan_segments(text, dict(BASE_PROFILE), rng=FixedRng(1.0))
    assert [t for t, _ in segs] == ["A" * 30, "B" * 40]
    assert segs[0][1] == 0.0
    assert segs[1][1] == pytest.approx(1.0 + 40 / 10.0)


def test_plan_segments_jitter_deterministic():
    profile = dict(BASE_PROFILE, split_jitter=0.35)
    text = "A" * 30 + "\n\n" + "B" * 40
    rng = FixedRng(1.2)
    segs = plan_segments(text, profile, rng=rng)
    assert rng.calls and rng.calls[0] == (0.65, 1.35)
    assert segs[1][1] == pytest.approx((1.0 + 4.0) * 1.2)


def test_plan_segments_delay_clamped_min_max():
    low = plan_segments("A" * 30 + "\n\n" + "B" * 5, dict(BASE_PROFILE, min_delay=2.0), rng=FixedRng(1.0))
    assert low[1][1] == pytest.approx(2.0)
    high = plan_segments("A" * 30 + "\n\n" + "B" * 40, dict(BASE_PROFILE, max_delay=1.0), rng=FixedRng(1.0))
    assert high[1][1] == pytest.approx(1.0)


def test_plan_segments_total_delay_cap_scales_proportionally():
    profile = dict(BASE_PROFILE, total_delay_cap=8.0)
    text = "\n\n".join("X" * 40 for _ in range(5))
    segs = plan_segments(text, profile, rng=FixedRng(1.0))
    assert [d for _, d in segs] == pytest.approx([0.0, 2.0, 2.0, 2.0, 2.0])


def test_plan_segments_max_parts_truncates_with_merged_tail():
    profile = dict(BASE_PROFILE, max_parts=3)
    text = "\n\n".join(f"第{i}段落内容" for i in range(1, 9))
    segs = plan_segments(text, profile, rng=FixedRng(1.0))
    assert len(segs) == 3
    assert segs[0][0] == "第1段落内容"
    assert "第3段落内容" in segs[2][0] and "第8段落内容" in segs[2][0]
    assert segs[2][0].count("\n\n") == 5


def test_split_sentences_packing():
    assert split_sentences("一二三四。五六七八。九十。", 10) == ["一二三四。五六七八。", "九十。"]
    assert split_sentences("短句。", 10) == ["短句。"]
# 无标点超长句保持原样（不切断代码/链接）
    assert split_sentences("无标点的长句子" * 5, 10) == ["无标点的长句子" * 5]


def test_plan_segments_sentence_split_single_paragraph():
    profile = dict(BASE_PROFILE, sentence_split=True, sentence_max=10)
    segs = plan_segments("一二三四。五六七八。九十。", profile, rng=FixedRng(1.0))
    assert [t for t, _ in segs] == ["一二三四。五六七八。", "九十。"]
    assert segs[0][1] == 0.0


def test_plan_segments_sentence_split_inside_long_paragraph():
    profile = dict(BASE_PROFILE, sentence_split=True, sentence_max=12)
    text = "开头引入一句话。\n\n" + "一二三四五。六七八九十。" * 2
    segs = plan_segments(text, profile, rng=FixedRng(1.0))
    texts_ = [t for t, _ in segs]
    assert len(texts_) >= 3
    assert all(len(t) <= 12 for t in texts_[1:])


def test_plan_segments_returns_empty_when_not_splittable():
    assert plan_segments("", dict(BASE_PROFILE)) == []
    assert plan_segments("短文本", dict(BASE_PROFILE)) == []
# 单段长文本未开句切 → 不切分
    assert plan_segments("单段" * 60, dict(BASE_PROFILE)) == []


# ---------- D3 forward_score / structure_signals ----------

def test_forward_score_code_report():
    reply = "代码如下：\n```py\nprint(1)\nprint(2)\n```\n以上就是实现。"
    sig = structure_signals(None, reply)
    assert sig["has_code"] is True
    assert sig["ratio"] > 0.4
    assert sig["score"] >= STRUCTURE_FORWARD_RATIO
    assert sig["report_tone"] is True
    assert forward_score(None, reply) == sig["score"]


def test_forward_score_table_heading_list():
    sig = structure_signals(None, "| a | b |\n|---|---|\n| 1 | 2 |")
    assert sig["has_table"] is True and sig["ratio"] == pytest.approx(1.0)
    sig2 = structure_signals(None, "## 步骤\n1. 打开\n2. 关闭")
    assert sig2["ratio"] == pytest.approx(1.0)


def test_forward_score_chatter_stays_low():
    sig = structure_signals(None, "哈哈，好呀。\n\n那就这样吧，晚点聊～")
    assert sig["score"] < STRUCTURE_FORWARD_RATIO
    assert sig["has_code"] is False and sig["has_table"] is False


def test_forward_score_tool_and_long_text_signals():
    rounds = [
        {"text": "", "tools": [{"tool": "a"}, {"tool": "b"}, {"tool": "c"}, {"tool": "d"}, {"tool": "e"}]},
        {"text": "搞定", "tools": []},
    ]
    sig = structure_signals(rounds, "搞定")
    assert sig["tool_rounds"] == 5
    assert sig["parts"] == 1
    assert sig["score"] == pytest.approx(0.15)
    long_chatter = structure_signals(None, "闲聊" * 400)
    assert long_chatter["length"] > 600
    assert long_chatter["score"] == pytest.approx(0.1)


# ---------- D2 delivery_profile ----------

def test_delivery_profile_defaults_without_config_keys():
    p = delivery_profile(SimpleNamespace(), "onebot11")
    assert p["sentence_split"] is False and p["sentence_max"] == 80
    assert p["typing_speed"] == pytest.approx(25.0) and p["split_jitter"] == pytest.approx(0.35)
    assert p["total_delay_cap"] == pytest.approx(20.0)
    assert p["base_delay"] == pytest.approx(1.2)
    assert p["min_delay"] == pytest.approx(0.5) and p["max_delay"] == pytest.approx(6.0)
    assert p["min_length"] == 120 and p["max_parts"] == 6
    assert p["reply_split"] == "paragraph"
    assert p["forward_min_messages"] == 2 and p["forward_threshold"] == 600


def test_delivery_profile_wildcard_overrides():
    cfg = SimpleNamespace(
        split_delay=1.2,
        delivery_profiles={
            "onebot*": {"base_delay": 0.2, "forward_threshold": 100, "max_parts": 2, "reply_split": "off"},
            "yunhu": {"forward_min_messages": 5},
        },
    )
    hit = delivery_profile(cfg, "onebot11")
    assert hit["base_delay"] == pytest.approx(0.2)
    assert hit["forward_threshold"] == 100 and hit["max_parts"] == 2 and hit["reply_split"] == "off"
    other = delivery_profile(cfg, "yunhu")
    assert other["base_delay"] == pytest.approx(1.2) and other["forward_min_messages"] == 5
    miss = delivery_profile(cfg, "telegram")
    assert miss["base_delay"] == pytest.approx(1.2) and miss["forward_threshold"] == 600


def test_match_platform_semantics():
    from QvQChat.conversation.delivery import match_platform

    assert match_platform("*", "anything")
    assert match_platform("onebot*", "onebot11")
    assert match_platform("yunhu", "yunhu")
    assert not match_platform("yunhu", "onebot11")
    assert not match_platform("one*", "qq")


# ---------- D4 retry / pending queue ----------

def test_is_retryable_classification():
    assert is_retryable(asyncio.TimeoutError("t")) is True
    assert is_retryable(ConnectionError("reset")) is True
    assert is_retryable(RuntimeError("NetworkError while sending")) is True
    assert is_retryable(RuntimeError("invalid arguments")) is False
    assert is_retryable(None) is False


async def test_dispatch_text_success_and_failed_status():
    async def ok_sender(name, content):
        return {"status": "ok", "sent": name}

    used, result, err = await dispatch_text(None, SimpleNamespace(), ok_sender, ["Markdown"], "# hi")
    assert used == "Markdown" and result["sent"] == "Markdown" and err is None

    calls: list[str] = []

    async def failing_status(name, content):
        calls.append(name)
        return {"status": "failed"}

    used2, _, err2 = await dispatch_text(
        None, SimpleNamespace(send_retry=2, retry_delay=0), failing_status, ["Text"], "x"
    )
    assert used2 == "" and err2 is not None
# failed 状态包装为 RuntimeError，非网络类 → 不重试
    assert calls == ["Text"]


async def test_send_plain_retries_timeout_then_succeeds():
    delivery, main = make_delivery(send_retry=1, retry_delay=0)
    event = FakePlainEvent(fail_times=1)
    assert await delivery._send_plain(event, "重试成功") is True
    assert event.attempts == 2
    assert event.sent == ["重试成功"]


async def test_send_plain_no_retry_for_non_network_error():
    delivery, main = make_delivery(send_retry=3, retry_delay=0)
    event = FakePlainEvent(fail_times=99, exc=RuntimeError("bad params"))
    assert await delivery._send_plain(event, "快速失败") is False
    assert event.attempts == 1


async def test_send_plain_failure_enqueued():
    delivery, main = make_delivery(send_retry=0, retry_delay=0)
    event = FakePlainEvent(fail_times=99)
    assert await delivery._send_plain(event, "重要消息") is False
    data = main.sdk.storage.get(pending_key("onebot11:private:u9"))
    assert data and len(data) == 1
    entry = data[0]
    assert entry["text"] == "重要消息"
    assert entry["platform"] == "onebot11" and entry["detail_type"] == "user"
    assert entry["target_id"] == "u9" and entry["ts"] > 0


def test_pending_queue_fifo_eviction():
    delivery, main = make_delivery(pending_send_max=3)
    for i in range(5):
        assert enqueue_pending(main.sdk, main.cfg, "k", {"text": f"m{i}"}) is True
    data = main.sdk.storage.get(pending_key("k"))
    assert [d["text"] for d in data] == ["m2", "m3", "m4"]


async def test_split_mid_failure_queues_rest_without_breaking_sent():
    delivery, main = make_delivery(
        send_retry=0, retry_delay=0, split_min_length=5, split_delay=0,
        min_delay=0, max_delay=0, typing_speed=100000,
    )
    event = FakePlainEvent(fail_times=1)
    await delivery._send_split(event, "第一段甲。\n\n第二段乙。\n\n第三段丙。")
    data = main.sdk.storage.get(pending_key("onebot11:private:u9"))
    assert [d["text"] for d in data] == ["第一段甲。", "第二段乙。", "第三段丙。"]


async def test_replay_pending_success_pops_head():
    delivery, main = make_delivery(send_retry=0, retry_delay=0)
    main.sdk.adapter.add("onebot11", FakeSendChain(sends=("Text",)), sends=("Text",))
    enqueue_pending(main.sdk, main.cfg, "onebot11:private:u9", {
        "platform": "onebot11", "detail_type": "user", "target_id": "u9",
        "text": "补发的消息", "ts": 1.0,
    })
    assert await delivery.replay_pending("onebot11:private:u9") is True
    assert main.sdk.storage.get(pending_key("onebot11:private:u9"), []) == []
    chain = main.sdk.adapter.get("onebot11").Send
    sent = [args for name, args, _ in chain.calls if name == "Text"]
    assert sent and sent[0][0] == "补发的消息"


async def test_replay_pending_failure_keeps_entry():
    delivery, main = make_delivery(send_retry=0, retry_delay=0)
    enqueue_pending(main.sdk, main.cfg, "onebot11:private:u9", {
        "platform": "ghost", "detail_type": "user", "target_id": "u9",
        "text": "补发", "ts": 1.0,
    })
    assert await delivery.replay_pending("onebot11:private:u9") is False
    data = main.sdk.storage.get(pending_key("onebot11:private:u9"))
    assert data and data[0]["text"] == "补发"


async def test_deliver_reply_replays_queue_head_on_first_delivery():
    delivery, main = make_delivery(send_retry=0, retry_delay=0)
    main.sdk.adapter.add("onebot11", FakeSendChain(sends=("Text",)), sends=("Text",))
    enqueue_pending(main.sdk, main.cfg, "onebot11:private:u9", {
        "platform": "onebot11", "detail_type": "user", "target_id": "u9",
        "text": "补发消息", "ts": 1.0,
    })
    event = FakePlainEvent()
    await delivery.deliver_reply(event, "普通回复", [], force=False)
    assert main.sdk.storage.get(pending_key("onebot11:private:u9"), []) == []
    assert "普通回复" in event.sent
# 每进程每个会话只顺带重放一次
    enqueue_pending(main.sdk, main.cfg, "onebot11:private:u9", {
        "platform": "onebot11", "detail_type": "user", "target_id": "u9",
        "text": "第二条", "ts": 2.0,
    })
    event2 = FakePlainEvent()
    await delivery.deliver_reply(event2, "又一条", [], force=False)
    data = main.sdk.storage.get(pending_key("onebot11:private:u9"))
    assert data and data[0]["text"] == "第二条"


# ---------- P0 qvq.deliver hook ----------

async def test_deliver_hook_payload_and_rewrite():
    delivery, main = make_delivery(split_min_length=5, split_delay=0, min_delay=0, max_delay=0)
    captured: list[tuple[str, dict]] = []

    async def fake_emit(name, data=None, **kwargs):
        captured.append((name, data))
        if name == "qvq.deliver":
            rewritten = dict(data)
            rewritten["segments"] = [("改写后的段落", 0.0)]
            return rewritten
        return data

    main.sdk.lifecycle.emit = fake_emit
    event = FakePlainEvent()
    await delivery._send_split(event, "甲段内容。\n\n乙段内容。")
    name, payload = captured[0]
    assert name == "qvq.deliver"
    assert payload["chat_key"] == "onebot11:private:u9"
    assert payload["platform"] == "onebot11"
    assert len(payload["segments"]) == 2
    assert payload["delays"] == [d for _, d in payload["segments"]]
    assert payload["segments"][0] == ("甲段内容。", 0.0)
# 订阅方改写生效
    assert event.sent == ["改写后的段落"]


async def test_deliver_hook_errors_swallowed():
    delivery, main = make_delivery(split_min_length=5, split_delay=0, min_delay=0, max_delay=0)

    async def boom(name, data=None, **kwargs):
        raise RuntimeError("subscriber crashed")

    main.sdk.lifecycle.emit = boom
    event = FakePlainEvent()
    await delivery._send_split(event, "甲段内容。\n\n乙段内容。")
    assert event.sent == ["甲段内容。", "乙段内容。"]


async def test_deliver_hook_accepts_dict_segments():
    delivery, main = make_delivery(split_min_length=5, split_delay=0, min_delay=0, max_delay=0)

    async def fake_emit(name, data=None, **kwargs):
        if name == "qvq.deliver":
            return dict(data, segments=[{"text": "字典项段落", "delay": 0}])
        return data

    main.sdk.lifecycle.emit = fake_emit
    event = FakePlainEvent()
    await delivery._send_split(event, "甲段内容。\n\n乙段内容。")
    assert event.sent == ["字典项段落"]
