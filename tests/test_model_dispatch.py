from types import SimpleNamespace

from QvQChat.engine.base import ChatRequest, ChatResponse, EngineError, TaskSpec
from QvQChat.engine.pool import ModelPool

from fakes import FakeSDK, make_config


def make_pool(**cfg):
    pool = ModelPool(FakeSDK(), make_config(**cfg))
    pool.save_provider(
        {
            "id": "p1",
            "name": "P1",
            "base_url": "https://x/v1",
            "api_key": "k",
            "models": [
                {"id": "plain", "enabled": True, "tool_call": False, "context_length": 8192,
                 "cost": {"input": 10.0, "output": 20.0}},
                {"id": "smart", "enabled": True, "tool_call": True, "vision": True,
                 "context_length": 32768, "cost": {"input": 5.0, "output": 5.0}},
                {"id": "cheap", "enabled": True, "tool_call": True,
                 "cost": {"input": 0.5, "output": 0.5}},
            ],
        }
    )
    return pool


 


def test_list_models_exposes_context_length_and_cost():
    pool = make_pool()
    models = {m["id"]: m for m in pool.list_models()}
    assert models["p1:plain"]["context_length"] == 8192
    assert models["p1:smart"]["context_length"] == 32768
    assert models["p1:cheap"]["context_length"] is None
    assert models["p1:plain"]["cost"] == {"input": 10.0, "output": 20.0}
    costs = pool.model_costs()
    assert costs["p1:smart"] == {"input": 5.0, "output": 5.0}
    assert costs["p1:cheap"] == {"input": 0.5, "output": 0.5}
    assert set(costs) == {"p1:plain", "p1:smart", "p1:cheap"}


 


def test_resolve_model_explicit_beats_needs():
    pool = make_pool()
 
    model = pool.resolve_model("p1:plain", needs=["tool_call"])
    assert model["id"] == "p1:plain"
 
    assert pool.resolve_model(None, needs=["tool_call"])["id"] == "p1:smart"
 
    assert pool.resolve_model("plain")["id"] == "p1:plain"


 


def test_has_model_query():
    pool = make_pool()
    assert pool.has_model(["tool_call"]) is True
    assert pool.has_model(["vision"]) is True
    assert pool.has_model(["tool_call", "vision"]) is True
    assert pool.has_model(["video"]) is False
    assert pool.has_model() is True 
    empty = ModelPool(FakeSDK(), make_config())
    assert empty.has_model(["tool_call"]) is False
    assert empty.has_model() is False


def test_capability_status_unknown_vs_no():
    pool = make_pool()
    assert pool.capability_status("tool_call") == "yes"
 
    pool_no = ModelPool(FakeSDK(), make_config())
    pool_no.save_provider(
        {"id": "n", "name": "N", "base_url": "https://n/v1", "api_key": "k",
         "models": [{"id": "a", "enabled": True, "video": False}, {"id": "b", "enabled": True, "video": False}]}
    )
    assert pool_no.capability_status("video") == "no"
 
    pool2 = ModelPool(FakeSDK(), make_config())
    pool2.save_provider(
        {"id": "q", "name": "Q", "base_url": "https://y/v1", "api_key": "k",
         "models": [{"id": "m"}]}
    )
    assert pool2.capability_status("tool_call") == "unknown"


 


def test_resolve_task_model_priority_chain():
    pool = make_pool()
 
    assert pool.resolve_task_model(TaskSpec(kind="chat"))["id"] == "p1:plain"
 
    assert pool.resolve_task_model(TaskSpec(kind="chat", needs=["tool_call"]))["id"] == "p1:smart"
 
    assert pool.resolve_task_model(TaskSpec(kind="compact", prefer="cheap"))["id"] == "p1:cheap"
 
    pool2 = make_pool(task_models={"compact": "p1:plain"})
    assert pool2.resolve_task_model(TaskSpec(kind="compact", prefer="cheap"))["id"] == "p1:plain"
 
    assert pool2.resolve_task_model(
        TaskSpec(kind="compact", model="p1:smart", needs=["vision"])
    )["id"] == "p1:smart"
 
    pool3 = make_pool()
    pool3.save_provider(
        {"id": "p2", "name": "P2", "base_url": "https://z/v1", "api_key": "k",
         "models": [{"id": "free", "enabled": True}]}
    )
    assert pool3.resolve_task_model(TaskSpec(kind="compact", prefer="cheap"))["id"] == "p1:cheap"


async def test_dispatch_routes_to_resolved_model():
    pool = make_pool()
    requested = []

    async def fake_chat(base_url, api_key, scoped, on_delta=None, on_reset=None, on_reasoning=None):
        requested.append(scoped.model)
        return ChatResponse(content="ok", model=scoped.model)

    pool.engine = SimpleNamespace(chat=fake_chat)
    resp = await pool.dispatch(
        TaskSpec(kind="compact", prefer="cheap"),
        ChatRequest(messages=[{"role": "user", "content": "hi"}], max_tokens=32),
    )
    assert requested == ["cheap"]
    assert resp.model == "p1:cheap"

    resp = await pool.dispatch(
        TaskSpec(kind="chat", needs=["tool_call"]),
        ChatRequest(messages=[{"role": "user", "content": "hi"}]),
    )
    assert requested[-1] == "smart"
    assert resp.model == "p1:smart"


