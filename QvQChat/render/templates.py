"""
内置渲染模板

每个模板是 HTML + CSS 的组合，用 {param} 占位符。
AI 通过 <|render|>tpl:模板名||key=value||key2=value2</|render|> 调用。
"""

from typing import Any, Dict


def _esc(value: Any) -> str:
    """HTML 转义"""
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# 模板定义: name -> {html, css, defaults, description}
BUILTIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "quote_card": {
        "description": "引言卡：一句话 + 作者，适合金句/吐槽",
        "params": {"text": "内容", "author": "作者/出处"},
        "defaults": {"text": "…", "author": ""},
        "html": """<div class="quote-card">
  <div class="quote-mark">“</div>
  <div class="quote-text">{text}</div>
  <div class="quote-author">—— {author}</div>
</div>""",
        "css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Noto Sans SC", sans-serif; }
.quote-card { width:640px; height:360px; background:linear-gradient(135deg,#1a1a2e,#16213e); border-radius:20px; padding:48px 40px; color:#fff; display:flex; flex-direction:column; justify-content:center; }
.quote-mark { font-size:72px; line-height:1; color:#e94560; margin-bottom:-16px; }
.quote-text { font-size:26px; line-height:1.6; margin:12px 0; }
.quote-author { text-align:right; font-size:16px; color:rgba(255,255,255,.6); margin-top:8px; }""",
    },
    "info_card": {
        "description": "信息卡：标题 + 多行要点，适合总结/要点",
        "params": {"title": "标题", "lines": "内容（多行用 \\n 分隔）"},
        "defaults": {"title": "信息", "lines": ""},
        "html": """<div class="info-card">
  <div class="info-title">{title}</div>
  <div class="info-lines">{lines_html}</div>
</div>""",
        "css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Noto Sans SC", sans-serif; }
.info-card { width:560px; padding:32px; background:#fff; border-radius:16px; box-shadow:0 8px 24px rgba(0,0,0,.08); border-top:4px solid #4f46e5; }
.info-title { font-size:24px; font-weight:700; color:#1f2937; margin-bottom:16px; }
.info-lines { font-size:16px; color:#374151; line-height:1.8; }
.info-lines .line { padding-left:16px; position:relative; }
.info-lines .line::before { content:"▸"; position:absolute; left:0; color:#4f46e5; }""",
    },
    "mood_card": {
        "description": "心情卡：大表情 + 状态文字，适合表达情绪",
        "params": {"emoji": "表情", "status": "状态描述"},
        "defaults": {"emoji": "😊", "status": ""},
        "html": """<div class="mood-card">
  <div class="mood-emoji">{emoji}</div>
  <div class="mood-status">{status}</div>
</div>""",
        "css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Noto Sans SC", sans-serif; }
.mood-card { width:480px; height:360px; display:flex; flex-direction:column; align-items:center; justify-content:center; background:linear-gradient(160deg,#fdfcfb,#e2d1c3); border-radius:24px; }
.mood-emoji { font-size:120px; line-height:1; }
.mood-status { margin-top:24px; font-size:22px; color:#5d4037; }""",
    },
    "leaderboard": {
        "description": "排行榜：标题 + 排名条目列表",
        "params": {"title": "标题", "entries": "条目（格式：名次. 名字 分数，多行用 \\n 分隔）"},
        "defaults": {"title": "排行榜", "entries": ""},
        "html": """<div class="lb-card">
  <div class="lb-title">{title}</div>
  <div class="lb-entries">{entries_html}</div>
</div>""",
        "css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Noto Sans SC", sans-serif; }
.lb-card { width:520px; padding:28px; background:#0f172a; border-radius:16px; color:#e2e8f0; }
.lb-title { font-size:22px; font-weight:700; text-align:center; margin-bottom:16px; color:#facc15; }
.lb-entries { font-size:16px; }
.lb-entries .entry { display:flex; justify-content:space-between; padding:8px 12px; border-bottom:1px solid rgba(255,255,255,.08); }
.lb-entries .entry:last-child { border-bottom:none; }
.lb-entries .entry .rank { color:#facc15; font-weight:600; margin-right:12px; }""",
    },
    "poem_card": {
        "description": "诗句卡：标题 + 诗句行，适合诗词/歌词",
        "params": {"title": "标题", "lines": "诗句（多行用 \\n 分隔）"},
        "defaults": {"title": "", "lines": ""},
        "html": """<div class="poem-card">
  <div class="poem-title">{title}</div>
  <div class="poem-lines">{lines_html}</div>
</div>""",
        "css": """* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Noto Sans SC", serif; }
.poem-card { width:600px; height:400px; padding:48px; background:linear-gradient(180deg,#2c3e50,#34495e); color:#f5f5f5; display:flex; flex-direction:column; align-items:center; justify-content:center; }
.poem-title { font-size:28px; font-weight:700; margin-bottom:20px; color:#e8d48b; }
.poem-lines { text-align:center; font-size:20px; line-height:2; letter-spacing:.08em; }""",
    },
}


def get_builtin_template(name: str) -> Dict[str, Any]:
    """获取内置模板定义（含默认值），不存在返回 None"""
    tpl = BUILTIN_TEMPLATES.get(name)
    if not tpl:
        return None
    return dict(tpl)


def build_template_html(name: str, params: Dict[str, Any]) -> str:
    """用参数构建模板的完整 HTML（渲染前处理多行/转义）"""
    tpl = get_builtin_template(name)
    if not tpl:
        raise ValueError(f"未知模板: {name}")

    data = dict(tpl["defaults"])
    data.update(params or {})

    html = tpl["html"]

    # 处理多行参数
    lines = str(data.get("lines", ""))
    lines_html = "".join(f'<div class="line">{_esc(l)}</div>' for l in lines.split("\n") if l.strip())
    entries = str(data.get("entries", ""))
    entries_html = ""
    for e in entries.split("\n"):
        e = e.strip()
        if not e:
            continue
        parts = e.split(".", 1)
        if len(parts) == 2 and parts[0].strip().isdigit():
            rank, rest = parts[0].strip(), parts[1].strip()
            entries_html += f'<div class="entry"><span><span class="rank">{_esc(rank)}.</span>{_esc(rest)}</span></div>'
        else:
            entries_html += f'<div class="entry"><span>{_esc(e)}</span></div>'

    html = html.replace("{lines_html}", lines_html)
    html = html.replace("{entries_html}", entries_html)
    html = html.replace("{lines}", _esc(lines))
    html = html.replace("{entries}", _esc(entries))

    # 其他简单占位符
    for key, val in data.items():
        if key in ("lines", "entries"):
            continue
        html = html.replace("{" + key + "}", _esc(val))

    return html


def get_template_catalog_text() -> str:
    """生成 AI 可读的模板目录文本"""
    lines = []
    for name, tpl in BUILTIN_TEMPLATES.items():
        params = "，".join(tpl.get("params", {}).values())
        lines.append(f"- {name}: {tpl['description']}。参数：{params}")
    return "\n".join(lines)
