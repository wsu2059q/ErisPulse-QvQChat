"""
AI 客户端封装

封装单个 AI 模型的 API 调用，支持文本对话、图片识别和工具调用。
"""

import asyncio
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

        Args:
            messages: 消息列表
            temperature: 温度覆盖
            max_tokens: 最大token覆盖
            timeout: 超时秒数
            tools: 工具定义列表
            model: 模型名覆盖
            system_prompt: 系统提示词覆盖

        Returns:
            AI回复字符串，或包含 tool_calls 的 message 对象
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

        use_messages = messages
        if system_prompt:
            use_messages = [{"role": "system", "content": system_prompt}] + [
                m for m in messages if m.get("role") != "system"
            ]

        try:
            kwargs: Dict[str, Any] = {
                "model": use_model,
                "messages": use_messages,
                "temperature": use_temp,
                "max_tokens": use_max,
            }
            if tools:
                kwargs["tools"] = tools

            response = await asyncio.wait_for(
                self.client.chat.completions.create(**kwargs),
                timeout=timeout,
            )

            message = response.choices[0].message

            # 处理 tool_calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                return message

            return message.content

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
