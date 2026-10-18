from __future__ import annotations

import asyncio
import json
import re

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    AsyncOpenAI,
    RateLimitError,
)

from .base import ChatRequest, ChatResponse, EngineError, ToolCall
from .. import texts

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class _ThinkDeltaFilter:
    """流式增量中抑制 <think>…</think> 段落（含标签被分片的情况）。"""

    _OPEN = "<think>"
    _CLOSE = "</think>"

    def __init__(self):
        self._buf = ""
        self._inside = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._inside:
                end = self._buf.find(self._CLOSE)
                if end == -1:
                    self._buf = self._buf[-len(self._CLOSE):]
                    break
                self._buf = self._buf[end + len(self._CLOSE):]
                self._inside = False
            else:
                start = self._buf.find(self._OPEN)
                if start == -1:
                    keep = 0
                    for n in range(len(self._OPEN) - 1, 0, -1):
                        if self._buf.endswith(self._OPEN[:n]):
                            keep = n
                            break
                    emit = self._buf[: len(self._buf) - keep] if keep else self._buf
                    if emit:
                        out.append(emit)
                    self._buf = self._buf[len(emit):] if keep else ""
                    break
                out.append(self._buf[:start])
                self._buf = self._buf[start + len(self._OPEN):]
                self._inside = True
        return "".join(out)