def test_dispatch_needs_empty_pool_fallback():
    pool = make_pool()
 
    assert pool.resolve_task_model(TaskSpec(kind="chat", needs=["video"]))["id"] == "p1:plain"
    empty = ModelPool(FakeSDK(), make_config())
    try:
        empty.resolve_task_model(TaskSpec(kind="chat"))
        raise AssertionError("should raise")
    except EngineError:
        pass


 


def _two_provider_pool():
    sdk = FakeSDK()
    pool = ModelPool(sdk, make_config())
    pool.save_provider({
        "id": "p1", "name": "P1", "base_url": "https://a/v1", "api_key": "k1",
        "models": [{"id": "a", "enabled": True}, {"id": "off", "enabled": False}],
    })
    pool.save_provider({
        "id": "p2", "name": "P2", "base_url": "https://b/v1", "api_key": "k2",
        "models": [{"id": "c", "enabled": True}, {"id": "d", "enabled": True}],
    })
    return sdk, pool


def test_model_chain_persists_cross_provider_order():
    sdk, pool = _two_provider_pool()
    assert [(e["provider"], e["model"]) for e in pool.model_chain()] == [
        ("p1", "a"), ("p1", "off"), ("p2", "c"), ("p2", "d"),
    ]

    pool.save_chain([
        {"provider": "p2", "model": "d"},
        {"provider": "p1", "model": "off"},
        {"provider": "p2", "model": "c"},
        {"provider": "p1", "model": "a"},
    ])
 
    reloaded = ModelPool(sdk, make_config())
    assert [(e["provider"], e["model"]) for e in reloaded.model_chain()] == [
        ("p2", "d"), ("p1", "off"), ("p2", "c"), ("p1", "a"),
    ]
 
    assert [m["id"] for m in reloaded.list_models()] == ["p2:d", "p2:c", "p1:a"]


def test_save_chain_ignores_unknown_and_appends_missing():
    sdk, pool = _two_provider_pool()
    pool.save_chain([
        {"provider": "ghost", "model": "x"},
        {"provider": "p2", "model": "c"},
        "not-a-chain-entry",
    ])
    assert [(e["provider"], e["model"]) for e in ModelPool(sdk, make_config()).model_chain()] == [
        ("p2", "c"), ("p1", "a"), ("p1", "off"), ("p2", "d"),
    ]


async def test_failover_follows_saved_chain():
    _, pool = _two_provider_pool()
    pool.save_chain([
        {"provider": "p2", "model": "d"},
        {"provider": "p1", "model": "a"},
        {"provider": "p2", "model": "c"},
    ])
    tried = []

    async def fake_chat(base_url, api_key, scoped, on_delta=None, on_reset=None, on_reasoning=None):
        tried.append(scoped.model)
        if len(tried) == 1:
            raise EngineError("boom")
        return ChatResponse(content="ok", model=scoped.model)

    pool.engine = SimpleNamespace(chat=fake_chat)
    resp = await pool.chat(ChatRequest(messages=[{"role": "user", "content": "hi"}]))
    assert tried == ["d", "a"]
    assert resp.model == "p1:a"


async def test_failover_keeps_unknown_capability_models_as_backups():
    pool = ModelPool(FakeSDK(), make_config())
    pool.save_provider({
        "id": "p1", "name": "P1", "base_url": "https://a/v1", "api_key": "k",
        "models": [{"id": "cap", "enabled": True, "tool_call": True}],
    })
    pool.save_provider({
        "id": "p2", "name": "P2", "base_url": "https://b/v1", "api_key": "k",
        "models": [
            {"id": "unknown", "enabled": True},
            {"id": "no", "enabled": True, "tool_call": False},
        ],
    })
    tried = []

    async def fake_chat(base_url, api_key, scoped, on_delta=None, on_reset=None, on_reasoning=None):
        tried.append(scoped.model)
        if scoped.model == "cap":
            raise EngineError("429 quota")
        return ChatResponse(content="ok", model=scoped.model)

    pool.engine = SimpleNamespace(chat=fake_chat)
    resp = await pool.chat(ChatRequest(messages=[{"role": "user", "content": "hi"}], needs=["tool_call"]))
 
    assert tried == ["cap", "unknown"]
    assert resp.model == "p2:unknown"


 


def test_vision_task_name_fallback_when_capability_unknown():
    """无模型声明 vision 时按模型名启发式挑（glm-4v / gpt-4o 等），而不是随便选文本模型。"""
    pool = ModelPool(FakeSDK(), make_config())
    pool.save_provider({
        "id": "p1", "name": "P1", "base_url": "https://x/v1", "api_key": "k",
        "models": [
            {"id": "text-only", "enabled": True},
            {"id": "glm-4v-flash", "enabled": True},
        ],
    })
    model = pool.resolve_task_model(TaskSpec(kind="vision", needs=["vision"]))
    assert model["id"] == "p1:glm-4v-flash"


def test_vision_task_explicit_mark_wins():
    pool = make_pool()
    model = pool.resolve_task_model(TaskSpec(kind="vision", needs=["vision"]))
    assert model["id"] == "p1:smart"


def test_vision_task_no_candidate_raises():
    pool = ModelPool(FakeSDK(), make_config())
    pool.save_provider({
        "id": "p1", "name": "P1", "base_url": "https://x/v1", "api_key": "k",
        "models": [{"id": "text-only", "enabled": True}],
    })
    try:
        pool.resolve_task_model(TaskSpec(kind="vision", needs=["vision"]))
    except EngineError as e:
        assert "task_models.vision" in str(e) or "视觉" in str(e)
    else:
        raise AssertionError("expected EngineError")
