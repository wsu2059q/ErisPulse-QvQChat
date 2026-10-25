"""存储索引化：conv_index 对账/自愈、create/delete 维护、跨天 prune 一次、user_seen 倒排。"""
import time

from QvQChat.conversation.service import (
    CONV_INDEX_KEY,
    CONV_PREFIX,
    USER_SEEN_PREFIX,
    ConversationService,
)
from fakes import FakeMain, FakeStorage


class CountingStorage(FakeStorage):
    """记录 keys() 调用次数的 FakeStorage（验证全扫只发生一次）。"""

    def __init__(self, data=None):
        super().__init__()
        if data is not None:
            self._data = data
        self.keys_calls = 0

    def keys(self):
        self.keys_calls += 1
        return super().keys()


def test_index_selfheal_after_manual_delete():
    main = FakeMain()
    manager = ConversationService(main)
    manager.append("g:group:1", "user", "hi")
    manager.append("g:group:2", "user", "yo")
    assert set(main.sdk.storage.get(CONV_INDEX_KEY)) == {"g:group:1", "g:group:2"}
# 手工删除索引键（模拟损坏）→ list_sessions 回退扫描并自愈重建
    main.sdk.storage.delete(CONV_INDEX_KEY)
    sessions = manager.list_sessions()
    assert {s["chat_key"] for s in sessions} == {"g:group:1", "g:group:2"}
    assert set(main.sdk.storage.get(CONV_INDEX_KEY)) == {"g:group:1", "g:group:2"}


def test_index_selfheal_after_corrupt():
    main = FakeMain()
    manager = ConversationService(main)
    manager.append("g:group:1", "user", "hi")
    main.sdk.storage.set(CONV_INDEX_KEY, "not-a-list")# 损坏
    sessions = manager.list_sessions()
    assert {s["chat_key"] for s in sessions} == {"g:group:1"}
    assert main.sdk.storage.get(CONV_INDEX_KEY) == ["g:group:1"]


def test_index_reconciles_legacy_sessions_on_first_list():
    """旧会话（无索引直接写 state 键）在首次 list_sessions 对账后进索引。"""
    main = FakeMain()
    manager = ConversationService(main)
# 模拟升级前数据：绕过 service 直接写会话键
    main.sdk.storage.set(CONV_PREFIX + "onebot11:group:9", {"contexts": [{"role": "user", "content": "旧消息"}]})
    main.sdk.storage.set(CONV_PREFIX + "dash:private:x", {"contexts": []})
    assert main.sdk.storage.get(CONV_INDEX_KEY, None) is None
    sessions = manager.list_sessions()
    assert {s["chat_key"] for s in sessions} == {"onebot11:group:9", "dash:private:x"}
    assert set(main.sdk.storage.get(CONV_INDEX_KEY)) == {"onebot11:group:9", "dash:private:x"}
# 对账只做一次：再 list 不再触发 keys() 全扫（索引有效即直接用）
    storage = CountingStorage(main.sdk.storage._data)
    main.sdk.storage = storage
    manager.sdk = main.sdk
    manager.list_sessions()
    assert storage.keys_calls == 0


def test_create_delete_maintain_index():
    main = FakeMain()
    manager = ConversationService(main)
    key1 = manager.create("dashboard", "private")
    manager.append(key1, "user", "hello")# 非空后 create 才会另开新 web 会话
    key2 = manager.create("dashboard", "private")
    assert key1 != key2
    assert set(main.sdk.storage.get(CONV_INDEX_KEY)) == {key1, key2}
# reset 保留 state（只清空内容）→ 索引不动
    manager.reset(key1)
    assert key1 in main.sdk.storage.get(CONV_INDEX_KEY)
    assert manager.list_sessions() and any(s["chat_key"] == key1 for s in manager.list_sessions())
# delete 彻底删除 → 索引移除
    assert manager.delete(key1) is True
    assert main.sdk.storage.get(CONV_INDEX_KEY) == [key2]
    assert all(s["chat_key"] != key1 for s in manager.list_sessions())
# 再删不报错、索引不变
    assert manager.delete(key1) is False
    assert main.sdk.storage.get(CONV_INDEX_KEY) == [key2]


