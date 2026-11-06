from QvQChat.tools_builtin.web import _decode_ddg_url, html_to_text, parse_ddg_html

DDG_PAGE = """
<div class="result results_links">
  <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnews%3Fid%3D1&amp;rut=abc">
    Example <b>News</b>
  </a>
  <a class="result__snippet" href="#">Breaking: <b>something</b> happened today.</a>
</div>
<div class="result results_links">
  <a class="result__a" href="https://docs.python.org/3/">Python 3 Docs</a>
  <a class="result__snippet" href="#">Official Python documentation.</a>
</div>
"""


def test_parse_ddg_html_extracts_and_decodes():
    results = parse_ddg_html(DDG_PAGE, limit=5)
    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/news?id=1"
    assert results[0]["title"] == "Example News"
    assert "something" in results[0]["snippet"]
    assert results[1]["url"] == "https://docs.python.org/3/"


def test_parse_ddg_html_respects_limit():
    assert len(parse_ddg_html(DDG_PAGE, limit=1)) == 1


def test_decode_ddg_url_forms():
    assert _decode_ddg_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fa.b%2Fc") == "https://a.b/c"
    assert _decode_ddg_url("//example.com/x") == "https://example.com/x"
    assert _decode_ddg_url("https://example.com") == "https://example.com"


def test_html_to_text_strips_scripts_and_tags():
    page = "<html><head><script>alert('x')</script><style>a{}</style></head><body><h1>标题</h1><p>正文 &amp; 内容</p></body></html>"
    text = html_to_text(page)
    assert "标题" in text and "正文 & 内容" in text
    assert "alert" not in text and "a{}" not in text


BING_PAGE = """
<ol id="b_results">
<li class="b_algo" data-id><h2><a href="https://example.com/a?x=1&amp;y=2" h="ID=SERP">Example <strong>Title</strong></a></h2>
<div class="b_caption"><p class="b_lineclamp4">First <b>snippet</b> text.</p></div></li>
<li class="b_algo"><h2><a href="https://example.com/b">Second Title</a></h2></li>
</ol>
"""


def test_parse_bing_html_extracts_title_url_snippet():
    from QvQChat.tools_builtin.web import parse_bing_html

    results = parse_bing_html(BING_PAGE, limit=5)
    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/a?x=1&y=2"
    assert results[0]["title"] == "Example Title"
    assert "First snippet text." in results[0]["snippet"]
    assert results[1]["snippet"] == ""


def test_parse_bing_html_respects_limit_and_skips_broken_blocks():
    from QvQChat.tools_builtin.web import parse_bing_html

    page = '<li class="b_algo"><div>no h2 here</div></li>' + BING_PAGE
    assert len(parse_bing_html(page, limit=1)) == 1


BAIDU_PAGE = """
<div class="result c-container">
  <h3 class="t"><a href="http://www.baidu.com/link?url=abc" target="_blank">Python <b>文档</b></a></h3>
</div>
<div class="result c-container">
  <h3><a href="http://www.baidu.com/link?url=def">异步 I/O 教程</a></h3>
</div>
<div class="result c-container">
  <h3><a href="http://www.baidu.com/link?url=abc">重复链接</a></h3>
</div>
"""


def test_parse_baidu_html_titles_and_dedup():
    from QvQChat.tools_builtin.web import parse_baidu_html

    results = parse_baidu_html(BAIDU_PAGE, limit=5)
    assert len(results) == 2  # 重复跳转链接去重
    assert results[0]["title"] == "Python 文档"
    assert results[0]["url"].startswith("http://www.baidu.com/link?url=")
    assert results[0]["snippet"] == ""


def test_web_search_engine_chain_fallback(monkeypatch):
    """引擎链：配置首选失败/无结果时按 bing→baidu→duckduckgo 兜底，结果标注实际引擎。"""
    import asyncio
    from types import SimpleNamespace

    from QvQChat.tools_builtin import web

    calls = []

    async def fake_get(url, timeout):
        calls.append(url)
        if "bing.com" in url:
            return 503, ""  # 首选 bing 挂了
        if "baidu.com" in url:
            return 200, BAIDU_PAGE
        raise RuntimeError("unreachable")

    monkeypatch.setattr(web, "_get", fake_get)
    ctx = SimpleNamespace(config=SimpleNamespace(web_search_results=5, web_timeout=5, web_search_engine="bing"))
    out = asyncio.run(web.web_search(ctx, "q"))
    assert "[baidu]" in out and "Python 文档" in out
    assert len(calls) == 2  # bing 失败 → baidu 成功即停，不再去 ddg

    # 全部失败：返回失败文案且不抛异常
    async def always_fail(url, timeout):
        return 500, ""

    monkeypatch.setattr(web, "_get", always_fail)
    out2 = asyncio.run(web.web_search(ctx, "q"))
    assert out2  # 失败文案
    # 未知引擎名回落 bing
    ctx3 = SimpleNamespace(config=SimpleNamespace(web_search_results=5, web_timeout=5, web_search_engine="nope"))
    assert ctx3 is not None


def test_web_search_unknown_engine_falls_back_to_bing(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from QvQChat.tools_builtin import web

    seen = []

    async def fake_get(url, timeout):
        seen.append(url)
        return 200, BING_PAGE

    monkeypatch.setattr(web, "_get", fake_get)
    ctx = SimpleNamespace(config=SimpleNamespace(web_search_results=5, web_timeout=5, web_search_engine="nope"))
    out = asyncio.run(web.web_search(ctx, "q"))
    assert "bing.com" in seen[0] and "[bing]" in out
