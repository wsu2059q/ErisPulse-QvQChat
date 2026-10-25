from QvQChat import texts
from QvQChat.agent.persona import ASSISTANT_ID, PersonaManager
from QvQChat.conversation.budget import ContextPacker, SystemPart
from QvQChat.engine.openai import OpenAIEngine

from fakes import FakeMain


def test_builtin_persona_present_and_editable():
    """内置人格可修改（覆盖存储），删除即恢复默认。"""
    manager = PersonaManager(FakeMain().sdk)
    personas = manager.list()
    assert any(p["id"] == ASSISTANT_ID and p.get("builtin") for p in personas)
    saved = manager.save({"id": ASSISTANT_ID, "name": "自定义", "system": "覆盖后的系统提示词"})
    assert saved["modified"] is True
    assert manager.get(ASSISTANT_ID)["system"] == "覆盖后的系统提示词"
    assert manager.delete(ASSISTANT_ID) is True
    restored = manager.get(ASSISTANT_ID)
    assert restored["builtin"] is True and not restored.get("modified")
    assert manager.delete(ASSISTANT_ID) is False


def test_persona_crud_and_binding():
    main = FakeMain()
    manager = PersonaManager(main.sdk)
    saved = manager.save({"name": "学者", "system": "你是严谨的学者。", "tools": ["recall"]})
    pid = saved["id"]
    assert manager.get(pid)["name"] == "学者"
    manager.bind("a:b:c", pid)
    assert manager.resolve("a:b:c")["id"] == pid
    manager.bind("a:b:c", None)
    assert manager.resolve("a:b:c")["id"] == ASSISTANT_ID
    assert manager.delete(pid) is True
    assert manager.get(pid)["id"] == ASSISTANT_ID


def test_persona_extended_fields_crud_and_defaults():
    """P2新字段存取 + get 缺省兼容（style={} examples=[] 等）。"""
    main = FakeMain()
    manager = PersonaManager(main.sdk)
    saved = manager.save({
        "name": "猫娘",
        "system": "你是猫娘。",
        "owner_title": "主人",
        "style": {"emoji_density": "high", "verbosity": "low", "formality": "casual", "junk": "x"},
        "examples": [{"user": "在吗", "assistant": "喵～在的哦主人"}],
        "banned_words": ["哈哈", ""],
        "catchphrases": ["喵～"],
        "nickname": "小喵",
        "avatar": "https://example.com/a.png",
    })
    pid = saved["id"]
    got = manager.get(pid)
    assert got["owner_title"] == "主人"
    assert got["style"] == {"emoji_density": "high", "verbosity": "low", "formality": "casual"}
    assert got["examples"] == [{"user": "在吗", "assistant": "喵～在的哦主人"}]
    assert got["banned_words"] == ["哈哈"]
    assert got["catchphrases"] == ["喵～"]
    assert got["nickname"] == "小喵"
    assert got["avatar"] == "https://example.com/a.png"
# 缺省兼容：不带新字段保存的人格 get 到的是空默认而非 KeyError
    saved2 = manager.save({"name": "朴素", "system": "朴素人格。"})
    plain = manager.get(saved2["id"])
    assert plain["style"] == {} and plain["examples"] == []
    assert plain["banned_words"] == [] and plain["catchphrases"] == []
    assert plain["owner_title"] == "" and plain["nickname"] == "" and plain["avatar"] == ""


def test_persona_save_merges_unspecified_fields():
    """P2部分保存不清空未提供的扩展字段（merge 语义）。"""
    main = FakeMain()
    manager = PersonaManager(main.sdk)
    saved = manager.save({"name": "A", "system": "sys", "owner_title": "老板", "style": {"verbosity": "low"}})
    pid = saved["id"]
    manager.save({"id": pid, "system": "sys2"})# 只改 system
    got = manager.get(pid)
    assert got["system"] == "sys2"
    assert got["owner_title"] == "老板"
    assert got["style"] == {"verbosity": "low"}
