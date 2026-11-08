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
# 投递意图标签：任意一段 AI 发言开头的 [[转发]]/[[直发]] 首个命中（True=转发/False=直发）。
# 最终回复自身的标签优先（inbox 合并），None=模型未表态（走自动规则）
    delivery_hint: bool | None = None


class AgentRunner:
    def __init__(self, pool: Any, registry: ToolRegistry, config: Any):
        self.pool = pool
        self.registry = registry
        self.config = config
# 动态工具注入（auto：可见工具数超阈值才启用；fail-open）
        from .toolselect import ToolSelector

        self.selector = ToolSelector(self)

    def _session_block(self, ctx: ToolContext) -> str:
        """当前会话事实块：平台/会话类型/目标 ID/触发者 + 发送路由约定。

        模型"不知道发给谁/发错平台"的根因是缺上下文——把它就在哪、默认去哪、
        跨会话要怎么做一次讲清，与 send_message 的缺省目标约定配套。
        """
        platform = str(getattr(ctx, "platform", "") or "")
        if not platform:
            return ""
        detail_type = str(getattr(ctx, "detail_type", "") or "")
        kind = "group" if detail_type == "group" else ("channel" if detail_type == "channel" else "private")
        return texts.t(
            "session_context",
            platform=platform,
            kind=kind,
            target_id=str(getattr(ctx, "target_id", "") or "-"),
            user_id=str(getattr(ctx, "user_id", "") or "-"),
        )

    def _ctx_is_admin(self, ctx: ToolContext) -> bool:
        """非管理员不注入其无权调用的工具 schema（与 invoke 期 tool_allowed 同一判定）。"""
        if ctx.main is None:
            return True
        try:
            return bool(ctx.main.is_admin(str(ctx.user_id or ""), ctx.origin, ctx.platform))
        except Exception:
            return True

    def _tool_visible_nonadmin(self, name: str) -> bool:
        """tool_allowed 的非管理员分支复刻：admin_tools 强制隐藏；safe 或 safe_tools 放行。"""
        tool = self.registry.get(name)
        if tool is None:
            return False
        if utils.match_pattern(name, list(getattr(self.config, "admin_tools", []) or [])):
            return False
        if getattr(tool, "access", "admin") == "safe":
            return True
        return utils.match_pattern(name, list(getattr(self.config, "safe_tools", []) or []))


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
                        on_reasoning=None, chat_key: str = "", priority: int = 0):
        """pool 支持 TaskSpec 分派时走 dispatch(kind)，否则退回 pool.chat（兼容老式池对象）。

        priority：并发闸门优先级（用户直答 0 / 插话 6 / 后台任务 8）。"""
        dispatch = getattr(self.pool, "dispatch", None)
        if callable(dispatch):
            spec = TaskSpec(kind=kind, needs=needs, prefer=prefer, model=model, chat_key=chat_key, priority=priority)
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
        final_text, tag_hint = utils.strip_output_tag((final.content or "").strip())
        result.text = final_text
        result.model = final.model or result.model
        if result.delivery_hint is None and tag_hint is not None:
            result.delivery_hint = tag_hint
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
        max_tokens: int | None = None,
        task_kind: str = "chat",
        priority: int = 0,
        prefill: str = "",
    ) -> AgentResult:
        contexts = self._sanitize_contexts(list(messages))
        session_block = self._session_block(ctx)
        if session_block:
            system = system + "\n\n" + session_block
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
            max_tokens=max_tokens,
            usage_total=usage_total,
            priority=priority,
            prefill=prefill,
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
        max_tokens: int | None = None,
        usage_total: dict | None = None,
        priority: int = 0,
        prefill: str = "",
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
# 权限对齐：非管理员看不到调不动的工具（避免模型反复调用然后被拒浪费轮次）
        if schemas and not self._ctx_is_admin(ctx):
            schemas = [s for s in schemas if self._tool_visible_nonadmin(str(s.get("function", {}).get("name") or ""))]
