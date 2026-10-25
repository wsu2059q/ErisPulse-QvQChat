import sys
from types import SimpleNamespace

from QvQChat.engine import tokens
from QvQChat.conversation.compactor import context_tokens, estimate_tokens


def setup_module(module):
    tokens.configure(None)


def teardown_module(module):
    tokens.configure(None)


def test_cjk_one_char_one_token():
    assert tokens.count_tokens("你好世界") == 4


def test_ascii_four_chars_one_token():
    assert tokens.count_tokens("abcdefgh") == 2
    assert tokens.count_tokens("abc") == 1# 3 字符向上取整


def test_empty_and_none():
    assert tokens.count_tokens("") == 0
    assert tokens.count_tokens(None) == 0


def test_mixed_text():
# 2 CJK + 3 ASCII → 2 + ceil(3/4) = 3
    assert tokens.count_tokens("你好abc") == 3


def test_multimodal_parts_flatten():
    parts = [
        {"type": "text", "text": "你好"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxxx"}},
        {"type": "text", "text": "ab"},
    ]
    assert tokens.count_tokens(parts) == 2 + 1


def test_messages_tokens_with_overhead():
    msgs = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": ""},
    ]
# 每条 +4：4 + 2 + 4 + 0
    assert tokens.messages_tokens(msgs) == 10


def test_tiktoken_missing_falls_back_silently():
# 配置 tiktoken 但未安装（本环境即未安装）：静默回退启发式
    tokens.configure(SimpleNamespace(token_estimator="tiktoken"))
    if "tiktoken" in sys.modules:# 若环境装了 tiktoken，跳过回退断言
        assert tokens.count_tokens("你好世界") > 0
    else:
        assert tokens.count_tokens("你好世界") == 4


def test_tiktoken_encoder_used_and_cached(monkeypatch):
    import types

    calls = {"n": 0}

    class FakeEncoder:
        def encode_ordinary(self, s):
            calls["n"] += 1
            return ["t"] * 3# 恒 3 token

    fake = types.ModuleType("tiktoken")
    fake.get_encoding = lambda name: FakeEncoder()
    monkeypatch.setitem(sys.modules, "tiktoken", fake)

    tokens.configure(SimpleNamespace(token_estimator="tiktoken"))
    assert tokens.count_tokens("你好世界abcdefgh") == 3
    assert tokens.count_tokens("另一段") == 3
    assert calls["n"] == 2# 编码器复用（无重新 get_encoding/导入）

# configure 复位后回到启发式
    tokens.configure(None)
    assert tokens.count_tokens("你好世界") == 4


def test_compactor_reexport_matches_engine():
    assert estimate_tokens("你好abcd") == tokens.count_tokens("你好abcd")
    assert context_tokens([{"role": "user", "content": "你好"}]) == tokens.messages_tokens(
        [{"role": "user", "content": "你好"}]
    )
# 旧接口语义：每条消息 +4 开销
    assert context_tokens([{"role": "user", "content": "你好"}]) == 6