# 显式传空串可清空
    manager.save({"id": pid, "owner_title": ""})
    assert manager.get(pid)["owner_title"] == ""


def test_persona_examples_capped_2000():
    main = FakeMain()
    manager = PersonaManager(main.sdk)
    big = "x" * 1500
    saved = manager.save({"name": "E", "system": "s", "examples": [
        {"user": big, "assistant": big},# 3000 > 2000 → 不收
        {"user": "u1", "assistant": "a1"},# 第一条超限即止
    ]})
    assert saved["examples"] == []
    saved2 = manager.save({"name": "E2", "system": "s", "examples": [
        {"user": "u" * 900, "assistant": "a" * 900},
        {"user": "b" * 100, "assistant": ""},# 累计 1900 ≤ 2000 收
        {"user": "c" * 200, "assistant": "never"},# 累计超 2000 止
    ]})
    assert len(saved2["examples"]) == 2


def test_builtin_personas_have_extended_defaults():
    manager = PersonaManager(FakeMain().sdk)
    for persona in manager.list():
        assert persona["style"] == {}
        assert persona["examples"] == []
        assert persona["banned_words"] == [] and persona["catchphrases"] == []
        assert persona["owner_title"] == "" and persona["nickname"] == ""


def test_bindings_listing_and_removal():
    """P3bindings() 直扫 KV 绑定前缀，unbind 即从表消失。"""
    main = FakeMain()
    manager = PersonaManager(main.sdk)
    assert manager.bindings() == {}
    saved = manager.save({"name": "P", "system": "s"})
    manager.bind("qq:private:1", saved["id"])
    manager.bind("qq:group:9", "concise")
    assert manager.bindings() == {"qq:private:1": saved["id"], "qq:group:9": "concise"}
    manager.bind("qq:group:9", None)
    assert manager.bindings() == {"qq:private:1": saved["id"]}


def test_resolve_group_fallback_two_levels():
    """P4隔离成员 key → 群 base key → 全局默认 → assistant 两级回落。"""
    main = FakeMain()
    manager = PersonaManager(main.sdk)
    group_key = "qq:group:100"
    member_key = "qq:group:100:u7"
    saved = manager.save({"name": "群设", "system": "群人格"})
# 1) 群 base 绑定对隔离成员 key 生效
    manager.bind(group_key, saved["id"])
    assert manager.resolve(member_key)["id"] == saved["id"]
# 2) 成员精确绑定优先于群 base
    manager.bind(member_key, "concise")
    assert manager.resolve(member_key)["id"] == "concise"
    manager.bind(member_key, None)
    assert manager.resolve(member_key)["id"] == saved["id"]
# 3) 未绑定回落全局默认
    manager.bind(group_key, None)
    manager.set_global_default("detailed")
    assert manager.resolve(member_key)["id"] == "detailed"
# 4) 无任何绑定回落 assistant
    manager.set_global_default(None)
    assert manager.resolve(member_key)["id"] == ASSISTANT_ID
# 非隔离 key 不做 strip 回落（直接精确查）
    assert manager.resolve("qq:private:2")["id"] == ASSISTANT_ID


def test_migrate_state_mirror_backfills_from_kv():
    """启动迁移：KV 权威，state.persona 过期则回填；无 KV 绑定不动。"""
    from QvQChat.conversation.service import CONV_PREFIX

    main = FakeMain()
    manager = PersonaManager(main.sdk)
    main.sdk.storage.set(CONV_PREFIX + "qq:private:1", {"persona": "old", "contexts": []})
    main.sdk.storage.set(CONV_PREFIX + "qq:private:2", {"persona": "keep", "contexts": []})
    manager.bind("qq:private:1", "concise")
    moved = manager.migrate_state_mirror()
    assert moved == 1
    assert main.sdk.storage.get(CONV_PREFIX + "qq:private:1")["persona"] == "concise"
    assert main.sdk.storage.get(CONV_PREFIX + "qq:private:2")["persona"] == "keep"
