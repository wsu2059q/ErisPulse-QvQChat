"""构建 demo/index.html：真实前端资产 + mock.js 内联成单文件（无后端可跑的面板演示）。

用法：仓库根目录 `python demo/build.py`，产物 demo/index.html（双击或静态托管）。
前端资产改动后重跑一次即可与包内界面保持同步。
"""

import os
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.normpath(os.path.join(HERE, "..", "QvQChat", "dashboard", "templates", "web"))

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


def read(rel: str) -> str:
    with open(os.path.join(WEB, rel), encoding="utf-8") as f:
        return f.read()


def inline(text: str) -> str:
    # 与 manager._inline_script 同规则：防 </script 提前闭合
    return "<script>" + text.replace("</script", "<\\/script") + "</script>"


ORDER = (
    "i18n", "store", "api", "theme", "md",
    "components/AppShell", "components/LoginPage", "components/PageOverview",
    "components/PageChat", "components/PageProviders", "components/PagePlatforms",
    "components/PagePersonas", "components/PageConfig", "components/PagePlugins",
    "components/PageSkills", "components/PageTasks", "components/PageMemory",
    "components/PageKnowledge", "components/PageSessions", "components/PageAudit",
    "components/PageStorage", "components/PageTools", "components/PageMcp",
    "components/PageOrchestrate", "components/BackupPanel", "components/PageInbox",
    "components/SchemaForm", "components/QuickPanel",
    "components/Mascot", "main",
)

css = read(os.path.join("styles", "app.css"))
html = read("app.html")
vendor = "".join(inline(read(os.path.join("vendor", n))) for n in ("vue.global.prod.js", "naive-ui.prod.js"))
mock = inline(read(os.path.join(HERE, "mock.js")))
js = "".join(inline(read(f"{n}.js")) for n in ORDER)

doc = (
    "<!DOCTYPE html><html data-theme='dark'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    "<title>QvQChat Demo</title>"
    "<link rel='icon' type='image/svg+xml' href='data:image/svg+xml," + quote(FAVICON_SVG) + "'>"
    "<style>html,body{margin:0;padding:0;height:100%}" + css + "</style></head>"
    "<body>" + html + vendor + mock + js + "</body></html>"
)

out = os.path.join(HERE, "index.html")
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write(doc)
print("built", out, len(doc), "bytes")
