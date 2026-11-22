"""构建 demo/index.html：真实前端资产 + mock.js 内联成单文件（无后端可跑的面板演示）。

用法：仓库根目录 `python demo/build.py`，产物 demo/index.html（双击或静态托管）。
前端资产改动后重跑一次即可与包内界面保持同步。
构建时从 QvQConfig 生成真实配置 schema（与后端 config_get 同一序列化规则），
设置页演示的是真实配置项而非手写样例。
"""

import json
import os
from dataclasses import fields as dc_fields
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.normpath(os.path.join(HERE, "..", "QvQChat", "dashboard", "templates", "web"))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

# 与 manager.FAVICON_SVG 同款机器人图案，demo 静态托管也带站点图标
FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#3aa5dc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="4" y="7" width="16" height="12" rx="2"/>'
    '<circle cx="9" cy="13" r="1.2" fill="#3aa5dc"/>'
    '<circle cx="15" cy="13" r="1.2" fill="#3aa5dc"/>'
    '<path d="M12 7V4"/><circle cx="12" cy="3" r="1" fill="#3aa5dc"/>'
    '<path d="M4 17l-2 2M20 17l2 2"/></svg>'
)

MODEL_CHOICES = ["deepseek-chat", "deepseek-reasoner", "Qwen/Qwen2.5-72B-Instruct"]
LIST_CHOICES = {
    "admin_tools": ["send_message", "run_command", "run_python", "web_search"],
    "safe_tools": ["send_message", "web_search", "knowledge_search"],
    "disabled_tools": [],
    "chat_whitelist": ["onebot11:group:1049", "onebot11:private:643319481"],
    "participation_groups": ["onebot11:group:1049"],
    "participation_groups_exclude": [],
    "skills_disabled": [],
    "forward_platforms": ["onebot11", "yunhu"],
    "no_forward_platforms": [],
}
MODEL_KEYS = {
    "default_model", "aux_model", "handover_model",
    "compact_model", "tool_select_model",
}


def read(rel: str) -> str:
    with open(os.path.join(WEB, rel), encoding="utf-8") as f:
        return f.read()


def inline(text: str) -> str:
    # 与 manager._inline_script 同规则：防 </script 提前闭合
    return "<script>" + text.replace("</script", "<\\/script") + "</script>"


def generated_config_js() -> str:
    """从 QvQConfig 生成与后端 config_get 同形的 {fields, groups}（demo 设置页数据源）。"""
    import sys

    sys.path.insert(0, ROOT)
    from QvQChat.Config import QvQConfig

    defaults = QvQConfig()
    fields = []
    for f in dc_fields(QvQConfig):
        meta = f.metadata or {}
        desc = meta.get("description") or {}
        text = str(desc.get("default") or "") if isinstance(desc, dict) else str(desc)
        ui = meta.get("ui") or {}
        value = getattr(defaults, f.name, None)
        secret = bool(ui.get("secret"))
        if secret and value not in (None, ""):
            value = "******"
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False) if f.name == "task_models" else value
        field = {
            "key": f.name,
            "value": value,
            "description": text,
            "group": str(ui.get("group") or "other"),
            "order": ui.get("order", 99),
            "widget": str(ui.get("widget") or "text"),
            "options": ui.get("options"),
            "type": QvQConfig.type_of(f.name),
            "min": ui.get("min"),
            "max": ui.get("max"),
            "step": ui.get("step"),
            "placeholder": ui.get("placeholder"),
            "secret": secret,
            "dangerous": bool(ui.get("dangerous")),
            "items": ui.get("items"),
        }
        if f.name in LIST_CHOICES:
            field["choices"] = LIST_CHOICES[f.name]
        elif f.name in MODEL_KEYS:
            field["choices"] = MODEL_CHOICES
        elif f.name == "task_models":
            field["widget"] = "model_map"
            field["items"] = ["chat", "compact", "title", "vision", "toolselect", "announce"]
            field["choices"] = MODEL_CHOICES
        fields.append(field)
    payload = {"fields": fields, "groups": QvQConfig.groups()}
    return "window.GENERATED_CONFIG = " + json.dumps(payload, ensure_ascii=False) + ";"


ORDER = (
    "i18n", "store", "api", "theme", "md",
    "components/AppShell", "components/LoginPage", "components/PageOverview",
    "components/PageChat", "components/PageProviders", "components/PagePlatforms",
    "components/PagePersonas", "components/PageConfig", "components/PagePlugins",
    "components/PageSkills", "components/PageTasks", "components/PageMemory",
    "components/PageKnowledge", "components/PageSessions", "components/PageAudit",
    "components/PageStorage", "components/PageTools", "components/PageMcp",
    "components/PageOrchestrate", "components/BackupPanel", "components/PageInbox",
            "components/PageUsage",
    "components/SettingsSection",
    "components/SchemaForm", "components/QuickPanel",
    "components/Mascot", "main",
)


def check_i18n_keys() -> None:
    """五语言键完整性校验：任一语言缺失 zh-CN 全集里的键即构建失败（防界面裸键）。"""
    import re

    text = read("i18n.js")
    # 字符串字面量里的 {placeholder} 会干扰花括号配平：先等长替换为空白（偏移不变）
    cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', lambda m: '"' + " " * (len(m.group(0)) - 2) + '"', text)
    langs = {}
    for m in re.finditer(r'"(zh-CN|zh-TW|en|ja|ru)":\s*\{', text):
        name = m.group(1)
        start = m.end() - 1
        depth, i = 0, start
        while i < len(cleaned):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[start:i]
        langs[name] = set(re.findall(r'([A-Za-z0-9_]+)\s*:', body))
        for assign in re.findall(r'I18N\["%s"\]\s*=\s*Object\.assign\([^,]+,\s*\{(.*?)\}\);' % re.escape(name), text, re.S):
            langs[name] |= set(re.findall(r'([A-Za-z0-9_]+)\s*:', assign))
    base = langs.get("zh-CN", set())
    missing = {ln: sorted(base - keys) for ln, keys in langs.items() if base - keys}
    if missing:
        raise SystemExit("i18n 缺键: " + json.dumps(missing, ensure_ascii=False))


check_i18n_keys()

css = read(os.path.join("styles", "app.css"))
html = read("app.html")
vendor = "".join(inline(read(os.path.join("vendor", n))) for n in ("vue.global.prod.js", "naive-ui.prod.js"))
generated = inline(generated_config_js())
mock = inline(read(os.path.join(HERE, "mock.js")))
js = "".join(inline(read(f"{n}.js")) for n in ORDER)

doc = (
    "<!DOCTYPE html><html data-theme='dark'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    "<title>QvQChat Demo</title>"
    "<link rel='icon' type='image/svg+xml' href='data:image/svg+xml," + quote(FAVICON_SVG) + "'>"
    "<style>html,body{margin:0;padding:0;height:100%}" + css + "</style></head>"
    "<body>" + html + vendor + generated + mock + js + "</body></html>"
)

out = os.path.join(HERE, "index.html")
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write(doc)
print("built", out, len(doc), "bytes")