def test_prune_usage_runs_once_per_day():
    main = FakeMain()
    old_key = "QvQChat:usage:2020-01-01"
    main.sdk.storage.set(old_key, {"tokens": 1})
    storage = CountingStorage(main.sdk.storage._data)
    main.sdk.storage = storage
    today = time.strftime("%Y-%m-%d")
    main.record_usage("c:private:1", {"total_tokens": 10}, model="p:m")
    assert main.sdk.storage.get(old_key, None) is None, "过期用量应被清理"
    assert main.sdk.storage.get("QvQChat:usage:last_prune") == today
    scans_after_first = storage.keys_calls
    assert scans_after_first >= 1
# 同日后续记账：不再全扫
    main.record_usage("c:private:1", {"total_tokens": 10}, model="p:m")
    assert storage.keys_calls == scans_after_first, "同一天只应扫一次"
# 跨天（模拟标记为昨天）：再次执行一次清理
    main.sdk.storage.set("QvQChat:usage:last_prune", "2000-01-01")
    main.record_usage("c:private:1", {"total_tokens": 10}, model="p:m")
    assert storage.keys_calls > scans_after_first, "跨天后应再执行一次"


def test_prune_usage_marker_not_deleted_by_scan():
    """last_prune 键自身带 QvQChat:usage: 前缀，扫描不得误删。"""
    main = FakeMain()
    today = time.strftime("%Y-%m-%d")
    main.sdk.storage.set("QvQChat:usage:last_prune", "2000-01-01")
    main.record_usage("c:private:1", {"total_tokens": 10})
    assert main.sdk.storage.get("QvQChat:usage:last_prune") == today


def test_user_seen_inverted_maintained_on_group_messages():
    main = FakeMain()
    manager = ConversationService(main)
    manager.append_user("onebot11:group:1", "群主(u1): 你好", sender_id="u1")
    seen = main.sdk.storage.get(USER_SEEN_PREFIX + "u1")
    assert isinstance(seen, list) and seen[0]["chat_key"] == "onebot11:group:1"
    assert seen[0]["head"] == "群主(u1): 你好"
# 私聊不入倒排（recent_user_messages 只查群）
    manager.append_user("onebot11:private:u1", "私聊内容", sender_id="u1")
    seen = main.sdk.storage.get(USER_SEEN_PREFIX + "u1")
    assert [i["chat_key"] for i in seen] == ["onebot11:group:1"]
# 同群再发言：去重、新在前
    manager.append_user("onebot11:group:2", "u1 在群2", sender_id="u1")
    manager.append_user("onebot11:group:1", "群主(u1): 又发言", sender_id="u1")
    seen = main.sdk.storage.get(USER_SEEN_PREFIX + "u1")
    assert [i["chat_key"] for i in seen] == ["onebot11:group:1", "onebot11:group:2"]


def test_recent_user_messages_via_inverted_index():
    main = FakeMain()
    manager = ConversationService(main)
    group_key = "onebot11:group:1"
    manager.set_group_name(group_key, "测试群")
    manager.append_user(group_key, "群主(u1): 安装云湖适配器", sender_id="u1")
    manager.append(group_key, "assistant", "好的")
    manager.append_user(group_key, "群主(u1): 适配器信息私聊说", sender_id="u1")
# 倒排存在：走倒排路径
    found = manager.recent_user_messages("u1", exclude_chat_key="onebot11:private:u1")
    assert len(found) == 2
    assert all("测试群" in item["label"] for item in found)
    assert "(u1):" in found[0]["content"]
# 排除群本身后为空
    assert manager.recent_user_messages("u1", exclude_chat_key=group_key) == []


def test_recent_user_messages_fallback_without_inverted():
    """倒排缺失（旧数据）：回退旧 keys() 全扫仍可命中。"""
    main = FakeMain()
    manager = ConversationService(main)
    group_key = "onebot11:group:7"
    manager.append_user(group_key, "群主(u1): 旧消息", sender_id="u1")
    main.sdk.storage.delete(USER_SEEN_PREFIX + "u1")
    found = manager.recent_user_messages("u1", exclude_chat_key="onebot11:private:u1")
    assert len(found) == 1
    assert "旧消息" in found[0]["content"]
