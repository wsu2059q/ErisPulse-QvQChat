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


async def test_add_list_delete():
    kb = make_kb()
    entry = await kb.add("规则", "每周五发周报", source="note")
    assert (await kb.list())[0]["title"] == "规则"
    assert (await kb.get(entry["id"]))["content"] == "每周五发周报"
    assert await kb.delete(entry["id"]) is True
    assert await kb.delete(entry["id"]) is False
    assert await kb.list() == []


async def test_search_scores_by_term_overlap():
    kb = make_kb()
    await kb.add("恐龙", "霸王龙是白垩纪晚期的顶级掠食者，主要化石发现于北美洲。")
    await kb.add("潜艇", "潜艇依靠压载舱下潜上浮，核动力潜艇可以连续航行数月。")
    hits = await kb.search("霸王龙 白垩纪", top_k=2)
    assert hits and hits[0]["title"] == "恐龙"
    assert await kb.search("完全不相关的量子词根") == []


async def test_long_content_chunks_are_searchable():
    kb = make_kb()
    body = ("部署手册：" + "先检查环境变量，再重启服务，最后验证健康检查端点。" * 40)
    await kb.add("部署手册", body)
    hits = await kb.search("健康检查端点", top_k=1)
    assert hits and "健康检查" in hits[0]["snippet"]


async def test_stats_counts_entries_and_chunks():
    kb = make_kb()
    await kb.add("a", "短内容")
    await kb.add("b", "字" * 900)
    stats = await kb.stats()
    assert stats["entries"] == 2
    assert stats["chunks"] >= 3


async def test_build_system_injects_kb_hits():
    main = FakeMain()
    await main.knowledge.add("恐龙", "霸王龙生活于白垩纪晚期。")
    persona = {"system": "你是助手。"}
    system = await main.sessions.build_system(persona, chat_key="onebot11:group:1", kb_query="霸王龙生活在哪个时期")
    assert "kb-doc" in system and "霸王龙" in system
    system2 = await main.sessions.build_system(persona, chat_key="onebot11:group:1", kb_query="潜艇怎么下潜")
    assert system2.count("kb-doc") == 0


async def test_knowledge_external_entries_searchable_and_readonly():
    from QvQChat.conversation.knowledge import KnowledgeBase

    kb = KnowledgeBase(FakeMain().sdk, FakeMain().cfg)
    kb.set_external_provider(lambda: [{
        "id": "ext:TTS:0",
        "title": "语音合成",
        "content": "语音合成使用 CosyVoice 模型，默认音色 alex。",
        "triggers": ["语音合成"],
        "owner": "",
        "external": True,
        "source": "TTS",
    }])
    hits = await kb.search("CosyVoice 音色")
    assert any(h["title"] == "语音合成" for h in hits)
    triggered = await kb.triggered(["我们聊聊语音合成吧"])
    assert triggered and triggered[0]["title"] == "语音合成"
# 外部条目只读：不落库
    assert await kb.list() == []
