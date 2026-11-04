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
