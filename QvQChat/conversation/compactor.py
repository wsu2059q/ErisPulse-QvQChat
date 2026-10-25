from __future__ import annotations

import re as _re
from typing import Any

from .. import texts, utils
from ..engine import tokens
from ..engine.base import ChatRequest, TaskSpec


def estimate_tokens(text) -> int:
    """薄 re-export：实际实现见 engine.tokens.count_tokens。"""
    return tokens.count_tokens(text)


def context_tokens(contexts: list) -> int:
    """薄 re-export：实际实现见 engine.tokens.messages_tokens（含每消息 +4 开销）。"""
    return tokens.messages_tokens(contexts)


FACT_KINDS = ("ENTITY", "PREFERENCE", "TODO")


def extract_facts(text: str) -> tuple[str, list[str]]:
    """从摘要输出中宽松解析 <facts> 段。

    返回 (去掉 facts 段的摘要文本, ["KIND|内容", ...])；解析失败（无标签/行格式不符）
    时原样返回文本、facts 为空（不入库）。"""
    raw = str(text or "")
    facts: list[str] = []
    match = _re.search(r"<facts>(.*?)</facts>", raw, _re.DOTALL | _re.IGNORECASE)
    summary = raw
    if match:
        summary = (raw[: match.start()] + raw[match.end():]).strip()
        for line in match.group(1).splitlines():
            line = line.strip().lstrip("-*•·").strip()
            if "|" not in line:
                continue
            kind, _, content = line.partition("|")
            kind = kind.strip().upper()
            content = content.strip()
            if kind in FACT_KINDS and content:
                facts.append(f"{kind}|{content}")
# <summary> 标签宽松剥离（模型可能加也可能不加）
    summary = _re.sub(r"</?summary>", "", summary, flags=_re.IGNORECASE).strip()
    return summary, facts


def split_turns(contexts: list) -> list[list[dict]]:


    turns: list[list[dict]] = []
    current: list[dict] = []
    for m in contexts:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "tool":
            if not current:
                current = [m]
                continue
            current.append(m)
            continue
        if role == "user":
            if current:
                turns.append(current)
            current = [m]
            continue
        if not current:
            current = [m]
            continue
        current.append(m)
    if current:
        turns.append(current)
    return turns


