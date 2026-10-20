from types import SimpleNamespace

from QvQChat.conversation.service import make_chat_key, parse_chat_key, strip_isolation
from QvQChat.Main import Main
from fakes import FakeChatEvent, FakeMain


def test_strip_isolation_group_and_private():
    isolated = make_chat_key("onebot11", "group", "1:u9")
    assert strip_isolation(isolated) == "onebot11:group:1"
    assert strip_isolation("onebot11:private:u1") == "onebot11:private:u1"
    assert strip_isolation("onebot11:group:1") == "onebot11:group:1"
    assert parse_chat_key(strip_isolation(isolated)) == ("onebot11", "group", "1")


def test_chat_key_of_with_isolation():
    main = FakeMain(group_isolation=True)
    ev = FakeChatEvent(text="hi", group=True, group_id="1", user_id="9", at=True)
    assert Main._chat_key_of(main, ev) == "onebot11:group:1:u9"


def test_chat_key_of_without_isolation():
    main = FakeMain(group_isolation=False)
    ev = FakeChatEvent(text="hi", group=True, group_id="1", user_id="u9", at=True)
    assert Main._chat_key_of(main, ev) == "onebot11:group:1"