# 动态工具注入（权限过滤之后：只从"本来就能用"的工具里挑）
        hidden_by_select: list[str] = []
        if schemas and getattr(self, "selector", None) is not None:
            visible_names = {str(s.get("function", {}).get("name") or "") for s in schemas}
            user_text = self._last_user_text(contexts)
            selected = await self.selector.select(user_text, schemas, chat_key=ctx.chat_key)
            if len(selected) < len(schemas):
                kept = {str(s.get("function", {}).get("name") or "") for s in selected}
                hidden_by_select = sorted(visible_names - kept)
                schemas = selected
        max_rounds = int(getattr(self.config, "max_tool_rounds", 50) or 50)
        max_calls = int(getattr(self.config, "max_tool_calls", 150) or 150)
        total_calls = 0
        rounds: list = []
        nudged = False  # 空最终回复重问已用过（限一次）
# tool_call 能力闭环（schemas 非空且未显式指定模型时）
        schemas, system, chat_needs = self._apply_tools_fallback(schemas, system, model)
        delivery_hint: bool | None = None
# 预填充（人格级口语开场白）：只在首轮请求以 assistant 结尾消息注入，模型从这里续写。
# 不写进 contexts——工具轮的后续请求与累积对话都不受污染。
        prefill = str(prefill or "").strip()
        prefill_state = {"pending": bool(prefill), "active": False}
        if prefill and on_delta is not None:
# 流式起步：先发开场白再发增量；failover on_reset 清段后由 pending 标志自动补发
            base_on_delta, base_on_reset = on_delta, on_reset

            async def on_delta(piece):  # noqa: F811 — 局部包装
                if prefill_state["pending"]:
                    prefill_state["pending"] = False
                    result = base_on_delta(prefill)
                    if asyncio.iscoroutine(result):
                        await result
                result = base_on_delta(piece)
                if asyncio.iscoroutine(result):
                    await result

            def on_reset():  # noqa: F811 — 局部包装
                prefill_state["pending"] = True
                return base_on_reset()

        for loop_index in range(max_rounds):
            messages = [{"role": "system", "content": system}] + contexts
            use_prefill = bool(prefill) and loop_index == 0 and not self._prefill_blocked(model)
            if use_prefill:
                messages.append({"role": "assistant", "content": prefill})
            request = ChatRequest(
                messages=messages,
                tools=schemas or None,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                needs=chat_needs,
            )
            if use_prefill:
                try:
                    response = await self._dispatch("chat", request, needs=chat_needs, model=model,
                                                    on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning,
                                                    chat_key=ctx.chat_key, priority=priority)
                except Exception:
# 模型可能不支持 assistant 结尾续写（400 类）：立即去 prefill 重跑一次并记住
                    self._mark_prefill_blocked(model)
                    request = ChatRequest(
                        messages=[{"role": "system", "content": system}] + contexts,
                        tools=schemas or None,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        needs=chat_needs,
                    )
                    response = await self._dispatch("chat", request, needs=chat_needs, model=model,
                                                    on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning,
                                                    chat_key=ctx.chat_key, priority=priority)
            else:
                response = await self._dispatch("chat", request, needs=chat_needs, model=model,
                                                on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning,
                                                chat_key=ctx.chat_key, priority=priority)
# 引擎剥图重试过 → 模型本轮没看见图：补一份视觉描述，避免它装作看过
            if getattr(response, "images_stripped", False):
                urls = list(getattr(response, "stripped_image_urls", []) or [])
                if urls:
                    described = await self.pool.describe_images(urls, on_error="text")
                    lines = [f"[image {i + 1}] {d}" for i, d in enumerate(described) if d]
                    if lines:
                        contexts.append(
                            {
                                "role": "user",
                                "content": texts.t("vision_stripped_note") + "\n" + "\n".join(lines),
                            }
                        )
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage_total[key] = usage_total.get(key, 0) + response.usage.get(key, 0)
            used_model = response.model or used_model
            if not response.tool_calls:
                final_text, tag_hint = utils.strip_output_tag((response.content or "").strip())
                # 跑完工具后返回空文本（部分模型 tool_calls 结束后的常态）：
                # 不把"没有可回复的内容"甩给用户——补一轮无工具重问，要最终结论（限一次）
                if not final_text.strip() and not nudged:
                    nudged = True
                    contexts.append({"role": "user", "content": texts.t("empty_final_nudge")})
                    continue
