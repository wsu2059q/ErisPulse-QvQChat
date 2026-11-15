"""manage_plugin_config 工具：插件声明的配置读/改走框架声明式管线。

对齐 Dashboard 插件设置页行为：schema 出字段表、整节校验、逐键写入、qvq.plugin_config 事件。
"""
from dataclasses import dataclass, field

from QvQChat.agent.tools import ToolContext
from QvQChat.tools_builtin import selfconfig

from fakes import FakeMain


@dataclass
class ToyConfig:
    tag: str = field(default="x", metadata={"description": "标签"})
    limit: int = field(default=3, metadata={"description": "上限", "ui": {"min": 0, "max": 10}})
    secret_token: str = field(default="", metadata={"description": "令牌", "secret": True})


def make_ctx():
    main = FakeMain()
    main.plugin_settings_catalog = {"ToyPlugin": "玩具插件", "NoConfig": "无配置类"}
    main.sdk.module._module_classes["ToyPlugin"] = type("ToyPluginModule", (), {"ConfigClass": ToyConfig})
    main.sdk.module._module_classes["NoConfig"] = type("NoConfigModule", (), {})
    ctx = ToolContext(main=main, sdk=main.sdk, config=main.cfg, chat_key="test", origin="rpc")
    return main, ctx


async def test_list_shows_catalog_and_fields():
    main, ctx = make_ctx()
    out = await selfconfig.manage_plugin_config(ctx, action="list")
    assert "ToyPlugin" in out and "玩具插件" in out
    assert "tag" in out and "secret_token" in out


async def test_get_masks_secret_values():
    main, ctx = make_ctx()
    main.sdk.config.setConfig("ToyPlugin.secret_token", "sk-abc123")
    out = await selfconfig.manage_plugin_config(ctx, action="get", module="ToyPlugin")
    assert "sk-abc123" not in out and "***" in out
    out_key = await selfconfig.manage_plugin_config(ctx, action="get", module="ToyPlugin", key="tag")
    assert "tag" in out_key


async def test_set_applies_and_emits_event():
    main, ctx = make_ctx()
    out = await selfconfig.manage_plugin_config(ctx, action="set", module="ToyPlugin", values={"tag": "y", "limit": 5})
    assert '"ok": true' in out.lower()
    sets = dict(main.sdk.config.sets)
    assert sets.get("ToyPlugin.tag") == "y" and sets.get("ToyPlugin.limit") == 5
    emitted = [d for evt, d in main.sdk.lifecycle.emitted if evt == "qvq.plugin_config"]
    assert emitted and emitted[0]["module"] == "ToyPlugin"
# 整节读回（FakeConfig 合并点路径子键）
    out_get = await selfconfig.manage_plugin_config(ctx, action="get", module="ToyPlugin")
    assert '"tag": "y"' in out_get or "'tag': 'y'" in out_get or '"tag":"y"' in out_get


async def test_set_rejects_unknown_keys():
    main, ctx = make_ctx()
    out = await selfconfig.manage_plugin_config(ctx, action="set", module="ToyPlugin", values={"nope": 1})
    assert '"ok": false' in out.lower()
    assert not main.sdk.config.sets


async def test_set_rejects_invalid_values():
    main, ctx = make_ctx()
    out = await selfconfig.manage_plugin_config(ctx, action="set", module="ToyPlugin", values={"limit": "abc"})
    assert '"ok": false' in out.lower() or "errors" in out
    assert not main.sdk.config.sets


async def test_unknown_module_rejected():
    main, ctx = make_ctx()
    out = await selfconfig.manage_plugin_config(ctx, action="set", module="NotListed", values={"a": 1})
    assert "NotListed" in out
    out2 = await selfconfig.manage_plugin_config(ctx, action="get", module="NoConfig")
    assert "ConfigClass" in out2


async def test_qvqchat_own_config_untouched():
    main, ctx = make_ctx()
    out = await selfconfig.manage_plugin_config(ctx, action="set", module="QvQChat", values={"admins": ["1"]})
    assert "unknown plugin module" in out
