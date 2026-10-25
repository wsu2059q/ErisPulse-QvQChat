"""投递节奏引擎与结构感知信号的纯函数实现（工单 D1/D3、）。

- plan_segments: 段落/句级切分 + 拟人化打字延迟；随机源可注入（rng 参数）保证测试确定性。
- structure_signals / forward_score: 回复的结构化信号分析，供结构感知转发判定使用。

全部为无副作用纯函数，不依赖 SDK / 配置对象。
"""
from __future__ import annotations

import random
import re

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?…~])")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
TABLE_RE = re.compile(r"^\s*\|.*\|\s*$")
OLIST_RE = re.compile(r"^\s*\d+\.\s*")
HEAD_RE = re.compile(r"^#{1,6}\s")
REPORT_TONE_RE = re.compile(r"(综上|总结|汇总|如下|以上|报告完毕|一览|概览|清单)")

# D3 结构感知转发：综合信号分达到该阈值时判定为结构化内容，走合并转发
STRUCTURE_FORWARD_RATIO = 0.4

# 单段结构化信号加成上限
_TOOL_SIGNAL_CAP = 0.15
_TOOL_SIGNAL_STEP = 0.03
_LONG_TEXT_SIGNAL = 0.10
_LONG_TEXT_CHARS = 600
_REPORT_TONE_SIGNAL = 0.10

DEFAULT_PROFILE: dict = {
    "sentence_split": False,
    "sentence_max": 80,
    "typing_speed": 25.0,
    "split_jitter": 0.35,
    "total_delay_cap": 20.0,
    "base_delay": 1.2,
    "min_delay": 0.5,
    "max_delay": 6.0,
    "min_length": 120,
    "max_parts": 6,
}


def as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def split_sentences(paragraph: str, sentence_max: int) -> list[str]:
    """按句末标点（。！？!?…~）切句并贪心打包成不超过 sentence_max 的段。

    无标点的超长单句无法再切，保持原样（尽力而为，避免切断代码/链接）。
    """
    paragraph = str(paragraph or "")
    if not paragraph:
        return []
    if sentence_max <= 0 or len(paragraph) <= sentence_max:
        return [paragraph]
    pieces = [p for p in SENTENCE_SPLIT_RE.split(paragraph) if p]
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if buf and len(buf) + len(piece) > sentence_max:
            chunks.append(buf)
            buf = piece
        else:
            buf += piece
    if buf:
        chunks.append(buf)
    return chunks


