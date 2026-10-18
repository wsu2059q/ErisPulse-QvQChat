from QvQChat import texts
from QvQChat.agent.persona import ASSISTANT_ID, PersonaManager
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
