"""bot 互聊（拟人化）：兄弟 bot 的消息默认可参与对话（连锁 3 轮收口）；
关闭开关只旁听；同账户重复投递去重不影响跨账户各回各的。"""

import asyncio

from QvQChat.Main import Main

from fakes import FakeChatEvent


def make_main(**overrides):
    from test_aggregate import make_main as base

    overrides.setdefault("aggregate_window", 0.01)
    return base(**overrides)


def _setup_bots(main):
    main.sdk.adapter.bots = {"amer": {"status": "running"}, "iris": {"status": "running"}}


async def _send(main, account, user_id, text, at=True):
    ev = FakeChatEvent(
        text=text, group=True, group_id="1", user_id=user_id,
        user_name=user_id, at=at, account=account,
    )
    await Main._on_message(main, ev)
    await asyncio.sleep(0.3)
    return ev


async def test_sibling_mention_triggers_reply():
    """用户 @ amer → amer 回；之后 iris（兄弟 bot）@ amer → 互聊触发。"""
    main = make_main()
    _setup_bots(main)
    await _send(main, "amer", "user1", "都出来玩", at=True)
    assert len(main.captured) == 1
    await _send(main, "amer", "iris", "带我一个喵", at=True)
    assert len(main.captured) == 2


async def test_chain_cap_after_three_rounds():
    """连续兄弟 bot 触发超过 3 轮：收口不回，等真人发言重置。"""
    main = make_main()
    _setup_bots(main)
    await _send(main, "amer", "user1", "开工", at=True)  # 真人
    for i in range(3):
        await _send(main, "amer", "iris", f"聊第{i}句", at=True)
    assert len(main.captured) == 4  # 真人 1 + 兄弟 3
    await _send(main, "amer", "iris", "第四句还想聊", at=True)
    assert len(main.captured) == 4  # 第 4 轮被收口
    await _send(main, "amer", "user1", "我来啦", at=True)  # 真人重置
    assert len(main.captured) == 5


async def test_cross_talk_off_lurks_siblings():
    main = make_main(bot_cross_talk=False)
    _setup_bots(main)
    await _send(main, "amer", "user1", "开工", at=True)
    n = len(main.captured)
    await _send(main, "amer", "iris", "带我玩", at=True)
    assert len(main.captured) == n  # 兄弟 bot 消息只旁听


async def test_observe_payload_marks_sibling():
    main = make_main()
    _setup_bots(main)
    await _send(main, "amer", "iris", "在吗", at=True)
    payload = next(d for e, d in main.sdk.lifecycle.emitted if e == "qvq.observe")
    assert payload["sender_is_bot"] is True


async def test_same_account_duplicate_dropped():
    main = make_main()
    _setup_bots(main)
    await _send(main, "amer", "user1", "查个角色", at=True)
    n = len(main.captured)
    ev2 = FakeChatEvent(text="查个角色", group=True, group_id="1", user_id="user1",
                        at=True, account="amer")
    ev2.get = lambda key, default=None: {"message_id": "M123"}.get(key, default)
    await Main._on_message(main, ev2)  # 同 message_id：适配器重试，丢弃
    assert len(main.captured) == n
# 新 message_id + 新文本 = 人类新消息：正常回答（同文本 6 秒内会被既有重复保护拦截，属预期）
    ev3 = FakeChatEvent(text="查个角色第二章", group=True, group_id="1", user_id="user1",
                        at=True, account="amer")
    ev3.get = lambda key, default=None: {"message_id": "M124"}.get(key, default)
    await Main._on_message(main, ev3)
    await asyncio.sleep(0.3)
    assert len(main.captured) == n + 1, main.logger.records[-6:]


async def test_two_accounts_each_reply():
    """两个账户各收一份各自回（预期行为，不互相压制）。"""
    main = make_main()
    _setup_bots(main)
    await _send(main, "amer", "user1", "都来查这个角色", at=True)
    await _send(main, "iris", "user1", "都来查这个角色", at=True)
    assert len(main.captured) == 2, main.logger.records[-6:]


async def test_external_bots_list_recognized_as_sibling():
    """外部 bot 名单：别家后端的 bot id（纯 id / platform:id）按 bot 信号认定。"""
    main = make_main()
    main.cfg.external_bots = ["999888", "snowluma:777666"]
    ev_out = FakeChatEvent(text="签到出凶了", user_id="999888", at=False)
    assert main._is_sibling_bot(ev_out, "999888") is True
    ev_prefixed = FakeChatEvent(text="骰子", user_id="777666", at=False, platform="snowluma")
    assert main._is_sibling_bot(ev_prefixed, "777666") is True
# 平台不匹配的带前缀条目不算
    ev_wrong = FakeChatEvent(text="hi", user_id="777666", at=False, platform="qqbot")
    assert main._is_sibling_bot(ev_wrong, "777666") is False
# 名单外的普通用户
    ev_human = FakeChatEvent(text="今天好累", user_id="human1", at=False)
    assert main._is_sibling_bot(ev_human, "human1") is False
