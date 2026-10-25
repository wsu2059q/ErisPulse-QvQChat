from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from ..engine.base import ChatRequest, EngineError, TaskSpec
from .. import texts, utils
from ..prompts import CRITIQUE_PROMPT, REFLEXION_PLAN_PROMPT
from ..utils import truncate
from .tools import ToolContext, ToolRegistry


@dataclass
class AgentResult:
    text: str
    tool_trace: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    rounds: list = field(default_factory=list)
    model: str = ""
# 计划-执行-反思（deep 任务）：阶段产物，普通 chat 任务保持空串
    plan: str = ""
    critique: str = ""


class AgentRunner:
    def __init__(self, pool: Any, registry: ToolRegistry, config: Any):
        self.pool = pool
        self.registry = registry
        self.config = config

    def _assistant_message(self, content: str | None, tool_calls: list) -> dict:
        message: dict = {"role": "assistant", "content": content or ""}
        serialized = []
        for index, tc in enumerate(tool_calls):
            serialized.append(
                {
                    "id": tc.call_id or f"call_{int(time.time() * 1000)}_{index}",
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments or {}, ensure_ascii=False),
                    },
                }
            )
        if serialized:
            message["tool_calls"] = serialized
        return message

    async def _run_tool(self, tool_call, ctx: ToolContext, trace: list, on_tool_event=None, step_id: str = "") -> tuple[str, bool]:
        """执行一次工具调用。返回 (输出文本, 是否失败)；失败判定来自 registry.invoke 的 meta["error"]。"""
        arguments_text = (
            tool_call.arguments
            if isinstance(tool_call.arguments, str)
            else json.dumps(tool_call.arguments or {}, ensure_ascii=False)
        )
        if on_tool_event is not None:
            try:
                result = on_tool_event(
                    {
                        "phase": "start",
                        "step_id": step_id,
                        "name": tool_call.name,
                        "arguments": truncate(arguments_text, 2000),
                    }
                )
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass
        started = time.monotonic()
        meta: dict = {}
        try:
            output = await self.registry.invoke(
                tool_call.name,
                tool_call.arguments,
                ctx,
                timeout=float(getattr(self.config, "tool_timeout", 120)),
                meta=meta,
            )
        except Exception as e:
            output = f"error: {e}"
            meta["error"] = True
        ms = int((time.monotonic() - started) * 1000)
        trace.append(
            {
                "tool": tool_call.name,
                "arguments": truncate(arguments_text, 300),
                "output": truncate(output, 300),
                "ms": ms,
            }
        )
        if on_tool_event is not None:
            try:
                result = on_tool_event(
                    {
                        "phase": "end",
                        "step_id": step_id,
                        "name": tool_call.name,
                        "output": truncate(output, 2000),
                        "ms": ms,
                    }
                )
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass
        return output, bool(meta.get("error"))

    @staticmethod
    def _sanitize_contexts(contexts: list) -> list:
        cleaned: list = []
        for message in contexts:
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role == "user":
                cleaned.append({"role": "user", "content": message.get("content")})
            elif role == "assistant":
                entry: dict = {"role": "assistant", "content": message.get("content") or ""}
                if message.get("tool_calls"):
                    entry["tool_calls"] = message["tool_calls"]
                cleaned.append(entry)
            elif role == "tool":
                entry = {"role": "tool", "content": message.get("content") or ""}
                if message.get("tool_call_id"):
                    entry["tool_call_id"] = message["tool_call_id"]
                cleaned.append(entry)
            elif role == "system":
                cleaned.append({"role": "system", "content": message.get("content") or ""})
        return cleaned

    @staticmethod
    def _images_from_output(output: str) -> list:
        try:
            parsed = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(parsed, dict):
            return []
        images = []
        for key in ("image_path", "image_url", "image"):
            value = parsed.get(key)
            if isinstance(value, str) and value:
                images.append(value)
        return images