# 最终回复自身的标签优先级最高（覆盖过程中声明的意图）
                if tag_hint is not None:
                    delivery_hint = tag_hint
                final_text = self._with_prefill(final_text, prefill)
                rounds.append({"text": final_text, "tools": []})
                return AgentResult(text=final_text, tool_trace=trace, usage=usage_total, rounds=rounds,
                                   model=used_model, delivery_hint=delivery_hint)
            trace_before = len(trace)
# 中间发言也可携带 [[转发]]/[[直发]] 标签（首个命中记录为整轮投递意图，并从展示文本剥离）
            speech, tag_hint = utils.strip_output_tag((response.content or "").strip())
            speech = utils.strip_stray_tags(speech)
            if delivery_hint is None and tag_hint is not None:
                delivery_hint = tag_hint
            rounds.append({"text": speech, "tools": []})
            contexts.append(self._assistant_message(response.content, response.tool_calls))
            if on_intermediate is not None:
                if speech:
                    try:
                        callback_result = on_intermediate(speech)
                        if asyncio.iscoroutine(callback_result):
                            await callback_result
                    except Exception as e:
# 回调失败不能无声（投递层会记日志，这里兜底记非投递类异常）
                        logger = getattr(getattr(ctx, "main", None), "logger", None)
                        if logger is not None:
                            try:
                                logger.warning(f"on_intermediate callback failed: {e}")
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
            # 透传回调给工具：spawn_agent 用它把子智能体内部步骤也播到同一条直播流
            ctx.on_tool_event = on_tool_event
            outputs = await asyncio.gather(
                *[
                    self._run_tool(tc, ctx, trace, on_tool_event=on_tool_event, step_id=f"s{step_counter['n'] + i}")
                    for i, tc in enumerate(response.tool_calls)
                ]
            )
# 自愈：模型点名了被工具选择器隐藏（但本来有权限）的工具 → 下一轮补回 schema
            if hidden_by_select:
                missing = [str(tc.name) for tc in response.tool_calls if str(tc.name) in hidden_by_select]
                for name in missing:
                    entry = next(
                        (s for s in self.registry.llm_schemas(
                            whitelist=persona_tools,
                            disabled=list(getattr(self.config, "disabled_tools", []) or []),
                        ) if s.get("function", {}).get("name") == name),
                        None,
                    )
                    if entry is not None:
                        schemas.append(entry)
                        hidden_by_select.remove(name)
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
             chat_key=ctx.chat_key, priority=priority)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage_total[key] = usage_total.get(key, 0) + final.usage.get(key, 0)
        raw_text = (final.content or "").strip()
        final_text, tag_hint = utils.strip_output_tag(raw_text)
# 最终回复自身的标签优先级最高
        if tag_hint is not None:
            delivery_hint = tag_hint
        final_text = self._with_prefill(final_text, prefill)
        rounds.append({"text": final_text, "tools": []})
        return AgentResult(text=final_text, tool_trace=trace, usage=usage_total, rounds=rounds,
                           model=used_model or final.model, delivery_hint=delivery_hint)

    @staticmethod
    def _with_prefill(text: str, prefill: str) -> str:
        """开场白 + 续写拼合：模型若把开场白原样复读（部分后端行为），以续写为准去重。"""
        text = str(text or "")
        prefill = str(prefill or "").strip()
        if not prefill or not text:
            return text
        if text.startswith(prefill):
            return text
        return prefill + text

    def _prefill_blocked(self, model: str | None) -> bool:
        """auto 探测记忆：该模型此前 prefill 请求失败（本进程内不再重试）。"""
        return bool(model) and model in getattr(self, "_prefill_failures", set())

    def _mark_prefill_blocked(self, model: str | None) -> None:
        if model:
            failures = getattr(self, "_prefill_failures", None)
            if failures is None:
                failures = set()
                self._prefill_failures = failures
            failures.add(model)

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
