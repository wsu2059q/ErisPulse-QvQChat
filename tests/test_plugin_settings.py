"""插件设置（框架声明式配置流）：qvq_settings 归属标记发现 / ConfigClass schema 端点 /
save 校验 + 逐键 setConfig + 事件 / plugin_config 服务（getConfig 现值透传）。"""

from dataclasses import dataclass, field
from types import SimpleNamespace

from QvQChat.Main import Main
from QvQChat.bridge.ecosystem import EcosystemBridge
from QvQChat.dashboard.manager import DashboardManager

from fakes import FakeMain

MODULE = "QvQStalker"


def _desc(key, text, widget="text", options=None, order=1):
    ui = {"widget": widget, "group": "basic", "order": order}
    if options:
        ui["options"] = options
    return {"description": {"i18n": f"Fake.{key}", "default": text}, "ui": ui}


@dataclass
class StalkerConfig:
    """测试用插件 ConfigClass（与真实插件同构：_desc 声明式元数据）。"""

    mode: str = field(
        default="balanced",
        metadata=_desc("mode", "参与模式", "select", ["conservative", "balanced", "active"], 1),
    )
    urge_threshold: float = field(
        default=1.0, metadata=_desc("urge_threshold", "冲动值阈值", "number", order=2)
    )
    llm_judge: bool = field(default=False, metadata=_desc("llm_judge", "小模型判断", "switch", order=3))


@dataclass
class RequiredConfig:
    """带 required 约束的最小 ConfigClass（校验失败路径用）。"""

    token: str = field(default="", metadata={**_desc("token", "访问令牌", order=1), "required": True})


class FakeJsonRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


class FakeQp:
    pass


def make_bridge(catalog=None):
    main = FakeMain(catalog=catalog)
    return main, EcosystemBridge(main)


def make_manager(catalog=None, config_class=StalkerConfig):
    main = FakeMain()
    if catalog is None:
        catalog = {MODULE: "QvQStalker 群聊参与决策"}
    main.plugin_settings_catalog = dict(catalog)
    if config_class is not None:
        main.sdk.module._module_classes[MODULE] = type(
            "StalkerModule", (), {"ConfigClass": config_class}
        )
    return main, DashboardManager(main)


# ==================== 发现（ecosystem qvq_settings → 归属标记目录 {module: title}） ====================

async def test_refresh_collects_settings_title_marker():
    catalog = {"QvQStalker": [{"name": "qvq_decision", "signature": "()"}]}
    main, bridge = make_bridge(catalog)
    main.sdk.module.handlers[("QvQStalker", "qvq_settings")] = {"title": "QvQStalker 群聊参与决策"}
    await bridge.refresh()
    assert main.plugin_settings_catalog == {"QvQStalker": "QvQStalker 群聊参与决策"}


async def test_settings_title_missing_falls_back_to_module_name():
    main, bridge = make_bridge({"A": [{"name": "s1", "signature": "()"}]})
    main.sdk.module.handlers[("A", "qvq_settings")] = {}  # 声明了服务但没给 title
    await bridge.refresh()
    assert main.plugin_settings_catalog == {"A": "A"}


async def test_settings_service_probe_failure_is_silent():
    """白名单陷阱：服务未声明/抛错 → 静默跳过，不进目录。"""
    main, bridge = make_bridge({"A": [{"name": "s1", "signature": "()"}]})

    def boom(**kw):
        raise RuntimeError("not whitelisted")

    main.sdk.module.handlers[("A", "qvq_settings")] = boom
    await bridge.refresh()
    assert main.plugin_settings_catalog == {}
    del main.sdk.module.handlers[("A", "qvq_settings")]  # 服务不存在（call 抛错）同样静默
    await bridge.refresh()
    assert main.plugin_settings_catalog == {}


async def test_settings_catalog_hot_refresh_add_remove():
    main, bridge = make_bridge({"QvQStalker": [{"name": "qvq_decision", "signature": "()"}]})
    main.sdk.module.handlers[("QvQStalker", "qvq_settings")] = {"title": "T"}
    await bridge.refresh()
    assert main.plugin_settings_catalog == {"QvQStalker": "T"}
    del main.sdk.module.handlers[("QvQStalker", "qvq_settings")]  # 模拟卸载
    await bridge.refresh()
    assert main.plugin_settings_catalog == {}


# ==================== plugin_config 服务（getConfig 现值透传 + module 过滤） ====================

