"""内置联网工具：web_search（DuckDuckGo HTML）与 web_fetch（网页转文本）。

零第三方依赖：只用标准库 urllib + 正则做最小可用解析。站点专有解析（B站/知乎等）
不在这里做——见 docs/ecosystem-web.md：由生态模块注册服务，经 eco 桥成为工具。
"""
from __future__ import annotations

import asyncio
import html
import re
import urllib.error
import urllib.parse
import urllib.request

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry

DDG_HTML = "https://html.duckduckgo.com/html/?q={query}"
JINA_READER = "https://r.jina.ai/{url}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    r'.*?<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)


def _strip_tags(text: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", text or "")).split())


def _decode_ddg_url(url: str) -> str:
    """DuckDuckGo 的跳转链接（/l/?uddg=...）还原真实 URL。"""
    raw = html.unescape(str(url or ""))
    if "uddg=" in raw:
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw).query)
        target = (parsed.get("uddg") or [""])[0]
        if target:
            return urllib.parse.unquote(target)
    if raw.startswith("//"):
        return "https:" + raw
    return raw


def parse_ddg_html(page: str, limit: int = 5) -> list[dict]:
    results: list[dict] = []
    for match in RESULT_RE.finditer(page or ""):
        results.append(
            {
                "title": _strip_tags(match.group("title")),
                "url": _decode_ddg_url(match.group("url")),
                "snippet": _strip_tags(match.group("snippet")),
            }
        )
        if len(results) >= limit:
            break
    return results


def html_to_text(page: str, limit: int = 6000) -> str:
    cleaned = SCRIPT_RE.sub(" ", page or "")
    text = html.unescape(TAG_RE.sub("\n", cleaned))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return utils.truncate("\n".join(lines), limit)


def _blocking_get(url: str, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return int(response.status), response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        return int(e.code), ""
    except Exception as e:
        raise RuntimeError(str(e)) from e


async def _get(url: str, timeout: float) -> tuple[int, str]:
    return await asyncio.to_thread(_blocking_get, url, timeout)


def _setting(ctx: ToolContext, key: str, default):
    return getattr(ctx.config, key, default)


async def web_search(ctx: ToolContext, query: str) -> str:
    query = str(query or "").strip()
    if not query:
        return texts.t("web_query_required")
    limit = max(1, int(_setting(ctx, "web_search_results", 5) or 5))
    timeout = float(_setting(ctx, "web_timeout", 20) or 20)
    status, page = await _get(DDG_HTML.format(query=urllib.parse.quote_plus(query)), timeout)
    if status != 200 or not page:
        return texts.t("web_search_failed", status=status)
    results = parse_ddg_html(page, limit=limit)
    if not results:
        return texts.t("web_search_empty", query=query)
    blocks = []
    for index, item in enumerate(results):
        blocks.append(f"[{index + 1}] {item['title']}\n{item['url']}\n{item['snippet']}")
    return texts.t("web_search_header", query=query) + "\n\n" + "\n\n".join(blocks)


async def web_fetch(ctx: ToolContext, url: str) -> str:
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://")):
        return texts.t("web_url_required")
    timeout = float(_setting(ctx, "web_timeout", 20) or 20)
    limit = max(500, int(_setting(ctx, "web_fetch_chars", 6000) or 6000))
 
    try:
        status, text = await _get(JINA_READER.format(url=url), timeout)
        if status == 200 and text.strip():
            return utils.truncate(text.strip(), limit)
    except Exception:
        pass
    try:
        status, page = await _get(url, timeout)
    except Exception as e:
        return texts.t("web_fetch_failed", error=e)
    if status != 200 or not page:
        return texts.t("web_fetch_failed", error=f"HTTP {status}")
    return html_to_text(page, limit=limit)


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def register(registry: ToolRegistry, main) -> None:
    if not bool(getattr(main.cfg, "web_tools_enabled", True)):
        return
    registry.register(Tool(
        name="web_search",
        access="safe",
        description=(
            "Search the web (DuckDuckGo) for current information. Returns titles, URLs and snippets. "
            "Use when the answer depends on recent/verifiable facts rather than memory; cite the URL in your reply."
        ),
        parameters=_schema(
            {"query": {"type": "string", "description": "Search query"}},
            ["query"],
        ),
        handler=web_search,
    ))
    registry.register(Tool(
        name="web_fetch",
        access="safe",
        description=(
            "Fetch a web page and return readable text/Markdown (JS-heavy pages are rendered via a reader service). "
            "Use after web_search, or when the user gives a direct URL."
        ),
        parameters=_schema(
            {"url": {"type": "string", "description": "http(s) URL to read"}},
            ["url"],
        ),
        handler=web_fetch,
    ))
