from __future__ import annotations

from typing import Any

from .. import texts, utils
from ..engine.base import ChatRequest


def estimate_tokens(text) -> int:

    if isinstance(text, list):
        text = " ".join(
            str(p.get("text") or "") for p in text if isinstance(p, dict) and p.get("type") == "text"
        )
    return len(str(text or "")) // 2


def context_tokens(contexts: list) -> int:
    total = 0
    for m in contexts:
        total += estimate_tokens(m.get("content") if isinstance(m, dict) else m)
    return total


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


    def _pool(self):
        return getattr(self.main, "pool", None)


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
        transcript = "\n".join(
            f"{m.get('role')}: {str(self._content_text(m.get('content')))[:240]}"
            for m in removed
            if isinstance(m, dict)
        )
        pool = self._pool()
        if pool is None:
            return ""
        model = str(getattr(self.config, "compact_model", "") or "") or None
        try:
            response = await pool.chat(
                ChatRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Summarize the following conversation excerpt into concise bullet "
                                "points in the same language as the content. Keep names, ids, "
                                "decisions, facts and unresolved questions. No preamble."
                            ),
                        },
                        {"role": "user", "content": transcript[:8000]},
                    ],
                    model=model,
                    max_tokens=600,
                    temperature=0.2,
                )
            )
            return (response.content or "").strip()
        except Exception as e:
            self.main.logger.warning(f"compactor summarize failed: {e}")
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
                if strategy == "truncate":
                    summary = ""
                    actions.append(f"truncate:-{len(removed)}")
                else:
                    summary = await self._summarize_turns(removed)
                    actions.append(f"summarize:-{len(removed)}" + ("(ok)" if summary else "(dry)"))
                kept = merge_turns(kept_turns)
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
