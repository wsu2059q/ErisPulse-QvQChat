import asyncio

from QvQChat.conversation.service import ConversationService, make_chat_key, parse_chat_key
from QvQChat.conversation.memory import MemoryStore

from fakes import FakeMain


def test_chat_key_roundtrip():
    key = make_chat_key("onebot11", "group", "123")
    assert key == "onebot11:group:123"
    assert parse_chat_key(key) == ("onebot11", "group", "123")
    assert parse_chat_key("broken") == ("", "", "")


def test_session_append_trim_and_reset():
    main = FakeMain(context_limit=3)
    manager = ConversationService(main)
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
    manager = ConversationService(main)
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
    manager = ConversationService(main)
    assert manager.label_incoming("大家好", sender_id="u1", sender_name="群主") == "群主(u1): 大家好"
    assert manager.label_incoming("大家好", sender_id="u1") == "(u1): 大家好"
    assert manager.label_incoming("大家好") == "大家好"


def test_group_name_cache_roundtrip():
    main = FakeMain()
    manager = ConversationService(main)
    assert manager.group_name_of("g") == ""
    manager.set_group_name("g", "测试群")
    assert manager.group_name_of("g") == "测试群"


def test_recent_user_messages_cross_session():
    main = FakeMain()
    manager = ConversationService(main)
    group_key = "onebot11:group:1"
    manager.set_group_name(group_key, "测试群")
    labeled1 = manager.label_incoming("安装云湖适配器", sender_id="u1", sender_name="群主")
    manager.append_user(group_key, labeled1, sender_id="u1")
    manager.append(group_key, "assistant", "好的")
    labeled2 = manager.label_incoming("适配器信息私聊说", sender_id="u1", sender_name="群主")
    manager.append_user(group_key, labeled2, sender_id="u1")

# append_user 已维护 user_seen 倒排 → 本查询走倒排路径
    seen = main.sdk.storage.get("QvQChat:user_seen:u1")
    assert isinstance(seen, list) and seen[0]["chat_key"] == group_key

    found = manager.recent_user_messages("u1", exclude_chat_key="onebot11:private:u1")
    assert len(found) == 2
    assert all("测试群" in item["label"] for item in found)
    assert "(u1):" in found[0]["content"]
    assert "私聊说" in found[-1]["content"]

    assert manager.recent_user_messages("nobody") == []
    same_key = manager.recent_user_messages("u1", exclude_chat_key=group_key)
    assert same_key == []


def test_recent_user_messages_fallback_scan():
    """倒排键缺失（旧数据）时回退旧 keys() 全扫，结果一致。"""
    main = FakeMain()
    manager = ConversationService(main)
    group_key = "onebot11:group:1"
    manager.set_group_name(group_key, "测试群")
    manager.append_user(group_key, "群主(u1): 安装云湖适配器", sender_id="u1")
    manager.append_user(group_key, "群主(u1): 适配器信息私聊说", sender_id="u1")
    main.sdk.storage.delete("QvQChat:user_seen:u1")# 模拟倒排缺失

    found = manager.recent_user_messages("u1", exclude_chat_key="onebot11:private:u1")
    assert len(found) == 2
    assert all("测试群" in item["label"] for item in found)
    assert manager.recent_user_messages("u1", exclude_chat_key=group_key) == []


def test_seed_contexts_persists_once():
    main = FakeMain()
    manager = ConversationService(main)
    seed = [{"role": "user", "content": "历史"}]
    first = manager.seed_contexts("s", seed)
    assert first == seed
    manager.append("s", "user", "新消息")
    stored = manager.get_contexts("s")
    assert stored[0]["content"] == "历史"
    assert stored[-1]["content"] == "新消息"
    again = manager.seed_contexts("s", [{"role": "user", "content": "不该覆盖"}])
    assert again[0]["content"] == "历史"


# ===== 摘要合并压缩与 facts =====


async def test_append_summary_over_cap_fallback_keeps_head_and_tail():
    main = FakeMain(summary_cap=100)
    manager = ConversationService(main)
    key = "s"
    old = "头部身份信息：用户是张三，在杭州工作。" * 10# 远超 cap
    manager.append_summary(key, old)
    new = "新增内容，尾部待办：周五前交付报告。" * 5
    manager.append_summary(key, new)
    summary = manager.summary_of(key)