class OpenAIEngine:
    def __init__(self):
        self._clients: dict[tuple, AsyncOpenAI] = {}
        self.retry_delays: tuple = (1.0, 2.0, 4.0)

    async def _create_with_retry(self, client, kwargs: dict):
        delays = self.retry_delays
        attempt = 0
        while True:
            try:
                return await client.chat.completions.create(**kwargs)
            except RateLimitError:
                reason = "rate limited"
            except APIConnectionError as e:
                reason = f"connection error: {e}"
            except APIStatusError as e:
                status = getattr(e, "status_code", 0) or 0
                if status < 500:
                    raise
                reason = f"HTTP {status}"
            if attempt >= len(delays):
                raise EngineError(texts.t("engine_retry_exhausted", reason=reason, attempt=attempt))
            await asyncio.sleep(delays[attempt])
            attempt += 1

    def client_for(self, base_url: str, api_key: str) -> AsyncOpenAI:
        key = (base_url or "", api_key or "")
        if key not in self._clients:
            self._clients[key] = AsyncOpenAI(
                base_url=base_url or None,
                api_key=api_key or "none",
            )
        return self._clients[key]

    @staticmethod
    def merge_system(messages: list) -> list:
        merged: list = []
        for msg in messages:
            if msg.get("role") == "system" and merged and merged[-1].get("role") == "system":
                merged[-1] = dict(merged[-1])
                merged[-1]["content"] = merged[-1]["content"] + "\n\n" + str(msg.get("content") or "")
            else:
                merged.append(msg)
        return merged

    @staticmethod
    def _extract(message) -> tuple[str, list[ToolCall]]:
        content = getattr(message, "content", None) or ""
        if not isinstance(content, str):
            try:
                content = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part)
                    for part in content
                )
            except TypeError:
                content = str(content)
        reasoning = (
            getattr(message, "reasoning_content", None)
            or getattr(message, "reasoning", None)
            or ""
        )
        text = _THINK_RE.sub("", str(content)).strip()
        if not text and reasoning:
            text = str(reasoning).strip()
        tool_calls: list[ToolCall] = []
        if getattr(message, "tool_calls", None):
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCall(
                        call_id=tc.id or "",
                        name=tc.function.name,
                        arguments=args if isinstance(args, dict) else {},
                    )
                )
        return text, tool_calls

    @staticmethod
    def _has_image_parts(messages: list) -> bool:
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, list) and any(
                isinstance(part, dict) and part.get("type") == "image_url" for part in content
            ):
                return True
        return False

    @staticmethod
    def _without_images(messages: list) -> list:
        cleaned = []
        for message in messages:
            if not isinstance(message, dict):
                cleaned.append(message)
                continue
            content = message.get("content")
            if isinstance(content, list):
                text = " ".join(
                    str(part.get("text") or "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ).strip()
                cleaned.append({**message, "content": text})
            else:
                cleaned.append(message)
        return cleaned

    async def _stream_chat(self, client, kwargs: dict, on_delta, on_reset=None):
        """流式请求：content 增量经 on_delta 回调，tool_calls 增量拼装为完整调用。
        finish_reason=length 时自动续写（最多 2 次）；工具参数被截断则清屏加大预算重试。"""
        filter_ = _ThinkDeltaFilter()
        texts: list[str] = []
        tools_acc: dict[int, dict] = {}
        model = str(kwargs.get("model") or "")
        usage_obj = None
        finish = ""

        async def consume(stream) -> None:
            nonlocal model, usage_obj, finish
            try:
                async for chunk in stream:
                    if getattr(chunk, "model", None):
                        model = chunk.model
                    if getattr(chunk, "usage", None) is not None:
                        usage_obj = chunk.usage
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    if getattr(choices[0], "finish_reason", None):
                        finish = str(choices[0].finish_reason)
                    delta = choices[0].delta
                    piece = getattr(delta, "content", None)
                    if piece:
                        out = filter_.feed(piece)
                        if out:
                            texts.append(out)
                            try:
                                result = on_delta(out)
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                pass
                    for tcd in getattr(delta, "tool_calls", None) or []:
                        index = tcd.index if tcd.index is not None else 0
                        slot = tools_acc.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        if getattr(tcd, "id", None):
                            slot["id"] = tcd.id
                        fn = getattr(tcd, "function", None)
                        if fn is not None:
                            if getattr(fn, "name", None):
                                slot["name"] = fn.name if not slot["name"] else slot["name"] + fn.name
                            if getattr(fn, "arguments", None):
                                slot["arguments"] += fn.arguments
            finally:
                close = getattr(stream, "close", None)
                if close is not None:
                    try:
                        await close()
                    except Exception:
                        pass

        async def run_stream(kw) -> None:
            stream = await client.chat.completions.create(**kw)
            await consume(stream)

        await run_stream(kwargs)
        # 工具调用参数被截断：清空已输出内容，加大预算整轮重试
        if finish == "length" and tools_acc:
            if on_reset is not None:
                try:
                    result = on_reset()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass
            texts.clear()
            tools_acc.clear()
            retry_kwargs = dict(kwargs)
            retry_kwargs["max_tokens"] = min(int(kwargs.get("max_tokens") or 2048) * 4, 65536)
            await run_stream(retry_kwargs)
        # 纯文本被截断：带上下文续写，保证回复完整
        rounds = 0
        while finish == "length" and not tools_acc and rounds < 2:
            rounds += 1
            cont_kwargs = dict(kwargs)
            cont_kwargs["messages"] = list(kwargs["messages"]) + [
                {"role": "assistant", "content": "".join(texts)},
                {"role": "user", "content": texts.t("engine_continue")},
            ]
            await run_stream(cont_kwargs)
        text = _THINK_RE.sub("", "".join(texts)).strip()
        tool_calls: list[ToolCall] = []
        for slot in (tools_acc[i] for i in sorted(tools_acc)):
            try:
                args = json.loads(slot["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    call_id=slot["id"],
                    name=slot["name"],
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        usage: dict = {}
        if usage_obj is not None:
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage_obj, "total_tokens", 0) or 0,
            }
        return ChatResponse(content=text or None, tool_calls=tool_calls, model=model, usage=usage)

    async def chat(self, base_url: str, api_key: str, request: ChatRequest, on_delta=None, on_reset=None) -> ChatResponse:
        client = self.client_for(base_url, api_key)
        kwargs: dict = {"model": request.model, "messages": self.merge_system(request.messages)}
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens
        if request.tools:
            kwargs["tools"] = request.tools
            kwargs["tool_choice"] = "auto"
        streaming = on_delta is not None
        if streaming:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}
        try:
            try:
                if streaming:
                    try:
                        resp = await self._stream_chat(client, kwargs, on_delta, on_reset=on_reset)
                    except APIStatusError as e:
                        # 部分网关不支持 stream_options，退回普通流式
                        if (getattr(e, "status_code", 0) or 0) == 400 and kwargs.pop("stream_options", None):
                            resp = await self._stream_chat(client, kwargs, on_delta)
                        else:
                            raise
                else:
                    resp = await self._create_with_retry(client, kwargs)
            except APIStatusError as e:
                status = getattr(e, "status_code", 0) or 0
                if status in (400, 404, 415, 422) and self._has_image_parts(kwargs["messages"]):
                    kwargs["messages"] = self._without_images(kwargs["messages"])
                    if streaming:
                        if on_reset is not None:
                            try:
                                result = on_reset()
                                if asyncio.iscoroutine(result):
                                    await result
                            except Exception:
                                pass
                        resp = await self._stream_chat(client, kwargs, on_delta, on_reset=on_reset)
                    else:
                        resp = await self._create_with_retry(client, kwargs)
                else:
                    raise
            if streaming:
                return resp
            choice = resp.choices[0] if getattr(resp, "choices", None) else None
            message = choice.message if choice else None
            text, tool_calls = self._extract(message) if message is not None else ("", [])
            finish_reason = str(getattr(choice, "finish_reason", "") or "")
            if finish_reason == "length" and not tool_calls:
                # 非流式被截断：加大预算重试一次（无论已产出多少文本）
                retry_kwargs = dict(kwargs)
                retry_kwargs["max_tokens"] = min(int(kwargs.get("max_tokens") or 2048) * 4, 65536)
                resp = await client.chat.completions.create(**retry_kwargs)
                choice = resp.choices[0] if getattr(resp, "choices", None) else None
                message = choice.message if choice else None
                text, tool_calls = self._extract(message) if message is not None else ("", [])
        except (APIConnectionError, AuthenticationError, RateLimitError, APIStatusError) as e:
            raise EngineError(str(e)) from e
        except EngineError:
            raise
        except Exception as e:
            raise EngineError(texts.t("engine_call_failed", error=str(e))) from e
        usage: dict = {}
        raw_usage = getattr(resp, "usage", None)
        if raw_usage is not None:
            usage = {
                "prompt_tokens": getattr(raw_usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(raw_usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(raw_usage, "total_tokens", 0) or 0,
            }
        return ChatResponse(
            content=text or None,
            tool_calls=tool_calls,
            model=getattr(resp, "model", "") or "",
            usage=usage,
        )
