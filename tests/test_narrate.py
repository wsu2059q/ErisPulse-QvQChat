"""边做边说（reply_narrate）模式：提示词注入 + 中间口播独立于 tool_notice_mode 投递。"""

import asyncio

from QvQChat.Main import Main
from QvQChat.prompts import NARRATE_PROMPT

from fakes import FakeChatEvent, FakeMain


def _build_system(main, chat_key="onebot11:group:1"):
    persona = main.personas.resolve(chat_key)
    return main.sessions.build_system(chat_key=chat_key, persona=persona)


def test_narrate_prompt_injected_when_enabled():
    main = FakeMain(reply_narrate=True)
    system = _build_system(main)
    assert NARRATE_PROMPT[:40] in system


def test_narrate_prompt_absent_when_disabled():
    main = FakeMain(reply_narrate=False)
    system = _build_system(main)
    assert NARRATE_PROMPT[:40] not in system


def _make_processing_main(**overrides):
    """复用 test_aggregate 的 make_main 驱动完整 _on_message，runner 主动调用 on_intermediate。"""
    import inspect

    from test_aggregate import make_main

    main = make_main(**overrides)

    class NarrateRunner:
        def __init__(self):
            self.calls = []

        async def run(self, *, on_intermediate=None, **kwargs):
            self.calls.append(kwargs)
            if on_intermediate is not None:
                result = on_intermediate("我查一下这个账号，先看看是真的再下判断")
                if asyncio.iscoroutine(result):
                    await result
            return type("R", (), {"text": "结论：账号确实是 404", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = NarrateRunner()
    main.narrate_runner = main.runner
    return main


async def test_intermediate_speech_sent_in_narrate_mode():
    main = _make_processing_main(reply_narrate=True, aggregate_window=0.05, tool_notice_mode="brief")
    ev = FakeChatEvent(text="查一下他的GitHub", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    narrations = [r for r in ev.replies if "先看看是真的" in str(r)]
    assert narrations, f"narrate 开启时中间口播应直达群里, replies={ev.replies}"


async def test_intermediate_speech_not_sent_when_narrate_off():
    main = _make_processing_main(reply_narrate=False, aggregate_window=0.05, tool_notice_mode="brief")
    ev = FakeChatEvent(text="查一下他的GitHub", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert not any("先看看是真的" in str(r) for r in ev.replies)


async def test_intermediate_speech_sent_when_notice_all():
    """原 tool_notice_mode=all 行为保留。"""
    main = _make_processing_main(aggregate_window=0.05, tool_notice_mode="all")
    ev = FakeChatEvent(text="查一下", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert any("先看看是真的" in str(r) for r in ev.replies)


async def test_passive_failure_silent_by_default():
    """被动任务（origin=plugin）失败默认静默：不把错误详情回进群里。"""
    import asyncio

    from test_aggregate import make_main as aggregate_make_main

    class FailingRunner:
        async def run(self, **kwargs):
            raise RuntimeError("全部模型调用失败 Error 429")

    main = aggregate_make_main(aggregate_window=0.05)
    main.runner = FailingRunner()
    ev = FakeChatEvent(text="查一下", group=True, group_id="1", user_id="u2", user_name="活塞头", at=True)
    # 模拟插件插话来源
    main._pending.clear()
    main._batch_message(ev, "onebot11:group:1", "查一下", [], origin="plugin")
    await asyncio.sleep(0.15)
    assert not ev.replies, f"被动失败不应回复群聊, replies={ev.replies}"
    assert main.logger.records and any("process failed" in str(r) for r in main.logger.records)


async def test_active_failure_still_replies():
    """主动触发失败仍回复错误（用户发起了消息，应当收到反馈）。"""
    import asyncio

    from test_aggregate import make_main as aggregate_make_main

    class FailingRunner:
        async def run(self, **kwargs):
            raise RuntimeError("boom")

    main = aggregate_make_main(aggregate_window=0.05)
    main.runner = FailingRunner()
    ev = FakeChatEvent(text="查一下", group=True, group_id="1", user_id="u2", user_name="活塞头", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert any("boom" in str(r) for r in ev.replies), f"主动失败应回复, replies={ev.replies}"
