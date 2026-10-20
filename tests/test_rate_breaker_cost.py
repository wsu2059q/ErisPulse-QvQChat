import asyncio
import time
from types import SimpleNamespace

from QvQChat.engine.base import ChatRequest, ChatResponse, EngineError
from QvQChat.engine.pool import ModelPool
from QvQChat import texts
from QvQChat.Main import Main
from fakes import FakeChatEvent, FakeSDK, FakeMain, make_config


def make_pool():
    return ModelPool(FakeSDK(), make_config())


async def test_breaker_opens_after_failures_and_skips():
    pool = make_pool()
    requested = []

    async def fake_chat(base_url, api_key, scoped, on_delta=None, on_reset=None):
        requested.append(scoped.model)
        if scoped.model == "bad":
            raise EngineError("boom")
        return ChatResponse(content="ok", model=scoped.model)

    pool.engine = SimpleNamespace(chat=fake_chat)
    provider = {"id": "p1", "name": "P1", "base_url": "https://x/v1", "api_key": "k",
                "models": [{"id": "bad"}, {"id": "good"}]}
    pool.save_provider(provider)

    for _ in range(3):
        try:
            await pool.chat(ChatRequest(messages=[{"role": "user", "content": "hi"}]))
        except EngineError:
            pass
    assert requested.count("bad") == 3
    assert pool._is_open("p1:bad")
    requested.clear()
    await pool.chat(ChatRequest(messages=[{"role": "user", "content": "hi"}]))
    assert "bad" not in requested, "熔断后应跳过冷却模型"


def test_breaker_success_clears():
    pool = make_pool()
    pool._record_fail("m")
    pool._record_fail("m")
    assert pool._is_open("m") is False
    pool._record_fail("m")
    assert pool._is_open("m") is True


def test_record_usage_by_model_structured():
    main = FakeMain()
    main.record_usage("c:private:1", {"total_tokens": 100, "prompt_tokens": 70, "completion_tokens": 30}, model="p:m")
    data = main.sdk.storage.get("QvQChat:usage:" + time.strftime("%Y-%m-%d"), {})
    assert data["by_model"]["p:m"] == {"tokens": 100, "in": 70, "out": 30}


async def test_rate_limit_blocks_flood():
    main = make_rate_main(user_rate_limit=2, aggregate_window=0.01)
    sent = []

    class Ev(FakeChatEvent):
        async def reply(self, content, method="Text"):
            sent.append(content)

    ev = Ev(text="刷屏", group=True, group_id="1", user_id="u9", at=True)
    for _ in range(4):
        await Main._on_message(main, ev)
        await asyncio.sleep(0.06)
    assert len(main.captured) == 2, f"应只放行 2 条，实际 {len(main.captured)}"
    notice = texts.t("rate_limited")
    assert any(notice in s for s in sent)


def make_rate_main(**cfg):
    from test_aggregate import make_main
    return make_main(**cfg)
