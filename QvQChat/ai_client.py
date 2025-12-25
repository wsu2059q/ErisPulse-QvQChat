import asyncio
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError


class QvQAIClient:
    """AI客户端封装"""

    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger.get_child("QvQAIClient")
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化OpenAI客户端"""
        try:
            self.client = AsyncOpenAI(
                base_url=self.config.get("base_url", "https://api.openai.com/v1"),
                api_key=self.config.get("api_key", "")
            )
            self.logger.info(f"AI客户端初始化成功，模型: {self.config.get('model', 'unknown')}")
        except Exception as e:
            self.logger.error(f"AI客户端初始化失败: {e}")
            self.client = None

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """更新配置"""
        self.config.update(new_config)
        self._init_client()

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """发送聊天请求"""
        if not self.client:
            raise RuntimeError("AI客户端未初始化，请检查API密钥配置")

        try:
            response = await self.client.chat.completions.create(
                model=self.config.get("model", "gpt-3.5-turbo"),
                messages=messages,
                temperature=temperature if temperature is not None else self.config.get("temperature", 0.7),
                max_tokens=max_tokens if max_tokens is not None else self.config.get("max_tokens", 2000),
                stream=stream
            )

            if stream:
                return response
            else:
                return response.choices[0].message.content

        except RateLimitError as e:
            self.logger.warning(f"API速率限制: {e}")
            raise
        except APITimeoutError as e:
            self.logger.error(f"API请求超时: {e}")
            raise
        except APIError as e:
            self.logger.error(f"API错误: {e}")
            raise
        except Exception as e:
            self.logger.error(f"AI请求失败: {e}")
            raise

    async def test_connection(self) -> bool:
        """测试连接"""
        try:
            response = await self.chat(
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            return bool(response)
        except Exception as e:
            self.logger.error(f"连接测试失败: {e}")
            return False


class QvQAIManager:
    """多AI管理器"""
    
    def __init__(self, config_manager, logger):
        self.config = config_manager
        self.logger = logger.get_child("QvQAIManager")
        self.ai_clients: Dict[str, QvQAIClient] = {}
        self._init_ai_clients()
    
    def _init_ai_clients(self):
        """初始化所有AI客户端"""
        ai_types = ["dialogue", "memory", "query", "intent", "vision", "reply_judge"]
        for ai_type in ai_types:
            try:
                ai_config = self.config.get_ai_config(ai_type)
                if ai_config.get("api_key"):
                    self.ai_clients[ai_type] = QvQAIClient(ai_config, self.logger)
                else:
                    self.logger.warning(f"{ai_type} AI未配置API密钥")
            except Exception as e:
                self.logger.error(f"初始化{ai_type} AI失败: {e}")
    
    def get_client(self, ai_type: str) -> Optional[QvQAIClient]:
        """获取指定AI客户端"""
        return self.ai_clients.get(ai_type)
    
    def reload_client(self, ai_type: str) -> bool:
        """重新加载指定AI客户端"""
        try:
            ai_config = self.config.get_ai_config(ai_type)
            if ai_config.get("api_key"):
                self.ai_clients[ai_type] = QvQAIClient(ai_config, self.logger)
                return True
            return False
        except Exception as e:
            self.logger.error(f"重新加载{ai_type} AI失败: {e}")
            return False
    
    async def dialogue(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """对话AI"""
        client = self.get_client("dialogue")
        if not client:
            raise RuntimeError("对话AI未配置")
        return await client.chat(messages, temperature, max_tokens)
    
    async def memory_process(self, prompt: str) -> str:
        """记忆处理AI"""
        client = self.get_client("memory")
        if not client:
            raise RuntimeError("记忆AI未配置")
        return await client.chat([{"role": "user", "content": prompt}], temperature=0.3)
    
    async def query(self, prompt: str) -> str:
        """查询AI"""
        client = self.get_client("query")
        if not client:
            raise RuntimeError("查询AI未配置")
        return await client.chat([{"role": "user", "content": prompt}], temperature=0.3)
    
    async def identify_intent(self, user_input: str) -> str:
        """意图识别"""
        client = self.get_client("intent")
        if not client:
            return "dialogue"  # 默认为对话
        return await client.chat([{"role": "user", "content": user_input}], temperature=0.1)

    async def describe_image(self, image_url: str, prompt: str = "简要描述这张图片") -> str:
        """图片描述（视觉AI）"""
        client = self.get_client("vision")
        if not client:
            raise RuntimeError("视觉AI未配置")
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]
        return await client.chat(messages, temperature=0.3, max_tokens=300)

    async def should_reply(self, recent_messages: List[Dict[str, str]], current_message: str, bot_name: str = "") -> bool:
        """智能判断是否需要回复"""
        client = self.get_client("reply_judge")
        if not client:
            # 如果没有配置reply_judge，使用简单判断
            # 问题、@、请求、情绪强烈
            question_indicators = ["吗", "呢", "？", "?", "吗？", "？", "怎么", "什么", "为什么"]
            for indicator in question_indicators:
                if indicator in current_message:
                    return True
            # 简短回应不回复
            if len(current_message) < 3:
                return False
            # 随机回复
            import random
            return random.random() < 0.3

        try:
            # 构建对话上下文
            context = []
            for msg in recent_messages[-5:]:  # 最近5条消息
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context.append(f"{role}: {content}")

            context_str = "\n".join(context)

            prompt = f"""以下是最近的对话历史：
{context_str}

用户的最新消息：{current_message}
机器人名字：{bot_name}

判断是否需要AI回复（true/false）："""

            result = await client.chat([{"role": "user", "content": prompt}], temperature=0.1, max_tokens=10)
            return "true" in result.lower()
        except Exception as e:
            self.logger.warning(f"回复判断失败: {e}，使用默认判断")
            # 默认策略：有问号或超过5字就回复
            return "？" in current_message or "?" in current_message or len(current_message) >= 5

    async def test_all_connections(self) -> Dict[str, bool]:
        """测试所有AI连接"""
        results = {}
        for ai_type, client in self.ai_clients.items():
            results[ai_type] = await client.test_connection()
        return results
