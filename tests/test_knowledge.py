from QvQChat.conversation.knowledge import KnowledgeBase, chunk_text
from QvQChat.Main import Main
from fakes import FakeMain


def make_kb():
    import sys
    sys.path.insert(0, "tests")
    from fakes import FakeSDK
    return KnowledgeBase(FakeSDK())


def test_chunk_text_sizes():
    text = "字" * 950
    chunks = chunk_text(text, size=400, overlap=50)
    assert all(len(c) <= 400 for c in chunks)
    assert sum(len(c) for c in chunks) >= 950
    assert chunk_text("") == []
    assert chunk_text("短文本") == ["短文本"]


def test_add_list_delete():
    kb = make_kb()
    entry = kb.add("规则", "每周五发周报", source="note")
    assert kb.list()[0]["title"] == "规则"
    assert kb.get(entry["id"])["content"] == "每周五发周报"
    assert kb.delete(entry["id"]) is True
    assert kb.delete(entry["id"]) is False
    assert kb.list() == []


def test_search_scores_by_term_overlap():
    kb = make_kb()
    kb.add("恐龙", "霸王龙是白垩纪晚期的顶级掠食者，主要化石发现于北美洲。")
    kb.add("潜艇", "潜艇依靠压载舱下潜上浮，核动力潜艇可以连续航行数月。")
    hits = kb.search("霸王龙 白垩纪", top_k=2)
    assert hits and hits[0]["title"] == "恐龙"
    assert kb.search("完全不相关的量子词根") == []


def test_long_content_chunks_are_searchable():
    kb = make_kb()
    body = ("部署手册：" + "先检查环境变量，再重启服务，最后验证健康检查端点。" * 40)
    kb.add("部署手册", body)
    hits = kb.search("健康检查端点", top_k=1)
    assert hits and "健康检查" in hits[0]["snippet"]


def test_stats_counts_entries_and_chunks():
    kb = make_kb()
    kb.add("a", "短内容")
    kb.add("b", "字" * 900)
    stats = kb.stats()
    assert stats["entries"] == 2
    assert stats["chunks"] >= 3


def test_build_system_injects_kb_hits():
    main = FakeMain()
    main.knowledge.add("恐龙", "霸王龙生活于白垩纪晚期。")
    persona = {"system": "你是助手。"}
    system = main.sessions.build_system(persona, chat_key="onebot11:group:1", kb_query="霸王龙生活在哪个时期")
    assert "kb-doc" in system and "霸王龙" in system
    assert main.sessions.build_system(persona, chat_key="onebot11:group:1", kb_query="潜艇怎么下潜").count("kb-doc") == 0
