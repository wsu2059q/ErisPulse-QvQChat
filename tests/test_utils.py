from QvQChat.utils import (
    bigrams,
    cron_next,
    overlap_score,
    parse_schedule,
    sanitize_name,
    schema_from_signature,
    split_top_level,
    time_line,
    to_text,
    truncate,
)


def test_schema_types_and_required():
    schema = schema_from_signature("(city: str, days: int = 1, verbose: bool = False)")
    assert schema["type"] == "object"
    assert schema["required"] == ["city"]
    assert schema["properties"]["city"]["type"] == "string"
    assert schema["properties"]["days"]["type"] == "integer"
    assert schema["properties"]["days"]["default"] == 1
    assert schema["properties"]["verbose"]["type"] == "boolean"


def test_schema_union_annotations():
    schema = schema_from_signature("(data: dict | None = None, tags: list[str] | None = None, note: str | None = None)")
    assert schema["properties"]["data"]["type"] == "object"
    assert schema["properties"]["tags"]["type"] == "array"
    assert schema["properties"]["note"]["type"] == "string"
    assert schema["required"] == []


def test_schema_handles_defaults_and_ignores_varargs():
    schema = schema_from_signature("(a, b='x,y', *args, **kwargs)")
    assert schema["required"] == ["a"]
    assert schema["properties"]["b"]["default"] == "x,y"
    assert "args" not in schema["properties"]
    assert "kwargs" not in schema["properties"]


def test_split_top_level_respects_nesting():
    parts = split_top_level('f(a, b), "x,y", [1, 2]')
    assert parts == ["f(a, b)", '"x,y"', "[1, 2]"]


def test_parse_schedule_variants():
    assert parse_schedule("in:30m") == {"type": "once", "delay": 1800}
    assert parse_schedule("every:2h") == {"type": "interval", "seconds": 7200}
    parsed = parse_schedule("at:2026-10-17 09:00")
    assert parsed["type"] == "once" and "at" in parsed
    assert parse_schedule("0 9 * * 1-5") == {"type": "cron", "expr": "0 9 * * 1-5"}


def test_parse_schedule_rejects_garbage():
    try:
        parse_schedule("whenever")
        raise AssertionError("should have raised")
    except ValueError:
        pass


def test_cron_next_monotonic():
    import time

    now = time.time()
    nxt = cron_next("0 9 * * 1-5", now)
    assert nxt > now
    nxt2 = cron_next("*/5 * * * *", now)
    assert now < nxt2 <= now + 300


def test_sanitize_name():
    assert sanitize_name("Weather-CN") == "Weather_CN"
    assert sanitize_name("a_b") == "a_b"
    for cjk in ("天气-模块!", "///"):
        hashed = sanitize_name(cjk)
        assert hashed.startswith("n") and len(hashed) == 7
        assert sanitize_name(cjk) == hashed


def test_truncate_and_to_text():
    assert truncate("a" * 50, 10).endswith("chars total)")
    assert to_text(None) == "ok"
    assert to_text({"a": 1}) == '{"a": 1}'
    assert "x" in to_text(ValueError("x"))


def test_bigram_overlap():
    assert overlap_score("天气怎么样", "今天天气很好") > 0
    assert overlap_score("abc", "xyz") == 0
    assert bigrams("ab") == {"ab"}


def test_time_line_neutral():
    line = time_line()
    assert line.startswith("Current time:")


def test_split_reply_sections():
    from QvQChat.utils import split_reply_sections

    md = "## 一\n内容A\n\n## 二\n内容B\n结尾"
    parts = split_reply_sections(md)
    assert len(parts) == 2
    assert parts[0].startswith("## 一")
    assert "内容B" in parts[1]
    assert split_reply_sections("") == []
    many = "\n\n".join(f"## 段{i}\n内容{i}" for i in range(20))
    assert len(split_reply_sections(many, max_nodes=5)) == 5


def test_build_forward_nodes():
    from QvQChat.utils import build_forward_nodes

    nodes = build_forward_nodes(["第一段", "第二段\n续行"], nickname="Bot", user_id="42")
    assert len(nodes) == 2
    assert nodes[0]["type"] == "node"
    data = nodes[0]["data"]
    assert data["user_id"] == "42" and data["nickname"] == "Bot"
    assert data["content"][0]["data"]["text"].startswith("【1/2】第一段")
    assert "续行" in nodes[1]["data"]["content"][0]["data"]["text"]
