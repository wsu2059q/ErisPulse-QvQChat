"""插件设置注册域：qvq_settings 描述符规范化、值校验与覆盖存储。

插件经约定服务 ``qvq_settings()`` 声明可配置项（纯数据描述符），
QvQChat 负责发现（bridge/ecosystem.py）、校验（本模块）、存储
（``QvQChat:plugin_cfg:{module}``，仅覆盖值）与合并读取。

``validate_by_descriptor`` 与 ``QvQConfig.coerce`` 同语义，但不依赖
dataclass：描述符本身就是 schema。
"""
from __future__ import annotations

from . import texts

# 覆盖值存储键前缀（值形如 {key: coerced}，仅保存被覆盖的键）
PLUGIN_CFG_PREFIX = "QvQChat:plugin_cfg:"

SETTING_TYPES = ("str", "int", "float", "bool", "list")
SETTING_WIDGETS = ("text", "number", "switch", "select", "list", "json")

# 按类型推导默认控件（描述符未声明 widget 时）
_TYPE_WIDGETS = {"str": "text", "int": "number", "float": "number", "bool": "switch", "list": "list"}


def _num_or_none(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def normalize_settings_payload(raw, module: str) -> dict | None:
    """把插件 ``qvq_settings()`` 返回值规范化为 ``{title, items}``。

    非法载荷 / 无合法 item 返回 None（调用方不收录该模块）；
    单条非法 item 丢弃，不影响其余。
    """
    if not isinstance(raw, dict):
        return None
    items = []
    for item in raw.get("items") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        type_ = str(item.get("type") or "").strip()
        if not key or type_ not in SETTING_TYPES:
            continue
        widget = str(item.get("widget") or "").strip()
        if widget not in SETTING_WIDGETS:
            widget = _TYPE_WIDGETS.get(type_, "text")
        options = item.get("options")
        if isinstance(options, (list, tuple)) and options:
            options = [str(o) for o in options]
        else:
            options = None
        desc = item.get("desc")
        items.append(
            {
                "key": key,
                "type": type_,
                "default": item.get("default"),
                "widget": widget,
                "options": options,
                "min": _num_or_none(item.get("min")),
                "max": _num_or_none(item.get("max")),
                "step": _num_or_none(item.get("step")),
                "dangerous": bool(item.get("dangerous")),
                "desc": str(desc) if desc is not None else key,
            }
        )
    if not items:
        return None
    return {"title": str(raw.get("title") or module), "items": items}


def validate_by_descriptor(item: dict, value):
    """按描述符抝合并校验一个值，返回 ``(ok, coerced, err)``。

    语义与 QvQConfig.coerce 一致：bool 仅收 bool；数字收数字与数字字符串
    （空串报错），int 拒绝非整数；min/max 区间校验；select 校验成员；
    list 收列表/元组（逐项转 str 去空）或多行字符串（按行拆分）。
    """
    key = str(item.get("key") or "")
    type_ = str(item.get("type") or "")

    if type_ == "bool":
        if isinstance(value, bool):
            return True, value, None
        return False, None, texts.t("config_err_bool", name=key)

    if type_ in ("int", "float"):
        if isinstance(value, bool) or value is None:
            return False, None, texts.t("config_err_number", name=key)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return False, None, texts.t("config_err_number", name=key)
            try:
                value = float(text)
            except ValueError:
                return False, None, texts.t("config_err_number", name=key)
        if not isinstance(value, (int, float)):
            return False, None, texts.t("config_err_number", name=key)
        if type_ == "int":
            if isinstance(value, float) and not value.is_integer():
                return False, None, texts.t("config_err_int", name=key)
            coerced = int(value)
        else:
            coerced = float(value)
        lo, hi = item.get("min"), item.get("max")
        if (lo is not None and coerced < lo) or (hi is not None and coerced > hi):
            return False, None, texts.t("config_err_range", name=key, min=lo, max=hi)
        return True, coerced, None

    if type_ == "list":
        if value is None:
            return True, [], None
        if isinstance(value, str):
            raw_items = value.split("\n")
        elif isinstance(value, (list, tuple)):
            raw_items = list(value)
        else:
            return False, None, texts.t("config_err_list", name=key)
        coerced = []
        for entry in raw_items:
            text = str(entry).strip()
            if text:
                coerced.append(text)
        return True, coerced, None

    # str（含 select：校验成员）
    if value is None:
        value = ""
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    options = item.get("options")
    if options and value not in options:
        return False, None, texts.t("config_err_option", name=key, options=", ".join(str(o) for o in options))
    return True, value, None


def storage_key(module: str) -> str:
    return PLUGIN_CFG_PREFIX + module


def load_overrides(sdk, module: str) -> dict:
    """读取某模块的覆盖值（无则空 dict；坏数据容错为空）。"""
    try:
        stored = sdk.storage.get(storage_key(module), {})
    except Exception:
        return {}
    return dict(stored) if isinstance(stored, dict) else {}


def save_overrides(sdk, module: str, updates: dict) -> dict:
    """合并写入覆盖值并返回写后的全量覆盖表。"""
    overrides = load_overrides(sdk, module)
    overrides.update(updates)
    sdk.storage.set(storage_key(module), overrides)
    return overrides


def merge_entry(entry: dict, overrides: dict) -> dict:
    """描述符默认值 + 覆盖值 → 该模块的全量生效值（覆盖仅作用于同名键）。"""
    merged = {}
    for item in entry.get("items") or []:
        key = item.get("key")
        merged[key] = overrides[key] if key in overrides else item.get("default")
    return merged