# ===== 能力查询与任务分派 =====

    def _pool_capability(self, need: str) -> str:
        """yes/no/unknown；池对象不支持查询（老式 fake/自定义池）时返回 unknown。"""
        pool = getattr(self, "pool", None)
        status = getattr(pool, "capability_status", None)
        if not callable(status):
            return "unknown"
        try:
            result = status(need)
        except Exception:
            return "unknown"
        return str(result) if result else "unknown"

    async def _dispatch(self, kind: str, request: ChatRequest, *, needs: list | None = None,
                        model: str | None = None, prefer: str = "", on_delta=None, on_reset=None,
                        on_reasoning=None, chat_key: str = ""):
        """pool 支持 TaskSpec 分派时走 dispatch(kind)，否则退回 pool.chat（兼容老式池对象）。"""
        dispatch = getattr(self.pool, "dispatch", None)
        if callable(dispatch):
            spec = TaskSpec(kind=kind, needs=needs, prefer=prefer, model=model, chat_key=chat_key)
            return await dispatch(spec, request, on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning)
        return await self.pool.chat(request, on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning)

    def _apply_tools_fallback(self, schemas: list, system: str, model: str | None) -> tuple[list, str, list | None]:
        """tool_call 能力闭环：schemas 非空且未显式指定模型时决定是否筛选/降级。

        返回 (schemas, system, needs)：needs 为 None 表示不带能力过滤。"""
        if not schemas or model:
            return schemas, system, None
        status = self._pool_capability("tool_call")
        if status == "yes":
            return schemas, system, ["tool_call"]
        if status != "no":
# 能力未知：保持旧行为（照常带工具）
            return schemas, system, None
        fallback = str(getattr(self.config, "tools_fallback", "strip") or "strip").lower()
        if fallback == "off":
            return schemas, system, None
        if fallback == "strict":
            raise EngineError(texts.t("no_toolcall_model"))
# strip（默认）：去工具 + system 追加降级提示，保证必答
        return [], system + "\n\n" + texts.t("tools_degraded_note"), None

# ===== 计划-执行-反思（deep 任务三段式）=====

    @staticmethod
    def _content_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [str(p.get("text") or "") for p in content if isinstance(p, dict)]
            return "\n".join(t for t in parts if t)
        return str(content or "")

    @classmethod
    def _last_user_text(cls, contexts: list) -> str:
        for message in reversed(contexts):
            if isinstance(message, dict) and message.get("role") == "user":
                return cls._content_text(message.get("content"))
        return ""

    @staticmethod
    def _merge_usage(target: dict, response) -> None:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            target[key] = target.get(key, 0) + (response.usage or {}).get(key, 0)

    async def _plan_phase(self, system: str, contexts: list, usage: dict) -> str:
        """阶段一 PLAN：进工具循环前的一次廉价规划调用（kind=compact/prefer=cheap，失败降级为空计划）。"""
        user_text = self._last_user_text(contexts)
        if not user_text:
            return ""
        request = ChatRequest(
            messages=[
                {"role": "system", "content": REFLEXION_PLAN_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "<system>\n" + truncate(system, 4000) + "\n</system>\n\n"
                        "<task>\n" + truncate(user_text, 4000) + "\n</task>"
                    ),
                },
            ],
            tools=None,
            temperature=0.2,
        )
        try:
            response = await self._dispatch("compact", request, prefer="cheap")
        except Exception:
            return ""
        self._merge_usage(usage, response)
        return (response.content or "").strip()

    @staticmethod
    def _trace_summary(trace: list, limit: int = 20) -> str:
        lines: list[str] = []
        for entry in trace[:limit]:
            if not isinstance(entry, dict):
                continue
            lines.append(f"- {entry.get('tool')}: {entry.get('output') or ''}")
        if len(trace) > limit:
            lines.append(f"... ({len(trace) - limit} more)")
        return "\n".join(lines)

    async def _critique_phase(self, plan: str, task_text: str, result: AgentResult) -> str:
        """阶段三 CRITIQUE：给计划+最终回复+工具 trace 摘要，要求输出 DONE 或 FIX: 修正点。"""
        payload = (
            "<task>\n" + truncate(task_text, 2000) + "\n</task>\n\n"
            "<plan>\n" + truncate(plan, 2000) + "\n</plan>\n\n"
            "<final-reply>\n" + truncate(result.text, 3000) + "\n</final-reply>\n\n"
            "<tool-activity>\n" + (self._trace_summary(result.tool_trace) or "(no tools used)") + "\n</tool-activity>"
        )
        request = ChatRequest(
            messages=[
                {"role": "system", "content": CRITIQUE_PROMPT},
                {"role": "user", "content": payload},
            ],
            tools=None,
            temperature=0.1,
        )
        try:
            response = await self._dispatch("compact", request, prefer="cheap")
        except Exception:
            return ""
        self._merge_usage(result.usage, response)
        return (response.content or "").strip()

    @staticmethod
    def _parse_critique_fix(critique: str) -> str:
        """DONE（或无法识别）→ 不修正；FIX: xxx → 返回修正点文本。"""
        text = (critique or "").strip()
        if not text:
            return ""
        head = text.splitlines()[0].strip()
        if head.upper().startswith("DONE"):
            return ""
        if head.upper().startswith("FIX"):
            body = text[3:].lstrip(": ：-—").strip()
            return body or text
        return ""

    async def _fix_round(self, system: str, contexts: list, result: AgentResult, fix_points: str, *,
                         model=None, temperature=None, on_delta=None, on_reset=None, on_reasoning=None,
                         chat_key: str = "") -> None:
        """有界 1 次的无工具修正收尾：修正点作为追加 user 消息，就地更新 result。"""
        contexts.append({"role": "assistant", "content": result.text})
        contexts.append({"role": "user", "content": texts.t("deep_fix_note", fixes=truncate(fix_points, 2000))})
        request = ChatRequest(
            messages=[{"role": "system", "content": system}] + contexts,
            tools=None,
            model=model,
            temperature=temperature,
        )
        final = await self._dispatch("chat", request, model=model,
                                     on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning,
                                     chat_key=chat_key)
        self._merge_usage(result.usage, final)
        final_text = (final.content or "").strip()
        result.text = final_text
        result.model = final.model or result.model
        result.rounds.append({"text": final_text, "tools": []})

    async def run(
        self,
        *,
        system: str,
        messages: list,
        ctx: ToolContext,
        persona_tools: list | None = None,
        on_tool_round=None,
        on_intermediate=None,
        on_delta=None,
        on_reset=None,
        on_tool_event=None,
        on_reasoning=None,
        model: str | None = None,
        temperature: float | None = None,
        task_kind: str = "chat",
    ) -> AgentResult:
        contexts = self._sanitize_contexts(list(messages))
