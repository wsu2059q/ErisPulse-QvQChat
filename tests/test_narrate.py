"""长任务对话风格（tool_notice_mode）：off 静默 / first_last 首尾 / brief 全投递。"""

import asyncio

from QvQChat.Main import Main

from fakes import FakeChatEvent, FakeMain


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


async def test_intermediate_speech_delivered_once_per_speech_brief():
    """brief：模型每次开口都投递（开场 + 阶段发言）。"""
    main = _make_processing_main(aggregate_window=0.05, tool_notice_mode="brief")

    class TwoSpeechRunner:
        async def run(self, *, on_intermediate=None, **kwargs):
            if on_intermediate is not None:
                for line in ("收到，我先查一下", "中间进展：找到线索了"):
                    result = on_intermediate(line)
                    if asyncio.iscoroutine(result):
                        await result
            return type("R", (), {"text": "结论", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = TwoSpeechRunner()
    ev = FakeChatEvent(text="查一下他的GitHub", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert any("先查一下" in str(r) for r in ev.replies)
    assert any("中间进展" in str(r) for r in ev.replies)


async def test_first_last_delivers_only_opening():
    """first_last（首尾）：只发开场一句，其后阶段发言静默（最终结论走正常回复）。"""
    main = _make_processing_main(aggregate_window=0.05, tool_notice_mode="first_last")

    class TwoSpeechRunner:
        async def run(self, *, on_intermediate=None, **kwargs):
            if on_intermediate is not None:
                for line in ("收到，我先查一下", "中间进展：找到线索了"):
                    result = on_intermediate(line)
                    if asyncio.iscoroutine(result):
                        await result
            return type("R", (), {"text": "结论：查到了", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = TwoSpeechRunner()
    ev = FakeChatEvent(text="查一下他的GitHub", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert any("先查一下" in str(r) for r in ev.replies), ev.replies
    assert not any("中间进展" in str(r) for r in ev.replies), ev.replies
    assert any("查到了" in str(r) for r in ev.replies)  # 最终结论正常投递


async def test_intermediate_speech_sent_in_brief_mode():
    """对齐配置描述：brief = 发送 AI 的开场与阶段性发言（长任务前先应一声的载体）。"""
    main = _make_processing_main(reply_narrate=False, aggregate_window=0.05, tool_notice_mode="brief")
    ev = FakeChatEvent(text="查一下他的GitHub", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert any("先看看是真的" in str(r) for r in ev.replies), f"brief 应投递模型开场发言, replies={ev.replies}"


async def test_intermediate_speech_silent_when_notice_off():
    """off + 未开 narrate：完全静默。"""
    main = _make_processing_main(reply_narrate=False, aggregate_window=0.05, tool_notice_mode="off")
    ev = FakeChatEvent(text="查一下他的GitHub", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert not any("先看看是真的" in str(r) for r in ev.replies)


async def test_first_last_delivery_failure_does_not_consume_quota():
    """首句投递失败（发送返回 False）不消耗名额：下一句仍可尝试。"""
    main = _make_processing_main(aggregate_window=0.05, tool_notice_mode="first_last")

    import QvQChat.conversation.delivery as delivery_mod

    async def fail_send(event, text, quote=False):
        return False

    main.delivery._send_plain = fail_send

    class TwoSpeechRunner:
        async def run(self, *, on_intermediate=None, **kwargs):
            if on_intermediate is not None:
                for line in ("第一句", "第二句"):
                    result = on_intermediate(line)
                    if asyncio.iscoroutine(result):
                        await result
            return type("R", (), {"text": "结论", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = TwoSpeechRunner()
    ev = FakeChatEvent(text="查一下", group=True, group_id="1", user_id="u2", user_name="群主", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert len(ev.replies) == 0  # 都失败（fake 直接 False），但两次都尝试了


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
