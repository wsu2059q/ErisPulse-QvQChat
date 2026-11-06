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
    main = _make_inbox(group_isolation=True)
    ev = FakeChatEvent(text="hi", group=True, group_id="1", user_id="9", at=True)
    assert Main._chat_key_of(main, ev) == "onebot11:group:1:u9"


def test_chat_key_of_without_isolation():
    main = _make_inbox(group_isolation=False)
    ev = FakeChatEvent(text="hi", group=True, group_id="1", user_id="u9", at=True)
    assert Main._chat_key_of(main, ev) == "onebot11:group:1"


# ===== 单适配器多账户隔离（@账户 后缀）=====

class FakeSelfEvent:
    """携带接收账户信息的事件替身。"""

    def __init__(self, platform="onebot11", group="123", user="u9", account="bot_a", is_group=True):
        self._p, self._g, self._u, self._acc, self._ig = platform, group, user, account, is_group

    def get_platform(self):
        return self._p

    def is_group_message(self):
        return self._ig

    def get_group_id(self):
        return self._g

    def get_user_id(self):
        return self._u

    def get_self_account_id(self):
        return self._acc


def _make_inbox(**cfg):

    return FakeMain(**cfg)


def test_account_suffix_appended_when_enabled():
    main = _make_inbox(account_isolation=True)
    main.sdk.adapter.bots = {"bot_a": {}, "bot_b": {}}
    ev = FakeSelfEvent()
    key = Main._chat_key_of(main, ev)
    assert key == "onebot11:group:123@bot_a"


def test_account_suffix_absent_when_disabled():
    main = _make_inbox(account_isolation=False)
    main.sdk.adapter.bots = {"bot_a": {}, "bot_b": {}}
    assert Main._chat_key_of(main, FakeSelfEvent()) == "onebot11:group:123"


def test_account_suffix_absent_for_single_bot():
    """单账户适配器自动不加后缀：存量会话/人格/记忆无缝保留。"""
    main = _make_inbox(account_isolation=True)
    assert Main._chat_key_of(main, FakeSelfEvent()) == "onebot11:group:123"


def test_two_accounts_same_group_distinct_keys():
    main = _make_inbox(account_isolation=True)
    main.sdk.adapter.bots = {"bot_a": {}, "bot_b": {}}
    ka = Main._chat_key_of(main, FakeSelfEvent(account="bot_a"))
    kb = Main._chat_key_of(main, FakeSelfEvent(account="bot_b"))
    assert ka != kb


def test_account_with_group_isolation_combined():
    main = _make_inbox(account_isolation=True, group_isolation=True)
    main.sdk.adapter.bots = {"bot_a": {}, "bot_b": {}}
    key = Main._chat_key_of(main, FakeSelfEvent(user="u9", account="bot_a"))
    assert key == "onebot11:group:123:uu9@bot_a"


def test_strip_account_for_send_target():
    from QvQChat.conversation.service import strip_account, account_of

    assert strip_account("onebot11:group:123@bot_a") == "onebot11:group:123"
    assert account_of("onebot11:group:123@bot_a") == "bot_a"
    assert strip_account("onebot11:group:123") == "onebot11:group:123"
    assert account_of("onebot11:group:123") == ""
    # 群成员隔离组合形态
    assert strip_account("onebot11:group:123:u9@bot_a") == "onebot11:group:123:u9"
    # 目标 id 本身含 @ 的极端情况不受影响（@ 在最后一段才视为账户分隔）
    assert strip_account("onebot11:group:a@b:c") == "onebot11:group:a@b:c"


def test_delivery_event_chat_key_matches_inbox():
    from QvQChat.conversation.delivery import Delivery
    from fakes import FakeLogger, FakeSDK

    sdk = FakeSDK()
    sdk.adapter.bots = {"bot_a": {}, "bot_b": {}}
    harness = type("H", (), {"cfg": _make_inbox().cfg, "sdk": sdk, "logger": FakeLogger()})()
    delivery = Delivery(harness)
    assert delivery._event_chat_key(FakeSelfEvent()) == "onebot11:group:123@bot_a"
