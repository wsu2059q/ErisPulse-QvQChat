"""
<|render|> 标签解析

格式（AI 输出中内嵌）：
- 模板渲染: <|render|>tpl:quote_card||text=你好||author=小明</|render|>
- 自由 HTML: <|render|><div>你好</div>||css||.x{color:red}</|render|>

解析后返回 RenderRequest，交由 RenderManager 渲染。
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RENDER_TAG_RE = re.compile(
    r"<\|?\s*render\s*\|?>(.*?)<\|?\s*/\s*\|?\s*render\s*\|?>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class RenderRequest:
    """解析出的渲染请求"""

    kind: str  # "template" | "html"
    template_name: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    html: str = ""
    css: str = ""


def parse_render_tags(text: str) -> List[RenderRequest]:
    """从文本中解析所有 <|render|> 标签"""
    requests = []
    for match in RENDER_TAG_RE.finditer(text):
        content = match.group(1).strip()
        if not content:
            continue
        req = _parse_content(content)
        if req:
            requests.append(req)
    return requests


def _parse_content(content: str) -> Optional[RenderRequest]:
    """解析标签内容"""
    # 模板模式: tpl:名称||k=v||k2=v2
    if content.startswith("tpl:"):
        rest = content[4:].strip()
        parts = rest.split("||")
        name = parts[0].strip()
        params = {}
        for p in parts[1:]:
            p = p.strip()
            if "=" in p:
                k, v = p.split("=", 1)
                params[k.strip()] = v.strip()
        if name:
            return RenderRequest(kind="template", template_name=name, params=params)
        return None

    # 自由 HTML 模式: HTML 或 HTML||css||CSS
    html = content
    css = ""
    if "||css||" in content:
        html, _, css = content.partition("||css||")
    if html.strip():
        return RenderRequest(kind="html", html=html.strip(), css=css.strip())
    return None


def strip_render_tags(text: str) -> str:
    """从文本中移除所有渲染标签（渲染失败时保留文本内容）"""
    return RENDER_TAG_RE.sub(lambda m: m.group(1).strip() or "", text).strip()
