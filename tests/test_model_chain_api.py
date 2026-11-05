from QvQChat.dashboard.manager import DashboardManager

from fakes import FakeMain


class _Request:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def make_manager():
    main = FakeMain()
    main.pool.save_provider({
        "id": "p1", "name": "P1", "base_url": "https://a/v1", "api_key": "k1",
        "models": [{"id": "a", "enabled": True}],
    })
    main.pool.save_provider({
        "id": "p2", "name": "P2", "base_url": "https://b/v1", "api_key": "k2",
        "models": [{"id": "c", "enabled": True}],
    })
    return main, DashboardManager(main)


async def test_chain_save_roundtrips_through_models_get():
    main, manager = make_manager()
    resp = await manager.chain_save(_Request({"chain": [
        {"provider": "p2", "model": "c"},
        {"provider": "p1", "model": "a"},
    ]}))
    assert resp["ok"] is True

    data = await manager.models_get(_Request(None))
    assert [(c["provider"], c["model"]["id"]) for c in data["chain"]] == [("p2", "c"), ("p1", "a")]
    assert [m["id"] for m in data["models"]] == ["p2:c", "p1:a"]
# api_key 仍然不外泄（chain 只带 provider 元信息与模型配置）
    assert all("api_key" not in c["model"] for c in data["chain"])


async def test_chain_save_rejects_non_list():
    _, manager = make_manager()
    resp = await manager.chain_save(_Request({"chain": "nope"}))
    assert resp == ({"error": "chain list required"}, 400)


async def test_models_detect_returns_metadata(monkeypatch):
    main, manager = make_manager()
    seen = {}

    async def fake_detect(provider, model):
        seen["provider"] = provider
        seen["model"] = model
        return {"context_length": 1000000, "max_output_tokens": 131072, "tool_call": True}

    monkeypatch.setattr(main.pool, "detect_model", fake_detect)
    resp = await manager.models_detect(_Request({
        "provider": {"id": "custom", "base_url": "https://open.bigmodel.cn/api/coding/paas/v4"},
        "model": "glm-5.3",
    }))
    assert resp["ok"] is True
    assert resp["meta"]["context_length"] == 1000000
    assert seen["model"] == "glm-5.3"


async def test_models_detect_requires_model():
    _, manager = make_manager()
    resp = await manager.models_detect(_Request({"model": "  "}))
    assert resp == ({"error": "model required"}, 400)


async def test_models_enrich_reports_updated_count(monkeypatch):
    main, manager = make_manager()

    async def fake_enrich(force=False):
        assert force is True
        return 7

    monkeypatch.setattr(main.pool, "enrich_all_providers", fake_enrich)
    resp = await manager.models_enrich(_Request({}))
    assert resp == {"ok": True, "updated": 7}
