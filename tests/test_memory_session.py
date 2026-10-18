from QvQChat.session.manager import SessionManager, make_chat_key, parse_chat_key
from QvQChat.session.store import MemoryStore

from fakes import FakeMain


def test_chat_key_roundtrip():
    key = make_chat_key("onebot11", "group", "123")
    assert key == "onebot11:group:123"
    assert parse_chat_key(key) == ("onebot11", "group", "123")
    assert parse_chat_key("broken") == ("", "", "")


def test_session_append_trim_and_reset():
    main = FakeMain(context_limit=3)
    manager = SessionManager(main.sdk, main.cfg)
    key = "test:private:1"
    for i in range(10):
        manager.append(key, "user", f"m{i}")
    contexts = manager.get_contexts(key)
    assert len(contexts) == 6
    assert contexts[-1]["content"] == "m9"
    manager.reset(key)
    assert manager.get_contexts(key) == []


def test_session_persona_pointer_and_list():
    main = FakeMain()
    manager = SessionManager(main.sdk, main.cfg)
    manager.set_persona("a:b:c", "custom")
    assert manager.persona_of("a:b:c") == "custom"
    sessions = manager.list_sessions()
    assert any(s["chat_key"] == "a:b:c" and s["persona"] == "custom" for s in sessions)


def test_memory_remember_dedup_and_cap():
    from QvQChat import texts

    main = FakeMain(memory_max=3)
    store = MemoryStore(main.sdk, main.cfg)
    assert store.remember("s", "用户喜欢蓝色", importance=4) == texts.t("memory_added", count=1)
    assert "跳过" in store.remember("s", "用户喜欢蓝色") or "skipped" in store.remember("s", "用户喜欢蓝色")
    store.remember("s", "用户在杭州")
    store.remember("s", "养了一只猫", importance=2)
    store.remember("s", "第四条记忆", importance=1)
    assert len(store.entries("s")) == 3
    contents = [e["content"] for e in store.entries("s")]
    assert "第四条记忆" not in contents


def test_memory_recall_and_forget():
    main = FakeMain()
    store = MemoryStore(main.sdk, main.cfg)
    store.remember("s", "用户喜欢蓝色")
    store.remember("s", "用户在杭州工作")
    hits = store.recall("s", "喜欢的颜色")
    assert hits and "蓝色" in hits[0]["content"]
    assert store.forget("s", "杭州") == 1
    assert store.forget("s", "不存在的记忆") == 0
    assert len(store.entries("s")) == 1


def test_memory_scopes_and_clear():
    main = FakeMain()
    store = MemoryStore(main.sdk, main.cfg)
    store.remember("a", "x1")
    store.remember("global", "g1")
    scopes = {s["chat_key"] for s in store.list_scopes()}
    assert scopes == {"a", "global"}
    assert store.clear("a") == 1
    assert store.entries("a") == []


def test_label_incoming_group_format():
    main = FakeMain()
    manager = SessionManager(main.sdk, main.cfg)
    assert manager.label_incoming("大家好", sender_id="u1", sender_name="群主") == "群主(u1): 大家好"
    assert manager.label_incoming("大家好", sender_id="u1") == "(u1): 大家好"
    assert manager.label_incoming("大家好") == "大家好"


def test_group_name_cache_roundtrip():
    main = FakeMain()
    manager = SessionManager(main.sdk, main.cfg)
    assert manager.group_name_of("g") == ""
    manager.set_group_name("g", "测试群")
    assert manager.group_name_of("g") == "测试群"


def test_recent_user_messages_cross_session():
    main = FakeMain()
    manager = SessionManager(main.sdk, main.cfg)
    group_key = "onebot11:group:1"
    manager.set_group_name(group_key, "测试群")
    labeled1 = manager.label_incoming("安装云湖适配器", sender_id="u1", sender_name="群主")
    manager.append_user(group_key, labeled1, sender_id="u1")
    manager.append(group_key, "assistant", "好的")
    labeled2 = manager.label_incoming("适配器信息私聊说", sender_id="u1", sender_name="群主")
    manager.append_user(group_key, labeled2, sender_id="u1")

    found = manager.recent_user_messages("u1", exclude_chat_key="onebot11:private:u1")
    assert len(found) == 2
    assert all("测试群" in item["label"] for item in found)
    assert "(u1):" in found[0]["content"]
    assert "私聊说" in found[-1]["content"]

    assert manager.recent_user_messages("nobody") == []
    same_key = manager.recent_user_messages("u1", exclude_chat_key=group_key)
    assert same_key == []


def test_seed_contexts_persists_once():
    main = FakeMain()
    manager = SessionManager(main.sdk, main.cfg)
    seed = [{"role": "user", "content": "历史"}]
    first = manager.seed_contexts("s", seed)
    assert first == seed
    manager.append("s", "user", "新消息")
    stored = manager.get_contexts("s")
    assert stored[0]["content"] == "历史"
    assert stored[-1]["content"] == "新消息"
    again = manager.seed_contexts("s", [{"role": "user", "content": "不该覆盖"}])
    assert again[0]["content"] == "历史"
