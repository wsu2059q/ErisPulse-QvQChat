from QvQChat import texts
from QvQChat.conversation.visual import _short, build_sections


def test_short_normalizes_literal_escapes():
    assert _short('{"code": "a\\nb\\tc"}', 80) == '{"code": "a b c"}'


def test_build_sections_keeps_tool_group_compact():
    rounds = [{
        "text": "先查一下",
        "tools": [
            {
                "tool": "run_command",
                "arguments": '{"command": "ls -la\\n pwd"}',
                "output": "a.py\\n b.py",
                "ms": 12,
            },
            {
                "tool": "run_command",
                "arguments": '{"command": "pwd"}',
                "output": "/tmp",
                "ms": 3,
            },
        ],
    }]
    sections, text_count = build_sections(rounds, "done", [])
    assert text_count == 1
    process = sections[0]
    assert process.startswith(texts.t("forward_process_title"))
    assert "\\n" not in process
    assert "\n\n" not in process   
    assert "ls -la pwd" in process
    assert "先查一下" in sections
    assert "done" not in sections   


def test_build_sections_excludes_trace_when_configured():
    rounds = [{
        "text": "结论在这里",
        "tools": [{"tool": "run_command", "arguments": "{}", "output": "x", "ms": 5}],
    }]
    sections, text_count = build_sections(rounds, "结论在这里", [], include_trace=False)
    assert sections == ["结论在这里"]   
    assert text_count == 1


def test_build_sections_exclude_final_reply_drops_conclusion():
    rounds = [
        {"text": "", "tools": [{"tool": "read_file", "arguments": "{}", "output": "x", "ms": 1}]},
        {"text": "中间说明", "tools": []},
        {"text": "最终结论", "tools": []},
    ]
    sections, text_count = build_sections(rounds, "最终结论", [], exclude_final_reply=True)
    assert "最终结论" not in sections
    assert "中间说明" in sections
 
    assert text_count == 2


def test_build_sections_exclude_final_reply_keeps_single_section():
    """卡内只剩结论一条时保留（否则强制转发会变空卡）。"""
    sections, _ = build_sections([{"text": "只有结论", "tools": []}], "只有结论", [], exclude_final_reply=True)
    assert sections == ["只有结论"]


def test_build_sections_custom_limits():
    rounds = [{
        "text": "",
        "tools": [{"tool": "run_command", "arguments": '{"command": "%s"}' % ("x" * 300),
                   "output": "y" * 900, "ms": 1}],
    }]
    default_sections, _ = build_sections(rounds, "", [])
    wide_sections, _ = build_sections(rounds, "", [], args_chars=300, output_chars=1000)
    assert len(default_sections[0]) < len(wide_sections[0])
    assert "y" * 600 in wide_sections[0]