# 全程用量聚合：PLAN/EXECUTE/CRITIQUE/修正轮共用一个累计器（供计费与限额）
        usage_total: dict = {}
        plan = ""
        if str(task_kind) == "deep":
# 阶段一 PLAN：规划文本注入 system 尾部 <task-plan> 块
            plan = await self._plan_phase(system, contexts, usage_total)
            if plan:
                system = system + "\n\n<task-plan>\n" + plan + "\n</task-plan>"
# 原始用户任务文本：在工具循环改写 contexts（预算提示/图片注记）之前留存，供审查阶段使用
        task_text = self._last_user_text(contexts)
# 阶段二 EXECUTE：工具循环（含工具自愈）
        result = await self._run_loop(
            system=system,
            contexts=contexts,
            ctx=ctx,
            persona_tools=persona_tools,
            on_tool_round=on_tool_round,
            on_intermediate=on_intermediate,
            on_delta=on_delta,
            on_reset=on_reset,
            on_tool_event=on_tool_event,
            on_reasoning=on_reasoning,
            model=model,
            temperature=temperature,
            usage_total=usage_total,
        )
        if str(task_kind) != "deep":
            return result
# 阶段三 CRITIQUE：审查后 FIX 时有界 1 次无工具修正
        result.plan = plan
        critique = await self._critique_phase(plan, task_text, result)
        result.critique = critique
        fix_points = self._parse_critique_fix(critique)
        if fix_points:
            await self._fix_round(system, contexts, result, fix_points, model=model, temperature=temperature,
                                  on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning,
                                  chat_key=ctx.chat_key)
        return result

    async def _run_loop(
        self,
        *,
        system: str,
        contexts: list,
        ctx: ToolContext,
        persona_tools: list | None = None,
        on_tool_round=None,
        on_intermediate=None,
        on_delta=None,
        on_reset=None,
        on_tool_event=None,
        on_reasoning=None,
        model: str | None = None,
        temperature: float | None = None,
        usage_total: dict | None = None,
    ) -> AgentResult:
        trace: list = []
        pending_images: list = []
        if usage_total is None:
            usage_total = {}
        used_model = ""
        step_counter = {"n": 0}
# 工具自愈：per-tool 连续失败计数（name → 最近错误输出列表），成功即清零
        fail_streak: dict[str, list[str]] = {}
        heal_enabled = bool(getattr(self.config, "tool_self_heal", True))
        schemas = self.registry.llm_schemas(
            whitelist=persona_tools,
            disabled=list(getattr(self.config, "disabled_tools", []) or []),
        )
        max_rounds = int(getattr(self.config, "max_tool_rounds", 50) or 50)
        max_calls = int(getattr(self.config, "max_tool_calls", 150) or 150)
        total_calls = 0
        rounds: list = []