def merge_turns(turns: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    for turn in turns:
        out.extend(turn)
    return out


class Compactor:


    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self.config = main.cfg
# 模块级注入 token 估算配置（Main 不改，构造时注入）
        tokens.configure(self.config)


    def _pool(self):
        return getattr(self.main, "pool", None)

    async def _dispatch_compact(self, request: ChatRequest):
        """摘要调用迁 dispatch(kind="compact", prefer="cheap")；老式池对象退回 chat。"""
        pool = self._pool()
        if pool is None:
            return None
        dispatch = getattr(pool, "dispatch", None)
        model = str(getattr(self.config, "compact_model", "") or "") or None
        if callable(dispatch):
            return await dispatch(TaskSpec(kind="compact", prefer="cheap", model=model), request)
        return await pool.chat(ChatRequest(
            messages=request.messages,
            model=model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        ))


    def microcompact(self, contexts: list) -> tuple[list, int]:
        keep_chars = int(getattr(self.config, "tool_output_keep", 300) or 0)
        if keep_chars <= 0:
            return contexts, 0
        tool_positions = [
            i for i, m in enumerate(contexts)
            if isinstance(m, dict) and m.get("role") == "tool"
        ]
        keep_last = 2
        stale = tool_positions[:-keep_last] if len(tool_positions) > keep_last else []
        if not stale:
            return contexts, 0
        out = list(contexts)
        changed = 0
        for i in stale:
            m = out[i]
            content = str(m.get("content") or "")
            if len(content) > keep_chars:
                out[i] = {**m, "content": content[:keep_chars] + f"\n[microcompact: 已截断，原 {len(content)} 字符]"}
                changed += 1
        return out, changed


    def _select_removed(self, contexts: list) -> tuple[list[dict], list[list[dict]]]:

        turns = split_turns(contexts)
        if len(turns) <= 1:
            return [], turns
        keep_ratio = min(0.5, max(0.1, float(getattr(self.config, "keep_ratio", 0.25) or 0.25)))
        keep_n = max(4, int(len(turns) * keep_ratio))
        keep_n = min(keep_n, len(turns))
        removed_turns = turns[:-keep_n]
        if not removed_turns:
            return [], turns[-keep_n:]
        return merge_turns(removed_turns), turns[-keep_n:]

    async def _summarize_turns(self, removed: list) -> str:
# 摘要条目截断/总量上限参数化（原硬编码 240/8000）
        entry_chars = int(getattr(self.config, "compact_transcript_chars", 400) or 0)
        input_chars = int(getattr(self.config, "compact_input_chars", 12000) or 0)
        lines: list[str] = []
        for m in removed:
            if not isinstance(m, dict):
                continue
            line = f"{m.get('role')}: {self._content_text(m.get('content'))}"
            lines.append(line[:entry_chars] if entry_chars > 0 else line)
        transcript = "\n".join(lines)
        if input_chars > 0:
            transcript = transcript[:input_chars]
        pool = self._pool()
        if pool is None:
            return ""
        try:
            response = await self._dispatch_compact(
                ChatRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": texts.t("compact_summary_prompt"),
                        },
                        {"role": "user", "content": transcript},
                    ],
                    max_tokens=600,
                    temperature=0.2,
                )
            )
            return (getattr(response, "content", "") or "").strip()
        except Exception as e:
            self.main.logger.warning(f"compactor summarize failed: {e}")
            return ""

    async def summarize_text(self, old: str, new: str) -> str:
        """两段摘要文本的 LLM 合并压缩（用于 append_summary 超 cap 时）。"""
        pool = self._pool()
        if pool is None:
            return ""
        input_chars = int(getattr(self.config, "compact_input_chars", 12000) or 0)
        old_text = str(old or "")
        new_text = str(new or "")
        if input_chars > 0:
            old_text = old_text[: input_chars // 2]
            new_text = new_text[: max(200, input_chars - len(old_text))]
        try:
            response = await self._dispatch_compact(
                ChatRequest(
                    messages=[
                        {"role": "system", "content": texts.t("compact_merge_prompt")},
                        {
                            "role": "user",
                            "content": (
                                "<old>\n" + old_text + "\n</old>\n\n<new>\n" + new_text + "\n</new>"
                            ),
                        },
                    ],
                    max_tokens=600,
                    temperature=0.2,
                )
            )
            return (getattr(response, "content", "") or "").strip()
        except Exception as e:
            self.main.logger.warning(f"compactor merge failed: {e}")
            return ""

    async def summarize_entries(self, removed: list) -> str:

        return await self._summarize_turns(removed)

    @staticmethod
    def _content_text(content) -> str:
        if isinstance(content, list):
            return " ".join(
                str(p.get("text") or "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        return str(content or "")

    async def compact(self, chat_key: str, force: bool = False, reason: str = "") -> dict:

        service = self.main.conversations
        contexts = service.get_contexts(chat_key)
        if not contexts:
            return {"chat_key": chat_key, "actions": [], "reason": reason or "empty"}

        actions: list[str] = []
        slimmed, changed = self.microcompact(contexts)
        if changed:
            actions.append(f"microcompact:{changed}")
            contexts = slimmed

        threshold = int(getattr(self.config, "context_compress_tokens", 128000) or 0)
        over = bool(threshold and context_tokens(contexts) > threshold)
        turns_since = service.turns_since_compact(chat_key)
        every = int(getattr(self.config, "compact_every_turns", 10) or 0)
        preventive = bool(every and turns_since >= every)
        strategy = str(getattr(self.config, "context_strategy", "auto") or "auto").lower()

        if strategy != "off" and (force or over or preventive):
            removed, kept_turns = self._select_removed(contexts)
            if removed:
                summary = ""
                if strategy == "truncate":
                    actions.append(f"truncate:-{len(removed)}")
                else:
                    raw = await self._summarize_turns(removed)
                    summary = raw
                    actions.append(f"summarize:-{len(removed)}" + ("(ok)" if raw else "(dry)"))
                kept = merge_turns(kept_turns)
                if summary:
# 分离 <facts> 段（宽松解析，失败不入库）
                    clean, facts = extract_facts(summary)
                    if clean:
                        summary = clean
                    if facts and getattr(self.config, "facts_extract", True):
                        added = service.append_facts(chat_key, facts)
                        if added:
                            actions.append(f"facts:+{added}")
                if summary:
                    service.append_summary(chat_key, summary)
                service.replace_contexts(chat_key, kept)
                service.mark_compacted(chat_key)
                actions.append(f"kept:{len(kept)}")
            else:
                service.mark_compacted(chat_key)
                actions.append("noop:few-turns")
        elif over or preventive:
            service.replace_contexts(chat_key, contexts)
            service.mark_compacted(chat_key)
            actions.append("strategy-off:slim-only")
        elif changed:
            service.replace_contexts(chat_key, contexts)
            actions.append("slim-only")

        return {"chat_key": chat_key, "actions": actions, "reason": reason, "tokens": context_tokens(contexts)}
