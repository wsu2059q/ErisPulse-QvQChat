"""插件设置注册闭环：qvq_settings 发现 / descriptor 校验 / plugin_config 服务 / 端点与事件。"""

from types import SimpleNamespace

from QvQChat.Main import Main
from QvQChat.bridge.ecosystem import EcosystemBridge
from QvQChat.dashboard.manager import DashboardManager
from QvQChat.pluginsettings import (
    PLUGIN_CFG_PREFIX,
    normalize_settings_payload,
    validate_by_descriptor,
)

from fakes import FakeMain

DESCRIPTORS = {
    "title": "QvQStalker 群聊参与",
    "items": [
        {"key": "mode", "type": "str", "default": "balanced", "widget": "select",
         "options": ["conservative", "balanced", "active"], "desc": "参与模式"},
        {"key": "urge_threshold", "type": "float", "default": 1.0, "widget": "number",
         "min": 0, "max": 10, "desc": "冲动值阈值"},
        {"key": "min_messages_between_replies", "type": "int", "default": 15, "desc": "两次插话最小消息数"},
        {"key": "llm_judge", "type": "bool", "default": False, "widget": "switch", "desc": "L5 小模型判断"},
        {"key": "watch_words", "type": "list", "default": [], "desc": "关注词"},
    ],
}


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


def make_manager(catalog=None):
    main = FakeMain()
    if catalog is None:
        catalog = {"QvQStalker": normalize_settings_payload(DESCRIPTORS, "QvQStalker")}
    main.plugin_settings_catalog = catalog
    return main, DashboardManager(main)


# ==================== 发现（ecosystem qvq_settings → main.plugin_settings_catalog） ====================

async def test_refresh_collects_plugin_settings_catalog():
    catalog = {"QvQStalker": [{"name": "qvq_decision", "signature": "()"}]}
    main, bridge = make_bridge(catalog)
    main.sdk.module.handlers[("QvQStalker", "qvq_settings")] = DESCRIPTORS
    await bridge.refresh()
    entry = main.plugin_settings_catalog["QvQStalker"]
    assert entry["title"] == "QvQStalker 群聊参与"
    items = {i["key"]: i for i in entry["items"]}
    assert items["mode"]["widget"] == "select"
    assert items["mode"]["options"] == ["conservative", "balanced", "active"]
    assert items["min_messages_between_replies"]["widget"] == "number"  # 未声明 widget 按类型推导
    assert items["llm_judge"]["widget"] == "switch"
    assert items["mode"]["desc"] == "参与模式"


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
    main.sdk.module.handlers[("QvQStalker", "qvq_settings")] = DESCRIPTORS
    await bridge.refresh()
    assert "QvQStalker" in main.plugin_settings_catalog
    del main.sdk.module.handlers[("QvQStalker", "qvq_settings")]  # 模拟卸载
    await bridge.refresh()
    assert main.plugin_settings_catalog == {}


def test_normalize_filters_bad_items_and_falls_back_title():
    payload = {
        "items": [
            {"key": "ok", "type": "str", "default": "x", "desc": "正常项"},
            {"key": "", "type": "str"},               # 缺 key
            {"key": "bad_type", "type": "dict"},       # 非法类型
            "not-a-dict",
        ]
    }
    entry = normalize_settings_payload(payload, "Mod")
    assert [i["key"] for i in entry["items"]] == ["ok"]
    assert entry["title"] == "Mod"  # 未提供 title 回退模块名
    assert normalize_settings_payload(None, "Mod") is None
    assert normalize_settings_payload({"items": []}, "Mod") is None
    assert normalize_settings_payload({"items": [{"key": "k", "type": "dict"}]}, "Mod") is None


# ==================== validate_by_descriptor（与 QvQConfig.coerce 同语义） ====================

def _item(key, **kw):
    base = {"key": key, "type": "str"}
    base.update(kw)
    return base


def test_validate_bool_strict():
    assert validate_by_descriptor(_item("b", type="bool"), True) == (True, True, None)
    assert validate_by_descriptor(_item("b", type="bool"), False)[0] is True
# 字符串 "true" / 数字 1 都不是 bool
    assert validate_by_descriptor(_item("b", type="bool"), "true")[0] is False
    assert validate_by_descriptor(_item("b", type="bool"), 1)[0] is False


def test_validate_numbers_and_range():
    ok, coerced, _ = validate_by_descriptor(_item("n", type="int"), "15")
    assert ok is True and coerced == 15 and isinstance(coerced, int)
    ok, coerced, _ = validate_by_descriptor(_item("n", type="float"), "2.5")
    assert ok is True and coerced == 2.5 and isinstance(coerced, float)
    assert validate_by_descriptor(_item("n", type="int"), 1.5)[0] is False
    assert validate_by_descriptor(_item("n", type="int"), "")[0] is False
    assert validate_by_descriptor(_item("n", type="int"), None)[0] is False
    assert validate_by_descriptor(_item("n", type="int"), "abc")[0] is False
    assert validate_by_descriptor(_item("n", type="float", min=0, max=10), 11.0)[0] is False
    assert validate_by_descriptor(_item("n", type="float", min=0, max=10), -1)[0] is False
    assert validate_by_descriptor(_item("n", type="float", min=0, max=10), 3.3) == (True, 3.3, None)


