from QvQChat.bridge.ecosystem import EcosystemBridge

from fakes import FakeMain, make_ctx


def make_bridge(catalog=None, **config_overrides):
    main = FakeMain(catalog=catalog, **config_overrides)
    bridge = EcosystemBridge(main)
    return main, bridge


def make_ctx_for(main):
    return make_ctx(main)


async def test_refresh_builds_tools_from_catalog():
    catalog = {
        "Weather": [
            {"name": "get_weather", "signature": "(city: str, days: int = 1)", "description": "查询天气"}
        ],
        "QvQChat": [{"name": "chat", "signature": "(session_id, prompt)"}],
    }
    main, bridge = make_bridge(catalog)
    main.sdk.module.handlers[("Weather", "get_weather")] = {"warm": 26}
    info = await bridge.refresh()
    assert info["modules"] == 1 and info["tools"] == 1
    tool = main.registry.get("eco_Weather_get_weather")
    assert tool is not None
    assert "查询天气" in tool.description
    assert tool.parameters["required"] == ["city"]
    assert tool.parameters["properties"]["days"]["default"] == 1
    result = await tool.handler(make_ctx_for(main), city="杭州")
    assert ("Weather", "get_weather", (), {"city": "杭州"}) in main.sdk.module.calls
    assert "warm" in result


async def test_extension_prompts_channel_removed():
    """qvq_prompts 注入通道已删除：不调用、不存储，服务改为由签名实时生成工具。"""
    catalog = {"Notes": [{"name": "search", "signature": "(q: str)"}]}
    main, bridge = make_bridge(catalog)
    main.sdk.module.handlers[("Notes", "qvq_prompts")] = [
        "low priority line",
        {"text": "high priority line", "priority": 5},
    ]
    await bridge.refresh()
    assert not any(call[1] == "qvq_prompts" for call in main.sdk.module.calls)
    assert all("prompts" not in entry for entry in bridge.extensions_status())


async def test_extension_personas_registered_and_cleaned():
    catalog = {"Notes": [{"name": "search", "signature": "(q: str)"}]}
    main, bridge = make_bridge(catalog)
    main.sdk.module.handlers[("Notes", "qvq_personas")] = [
        {"id": "scholar", "name": "学者", "system": "你是严谨的学者。"}
    ]
    await bridge.refresh()
    assert main.personas.get("ext.Notes.scholar")["id"] == "ext.Notes.scholar"
    main.sdk.module.handlers[("Notes", "qvq_personas")] = []
    await bridge.refresh()
    assert main.personas.delete("ext.Notes.scholar") is False


async def test_extension_schemas_override_signature():
    catalog = {"Weather": [{"name": "get_weather", "signature": "(city, days=1)"}]}
    main, bridge = make_bridge(catalog)
    main.sdk.module.handlers[("Weather", "qvq_schemas")] = {
        "get_weather": {
            "type": "object",
            "properties": {"city": {"type": "string"}, "unit": {"type": "string"}},
            "required": ["city", "unit"],
        }
    }
    await bridge.refresh()
    tool = main.registry.get("eco_Weather_get_weather")
    assert tool.parameters["required"] == ["city", "unit"]
    assert "unit" in tool.parameters["properties"]


async def test_refresh_excludes_and_respects_include():
    catalog = {
        "A": [{"name": "s1", "signature": "()"}],
        "B": [{"name": "s2", "signature": "()"}],
    }
    main, bridge = make_bridge(catalog, eco_include=["A"])
    info = await bridge.refresh()
    assert info["tools"] == 1
    main2, bridge2 = make_bridge(catalog, eco_exclude=["A", "B"])
    info2 = await bridge2.refresh()
    assert info2["tools"] == 0


async def test_refresh_replaces_previous_tools():
    main, bridge = make_bridge({"A": [{"name": "s1", "signature": "()"}]})
    await bridge.refresh()
    assert main.registry.get("eco_A_s1") is not None
    main.sdk.module._catalog = {}
    await bridge.refresh()
    assert main.registry.get("eco_A_s1") is None


async def test_service_catalog_unavailable_is_tolerated():
    main, bridge = make_bridge(None)

    def broken():
        raise RuntimeError("old sdk")

    main.sdk.module.services = broken
    info = await bridge.refresh()
    assert info["tools"] == 0


async def test_lifecycle_subscription_registered():
    main, bridge = make_bridge({})
    bridge.start()
    events = [name for name, _ in main.sdk.lifecycle.registered]
    assert "module.load" in events and "module.unload" in events


async def test_eco_access_declared_by_module():
    """模块经 qvq_access 自声明 safe：只读服务对所有人开放，写库服务保持 admin。"""
    catalog = {
        "QvQMemes": [
            {"name": "send_sticker", "signature": "(query: str)", "description": "发表情包"},
            {"name": "sticker_add", "signature": "(url: str = '')", "description": "收录表情包"},
        ],
    }
    main, bridge = make_bridge(catalog)
    main.sdk.module.handlers[("QvQMemes", "qvq_access")] = {
        "send_sticker": "safe",
        "sticker_add": "admin",
    }
    await bridge.refresh()
    assert main.registry.get("eco_QvQMemes_send_sticker").access == "safe"
    assert main.registry.get("eco_QvQMemes_sticker_add").access == "admin"
    hint = bridge.safe_tool_hint()
    assert "eco_QvQMemes_send_sticker" in hint
    assert "sticker_add" not in hint


async def test_eco_access_default_admin_without_declaration():
    catalog = {"Weather": [{"name": "get_weather", "signature": "(city: str)"}]}
    main, bridge = make_bridge(catalog)
    await bridge.refresh()
    assert main.registry.get("eco_Weather_get_weather").access == "admin"


async def test_eco_access_operator_overrides():
    """运营方 eco_admin 能否决自声明 safe；eco_safe 可抬高未声明服务。"""
    catalog = {
        "QvQMemes": [{"name": "send_sticker", "signature": "(query: str)"}],
        "Weather": [{"name": "get_weather", "signature": "(city: str)"}],
    }
    main, bridge = make_bridge(catalog, eco_admin=["QvQMemes:*"], eco_safe=["Weather:get_weather"])
    main.sdk.module.handlers[("QvQMemes", "qvq_access")] = {"send_sticker": "safe"}
    await bridge.refresh()
    assert main.registry.get("eco_QvQMemes_send_sticker").access == "admin"
    assert main.registry.get("eco_Weather_get_weather").access == "safe"


async def test_eco_access_inline_meta_forward_compat():
    """未来框架透传服务条目自定义字段时，access 字段自动生效。"""
    catalog = {"Pic": [{"name": "search", "signature": "(q: str)", "access": "safe"}]}
    main, bridge = make_bridge(catalog)
    await bridge.refresh()
    assert main.registry.get("eco_Pic_search").access == "safe"
