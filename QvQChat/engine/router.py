"""难度感知模型路由（V1 启发式，纯函数）。

classify(text) -> RouteDecision(prefer, reason)：
  - cheap    寒暄/表情/短确认/极短消息 -> 便宜模型（prefer="cheap"，池内按成本升序）
  - balanced 一般对话/轻工具任务 -> 池序默认
  - quality  长文/代码标记/分析类关键词 -> 高质量模型（V1 仅作标签，排序仍走池序）

reason 为人类可读英文常量，供 debug 日志与 routing_log 统计回看；
仅内部观测用途，不做 i18n（配置键 routing_enabled/routing_ttl 的描述见 texts.py）。
"""

from __future__ import annotations

import re
from typing import NamedTuple

SHORT_MAX = 60# < 60 字偏 cheap
LONG_MIN = 300# > 300 字偏 quality


class RouteDecision(NamedTuple):
    prefer: str
    reason: str


# 寒暄/短确认词表：整条消息（去表情/标点/空白并折叠重复字符后）命中即 cheap
_SMALLTALK = {
    "嗯", "哦", "噢", "啊", "哦豁", "em", "e", "嗯哼",
    "哈", "嘿", "嘻", "呵", "草", "泪", "乐", "绷不住",
    "好", "好的", "好呀", "好嘞", "好哦", "好滴", "好哒", "好叭", "木有", "没问题",
    "ok", "okay", "k", "o了", "yes", "no", "yeah", "yep", "nope", "ya",
    "对", "对的", "对啦", "是", "是的", "是呀", "是滴",
    "行", "行吧", "可以", "收到", "知道了", "知道啦", "明白", "明白啦", "懂了", "懂啦",
    "谢谢", "多谢", "感谢", "thx", "thanks", "thankyou", "3q",
    "晚安", "早安", "午安", "拜拜", "白白", "再见", "bye", "byby",
    "hi", "hello", "hey", "yo", "在吗", "在",
    "6", "9", "23", "666", "233", "hhh", "hh", "lol", "xswl",
}

# 疑问/分析类关键词：命中升档（每词 +2，累计封顶 +4）
_UPGRADE_KEYWORDS = (
    "为什么", "怎么回事", "怎么办", "如何",
    "分析", "总结", "归纳", "概括", "对比", "权衡", "评审", "优化", "重构", "排查",
    "写", "实现", "设计", "翻译", "润色", "证明", "推导",
    "debug", "报错", "异常", "堆栈", "崩溃", "traceback",
    "why", "analyze", "analysis", "summarize", "summary", "implement", "refactor",
    "review", "optimize", "fix", "error", "exception", "crash",
)

# 工具任务暗示：命中则至少 balanced（保底不下探 cheap）
_TOOL_HINTS = ("查", "搜", "打开", "找", "检索", "翻一下", "看下", "看一下",
               "search", "find", "look up", "lookup", "open", "check")

# 表情符号区间（emoji 杂项区 + 常用符号区 + 变体选择符/零宽连接符）
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D\u303D\u3297\u3299]+"
)
_PUNCT_RE = re.compile(r"[\s!-/:-@\[-`{-~。，、；：？！…—～·“”‘’《》【】「」『』]+")


def _strip_emoji_punct(text: str) -> str:
    return _PUNCT_RE.sub("", _EMOJI_RE.sub("", text))


def _has_code_marker(text: str) -> bool:
    """代码块（```）或成对的行内代码标记（`…`）。"""
    return "```" in text or text.count("`") >= 2


def classify(text: str) -> RouteDecision:
    """对单条用户消息做难度分级，返回 (prefer, reason)。启发式打分：

    - 纯寒暄/表情/空消息 -> cheap（直接判定）
    - 长度 <60 字 -2 分；>300 字 +2 分
    - 代码块/行内代码标记 +4 分（按任务规则直取 quality）
    - 分析/疑问关键词每词 +2（封顶 +4）
    - 工具任务暗示 -> 分数保底 0（至少 balanced）
    - 总分 <=-1 cheap / >=2 quality / 其余 balanced
    """
    raw = str(text or "").strip()
    if not raw:
        return RouteDecision("cheap", "empty message")
    cleaned = _strip_emoji_punct(raw).lower()
    if not cleaned:
        return RouteDecision("cheap", "emoji/punctuation only")
    collapsed = re.sub(r"(.)\1+", r"\1", cleaned)
    if cleaned in _SMALLTALK or collapsed in _SMALLTALK:
        return RouteDecision("cheap", "small talk / short acknowledgment")

    lowered = raw.lower()
    score = 0
    parts: list[str] = []
    if len(raw) < SHORT_MAX:
        score -= 2
        parts.append("short message")
    elif len(raw) > LONG_MIN:
        score += 2
        parts.append("long message")
    if _has_code_marker(raw):
        score += 4
        parts.append("code block/inline code present")
    hits: list[str] = []
    for keyword in _UPGRADE_KEYWORDS:
        if keyword in lowered and keyword not in hits:
            hits.append(keyword)
    if hits:
        score += min(2 * len(hits), 4)
        parts.append("analysis keywords: " + ",".join(hits))
    if any(hint in lowered for hint in _TOOL_HINTS):
        if score < 0:
            score = 0
        parts.append("tool-task hint")

    if score <= -1:
        return RouteDecision("cheap", "; ".join(parts) or "plain message")
    if score >= 2:
        return RouteDecision("quality", "; ".join(parts))
    return RouteDecision("balanced", "; ".join(parts) or "plain message")
