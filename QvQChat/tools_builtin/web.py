"""内置联网工具：web_search（聚合搜索：bing/baidu/duckduckgo）与 web_fetch（网页转文本）。

零第三方依赖：只用标准库 urllib + 正则做最小可用解析。搜索源可配置
（web_search_engine），首选失败或无结果时按 bing→baidu→duckduckgo 自动兜底。
站点专有解析（B站/知乎等）不在这里做——见 docs/ecosystem-web.md：由生态模块
注册服务，经 eco 桥成为工具。
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
BING_HTML = "https://cn.bing.com/search?q={query}&mkt=zh-CN"
BAIDU_HTML = "https://www.baidu.com/s?wd={query}&rn=10"
SOGOU_HTML = "https://www.sogou.com/web?query={query}"
SO360_HTML = "https://www.so.com/s?q={query}"
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
# Bing：结果块 <li class="b_algo">，标题链接在 <h2><a>，摘要在 b_lineclamp <p>
BING_BLOCK_RE = re.compile(r'<li class="b_algo".*?</li>', re.DOTALL)
BING_LINK_RE = re.compile(
    r'<h2[^>]*>\s*<a[^>]+href="(?P<url>https?[^"]+)"[^>]*>(?P<title>.*?)</a>', re.DOTALL
)
BING_SNIP_RE = re.compile(r'<p[^>]*class="b_lineclamp[^"]*"[^>]*>(?P<snip>.*?)</p>', re.DOTALL)
# Baidu：新版结果页摘要已 JS 化，仅可靠提取 <h3><a> 标题与跳转链接
BAIDU_LINK_RE = re.compile(
    r'<h3[^>]*>\s*<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.DOTALL
)
# Sogou：标题锚 <a name="dttl" href="/link?url=...">，摘要在 text-layout/space-txt 块
SOGOU_LINK_RE = re.compile(
    r'<a name="dttl"[^>]+href="(?P<url>/link\?url=[^"]+|https?[^"]+)"[^>]*>(?P<title>.*?)</a>', re.DOTALL
)
SOGOU_SNIP_RE = re.compile(
    r'class="[^"]*(?:text-layout|space-txt|fz-mid)[^"]*"[^>]*>(?P<snip>.*?)</(?:p|div|span)>', re.DOTALL
)
# 360：标题在 <h3 class="res-title"><a href="https://www.so.com/link?m=...">
SO360_LINK_RE = re.compile(
    r'<h3\s+class="res-title">\s*<a[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.DOTALL
)
SO360_SNIP_RE = re.compile(r'<p class="res-desc[^"]*"[^>]*>(?P<snip>.*?)</p>', re.DOTALL)
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


def parse_bing_html(page: str, limit: int = 5) -> list[dict]:
    """Bing 结果块解析：b_algo 块内取 h2 链接与 b_lineclamp 摘要。"""
    results: list[dict] = []
    for block in BING_BLOCK_RE.finditer(page or ""):
        chunk = block.group(0)
        link = BING_LINK_RE.search(chunk)
        if link is None:
            continue
        snip = BING_SNIP_RE.search(chunk)
        results.append(
            {
                "title": _strip_tags(link.group("title")),
                "url": html.unescape(link.group("url")),
                "snippet": _strip_tags(snip.group("snip")) if snip else "",
            }
        )
        if len(results) >= limit:
            break
    return results


def parse_baidu_html(page: str, limit: int = 5) -> list[dict]:
    """Baidu 结果解析：仅标题 + 跳转链接（跳转链接可被 web_fetch 还原为真实页面）。"""
    return _title_link_results(BAIDU_LINK_RE, page, limit)


def parse_sogou_html(page: str, limit: int = 5) -> list[dict]:
    """Sogou 结果解析：dttl 锚标题 + 就近摘要；/link 跳转链接补全域名。"""
    results: list[dict] = []
    seen: set[str] = set()
    for match in SOGOU_LINK_RE.finditer(page or ""):
        title = _strip_tags(match.group("title"))
        url = html.unescape(match.group("url"))
        if url.startswith("/"):
            url = "https://www.sogou.com" + url
        if not title or url in seen:
            continue
        seen.add(url)
# 摘要取标题锚之后的一小段窗口（快照式结构，块级正则会被嵌套 div 截断）
        tail = (page or "")[match.end():match.end() + 1200]
        snip = SOGOU_SNIP_RE.search(tail)
        results.append({"title": title, "url": url, "snippet": _strip_tags(snip.group("snip"))[:200] if snip else ""})
        if len(results) >= limit:
            break
    return results


def parse_so360_html(page: str, limit: int = 5) -> list[dict]:
    """360 搜索结果解析：res-title 标题 + res-desc 摘要（so.com 跳转链接）。"""
    results: list[dict] = []
    seen: set[str] = set()
    for block in re.finditer(r'<h3\s+class="res-title">.*?(?=<h3\s+class="res-title">|$)', page or "", re.DOTALL):
        chunk = block.group(0)
        link = SO360_LINK_RE.search(chunk)
        if link is None:
            continue
        title = _strip_tags(link.group("title"))
        url = html.unescape(link.group("url"))
        if not title or url in seen:
            continue
        seen.add(url)
        snip = SO360_SNIP_RE.search(chunk)
        results.append({"title": title, "url": url, "snippet": _strip_tags(snip.group("snip"))[:200] if snip else ""})
        if len(results) >= limit:
            break
    return results


def _title_link_results(link_re, page: str, limit: int) -> list[dict]:
    """通用标题+链接解析（Baidu 式）：去重、跳转链接原样保留。"""
    results: list[dict] = []
    seen: set[str] = set()
    for match in link_re.finditer(page or ""):
        title = _strip_tags(match.group("title"))
        url = html.unescape(match.group("url"))
        if not title or url in seen:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "snippet": ""})
        if len(results) >= limit:
            break
    return results


# 搜索源注册表：engine → (URL 模板, 解析器)；fallback 链即此顺序
SEARCH_ENGINES = {
    "bing": (BING_HTML, parse_bing_html),
    "baidu": (BAIDU_HTML, parse_baidu_html),
    "sogou": (SOGOU_HTML, parse_sogou_html),
    "so360": (SO360_HTML, parse_so360_html),
    "duckduckgo": (DDG_HTML, parse_ddg_html),
}
FALLBACK_CHAIN = ("bing", "baidu", "sogou", "duckduckgo")


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


async def _search_via(engine: str, query: str, limit: int, timeout: float) -> tuple[int, list[dict]]:
    """单引擎搜索：返回 (HTTP 状态, 结果列表)；网络异常转 RuntimeError 上抛。"""
    template, parser = SEARCH_ENGINES[engine]
    status, page = await _get(template.format(query=urllib.parse.quote_plus(query)), timeout)
    if status != 200 or not page:
        return status, []
    return 200, parser(page, limit=limit)


async def web_search(ctx: ToolContext, query: str) -> str:
    query = str(query or "").strip()
    if not query:
        return texts.t("web_query_required")
    limit = max(1, int(_setting(ctx, "web_search_results", 5) or 5))
    timeout = float(_setting(ctx, "web_timeout", 20) or 20)
# 引擎链：配置首选在前，其余按兜底顺序补齐（去重）；首选失败/无结果自动换源
    primary = str(_setting(ctx, "web_search_engine", "bing") or "bing").strip().lower()
    if primary not in SEARCH_ENGINES:
        primary = "bing"
    chain = [primary] + [e for e in FALLBACK_CHAIN if e != primary]
    attempts: list[str] = []
    for engine in chain:
        try:
            status, results = await _search_via(engine, query, limit, timeout)
        except Exception as e:
# 逐引擎记录失败原因（如网络不可达），全部失败时一次看全，便于定位部署机出网问题
            attempts.append(f"{engine}: {type(e).__name__}: {e}")
            continue
        if results:
            blocks = []
            for index, item in enumerate(results):
                blocks.append(f"[{index + 1}] {item['title']}\n{item['url']}\n{item['snippet']}")
            return texts.t("web_search_header", query=query) + f"\n[{engine}]\n\n" + "\n\n".join(blocks)
        attempts.append(f"{engine}: HTTP {status} 无结果")
    return texts.t("web_search_failed", status="; ".join(attempts) or "-")


async def web_fetch(ctx: ToolContext, url: str) -> str:
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://")):
        return texts.t("web_url_required")
    timeout = float(_setting(ctx, "web_timeout", 20) or 20)
    limit = max(500, int(_setting(ctx, "web_fetch_chars", 6000) or 6000))
# 第一优先：r.jina.ai 渲染（对 JS 站点/正文提取更好）；失败回退原始 HTML 去标签
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
