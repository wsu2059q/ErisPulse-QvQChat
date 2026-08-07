"""
<|render|> 标签解析

格式（AI 输出中内嵌，只支持自由 HTML）：
- <|render|><div>内容</div>||css||.x{color:red}</|render|>

解析后返回 RenderRequest，交由 RenderManager 渲染。
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

RENDER_TAG_RE = re.compile(
    r"<\|?\s*render\s*\|?>(.*?)<\|?\s*/\s*\|?\s*render\s*\|?>",
    re.IGNORECASE | re.DOTALL,
)


@dataclass
class RenderRequest:
    """解析出的渲染请求"""

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
    """解析标签内容（自由 HTML，可选 ||css|| 段）"""
    # 忽略旧的模板格式 tpl:xxx（模板系统已移除）
    if content.startswith("tpl:"):
        return None
    html = content
    css = ""
    if "||css||" in content:
        html, _, css = content.partition("||css||")
    if html.strip():
        return RenderRequest(html=html.strip(), css=css.strip())
    return None


def strip_render_tags(text: str) -> str:
    """从文本中移除所有渲染标签（渲染失败时保留文本内容）"""
    return RENDER_TAG_RE.sub(lambda m: m.group(1).strip() or "", text).strip()
