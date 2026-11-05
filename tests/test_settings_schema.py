"""设置校验 seam：QvQConfig.coerce / GROUP_META / 元数据。"""

from dataclasses import fields as dc_fields

from QvQChat.Config import GROUP_META, QvQConfig


def _ui(key: str) -> dict:
    f = QvQConfig.field_map()[key]
    return (f.metadata or {}).get("ui") or {}


def test_coerce_rejects_empty_string_number():
    """清空数字字段必须报错，而不是把 "" 落盘（存量 int("") 崩溃链的止血点）。"""
    ok, coerced, err = QvQConfig.coerce("context_limit", "")
    assert ok is False
    assert coerced is None
    assert err


def test_coerce_bool_only_accepts_bool():
    assert QvQConfig.coerce("reply_private", True) == (True, True, None)
    assert QvQConfig.coerce("reply_private", False)[0] is True
# 字符串 "true" / 数字 1 都不再被当作 bool（bool 是 int 子类，需显式拒绝）
    assert QvQConfig.coerce("reply_private", "true")[0] is False
    assert QvQConfig.coerce("reply_private", 1)[0] is False


def test_coerce_number_string_and_types():
    ok, coerced, _ = QvQConfig.coerce("context_limit", "30")
    assert ok is True and coerced == 30 and isinstance(coerced, int)
    ok, coerced, _ = QvQConfig.coerce("split_delay", "1.5")
    assert ok is True and coerced == 1.5 and isinstance(coerced, float)
    ok, coerced, _ = QvQConfig.coerce("aggregate_window", 0)
    assert ok is True and coerced == 0.0
# 非数字字符串 / None / 小数给 int 字段
    assert QvQConfig.coerce("context_limit", "abc")[0] is False
    assert QvQConfig.coerce("context_limit", None)[0] is False
    assert QvQConfig.coerce("context_limit", 1.5)[0] is False


def test_coerce_min_max_range():
    assert QvQConfig.coerce("keep_ratio", 0.9)[0] is False
    assert QvQConfig.coerce("keep_ratio", 0.05)[0] is False
    ok, coerced, _ = QvQConfig.coerce("keep_ratio", 0.3)
    assert ok is True and coerced == 0.3
    assert QvQConfig.coerce("temperature", -0.5)[0] is False
    ok, coerced, _ = QvQConfig.coerce("temperature", 1.2)
    assert ok is True and coerced == 1.2


def test_coerce_select_membership():
    assert QvQConfig.coerce("security_level", "strict") == (True, "strict", None)
    ok, _, err = QvQConfig.coerce("security_level", "wild")
    assert ok is False and err
    ok, coerced, _ = QvQConfig.coerce("interrupt_mode", "interrupt")
    assert ok is True and coerced == "interrupt"


def test_coerce_list_element_coercion():
    ok, coerced, _ = QvQConfig.coerce("wake_prefixes", ["a", 1, " b ", ""])
    assert ok is True and coerced == ["a", "1", "b"]
# 字符串输入按行拆分（不再整串存进去被逐字符迭代）
    ok, coerced, _ = QvQConfig.coerce("wake_prefixes", "x\ny\n\n z ")
    assert ok is True and coerced == ["x", "y", "z"]
    ok, coerced, _ = QvQConfig.coerce("wake_prefixes", None)
    assert ok is True and coerced == []
# 其它标量类型拒收
    assert QvQConfig.coerce("wake_prefixes", 5)[0] is False


def test_coerce_unknown_key():
    ok, _, err = QvQConfig.coerce("not_a_key", 1)
    assert ok is False and err


def test_coerce_str_and_secret_roundtrip():
    assert QvQConfig.coerce("view_token", "tok-1") == (True, "tok-1", None)
    assert QvQConfig.coerce("default_model", "p1:m1") == (True, "p1:m1", None)
    ok, coerced, _ = QvQConfig.coerce("default_model", 123)
    assert ok is True and coerced == "123"


def test_metadata_fixes():
    assert _ui("compact_model")["widget"] == "text"
    assert _ui("mcp_timeout")["order"] == 1
    assert _ui("view_token").get("secret") is True
    assert _ui("keep_ratio")["widget"] == "slider"
    assert _ui("keep_ratio")["min"] == 0.1 and _ui("keep_ratio")["max"] == 0.5
    assert _ui("temperature")["widget"] == "slider"
    assert _ui("disabled_tools").get("items") == "tools"
    assert _ui("skills_disabled").get("items") == "skills"


def test_dangerous_flags():
    for key in ("security_level", "trust_agent", "self_config", "admins", "work_dirs", "sensitive_paths"):
        assert _ui(key).get("dangerous") is True, key


def test_chat_group_orders_dense_and_unique():
    orders = sorted(
        (f.metadata or {}).get("ui", {}).get("order")
        for f in dc_fields(QvQConfig)
        if ((f.metadata or {}).get("ui") or {}).get("group") == "chat"
    )
    assert orders == list(range(1, len(orders) + 1))


def test_groups_table_covers_all_field_groups():
    table = QvQConfig.groups()
    ids = [g["id"] for g in table]
    used = {
        ((f.metadata or {}).get("ui") or {}).get("group", "other")
        for f in dc_fields(QvQConfig)
    }
    assert used <= set(ids)
# 组序来自 GROUP_META 注册表：模型/触发/对话在前，安全/权限收尾
    assert ids.index("model") < ids.index("chat") < ids.index("security") < ids.index("access")
    assert set(GROUP_META) <= set(ids)
