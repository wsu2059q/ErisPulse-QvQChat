"""检索升级：Lorebook 世界书触发（SillyTavern World Info 模式）+ embedding 语义检索 + 向量层。"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from QvQChat.conversation.knowledge import KnowledgeBase 
from QvQChat.engine import vectors 
from QvQChat.engine.vectors import VectorEngine 
from fakes import FakeSDK 

PROVIDER = {"base_url": "http://x/v1", "api_key": "sk-test", "model": "emb-test"}


class FakeEmbedClient:
    """确定性假 client：含'恐龙'→[1,0]，含'潜艇'→[0,1]，其它→[0.62,0.62]；fail=True 抛异常。"""

    def __init__(self, fail=False):
        self.calls: list[list[str]] = []
        self.fail = fail

    @property
    def embeddings(self):
        return self

    def create(self, model=None, input=None):
        if self.fail:
            raise RuntimeError("embedding unavailable")
        batch = [str(t) for t in (input or [])]
        self.calls.append(batch)
        return SimpleNamespace(data=[SimpleNamespace(embedding=self._vec(t)) for t in batch])

    @staticmethod
    def _vec(text: str) -> list[float]:
        if "恐龙" in text:
            return [1.0, 0.0]
        if "潜艇" in text:
            return [0.0, 1.0]
        return [0.62, 0.62]


def make_kb(**overrides) -> KnowledgeBase:
    cfg = dict(kb_triggers_enabled=True, kb_trigger_window=6, kb_cooldown_min=30)
    cfg.update(overrides)
    return KnowledgeBase(FakeSDK(), SimpleNamespace(**cfg))


def semantic_kb(fail=False) -> KnowledgeBase:
    kb = make_kb(embedding_enabled=True, embedding_provider=dict(PROVIDER))
    kb.vectors = VectorEngine(client=FakeEmbedClient(fail=fail))
    return kb


 

def test_vectors_available_false_without_config():
    assert vectors.available(None) is False
    assert vectors.available(SimpleNamespace()) is False
    assert vectors.available(SimpleNamespace(embedding_provider={})) is False
    assert vectors.available(SimpleNamespace(embedding_provider={"base_url": "http://x/v1"})) is False
    assert vectors.available(SimpleNamespace(embedding_provider={"base_url": "http://x/v1", "api_key": "k"})) is False
 
    full = SimpleNamespace(embedding_provider=dict(PROVIDER))
    assert vectors.available(full) is True
 
    assert vectors.available(SimpleNamespace(embedding_provider={"base_url": "u", "api_key": "k"}, embedding_model="m")) is True


def test_vectors_embed_batches_of_16_and_fails_to_none():
    client = FakeEmbedClient()
    engine = VectorEngine(client=client)
    out = engine.embed(["恐龙编号" + str(i) for i in range(40)], SimpleNamespace(embedding_provider=dict(PROVIDER)))
    assert out is not None and len(out) == 40
    assert [len(batch) for batch in client.calls] == [16, 16, 8]
    assert engine.embed([], SimpleNamespace(embedding_provider=dict(PROVIDER))) is None
 
    failing = VectorEngine(client=FakeEmbedClient(fail=True))
    assert failing.embed(["恐龙"], SimpleNamespace(embedding_provider=dict(PROVIDER))) is None
 
    assert VectorEngine(client=client).embed(["恐龙"], SimpleNamespace()) is None


def test_vectors_cosine_pure_function():
    assert vectors.cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert vectors.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert abs(vectors.cosine([1.0, 0.0], [1.0, 1.0]) - 0.7071067811865475) < 1e-9
    assert vectors.cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0 
    assert vectors.cosine([], []) == 0.0
    assert vectors.cosine(None, [1.0]) == 0.0


 

def test_semantic_search_ranks_by_cosine():
    kb = semantic_kb()
    kb.add("恐龙", "恐龙之霸王龙是白垩纪晚期的顶级掠食者。")
    kb.add("潜艇", "潜艇依靠压载舱下潜上浮。")
    hits = kb.search("恐龙时代", top_k=2)
    assert hits and hits[0]["title"] == "恐龙"
    assert hits[0]["score"] == 1.0
    assert len(hits) == 1 
    hits = kb.search("潜艇怎么下潜", top_k=2)
    assert hits and hits[0]["title"] == "潜艇"


def test_semantic_vector_cache_written_and_cleared():
    kb = semantic_kb()
    entry = kb.add("恐龙", "霸王龙是白垩纪掠食者。")
    kb.search("恐龙", top_k=1)
    cache = kb.sdk.storage.get("QvQChat:kbvec:" + entry["id"])
    assert isinstance(cache, dict) and cache.get("model") == "emb-test" and cache.get("vecs")
 
    before = len(kb.vectors._client.calls)
    kb.search("恐龙", top_k=1)
    assert len(kb.vectors._client.calls) == before + 1 
    kb.delete(entry["id"])
    assert kb.sdk.storage.get("QvQChat:kbvec:" + entry["id"]) is None


def test_semantic_fallback_on_embed_failure():
    kb = semantic_kb(fail=True)
    kb.add("恐龙", "霸王龙是白垩纪晚期的顶级掠食者，主要化石发现于北美洲。")
    hits = kb.search("霸王龙 白垩纪", top_k=2)
    assert hits and hits[0]["title"] == "恐龙"
    assert isinstance(hits[0]["score"], int) 


def test_semantic_disabled_by_flag_falls_back_to_lexical():
    kb = make_kb() 
    kb.add("恐龙", "霸王龙是白垩纪晚期的顶级掠食者。")
    assert kb._semantic_search("恐龙", 2) is None
    hits = kb.search("霸王龙 白垩纪", top_k=1)
    assert hits and hits[0]["title"] == "恐龙"
    assert kb.search("完全不相关的量子词根") == []


 

def test_triggered_hit_refreshes_last_trigger_ts():
    kb = make_kb()
    entry = kb.add("魔王设定", "魔王被封印在北塔第七层，惧怕圣光。", triggers=["魔王", "北塔"], priority=5)
    hits = kb.triggered(["群里聊到 魔王 会不会复活"], now=1000.0)
    assert [h["id"] for h in hits] == [entry["id"]]
    assert kb.get(entry["id"])["last_trigger_ts"] == 1000.0 


def test_triggered_any_keyword_case_insensitive():
    kb = make_kb()
    kb.add("a", "Dragon lore", triggers=["Dragon", "龙族"], cooldown_min=0)
    assert kb.triggered(["we love DRAGON ball"], now=0.0)
    assert kb.triggered(["今天聊聊龙族的历史"], now=0.0)
    assert kb.triggered(["完全无关的话题"], now=0.0) == []


def test_triggered_priority_desc_order():
    kb = make_kb()
    low = kb.add("low", "低优先条目", triggers=["关键词"], priority=1, cooldown_min=0)
    high = kb.add("high", "高优先条目", triggers=["关键词"], priority=9, cooldown_min=0)
    assert [h["id"] for h in kb.triggered(["提到 关键词 了"], now=100.0)] == [high["id"], low["id"]]


def test_triggered_cooldown_blocks_until_expiry():
    kb = make_kb()
    entry = kb.add("e", "冷却条目", triggers=["key"], cooldown_min=30)
    t0 = 1000.0 
    assert kb.triggered(["key"], now=t0)
    assert kb.triggered(["key"], now=t0 + 20 * 60) == [] 
    assert kb.triggered(["key"], now=t0 + 29 * 60 + 59) == [] 
    assert len(kb.triggered(["key"], now=t0 + 30 * 60)) == 1 
    assert kb.get(entry["id"])["last_trigger_ts"] == t0 + 30 * 60


def test_triggered_ignores_entries_without_triggers():
    kb = make_kb()
    kb.add("plain", "无触发词的普通条目") 
    kb.add("trig", "内容", triggers=["魔王"], cooldown_min=0)
    assert kb.triggered(["无触发词的普通条目"], now=0.0) == []
    hits = kb.triggered(["魔王出现了"], now=0.0)
    assert [h["title"] for h in hits] == ["trig"]


def test_triggered_disabled_by_config():
    kb = make_kb(kb_triggers_enabled=False)
    kb.add("t", "内容", triggers=["魔王"], cooldown_min=0)
    assert kb.triggered(["魔王魔王魔王"], now=0.0) == []


 

def test_add_new_fields_crud_passthrough():
    kb = make_kb()
    entry = kb.add("t", "c", source="note", triggers=["a", "b"], priority=7, cooldown_min=10)
    stored = kb.get(entry["id"])
    assert stored["triggers"] == ["a", "b"] and stored["priority"] == 7 and stored["cooldown_min"] == 10
 
    plain = kb.add("p", "c")
    assert all(k not in plain for k in ("triggers", "priority", "cooldown_min"))
 
    assert kb.add("d", "c", triggers=["x"])["cooldown_min"] == 30
 
    assert kb.import_entries([{"title": "i", "content": "ic", "triggers": ["k"], "priority": 3, "cooldown_min": 5}]) == 1
    imported = next(e for e in kb.list() if e["title"] == "i")
    assert imported["triggers"] == ["k"] and imported["priority"] == 3 and imported["cooldown_min"] == 5
 
    assert any(e.get("triggers") for e in kb.export())
    assert kb.delete(entry["id"]) is True and kb.get(entry["id"]) is None


 

def test_build_system_merges_triggered_before_search_hits():
    from fakes import FakeMain

    main = FakeMain()
    main.knowledge.add("魔王", "魔王被封印在北塔，惧怕圣光。", triggers=["魔王"], priority=5)
    main.knowledge.add("恐龙", "霸王龙生活于白垩纪晚期。")
    persona = {"system": "你是助手。"}
    parts = main.sessions.build_system_parts(
        persona,
        chat_key="onebot11:group:1",
        kb_query="魔王状态",
        kb_texts=["最近群里在聊魔王", "魔王现在怎么样了"],
    )
    kb_parts = [p for p in parts if p.kind == "kb"]
    assert kb_parts and "[triggered]" in kb_parts[0].text and "北塔" in kb_parts[0].text
 
    assert kb_parts[0].text.count("魔王被封印在北塔") == 1
    assert "白垩纪" not in kb_parts[0].text 
 
    parts2 = main.sessions.build_system_parts(persona, chat_key="onebot11:group:1", kb_query="霸王龙时期", kb_texts=["聊点别的"])
    kb2 = [p for p in parts2 if p.kind == "kb"]
    assert kb2 and "[triggered]" not in kb2[0].text and "白垩纪" in kb2[0].text
