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
    assert "\n\n" not in process  # 工具条目之间不再留空行
    assert "ls -la pwd" in process
    assert "先查一下" in sections
    assert "done" not in sections  # 有 rounds 时不再把整段回复重复塞进合并卡
