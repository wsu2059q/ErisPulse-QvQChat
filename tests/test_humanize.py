"""H 系列拟人化核心侧测试：H2 回声过滤与防抖分级。"""
from QvQChat.chat.inbox import debounce_window, is_self_event

from fakes import FakeChatEvent, FakeMain


def make_main(**overrides):
    return FakeMain(**overrides)


 


def test_debounce_window_group_vs_mention():
    cfg = type("C", (), {"aggregate_window": 5.0, "debounce_group_seconds": 2.0, "debounce_mention_seconds": 1.0})()
 
    assert debounce_window(cfg, is_group=False, is_at=False) == 5.0
 
    assert debounce_window(cfg, is_group=True, is_at=False) == 2.0
 
    assert debounce_window(cfg, is_group=True, is_at=True) == 1.0


def test_debounce_window_fallbacks():
    cfg = type("C", (), {"aggregate_window": 5.0, "debounce_group_seconds": 0.0, "debounce_mention_seconds": 0.0})()
 
    assert debounce_window(cfg, is_group=True, is_at=False) == 5.0
    assert debounce_window(cfg, is_group=True, is_at=True) == 5.0


 


def test_self_echo_dropped_by_self_id():
    main = make_main()
 
    ev = FakeChatEvent(text="回声", group=True, group_id="1", user_id="bot")
    assert is_self_event(main.cfg, main.sdk, ev) is True


def test_other_sender_not_dropped():
    main = make_main()
    ev = FakeChatEvent(text="你好", group=True, group_id="1", user_id="u9")
    assert is_self_event(main.cfg, main.sdk, ev) is False


def test_echo_filter_can_be_disabled():
    main = make_main(humanize_echo_filter=False)
    ev = FakeChatEvent(text="回声", group=True, group_id="1", user_id="bot")
    assert is_self_event(main.cfg, main.sdk, ev) is False


 


def test_filter_reply_parrot_detection():
    from QvQChat.conversation.rhythm import filter_reply

    text, action = filter_reply("今天天气不错，你说今天天气不错。", "今天天气不错", 3)
    assert action == "parrot"


def test_filter_reply_trims_sentences():
    from QvQChat.conversation.rhythm import filter_reply

    text, action = filter_reply("一。二。三。四。五。", "别的", 3)
    assert action == "trimmed"
    assert text == "一。二。三。"


def test_filter_reply_strips_trailing_question():
    from QvQChat.conversation.rhythm import filter_reply

 
    text, action = filter_reply("我吃了。你吃了吗？还要去哪？", "在干嘛", 5)
    assert action == "trimmed"
    assert text == "我吃了。你吃了吗？"


def test_filter_reply_passes_normal():
    from QvQChat.conversation.rhythm import filter_reply

    text, action = filter_reply("正常回答，一句话讲完。", "在干嘛", 3)
    assert action == "pass"
    assert text == "正常回答，一句话讲完。"