async def test_plugin_config_reads_framework_config_values():
    main = FakeMain()
    main.plugin_settings_catalog = {MODULE: "T", "Other": "O"}
    main.sdk.config.setConfig("QvQStalker.mode", "active")
    fake_self = SimpleNamespace(sdk=main.sdk, plugin_settings_catalog=main.plugin_settings_catalog)
    result = await Main.plugin_config(fake_self)
    assert result["QvQStalker"] == {"mode": "active"}  # 框架 config 现值（无默认值合并）
    assert result["Other"] == {}                       # 未配置 → 空 dict
    result = await Main.plugin_config(fake_self, module="QvQStalker")
    assert set(result) == {"QvQStalker"}
    result = await Main.plugin_config(fake_self, module="NoSuch")
    assert result == {}


# ==================== 端点：GET 形状（框架 schema + getConfig 现值） ====================

async def test_plugin_settings_get_schema_shape():
    main, manager = make_manager()
    main.sdk.config.setConfig("QvQStalker.mode", "active")
    data = await manager.plugin_settings_get(FakeQp())
    assert len(data["modules"]) == 1
    module = data["modules"][0]
    assert module["module"] == MODULE
    assert module["title"] == "QvQStalker 群聊参与决策"
    assert module["config_key"] == MODULE
    fields = module["schema"]["fields"]
    assert fields["mode"]["widget"] == "select"
    assert fields["mode"]["options"] == ["conservative", "balanced", "active"]
    assert fields["mode"]["description"] == "参与模式"  # i18n 已解析（default 兜底）
    assert fields["llm_judge"]["widget"] == "switch"
    assert fields["urge_threshold"]["type"] == "float"
    assert module["values"] == {"mode": "active"}  # sdk.config 现值


async def test_plugin_settings_get_skips_modules_without_config_class():
    main, manager = make_manager(catalog={"Ghost": "G"})
    data = await manager.plugin_settings_get(FakeQp())  # Ghost 无模块类/ConfigClass → 跳过
    assert data == {"modules": []}


async def test_plugin_settings_get_empty_catalog():
    main, manager = make_manager(catalog={})
    assert await manager.plugin_settings_get(FakeQp()) == {"modules": []}


# ==================== 端点：保存（框架校验 + 逐键 setConfig + 事件） ====================

async def test_plugin_settings_save_validates_and_applies():
    main, manager = make_manager()
    main.sdk.config.setConfig("QvQStalker.llm_judge", True)  # 已存现值参与合并
    res = await manager.plugin_settings_save(FakeJsonRequest({
        "module": MODULE,
        "values": {"mode": "active", "urge_threshold": "2.5"},  # str → float 由框架 coerce
    }))
    assert res == {"ok": True, "applied": ["mode", "urge_threshold"]}
    sets = main.sdk.config_sets
    assert ("QvQStalker.mode", "active") in sets
    assert ("QvQStalker.urge_threshold", 2.5) in sets
    assert ("QvQStalker.llm_judge", True) in sets  # 现值合并后逐键回写
    event, payload = main.sdk.lifecycle.emitted[-1]
    assert event == "qvq.plugin_config"
    assert payload["module"] == MODULE
    assert payload["values"] == {"mode": "active", "urge_threshold": 2.5, "llm_judge": True}


async def test_plugin_settings_save_rejects_invalid_values():
    main, manager = make_manager()
    res = await manager.plugin_settings_save(FakeJsonRequest({
        "module": MODULE,
        "values": {"mode": "wild", "llm_judge": True},  # mode 违反枚举 → 整体 400
    }))
    assert res[1] == 400
    assert res[0]["ok"] is False
    assert res[0]["applied"] == []
    assert set(res[0]["errors"]) == {"mode"}  # 校验错误按提交键归位
    assert main.sdk.config_sets == []         # 拒收：不落盘
    assert main.sdk.lifecycle.emitted == []


async def test_plugin_settings_save_rejects_required_empty():
    main, manager = make_manager(config_class=RequiredConfig)
    res = await manager.plugin_settings_save(FakeJsonRequest({
        "module": MODULE,
        "values": {"token": ""},
    }))
    assert res[1] == 400
    assert set(res[0]["errors"]) == {"token"}
    assert main.sdk.config_sets == []


async def test_plugin_settings_save_rejects_unknown_module_and_bad_body():
    main, manager = make_manager()
    res = await manager.plugin_settings_save(FakeJsonRequest({"module": "Nope", "values": {"a": 1}}))
    assert res[1] == 400
    res = await manager.plugin_settings_save(FakeJsonRequest({"module": MODULE, "values": "bad"}))
    assert res[1] == 400
    res = await manager.plugin_settings_save(FakeJsonRequest(["not", "dict"]))
    assert res[1] == 400
    assert main.sdk.config_sets == []
