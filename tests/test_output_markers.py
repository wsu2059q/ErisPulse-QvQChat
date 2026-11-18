"""输出标记识别：全角/半角括号统一归一化识别，替换作用于原文。

覆盖 投递标签（直发/转发）、跳过标记、假媒体前缀、让渡退出标签、内联媒体标记。
"""
from QvQChat import utils
from QvQChat.conversation import media


def test_output_tag_fullwidth_double_brackets():
    reply, force = utils.strip_output_tag("（（直发））你好呀")
    assert reply == "你好呀" and force is False
    reply2, force2 = utils.strip_output_tag("【【转发】】长内容")
    assert reply2 == "长内容" and force2 is True


def test_stray_tags_fullwidth_removed():
    out = utils.strip_stray_tags("（直发）开头\n正文\n（转发）继续")
    assert "直发" not in out and "转发" not in out
    assert "开头" in out and "正文" in out


def test_skip_reply_fullwidth_and_empty_placeholder():
    assert utils.is_skip_reply("【【不回复】】")
    assert utils.is_skip_reply("[[skip]]")
    assert utils.is_skip_reply("（空）")
    assert utils.is_skip_reply("(空)")
    assert not utils.is_skip_reply("正常回复")


def test_fake_media_prefix_fullwidth():
    out = utils.strip_fake_media_prefix("（语音）我头晕")
    assert out == "我头晕"


def test_handover_exit_fullwidth():
    from QvQChat.chat.inbox import _HANDOVER_EXIT_RE

    text = "那我先回去啦\n（交还）"
    assert _HANDOVER_EXIT_RE.search(utils.marker_normalized(text))
    cleaned = utils.sub_marker_pattern(_HANDOVER_EXIT_RE, text)
    assert "交还" not in cleaned and "回去啦" in cleaned


def test_media_marker_round_parens():
    parts = media.split_reply("（语音: 我有点头晕）")
    assert media.has_media(parts)
    kept = media.strip_markers("（语音: 我有点头晕）", keep_voice=True)
    assert kept == "我有点头晕"
    assert media.strip_markers("（表情: 猫猫）") == ""


def test_sanitize_keeps_empty_assistant_with_tool_calls():
    from QvQChat.engine.openai import OpenAIEngine

    msgs = [
        {"role": "user", "content": "查延迟"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "content": "结果"},
    ]
    out = OpenAIEngine.sanitize_messages(msgs)
    assert out[1]["content"] == ""
    user_only = OpenAIEngine.sanitize_messages([{"role": "user", "content": "  "}])
    assert user_only[0]["content"] == "（空）"
