from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from ..engine.base import ChatRequest
from .. import texts, utils
from ..utils import truncate
from .tools import ToolContext, ToolRegistry


@dataclass
class AgentResult:
    text: str
    tool_trace: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    rounds: list = field(default_factory=list)  # [{text, tools:[trace]}] 按轮次串行，供回放渲染
    model: str = ""


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

    async def _run_tool(self, tool_call, ctx: ToolContext, trace: list, on_tool_event=None, step_id: str = "") -> str:
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
        try:
            output = await self.registry.invoke(
                tool_call.name,
                tool_call.arguments,
                ctx,
                timeout=float(getattr(self.config, "tool_timeout", 120)),
            )
        except Exception as e:
            output = f"error: {e}"
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
        return output

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
        model: str | None = None,
        temperature: float | None = None,
    ) -> AgentResult:
        contexts = self._sanitize_contexts(list(messages))
        trace: list = []
        pending_images: list = []
        usage_total: dict = {}
        used_model = ""
        step_counter = {"n": 0}
        schemas = self.registry.llm_schemas(
            whitelist=persona_tools,
            disabled=list(getattr(self.config, "disabled_tools", []) or []),
        )
        max_rounds = int(getattr(self.config, "max_tool_rounds", 15))
        max_calls = int(getattr(self.config, "max_tool_calls", 30))
        total_calls = 0
        rounds: list = []
        for _ in range(max_rounds):
            request = ChatRequest(
                messages=[{"role": "system", "content": system}] + contexts,
                tools=schemas or None,
                model=model,
                temperature=temperature,
            )
            response = await self.pool.chat(request, on_delta=on_delta, on_reset=on_reset)
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
            # 中间发言回调：模型在调用工具前输出的叙述（开场/阶段播报）
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
            step_counter["n"] += len(response.tool_calls)
            if rounds:
                rounds[-1]["tools"] = trace[trace_before:]
            for tc, output in zip(response.tool_calls, outputs):
                contexts.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.call_id or f"call_{id(tc)}",
                        "content": output,
                    }
                )
                for image in self._images_from_output(output):
                    if len(pending_images) < 3:
                        pending_images.append(image)
            if pending_images:
                if self._pool_has_vision():
                    image_parts: list = [{"type": "text", "text": texts.t("tool_image_note")}]
                    image_parts += [{"type": "image_url", "image_url": {"url": url}} for url in pending_images[:3]]
                    contexts.append({"role": "user", "content": image_parts})
                else:
                    # 主模型无视觉：视觉模型代看，文字描述交给主模型
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
        final = await self.pool.chat(
            ChatRequest(
                messages=[{"role": "system", "content": system}] + contexts,
                tools=None,
                model=model,
                temperature=temperature,
            ),
            on_delta=on_delta,
            on_reset=on_reset,
        )
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage_total[key] = usage_total.get(key, 0) + final.usage.get(key, 0)
        final_text = (final.content or "").strip()
        rounds.append({"text": final_text, "tools": []})
        return AgentResult(text=final_text, tool_trace=trace, usage=usage_total, rounds=rounds, model=used_model or final.model)

    def _pool_has_vision(self) -> bool:
        try:
            caps = self.pool.primary_capabilities()
        except Exception:
            return True
        return caps.get("vision") is not False
