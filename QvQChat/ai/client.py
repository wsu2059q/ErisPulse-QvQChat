"""
AI 客户端封装

封装单个 AI 模型的 API 调用，支持文本对话、图片识别和工具调用。
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError


class AIClient:
    """
    单模型 AI 客户端

    封装 OpenAI 兼容 API，提供统一的调用接口。
    支持系统提示词覆盖、模型覆盖、工具调用。
    """

    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger.get_child("AIClient")
        self.client: Optional[AsyncOpenAI] = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            self.client = AsyncOpenAI(
                base_url=self.config.get("base_url", "https://api.openai.com/v1"),
                api_key=self.config.get("api_key", ""),
            )
        except Exception as e:
            self.logger.error(f"AI客户端初始化失败: {e}")
            self.client = None

    def update_config(self, new_config: Dict[str, Any]) -> None:
        self.config.update(new_config)
        self._init_client()

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Any:
        """
        发送聊天请求

        连续 system 消息会合并为单条（部分 API 如 SiliconFlow 仅允许一条）。

        :param messages: OpenAI 格式消息列表
        :param temperature: [float] 采样温度 (默认: 配置值 0.7)
        :param max_tokens: [int] 补全上限 (默认: 配置值 2000)
        :param timeout: [float] 请求超时秒数 (默认: 60)
        :param tools: [List[Dict]] OpenAI 格式工具定义
        :param model: [str] 模型名覆盖 (默认: 配置值)
        :param system_prompt: [str] 系统提示词，非空时插入消息首部
        :return: str AI 回复文本（空回复归一化为空串）；模型返回 tool_calls 时
            返回原始 message 对象，由调用方执行工具
        :raises APITimeoutError: 请求超时
        :raises RateLimitError: 触发 API 限流
        :raises APIError: 其他 API 错误
        """
        if not self.client:
            raise RuntimeError("AI客户端未初始化")

        use_model = model or self.config.get("model", "gpt-3.5-turbo")
        use_temp = (
            temperature
            if temperature is not None
            else self.config.get("temperature", 0.7)
        )
        use_max = (
            max_tokens
            if max_tokens is not None
            else self.config.get("max_tokens", 2000)
        )

        use_messages = list(messages)
        if system_prompt:
            use_messages.insert(0, {"role": "system", "content": system_prompt})

        # 合并连续的 system 消息为单条（部分 API 如 SiliconFlow 仅允许一条）
        merged: List[Dict[str, Any]] = []
        system_parts: List[str] = []
        for msg in use_messages:
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if content:
                    system_parts.append(content)
            else:
                if system_parts:
                    merged.append({
                        "role": "system",
                        "content": "\n\n".join(system_parts),
                    })
                    system_parts = []
                merged.append(msg)
        # 末尾的 system（异常情况，但兜底处理）
        if system_parts:
            merged.append({"role": "system", "content": "\n\n".join(system_parts)})
        use_messages = merged

        try:
            kwargs: Dict[str, Any] = {
                "model": use_model,
                "messages": use_messages,
                "temperature": use_temp,
                "max_tokens": use_max,
            }
            if tools:
                kwargs["tools"] = tools

            # 输出完整 system 提示词（调试用）
            sys_msgs = [m for m in use_messages if m.get("role") == "system"]
            for i, sm in enumerate(sys_msgs):
                self.logger.debug(
                    f"--- system[{i}] ({len(sm['content'])}字符) ---\n{sm['content'][:500]}"
                )

            # 输出最后一条 user 消息（调试用，确认上下文是否真的传给模型）
            user_msgs = [m for m in use_messages if m.get("role") == "user"]
            if user_msgs:
                um = user_msgs[-1]
                ucontent = um.get("content", "")
                if isinstance(ucontent, list):
                    ucontent = json.dumps(ucontent, ensure_ascii=False)
                self.logger.debug(
                    f"--- user[-1] ({len(ucontent)}字符) ---\n{ucontent[:500]}"
                )

            response = await asyncio.wait_for(
                self.client.chat.completions.create(**kwargs),
                timeout=timeout,
            )

            message = response.choices[0].message

            # 含 tool_calls 时返回原始 message 对象，由调用方执行工具
            if hasattr(message, "tool_calls") and message.tool_calls:
                return message

            # content 为 None 的情况：推理模型耗尽补全额度、响应截断等，归一化为空串
            content = message.content or ""
            if not content:
                finish = getattr(response.choices[0], "finish_reason", None)
                self.logger.warning(
                    f"AI返回空回复 - 模型: {use_model} (finish_reason={finish})"
                )
            return content

        except asyncio.TimeoutError:
            raise APITimeoutError(f"请求超时({timeout}秒)")
        except (RateLimitError, APITimeoutError, APIError):
            raise
        except Exception as e:
            self.logger.error(f"AI请求失败 - 模型: {use_model}: {e}")
            raise

    async def test_connection(self) -> bool:
        try:
            resp = await self.chat(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
                timeout=15,
            )
            return bool(resp)
        except Exception:
            return False
