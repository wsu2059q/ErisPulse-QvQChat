"""上下文预算装填。

SystemPart: 系统提示词的一个语义部件（kind + 文本 + required）。
PRIORITY: 部件优先级（数值越小越重要，超预算时从大者优先截半/丢弃）。
ContextPacker.pack(): 统一核算 system 部件 + 历史从新到旧装填 + user_msg 保位。

预算 = context_length * context_reserve(默认 0.85) - max_output - 256。
system 部分合计封顶预算一半；required（persona/capability）只截半不整段丢。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..engine import tokens
from .compactor import merge_turns, split_turns

PRIORITY: dict[str, float] = {
    "persona": 0,
    "capability": 1,
    "scene": 2,
    "summary": 3,
    "facts": 4,
    "profile": 4.5,
    "memory": 5,
    "kb": 6,
    "skill_full": 7,
    "skill_list": 8,
    "extra": 9,
}

TRUNCATED_MARK = "…[truncated]"


@dataclass
class SystemPart:
    kind: str
    text: str
    required: bool = False


@dataclass
class PackedContext:
    system: str
    messages: list
    stats: dict = field(default_factory=dict)


def _priority(kind: str) -> int:
    return PRIORITY.get(kind, PRIORITY["extra"])


def _halve(text: str) -> str:
    half = text[: max(1, len(text) // 2)].rstrip()
    return half + TRUNCATED_MARK


class ContextPacker:
    """按模型实际上下文长度装填 system 部件与历史消息。"""

    def _fit_system(self, parts: list[SystemPart], cap: int, dropped: dict) -> list[SystemPart]:
        kept = sorted(parts, key=lambda p: _priority(p.kind))

        def _total() -> int:
            return sum(tokens.count_tokens(p.text) for p in kept)

        if cap <= 0 or _total() <= cap:
            return kept
# 反复从低优先级（尾部）向高优先级处理：先截半，仍超预算再整段丢；
# required（persona/capability）只截半绝不整段丢。
        for _round in range(8):
            before = _total()
            index = len(kept) - 1
            while _total() > cap and index >= 0:
                part = kept[index]
                cost = tokens.count_tokens(part.text)
                if cost <= 0:
                    index -= 1
                    continue
                halved_text = _halve(part.text)
                halved_cost = tokens.count_tokens(halved_text)
                if halved_cost < cost:
                    kept[index] = SystemPart(part.kind, halved_text, part.required)
                    if _total() <= cap:
                        break
                    if not part.required:
                        dropped[part.kind] = dropped.get(part.kind, 0) + 1
                        kept.pop(index)
                elif not part.required:
# 已很短截半无收益 → 整段丢
                    dropped[part.kind] = dropped.get(part.kind, 0) + 1
                    kept.pop(index)
                index -= 1
            if _total() <= cap or _total() >= before:
                break
        return kept

    def pack(
        self,
        *,
        context_length: int,
        parts: list[SystemPart],
        history: list,
        user_msg: dict,
        max_output: int = 0,
        context_reserve: float = 0.85,
    ) -> PackedContext:
        dropped: dict = {}
        try:
            length = int(context_length or 0)
        except (TypeError, ValueError):
            length = 0
        try:
            reserve = float(context_reserve or 0.85)
        except (TypeError, ValueError):
            reserve = 0.85
        try:
            out = int(max_output or 0)
        except (TypeError, ValueError):
            out = 0
        budget = int(length * reserve) - out - 256
        stats: dict[str, Any] = {
            "context_length": length,
            "budget": budget,
            "used_system": 0,
            "used_history": 0,
            "dropped": dropped,
            "overflow_turns": 0,
        }
        if budget <= 0:
# 预算不可计算：退化为不装填（保持输入原样），避免产出空上下文
            stats["degenerate"] = True
            system = "\n\n".join(p.text for p in parts if p.text)
            return PackedContext(system=system, messages=list(history or []) + [user_msg], stats=stats)

        system_cap = budget // 2
        kept_parts = self._fit_system(list(parts or []), system_cap, dropped)
        system = "\n\n".join(p.text for p in kept_parts if p.text)
        used_system = tokens.count_tokens(system)
        stats["used_system"] = used_system

# 历史按轮从新到旧装填；user_msg 永远保位
        user_cost = tokens.count_tokens(user_msg.get("content") if isinstance(user_msg, dict) else user_msg)
        remaining = max(0, budget - used_system - user_cost)
        turns = split_turns(list(history or []))
        kept_turns: list = []
        used_history = 0
        overflow = 0
        for turn in reversed(turns):
            cost = tokens.messages_tokens(turn)
            if used_history + cost <= remaining:
                kept_turns.append(turn)
                used_history += cost
            else:
                overflow += 1
        kept_turns.reverse()
        stats["used_history"] = used_history
        stats["overflow_turns"] = overflow
        messages = merge_turns(kept_turns) + [user_msg]
        return PackedContext(system=system, messages=messages, stats=stats)
