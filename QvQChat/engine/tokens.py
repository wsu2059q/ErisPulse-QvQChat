"""Token 估算集中化。

估算口径：
- 启发式：CJK 字符约 1 字 1 token；其余（ASCII/半角）约 4 字符 1 token；
  每条消息另有 +4 的协议开销（chat-completions 消息框架开销的近似）。
- 精确：配置 token_estimator == "tiktoken" 且已安装 tiktoken 时按
  cl100k_base 编码精确计数（编码器全局缓存，import 失败静默回退启发式）。

configure(cfg) 由模块装载方（Compactor/Service/Pool 构造时）注入配置；
不注入时保持纯函数行为，便于测试。
"""
from __future__ import annotations

from typing import Any

# 每条消息的固定开销（近似 chat-completions 的消息框架开销）
PER_MESSAGE_OVERHEAD = 4

_config: Any = None
_encoder: Any = None
_encoder_tried = False


def configure(cfg: Any) -> None:
    """模块级注入配置（QvQConfig 或任意带属性对象）。传 None 即复位。"""
    global _config, _encoder, _encoder_tried
    _config = cfg
    _encoder = None
    _encoder_tried = False


def _estimator_name() -> str:
    if _config is None:
        return ""
    return str(getattr(_config, "token_estimator", "") or "").lower()


def _get_encoder():
    """tiktoken 编码器全局缓存；未配置/未安装/导入失败时返回 None。"""
    global _encoder, _encoder_tried
    if _encoder_tried:
        return _encoder
    _encoder_tried = True
    if _estimator_name() != "tiktoken":
        return None
    try:
        import tiktoken

        _encoder = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _encoder = None
    return _encoder


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF# CJK 统一表意
        or 0x3400 <= code <= 0x4DBF# 扩展 A
        or 0xF900 <= code <= 0xFAFF# 兼容表意
        or 0x3040 <= code <= 0x30FF# 平假名/片假名
        or 0xAC00 <= code <= 0xD7AF# 谚文音节
        or 0x3000 <= code <= 0x303F# CJK 标点
        or 0xFF00 <= code <= 0xFFEF# 全角形式
    )


def _flatten(text: Any) -> str:
    if text is None:
        return ""
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        return " ".join(
            str(p.get("text") or "")
            for p in text
            if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(text)


def _heuristic_tokens(text: str) -> int:
    cjk = 0
    other = 0
    for ch in text:
        if _is_cjk(ch):
            cjk += 1
        else:
            other += 1
    return cjk + (other + 3) // 4


def count_tokens(text: Any) -> int:
    """估算一段内容（字符串或多模态 parts 列表）的 token 数。"""
    flat = _flatten(text)
    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode_ordinary(flat))
        except Exception:
            pass
    return _heuristic_tokens(flat)


def messages_tokens(messages: list, per_message: int = PER_MESSAGE_OVERHEAD) -> int:
    """估算一组消息的总 token 数（含每条 +4 开销）。"""
    total = 0
    for message in messages or []:
        content = message.get("content") if isinstance(message, dict) else message
        total += per_message + count_tokens(content)
    return total