def test_validate_select_membership():
    item = _item("mode", type="str", options=["a", "b"])
    assert validate_by_descriptor(item, "a") == (True, "a", None)
    assert validate_by_descriptor(item, "wild")[0] is False
    assert validate_by_descriptor(_item("s", type="str"), 123) == (True, "123", None)


def test_validate_list_element_coercion():
    item = _item("words", type="list")
    ok, coerced, _ = validate_by_descriptor(item, ["a", 1, " b ", ""])
    assert ok is True and coerced == ["a", "1", "b"]
    assert validate_by_descriptor(item, "x\ny\n\n z ") == (True, ["x", "y", "z"], None)
    assert validate_by_descriptor(item, None) == (True, [], None)
    assert validate_by_descriptor(item, 5)[0] is False


# ==================== plugin_config 服务（合并 + module 过滤） ====================

async def test_plugin_config_merges_and_filters():
    main = FakeMain()
    main.sdk.storage.set("QvQChat:plugin_cfg:QvQStalker", {"mode": "active"})
    catalog = {
        "QvQStalker": normalize_settings_payload(DESCRIPTORS, "QvQStalker"),
        "Other": normalize_settings_payload({"title": "O", "items": [{"key": "k", "type": "str", "default": "v"}]}, "Other"),
    }
    fake_self = SimpleNamespace(sdk=main.sdk, plugin_settings_catalog=catalog)
    result = await Main.plugin_config(fake_self)
    assert result["QvQStalker"]["mode"] == "active"      # 覆盖值
    assert result["QvQStalker"]["urge_threshold"] == 1.0  # 未覆盖 → 默认值
    assert result["Other"] == {"k": "v"}
    result = await Main.plugin_config(fake_self, module="QvQStalker")
    assert set(result) == {"QvQStalker"}
    result = await Main.plugin_config(fake_self, module="NoSuch")
    assert result == {}


# ==================== 端点：GET 形状 / 保存 + 事件 / 非法 400 ====================

async def test_plugin_settings_get_shape():
    main, manager = make_manager()
    main.sdk.storage.set(PLUGIN_CFG_PREFIX + "QvQStalker", {"mode": "active"})
    data = await manager.plugin_settings_get(FakeQp())
    assert len(data["modules"]) == 1
    module = data["modules"][0]
    assert module["module"] == "QvQStalker"
    assert module["title"] == "QvQStalker 群聊参与"
    items = {i["key"]: i for i in module["items"]}
    assert items["mode"]["value"] == "active"           # 覆盖值
    assert items["urge_threshold"]["value"] == 1.0      # 默认值
    assert items["mode"]["desc"] == "参与模式"
    assert items["mode"]["options"] == ["conservative", "balanced", "active"]


async def test_plugin_settings_get_empty_catalog():
    main, manager = make_manager(catalog={})
    assert await manager.plugin_settings_get(FakeQp()) == {"modules": []}


async def test_plugin_settings_save_applies_stores_and_emits():
    main, manager = make_manager()
    res = await manager.plugin_settings_save(FakeJsonRequest({
        "module": "QvQStalker",
        "values": {"mode": "active", "urge_threshold": "2.5"},
    }))
    assert res == {"ok": True, "applied": ["mode", "urge_threshold"]}
    stored = main.sdk.storage.get(PLUGIN_CFG_PREFIX + "QvQStalker")
    assert stored == {"mode": "active", "urge_threshold": 2.5}  # 仅覆盖值落盘
    event, payload = main.sdk.lifecycle.emitted[-1]
    assert event == "qvq.plugin_config"
    assert payload["module"] == "QvQStalker"
    assert payload["values"]["mode"] == "active"
    assert payload["values"]["urge_threshold"] == 2.5
    assert payload["values"]["llm_judge"] is False  # 事件载荷 = 合并后全量


async def test_plugin_settings_save_partial_and_rejects():
    main, manager = make_manager()
    res = await manager.plugin_settings_save(FakeJsonRequest({
        "module": "QvQStalker",
        "values": {"mode": "wild", "llm_judge": True, "bogus": 1},
    }))
    assert res[1] == 400
    assert res[0]["ok"] is False
    assert res[0]["applied"] == ["llm_judge"]
    assert set(res[0]["errors"]) == {"mode", "bogus"}
# 部分成功：合法键已落盘，非法键不落
    stored = main.sdk.storage.get(PLUGIN_CFG_PREFIX + "QvQStalker")
    assert stored == {"llm_judge": True}


async def test_plugin_settings_save_rejects_unknown_module_and_bad_body():
    main, manager = make_manager()
    res = await manager.plugin_settings_save(FakeJsonRequest({"module": "Nope", "values": {"a": 1}}))
    assert res[1] == 400
    res = await manager.plugin_settings_save(FakeJsonRequest({"module": "QvQStalker", "values": "bad"}))
    assert res[1] == 400
    res = await manager.plugin_settings_save(FakeJsonRequest(["not", "dict"]))
    assert res[1] == 400
    assert main.sdk.storage.get(PLUGIN_CFG_PREFIX + "QvQStalker") is None
