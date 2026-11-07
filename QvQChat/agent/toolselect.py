"""动态工具注入（检索式工具选择）。

参考 ToolRet / Gorilla 的思路：工具数量很多时，把「全部工具 schema」换成
「一个廉价模型从工具清单里挑出的子集」，减少提示占用与误选。

设计要点：
- fail-open：解析失败/超时/无模型 → 回退全量，绝不因为选择器故障而少工具
- 核心工具恒保留（send_message 等），避免闲聊回复发不出去
- 会话级 TTL 缓存：同一话题连续回合不重复调用小模型
- 自愈：模型后续尝试调用一个"本可见但被隐藏"的工具时，下一轮补入该工具
"""
from __future__ import annotations

import asyncio
import json
import re
import time

from ..engine.base import ChatRequest, TaskSpec

# 始终保留的核心工具：聊天回合的最终交付手段，被剪掉会导致"有答案发不出"
CORE_TOOLS = (
# 交付三件套 + "保持聪明"三件套：联网与框架文档检索是自足能力的入口，
# 被动态注入剪掉的表现就是"突然不会自己查文档了"
    "send_message", "send_dsl", "send_erispulse_message",
    "search_erispulse_docs", "web_search", "web_fetch",
)

PROMPT = (
    "You select which tools an AI agent needs for the CURRENT user message. "
    "You get a numbered list of available tools (name — description) and the user message. "
    "Reply with ONLY a JSON array of tool names that are plausibly needed, e.g. [\"web_search\",\"run_command\"]. "
    "Rules: include a tool when it could help; when unsure, include it. "
    "Never invent names. At most {limit} tools. Reply with the JSON array alone."
)


def _parse_names(text: str, allowed: set[str]) -> list[str]:
    raw = str(text or "").strip()
# 容忍 ```json 包裹或前后解释文字
    match = re.search(r"\[[^\]]*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        name = str(item).strip()
        if name in allowed and name not in names:
            names.append(name)
    return names


class ToolSelector:
    def __init__(self, runner):
        self.runner = runner
        self.pool = runner.pool
        self.config = runner.config
        self._cache: dict[str, tuple[list[str], float]] = {}

    def enabled(self, schema_count: int) -> bool:
        mode = str(getattr(self.config, "tool_select", "auto") or "auto").lower()
        if mode == "off":
            return False
        if mode == "on":
            return schema_count > 0
        return schema_count > int(getattr(self.config, "tool_select_threshold", 16) or 16)

    def _cached(self, chat_key: str) -> list[str] | None:
        ttl = float(getattr(self.config, "tool_select_ttl", 180) or 0)
        if not chat_key or ttl <= 0:
            return None
        hit = self._cache.get(chat_key)
        if not hit:
            return None
        names, ts = hit
        if time.time() - ts > ttl:
            self._cache.pop(chat_key, None)
            return None
        return names

    def _remember(self, chat_key: str, names: list[str]) -> None:
        if not chat_key:
            return
        ttl = float(getattr(self.config, "tool_select_ttl", 180) or 0)
        if ttl <= 0:
            return
        if len(self._cache) > 256:
            now = time.time()
            self._cache = {k: v for k, v in self._cache.items() if now - v[1] <= ttl}
        self._cache[chat_key] = (names, time.time())

    async def select(self, user_text: str, schemas: list, chat_key: str = "") -> list:
        """返回筛选后的 schema 列表；任何异常都回退全量（fail-open）。"""
        if not schemas or not self.enabled(len(schemas)):
            return schemas
# 高负载降载：满载时不发筛选调用（全量注入零成本，只是 prompt 长一点）
        pool = getattr(self.runner, "pool", None)
        if pool is not None and callable(getattr(pool, "background_blocked", None)) and pool.background_blocked():
            sdk = getattr(self.pool, "sdk", None)
            logger = getattr(sdk, "logger", None) if sdk is not None else None
            if logger is not None:
                logger.debug("background skip: tool-select (saturated) -> full injection")
            return schemas
        cached = self._cached(chat_key)
        if cached is not None:
            allowed = {s["function"]["name"] for s in schemas}
            picked = [n for n in cached if n in allowed]
            if picked:
                return self._apply(schemas, picked)

        briefs = []
        for schema in schemas:
            function = schema.get("function") or {}
            name = str(function.get("name") or "")
            desc = str(function.get("description") or "").split("\n")[0][:160]
            briefs.append(f"- {name}: {desc}")
        limit = max(1, int(getattr(self.config, "tool_select_top_k", 12) or 12))
        request = ChatRequest(
            messages=[
                {"role": "system", "content": PROMPT.format(limit=limit)},
                {
                    "role": "user",
                    "content": "<tools>\n" + "\n".join(briefs) + "\n</tools>\n\n<message>\n"
                    + str(user_text or "")[:2000] + "\n</message>",
                },
            ],
            tools=None,
            temperature=0.0,
            max_tokens=200,
        )
        timeout = float(getattr(self.config, "tool_select_timeout", 3.0) or 3.0)
        explicit_model = str(getattr(self.config, "tool_select_model", "") or "") or None
        try:
            response = await asyncio.wait_for(
                self.runner._dispatch(
                    "toolselect",
                    request,
# 未显式指定模型时按成本优先（便宜模型足够做工具挑选）
                    prefer="" if explicit_model else "cheap",
                    model=explicit_model,
                    chat_key=chat_key,
                ),
                timeout=timeout,
            )
        except Exception as e:
            logger = getattr(getattr(self.runner, "pool", None), "sdk", None)
            try:
                logger.logger.debug(f"tool select failed, fail-open: {e}")
            except Exception:
                pass
            return schemas
        allowed = {s["function"]["name"] for s in schemas}
        picked = _parse_names(getattr(response, "content", "") or "", allowed)[:limit]
        if not picked:
            return schemas
        self._remember(chat_key, picked)
        selected = self._apply(schemas, picked)
# 诊断：log_debug 打开时可见被裁掉的内置工具（"明明装了却不调用"的排查入口）
        sdk = getattr(self.runner, "pool", None)
        sdk = getattr(sdk, "sdk", None) if sdk is not None else None
        cfg = getattr(self.runner, "config", None)
        if sdk is not None and bool(getattr(cfg, "log_debug", False)):
            kept = {s["function"]["name"] for s in selected}
            dropped = sorted(n for n in allowed if n not in kept)
            if dropped:
                try:
                    sdk.logger.debug(f"tool select pruned: {', '.join(dropped)}")
                except Exception:
                    pass
        return selected

    @staticmethod
    def _apply(schemas: list, picked: list[str]) -> list:
        # eco_* 一律豁免裁剪：表情包/TTS 等生态工具是"可选的正确答案"，
        # 被小模型裁掉后模型根本看不见，表现就是"明明装了却从不调用"
        eco_names = {s["function"]["name"] for s in schemas if s["function"]["name"].startswith("eco_")}
        wanted = set(picked) | set(CORE_TOOLS) | eco_names
        selected = [s for s in schemas if s["function"]["name"] in wanted]
        return selected or schemas
