import pytest

from QvQChat.engine.pool import ModelPool

from fakes import FakeSDK, make_config


def make_pool(**cfg):
    return ModelPool(FakeSDK(), make_config(**cfg))


def _catalog():
    return {
        "opencode": {
            "models": {
                "glm-5.3": {
                    "tool_call": True,
                    "reasoning": True,
                    "limit": {"context": 1000, "output": 100},
                    "cost": {"input": 1, "output": 2},
                    "modalities": {"input": ["text"]},
                }
            }
        },
        "zai": {
            "models": {
                "glm-5.3": {
                    "tool_call": True,
                    "reasoning": True,
                    "attachment": True,
                    "limit": {"context": 2000, "output": 200},
                    "cost": {"input": 0.5, "output": 1},
                    "modalities": {"input": ["text", "image"]},
                },
                "DeepSeek-V3.2": {
                    "tool_call": True,
                    "limit": {"context": 128000, "output": 8192},
                    "cost": {"input": 0.3, "output": 0.6},
                    "modalities": {"input": ["text"]},
                },
            }
        },
    }


# ===== models.dev 字段映射：limit.context/output，而不是不存在的 context_length =====


def test_models_dev_lookup_maps_limits_and_prefers_matching_provider():
    meta = ModelPool._models_dev_lookup(
        _catalog(), "https://api.z.ai/api/paas/v4", "glm-5.3", "custom", "Custom"
    )
    assert meta["context_length"] == 2000
    assert meta["max_output_tokens"] == 200
    assert meta["tool_call"] is True
    assert meta["reasoning"] is True
    assert meta["vision"] is True
    assert meta["files"] is True
    assert meta["cost"] == {"input": 0.5, "output": 1}


def test_models_dev_lookup_matches_path_prefixed_model_id():
    meta = ModelPool._models_dev_lookup(
        _catalog(), "https://api.siliconflow.cn/v1", "deepseek-ai/DeepSeek-V3.2", "siliconflow", "SiliconFlow"
    )
    assert meta["context_length"] == 128000
    assert meta["max_output_tokens"] == 8192
    assert meta["cost"] == {"input": 0.3, "output": 0.6}


# ===== 保存 provider 时按模型 id 合并，不能把已探测的能力/价格冲掉 =====


def test_save_provider_preserves_existing_model_metadata():
    pool = make_pool()
    pool.save_provider({
        "id": "p", "name": "P", "base_url": "https://x/v1", "api_key": "k",
        "models": [{
            "id": "m", "enabled": True, "tool_call": True,
            "context_length": 1000, "cost": {"input": 1.0, "output": 2.0},
        }],
    })
# 模拟模型池 UI 只回传 id/enabled 的旧保存路径
    pool.save_provider({
        "id": "p", "name": "P", "base_url": "https://x/v1", "api_key": "",
        "models": [{"id": "m", "enabled": True}],
    })
    model = pool.list_providers()[0]["models"][0]
    assert model["tool_call"] is True
    assert model["context_length"] == 1000
    assert model["cost"] == {"input": 1.0, "output": 2.0}


# ===== 自动补全：只填空缺，手动配置优先 =====


@pytest.mark.asyncio
async def test_enrich_models_fills_missing_without_overwriting_manual_values():
    pool = make_pool()
    models, updated = await pool.enrich_models(
        {"id": "custom", "base_url": "https://api.z.ai/api/paas/v4"},
        [{"id": "glm-5.3", "enabled": True, "vision": False}],
        catalog=_catalog(),
    )
    model = models[0]
    assert updated > 0
    assert model["tool_call"] is True
    assert model["context_length"] == 2000
    assert model["max_output_tokens"] == 200
    assert model["vision"] is False# 用户显式配置不被目录覆盖
    assert model["cost"] == {"input": 0.5, "output": 1}


# ===== 成本换算要覆盖已停用模型的历史用量 =====


def test_model_costs_includes_disabled_models():
    pool = make_pool()
    pool.save_provider({
        "id": "p", "name": "P", "base_url": "https://x/v1", "api_key": "k",
        "models": [
            {"id": "on", "enabled": True, "cost": {"input": 1.0, "output": 2.0}},
            {"id": "off", "enabled": False, "cost": {"input": 0.5, "output": 1.0}},
        ],
    })
    assert pool.model_costs() == {
        "p:on": {"input": 1.0, "output": 2.0},
        "p:off": {"input": 0.5, "output": 1.0},
    }