# 收敛后二次迁移为 no-op
    assert manager.migrate_state_mirror() == 0


def _rich_persona(main) -> str:
    saved = main.personas.save({
        "name": "小蝶",
        "system": "你是小蝶。",
        "owner_title": "主人",
        "style": {"emoji_density": "high", "verbosity": "low"},
        "examples": [{"user": "早上好", "assistant": "早安喵～"}],
        "banned_words": ["绝不允许"],
        "catchphrases": ["喵～"],
        "nickname": "蝶",
    })
    return saved["id"]


def test_build_system_injects_persona_extras():
    """P2身份行在首行；owner_title/style/examples/禁词口头禅注入；persona_extra 部件可被 pack 兜底。"""
    main = FakeMain()
    pid = _rich_persona(main)
    persona = main.personas.get(pid)
    parts = main.sessions.build_system_parts(persona)
    kinds = [p.kind for p in parts]
    assert kinds[0] == "persona" and kinds[1] == "persona_extra" and "capability" in kinds
    system = "\n".join(p.text for p in parts if p.text)
    lines = system.splitlines()
    assert lines[0] == texts.t("persona_identity", name="小蝶", id=pid)
    assert texts.t("owner_title_line", title="主人") in system
    assert texts.t("style_line", value="emoji_density: high; verbosity: low") in system
    assert "<persona-examples>" in system and "早上好" in system and "早安喵～" in system
    assert texts.t("persona_banned_words", words="绝不允许") in system
    assert texts.t("persona_catchphrases", phrases="喵～") in system
# 素人格不产生 persona_extra 部件
    plain = main.personas.get("assistant")
    assert all(p.kind != "persona_extra" for p in main.sessions.build_system_parts(plain))
# build_system 兼容层同样带上注入
    assert texts.t("persona_identity", name="小蝶", id=pid) in main.sessions.build_system(persona).splitlines()[0]


def test_context_packer_handles_persona_extra_kind():
    """PRIORITY 未收录 persona_extra：pack 按 extra 优先级稳定兜底，不报错；小预算下可被丢弃。"""
    parts = [
        SystemPart("persona", "核心人格" * 50, required=True),
        SystemPart("persona_extra", "扩展人格" * 50),
        SystemPart("extra", "用户附加"),
    ]
    packed = ContextPacker().pack(
        context_length=2000,
        parts=parts,
        history=[],
        user_msg={"role": "user", "content": "hi"},
        max_output=0,
    )
    assert packed.system
# 预算够：全部保留，且 persona_extra（未知 kind 兜底 extra 优先级、稳定序）排在 extra 之前
    assert "扩展人格" in packed.system and "用户附加" in packed.system
    assert packed.system.index("扩展人格") < packed.system.index("用户附加")
    tight = ContextPacker().pack(
        context_length=120,
        parts=parts,
        history=[],
        user_msg={"role": "user", "content": "hi"},
        max_output=0,
    )
    assert "核心人格" in tight.system# required persona 保位


def test_merge_system_messages():
    engine = OpenAIEngine()
    merged = engine.merge_system(
        [
            {"role": "system", "content": "a"},
            {"role": "system", "content": "b"},
            {"role": "user", "content": "hi"},
            {"role": "system", "content": "c"},
        ]
    )
    assert len(merged) == 3
    assert merged[0]["content"] == "a\n\nb"
    assert merged[2]["content"] == "c"


def test_texts_have_all_five_languages():
    required = {"zh-CN", "zh-TW", "en", "ja", "ru"}
    for key, translations in texts.STRINGS.items():
        missing = required - set(translations)
        assert not missing, f"{key} missing {missing}"


def test_texts_register_and_translate():
    texts.register_texts()
    out = texts.t("tool_not_found", name="zzz")
    assert "zzz" in out
    assert out != texts.t("tool_timeout", name="a", seconds=1)
