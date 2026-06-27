"""
AI 执行引擎

基于行为管理器和模型池执行 AI 调用。
支持多模型故障转移：行为分配的模型按顺序尝试，失败则切换下一个。
"""

import base64
import mimetypes
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

from .client import AIClient


class AIEngine:
    """
    AI 执行引擎

    核心方法 execute_behavior() 按以下流程工作：
    1. 从行为管理器获取行为配置（提示词、参数）
    2. 从行为管理器获取分配的模型列表
    3. 按顺序尝试每个模型，成功则返回
    4. 全部失败则抛出异常

    提供兼容方法（dialogue/intent/memory/vision/reply_judge）
    供现有调用方使用。
    """

    def __init__(self, model_pool, behavior_manager, logger):
        self.model_pool = model_pool
        self.behavior_manager = behavior_manager
        self.logger = logger.get_child("AIEngine")
        self._clients: Dict[str, AIClient] = {}  # model_id -> client

    def _get_client(self, model_config: Dict[str, Any]) -> AIClient:
        """获取或创建模型客户端（带缓存）"""
        model_id = model_config.get("_model_id", model_config.get("model", ""))
        if model_id not in self._clients:
            self._clients[model_id] = AIClient(model_config, self.logger)
        return self._clients[model_id]

    def reload_clients(self) -> None:
        """清除所有缓存的客户端（配置变更后调用）"""
        self._clients.clear()
        self.logger.info("已清除所有AI客户端缓存")

    def reload_behavior(self, behavior_id: str) -> None:
        """清除指定行为相关模型的客户端缓存"""
        behavior = self.behavior_manager.get_behavior(behavior_id)
        if not behavior:
            return
        for model_id in behavior.get("models", []):
            self._clients.pop(model_id, None)

    def is_available(self, behavior_id: str) -> bool:
        """检查行为是否可用"""
        return self.behavior_manager.is_behavior_available(behavior_id)

    async def execute_behavior(
        self,
        behavior_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> Any:
        """
        执行行为

        按行为分配的模型顺序尝试，失败则切换下一个模型。

        Args:
            behavior_id: 行为ID
            messages: 消息列表
            tools: 工具定义（可选）
            **kwargs: 额外参数覆盖

        Returns:
            AI回复内容

        Raises:
            RuntimeError: 行为不可用或所有模型均失败
        """
        behavior = self.behavior_manager.get_behavior(behavior_id)
        if not behavior:
            raise RuntimeError(f"行为 '{behavior_id}' 不存在")

        if not behavior.get("enabled", True):
            raise RuntimeError(f"行为 '{behavior_id}' 已禁用")

        models = self.behavior_manager.get_behavior_models(behavior_id)
        if not models:
            raise RuntimeError(f"行为 '{behavior_id}' 未分配模型")

        # 行为级参数
        prompt = behavior.get("system_prompt", "")
        params = self.behavior_manager.get_behavior_params(behavior_id)
        temperature = kwargs.pop("temperature", params.get("temperature"))
        max_tokens = kwargs.pop("max_tokens", params.get("max_tokens"))

        # 按顺序尝试每个模型
        errors = []
        for idx, model_config in enumerate(models):
            model_name = model_config.get("_model_name", model_config.get("model", ""))
            fallback_note = f" (备用{idx})" if idx > 0 else ""
            self.logger.debug(
                f"执行行为[{behavior_id}] -> 模型[{model_name}]{fallback_note}"
            )
            try:
                client = self._get_client(model_config)
                result = await client.chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    system_prompt=prompt if prompt else None,
                    **kwargs,
                )
                return result
            except Exception as e:
                if idx < len(models) - 1:
                    self.logger.warning(
                        f"行为[{behavior_id}] 模型[{model_name}]失败，切换备用: {e}"
                    )
                else:
                    self.logger.error(
                        f"行为[{behavior_id}] 模型[{model_name}]失败(无更多备用): {e}"
                    )
                errors.append(f"{model_name}: {e}")
                continue

        raise RuntimeError(f"行为[{behavior_id}] 所有模型均失败 - {'; '.join(errors)}")

    # ==================== 兼容方法 ====================

    async def dialogue(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """对话行为"""
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        result = await self.execute_behavior(
            "dialogue", messages, tools=tools, **kwargs
        )
        return result if isinstance(result, str) else str(result)

    async def identify_intent(self, user_input: str) -> str:
        """意图识别行为"""
        try:
            result = await self.execute_behavior(
                "intent",
                [{"role": "user", "content": user_input}],
            )
            return result.strip() if isinstance(result, str) else "dialogue"
        except Exception:
            return "dialogue"

    async def memory_process(self, prompt: str) -> str:
        """记忆提取行为"""
        result = await self.execute_behavior(
            "memory",
            [{"role": "user", "content": prompt}],
        )
        return result if isinstance(result, str) else str(result)

    async def _ensure_data_url(self, url: str) -> str:
        """
        将图片URL转为 base64 data URL（某些VLM仅接受此格式）

        若已是 data: URL 则直接返回；file:// 本地路径则读取转码；
        http(s) URL 则尝试下载转码；失败时返回原 URL 作兜底。
        """
        if url.startswith("data:"):
            return url

        # 本地文件路径
        if url.startswith("file://"):
            try:
                path = url[7:]
                with open(path, "rb") as f:
                    raw = f.read()
                mime = mimetypes.guess_type(path)[0] or "image/png"
                b64 = base64.b64encode(raw).decode()
                return f"data:{mime};base64,{b64}"
            except Exception as e:
                self.logger.debug(f"读取本地图片失败 {url}: {e}")
                return url

        # HTTP(S) 远程 URL
        if url.startswith(("http://", "https://")) and httpx is not None:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                mime = resp.headers.get("content-type", "image/png")
                mime = mime.split(";")[0].strip()
                b64 = base64.b64encode(resp.content).decode()
                return f"data:{mime};base64,{b64}"
            except Exception as e:
                self.logger.debug(f"下载远程图片失败 {url}: {e}")
                return url

        return url

    async def analyze_image(self, image_url: str, user_text: str = "") -> str:
        """图片分析行为"""
        try:
            # 转为 base64 data URL，确保 VLM 可以访问
            processed_url = await self._ensure_data_url(image_url)
            if processed_url != image_url:
                self.logger.debug(
                    f"图片URL已转换为data URL (长度: {len(processed_url)})"
                )

            prompt = "请详细描述这张图片的内容。"
            if user_text:
                prompt += f"\n\n用户的问题：{user_text}"
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": processed_url}},
                    ],
                }
            ]
            result = await self.execute_behavior("vision", messages)
            return result if isinstance(result, str) else ""
        except Exception as e:
            self.logger.warning(f"图片分析失败: {e}")
            return ""

    async def should_reply(
        self,
        recent_messages: List[Dict[str, str]],
        current_message: str,
        bot_name: str = "",
    ) -> bool:
        """回复判断行为"""
        try:
            context = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in recent_messages[-8:]
            )
            prompt = (
                f"你正在群聊中。根据对话历史判断是否需要回复。\n\n"
                f"【对话历史】\n{context}\n\n"
                f"【最新消息】{current_message}\n"
                + (
                    f"【有人提到你({bot_name})】\n"
                    if bot_name and bot_name in current_message
                    else ""
                )
                + f'\n只回答"回复"或"不回复"。'
            )
            result = await self.execute_behavior(
                "reply_judge",
                [{"role": "user", "content": prompt}],
            )
            return "不回复" not in (result if isinstance(result, str) else "")
        except Exception:
            return False

    async def should_continue(
        self,
        recent_messages: List[Dict[str, str]],
        bot_name: str = "",
    ) -> bool:
        """对话连续性判断"""
        try:
            context = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in recent_messages[-8:]
            )
            prompt = (
                f"你刚在群聊发了一条消息，分析后续消息判断是否继续回复。\n\n"
                f"【对话历史】\n{context}\n\n"
                + (f"【你的名字】{bot_name}\n" if bot_name else "")
                + f'\n只回答"继续"或"停止"。'
            )
            result = await self.execute_behavior(
                "reply_judge",
                [{"role": "user", "content": prompt}],
            )
            return "继续" in (result if isinstance(result, str) else "")
        except Exception:
            return False

    async def test_model(self, model_id: str) -> bool:
        """测试指定模型的连接"""
        config = self.model_pool.get_client_config(model_id)
        if not config:
            return False
        config["_model_id"] = model_id
        client = self._get_client(config)
        return await client.test_connection()

    def get_behavior_status(self) -> Dict[str, bool]:
        """获取所有行为的可用状态"""
        result = {}
        for b in self.behavior_manager.list_behaviors():
            result[b["id"]] = self.is_available(b["id"])
        return result