# 兜底合并不丢头尾：头 60% + 省略标记 + 尾 40%
    assert "头部身份信息" in summary, "头部（含身份/长期事实）不能丢"
    assert "周五前交付报告" in summary, "尾部新增内容不能丢"
    assert "…[中段省略]…" in summary
    assert len(summary) <= 100 + 60# 头尾 + 标记的少量开销


async def test_append_summary_over_cap_llm_merge_replaces_fallback():
    from QvQChat.engine.base import ChatResponse

    main = FakeMain(summary_cap=80)
    tasks = []
    main.spawn = lambda coro: tasks.append(asyncio.ensure_future(coro))

    class MergePool:
        async def chat(self, request, **kwargs):
            assert "old" in request.messages[1]["content"]
            return ChatResponse(content="合并后的紧凑摘要：张三在杭州，周五交报告。")

    main.pool = MergePool()
    manager = ConversationService(main)
    key = "s2"
    manager.append_summary(key, "旧摘要开头" + "旧细节" * 40)
    manager.append_summary(key, "新摘要结尾" + "新细节" * 40)
    assert "…[中段省略]…" in manager.summary_of(key), "先写兜底"
    await asyncio.gather(*tasks)
    assert manager.summary_of(key) == "合并后的紧凑摘要：张三在杭州，周五交报告。"


def test_extract_facts_loose_parsing():
    from QvQChat.conversation.compactor import extract_facts

    text = (
        "<summary>\n- 决定用方案A\n</summary>\n"
        "<facts>\nENTITY|张三\n- PREFERENCE|喜欢蓝色\nTODO|周五交报告\n"
        "无分隔符的行不入库\nBAD|未知类型\n</facts>"
    )
    summary, facts = extract_facts(text)
    assert facts == ["ENTITY|张三", "PREFERENCE|喜欢蓝色", "TODO|周五交报告"]
    assert "决定用方案A" in summary and "<facts>" not in summary

# 宽松解析失败：无标签 → 原样返回、不入库
    summary2, facts2 = extract_facts("普通摘要文本，没有任何结构")
    assert summary2 == "普通摘要文本，没有任何结构"
    assert facts2 == []


def test_append_facts_dedupe_truncate_and_cap():
    main = FakeMain(facts_max=3)
    manager = ConversationService(main)
    key = "s3"
    assert manager.append_facts(key, ["ENTITY|张三", "ENTITY|张三"]) == 1, "重复不入库"
    long_fact = "PREFERENCE|" + "长" * 300
    manager.append_facts(key, [long_fact, "TODO|交报告"])
    facts = manager.facts_of(key)
    assert len(facts) == 3, "facts_max 上限生效（保最新）"
    assert all(len(f) <= 200 for f in facts), "单条截 200 字符"
    assert facts[-1] == "TODO|交报告"
# reset 同步清空
    manager.reset(key)
    assert manager.facts_of(key) == []


def test_compact_extracts_facts_into_state():
    from QvQChat.engine.base import ChatResponse

    main = FakeMain()
    key = "s4"
    manager = ConversationService(main)

    class FactsPool:
        async def chat(self, request, **kwargs):
            return ChatResponse(
                content="要点：讨论了部署\n<facts>\nENTITY|生产服务器 prod-01\nTODO|迁移数据库\n</facts>"
            )

    main.pool = FactsPool()
    manager.compactor.config = main.cfg
    for i in range(12):
        manager.append(key, "user", f"消息{i}")
    report = asyncio.run(manager.compactor.compact(key, force=True))
    assert any(a.startswith("facts:+") for a in report["actions"]), f"facts 应入库: {report['actions']}"
    facts = manager.facts_of(key)
    assert "ENTITY|生产服务器 prod-01" in facts
    assert "TODO|迁移数据库" in facts
    summary = manager.summary_of(key)
    assert "生产服务器" not in summary or "<facts>" not in summary, "facts 不应混入摘要正文"


def test_build_system_injects_facts_section():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s5"
    manager.append_facts(key, ["ENTITY|张三", "PREFERENCE|喜欢蓝色"])
    persona = main.personas.resolve(key)
    system = manager.build_system(persona, chat_key=key)
    assert "ENTITY|张三" in system
    assert "PREFERENCE|喜欢蓝色" in system
    parts = manager.build_system_parts(persona, chat_key=key)
    kinds = [p.kind for p in parts]
    assert "facts" in kinds and "persona" in kinds and "capability" in kinds
    assert all(p.required for p in parts if p.kind in ("persona", "capability"))
    facts_part = next(p for p in parts if p.kind == "facts")
    assert "喜欢蓝色" in facts_part.text