# tool_call 能力闭环（schemas 非空且未显式指定模型时）
        schemas, system, chat_needs = self._apply_tools_fallback(schemas, system, model)
        for loop_index in range(max_rounds):
            request = ChatRequest(
                messages=[{"role": "system", "content": system}] + contexts,
                tools=schemas or None,
                model=model,
                temperature=temperature,
                needs=chat_needs,
            )
            response = await self._dispatch("chat", request, needs=chat_needs, model=model,
                                            on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning,
             chat_key=ctx.chat_key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage_total[key] = usage_total.get(key, 0) + response.usage.get(key, 0)
            used_model = response.model or used_model
            if not response.tool_calls:
                final_text = (response.content or "").strip()
                rounds.append({"text": final_text, "tools": []})
                return AgentResult(text=final_text, tool_trace=trace, usage=usage_total, rounds=rounds, model=used_model)
            trace_before = len(trace)
            rounds.append({"text": (response.content or "").strip(), "tools": []})
            contexts.append(self._assistant_message(response.content, response.tool_calls))
            if on_intermediate is not None:
                speech = (response.content or "").strip()
                if speech:
                    try:
                        callback_result = on_intermediate(speech)
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
                    except Exception:
                        pass
            if on_tool_round is not None:
                try:
                    details = [
                        {"name": tc.name, "arguments": utils.truncate(json.dumps(tc.arguments or {}, ensure_ascii=False), 60)}
                        for tc in response.tool_calls
                    ]
                    callback_result = on_tool_round(details)
                    if asyncio.iscoroutine(callback_result):
                        await callback_result
                except Exception:
                    pass
            outputs = await asyncio.gather(
                *[
                    self._run_tool(tc, ctx, trace, on_tool_event=on_tool_event, step_id=f"s{step_counter['n'] + i}")
                    for i, tc in enumerate(response.tool_calls)
                ]
            )
            remaining = max_rounds - (loop_index + 1)
            if remaining in (3, 2, 1) and remaining > 0:
                contexts.append({"role": "user", "content": texts.t("tool_budget_hint", n=remaining)})
            step_counter["n"] += len(response.tool_calls)
            if rounds:
                rounds[-1]["tools"] = trace[trace_before:]
            heal_hints: list[str] = []
            for tc, (output, errored) in zip(response.tool_calls, outputs):
                contexts.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.call_id or f"call_{id(tc)}",
                        "content": output,
                    }
                )
                if errored:
                    streak = fail_streak.setdefault(str(tc.name), [])
                    streak.append(truncate(str(output), 200))
# 连续第 2/4/… 次失败：注入一次修正提示，让下一轮模型自行调整参数
                    if heal_enabled and len(streak) >= 2 and len(streak) % 2 == 0:
                        errors = "\n".join(f"- {line}" for line in streak[-2:])
                        heal_hints.append(texts.t("tool_selfheal_hint", name=str(tc.name), errors=errors))
                else:
                    fail_streak.pop(str(tc.name), None)
                for image in self._images_from_output(output):
                    if len(pending_images) < 3:
                        pending_images.append(image)
            for hint in heal_hints:
                contexts.append({"role": "user", "content": hint})
            if pending_images:
                if self._pool_has_vision():
                    image_parts: list = [{"type": "text", "text": texts.t("tool_image_note")}]
                    image_parts += [{"type": "image_url", "image_url": {"url": url}} for url in pending_images[:3]]
                    contexts.append({"role": "user", "content": image_parts})
                else:
                    described = await self.pool.describe_images(pending_images)
                    lines = [
                        f"[image {i + 1}] {d}" for i, d in enumerate(described) if d
                    ]
                    block = texts.t("tool_image_note") + ("\n" + "\n".join(lines) if lines else "")
                    contexts.append({"role": "user", "content": block})
                pending_images = []
            total_calls += len(response.tool_calls)
            if total_calls >= max_calls:
                break
        contexts.append({"role": "user", "content": texts.t("tool_limit_hint")})
        final_request = ChatRequest(
            messages=[{"role": "system", "content": system}] + contexts,
            tools=None,
            model=model,
            temperature=temperature,
            needs=chat_needs,
        )
        final = await self._dispatch("chat", final_request, needs=chat_needs, model=model,
                                     on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning,
             chat_key=ctx.chat_key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage_total[key] = usage_total.get(key, 0) + final.usage.get(key, 0)
        final_text = (final.content or "").strip()
        rounds.append({"text": final_text, "tools": []})
        return AgentResult(text=final_text, tool_trace=trace, usage=usage_total, rounds=rounds, model=used_model or final.model)

    def _pool_has_vision(self) -> bool:
# 修近似探测——优先 pool.has_model(["vision"])（老式池对象退回旧近似逻辑）
        checker = getattr(self.pool, "has_model", None)
        if callable(checker):
            try:
                return bool(checker(["vision"]))
            except Exception:
                return True
        try:
            caps = self.pool.primary_capabilities()
        except Exception:
            return True
        return caps.get("vision") is not False