def plan_segments(text: str, profile: dict | None = None, rng=random) -> list[tuple[str, float]]:
    """把回复切成 (文本, 发送前延迟) 序列，模拟真人分段节奏。

    - 沿用 \\n{2,} 段落切分 + 短段前移合并（同 split_paragraphs 语义）
    - sentence_split 开启时段内超 sentence_max 按句末标点切句打包（单段长文本也可切）
    - 段数超 max_parts 时尾部合并截断
    - 每段延迟 = clamp(base_delay + len/typing_speed, min_delay, max_delay) × uniform(1±split_jitter)
      首段延迟恒为 0（立即发出）
    - 总延迟超 total_delay_cap 时按比例压缩（cap<=0 表示不封顶）

    不可切分（单段且未开句切、总长不足 min_length）时返回 []，调用方单条发送。
    """
    cfg = dict(DEFAULT_PROFILE)
    cfg.update(dict(profile or {}))
    text = str(text or "")
    min_length = as_int(cfg.get("min_length"), 120)
    max_parts = max(1, as_int(cfg.get("max_parts"), 6))
    sentence_max = as_int(cfg.get("sentence_max"), 80)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        return []
    merged: list[str] = []
    for part in paragraphs:
        if merged and len(merged[-1]) < min_length:
            merged[-1] += "\n\n" + part
        else:
            merged.append(part)
    if sum(len(p) for p in merged) < min_length:
        return []
    chunks: list[str] = []
    if bool(cfg.get("sentence_split")) and sentence_max > 0:
        for para in merged:
            chunks.extend(split_sentences(para, sentence_max))
    else:
        chunks = list(merged)
    if len(chunks) < 2:
        return []
    if len(chunks) > max_parts:
        head = chunks[: max_parts - 1]
        head.append("\n\n".join(chunks[max_parts - 1:]))
        chunks = head

    base = as_float(cfg.get("base_delay"), 1.2)
    typing_speed = as_float(cfg.get("typing_speed"), 25.0)
    min_delay = as_float(cfg.get("min_delay"), 0.5)
    max_delay = as_float(cfg.get("max_delay"), 6.0)
    jitter = min(1.0, max(0.0, as_float(cfg.get("split_jitter"), 0.35)))
    cap = as_float(cfg.get("total_delay_cap"), 20.0)
    if min_delay > max_delay:
        min_delay, max_delay = max_delay, min_delay

    def raw_delay(seg: str) -> float:
        typing = len(seg) / typing_speed if typing_speed > 0 else 0.0
        return min(max(base + typing, min_delay), max_delay)

    segments: list[tuple[str, float]] = [(chunks[0], 0.0)]
    for seg in chunks[1:]:
        delay = raw_delay(seg) * rng.uniform(1.0 - jitter, 1.0 + jitter)
        segments.append((seg, max(0.0, delay)))
    if cap > 0:
        total = sum(d for _, d in segments)
        if total > cap:
            scale = cap / total
            segments = [(t, round(d * scale, 6)) for t, d in segments]
    return segments


def structure_signals(rounds: list | None, reply: str) -> dict:
    """结构感知信号分析（纯函数）。

    主信号：结构行（代码块围栏/围栏内/表格行/有序列表/标题）占非空行比例 ratio。
    辅助信号：工具轮数（每轮 +0.03，封顶 0.15）、总长 >600 字（+0.10）、
    报告语气结尾词（+0.10），加权为综合分 score（0~1）。
    AI 发言段数 parts 单独暴露，不进入 score（纯寒暄多段不应转发）。
    """
    text = str(reply or "")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    structured = 0
    in_fence = False
    has_code = False
    has_table = False
    for ln in lines:
        if FENCE_RE.match(ln):
            in_fence = not in_fence
            has_code = True
            structured += 1
            continue
        if in_fence:
            structured += 1
            continue
        if TABLE_RE.match(ln):
            structured += 1
            has_table = True
        elif HEAD_RE.match(ln) or OLIST_RE.match(ln):
            structured += 1
    ratio = (structured / len(lines)) if lines else 0.0
    tool_rounds = 0
    parts = 0
    for round_data in rounds or []:
        if not isinstance(round_data, dict):
            continue
        tool_rounds += len([e for e in (round_data.get("tools") or []) if isinstance(e, dict)])
        if str(round_data.get("text") or "").strip():
            parts += 1
    report_tone = bool(lines) and bool(REPORT_TONE_RE.search(lines[-1]))
    score = ratio
    if tool_rounds:
        score += min(_TOOL_SIGNAL_CAP, _TOOL_SIGNAL_STEP * tool_rounds)
    if len(text) > _LONG_TEXT_CHARS:
        score += _LONG_TEXT_SIGNAL
    if report_tone:
        score += _REPORT_TONE_SIGNAL
    return {
        "ratio": round(ratio, 6),
        "score": round(min(1.0, score), 6),
        "has_code": has_code,
        "has_table": has_table,
        "parts": parts,
        "tool_rounds": tool_rounds,
        "length": len(text),
        "report_tone": report_tone,
    }


def forward_score(rounds: list | None, reply: str) -> float:
    """结构感知转发的综合信号分（0~1），达到 STRUCTURE_FORWARD_RATIO 视为结构化内容。"""
    return structure_signals(rounds, reply)["score"]
