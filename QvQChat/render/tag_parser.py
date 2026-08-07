"""
<|render|> 标签解析

格式（AI 输出中内嵌，只支持自由 HTML）：
- <|render|><div>内容</div>||css||.x{color:red}</|render|>

解析后返回 RenderRequest，交由 RenderManager 渲染。
兼容未闭合标签（AI 偶尔漏掉 </|render|>）。
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

# 闭合标签对
RENDER_TAG_RE = re.compile(
    r"<\|?\s*render\s*\|?>(.*?)<\|?\s*/\s*\|?\s*render\s*\|?>",
    re.IGNORECASE | re.DOTALL,
)
# 未闭合的开标签（兜底：AI 漏写闭合标签时，取开标签后的所有内容）
RENDER_OPEN_TAG_RE = re.compile(
    r"<\|?\s*render\s*\|?>",
    re.IGNORECASE,
)


@dataclass
class RenderRequest:
    """解析出的渲染请求"""

    html: str = ""
    css: str = ""


def parse_render_tags(text: str) -> List[RenderRequest]:
    """从文本中解析所有 <|render|> 标签（含未闭合兜底）"""
    requests = []
    consumed_spans: List[tuple] = []

    # 1. 先匹配闭合标签对
    for match in RENDER_TAG_RE.finditer(text):
        content = match.group(1).strip()
        consumed_spans.append((match.start(), match.end()))
        if not content:
            continue
        req = _parse_content(content)
        if req:
            requests.append(req)

    # 2. 兜底：未闭合的开标签（AI 漏写闭合标签）
    for match in RENDER_OPEN_TAG_RE.finditer(text):
        # 跳过已被闭合标签对消费的范围
        if any(s <= match.start() < e for s, e in consumed_spans):
            continue
        content = text[match.end():].strip()
        if not content:
            continue
        req = _parse_content(content)
        if req:
            requests.append(req)

    return requests


def _parse_content(content: str) -> Optional[RenderRequest]:
    """解析标签内容（自由 HTML，支持 ||css|| 和 <style> 标签两种 CSS 写法）"""
    # 忽略旧的模板格式 tpl:xxx（模板系统已移除）
    if content.startswith("tpl:"):
        return None
    html = content
    css_parts = []

    # 1. 提取 <style> 标签内的 CSS
    style_re = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
    style_matches = style_re.findall(html)
    if style_matches:
        css_parts.extend(style_matches)
        html = style_re.sub("", html)

    # 2. 提取 ||css|| 分隔符后的 CSS
    if "||css||" in html:
        html, _, css_text = html.partition("||css||")
        css_parts.append(css_text)

    css = "\n".join(p.strip() for p in css_parts if p.strip())
    if html.strip():
        return RenderRequest(html=html.strip(), css=css.strip())
    return None


def strip_render_tags(text: str) -> str:
    """从文本中移除所有渲染标签及其内容（渲染后 HTML 无需作为文本发送）"""
    # 闭合标签：移除整个 <|render|>...</|render|>
    text = RENDER_TAG_RE.sub("", text)
    # 未闭合标签：移除 <|render|> 及之后所有内容（通常 HTML 延伸到字符串末尾）
    parts = RENDER_OPEN_TAG_RE.split(text, maxsplit=1)
    return parts[0].strip()
