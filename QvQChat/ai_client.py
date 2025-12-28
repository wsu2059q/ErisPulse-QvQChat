from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError


class QvQAIClient:
    """
    AI客户端封装
    
    封装OpenAI API客户端，提供统一的对话接口。
    """

    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger.get_child("QvQAIClient")
        self.client = None
        self._init_client()

    def _init_client(self):
        """
        初始化OpenAI客户端
        """
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
        """
        更新配置并重新初始化客户端
        
        Args:
            new_config: 新配置字典
        """
        self.config.update(new_config)
        self._init_client()

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数（可选）
            max_tokens: 最大tokens数（可选）
            stream: 是否流式输出（默认False）
            
        Returns:
            str: AI回复内容
            
        Raises:
            RuntimeError: 客户端未初始化
            RateLimitError: API速率限制
            APITimeoutError: 请求超时
            APIError: API错误
        """
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
        """
        测试连接
        
        Returns:
            bool: 连接是否成功
        """
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
    """
    多AI管理器
    
    管理多个AI客户端，提供统一的调用接口。
    支持的AI类型：dialogue、memory、intent、reply_judge、vision
    """
    
    def __init__(self, config_manager, logger):
        self.config = config_manager
        self.logger = logger.get_child("QvQAIManager")
        self.ai_clients: Dict[str, QvQAIClient] = {}
        self._init_ai_clients()
    
    def _init_ai_clients(self):
        """
        初始化所有AI客户端

        智能配置合并：
        - AI可以使用自己的配置（model、api_key等）
        - 如果AI没有api_key，会自动复用dialogue的api_key
        - 只要配置中有有效的api_key，就会初始化该AI客户端

        AI类型说明：
        - dialogue: 对话AI（必需）
        - intent: 意图识别AI（必需）
        - memory: 记忆提取AI（可选）
        - reply_judge: 回复判断AI（可选）
        - vision: 视觉AI（可选）
        """
        ai_types = ["dialogue", "memory", "intent", "reply_judge", "vision"]
        for ai_type in ai_types:
            try:
                ai_config = self.config.get_ai_config(ai_type)

                # 检查是否有有效的api_key配置
                # 可能是AI自己的api_key，也可能是复用dialogue的api_key
                api_key = ai_config.get("api_key", "")
                if api_key and api_key.strip() and api_key != "your-api-key":
                    self.ai_clients[ai_type] = QvQAIClient(ai_config, self.logger)
                else:
                    # 只有dialogue必须有api_key，其他AI可以不配置
                    if ai_type == "dialogue":
                        self.logger.error(f"{ai_type} AI必须配置API密钥，否则无法工作")
                    else:
                        self.logger.info(f"{ai_type} AI未配置（复用dialogue API密钥）")
            except Exception as e:
                self.logger.error(f"初始化{ai_type} AI失败: {e}")
    
    def get_client(self, ai_type: str) -> Optional[QvQAIClient]:
        """
        获取指定AI客户端
        
        Args:
            ai_type: AI类型
            
        Returns:
            Optional[QvQAIClient]: AI客户端实例，不存在则返回None
        """
        return self.ai_clients.get(ai_type)
    
    def reload_client(self, ai_type: str) -> bool:
        """
        重新加载指定AI客户端

        Args:
            ai_type: AI类型

        Returns:
            bool: 是否重新加载成功
        """
        try:
            ai_config = self.config.get_ai_config(ai_type)
            api_key = ai_config.get("api_key", "")
            if api_key and api_key.strip() and api_key != "your-api-key":
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
        """
        对话AI
        
        Args:
            messages: 消息列表
            temperature: 温度参数（可选）
            max_tokens: 最大tokens数（可选）
            
        Returns:
            str: AI回复
        """
        client = self.get_client("dialogue")
        if not client:
            raise RuntimeError("对话AI未配置")
        return await client.chat(messages, temperature, max_tokens)
    
    async def memory_process(self, prompt: str) -> str:
        """
        记忆处理AI
        
        Args:
            prompt: 提示文本
            
        Returns:
            str: 处理结果
        """
        client = self.get_client("memory")
        if not client:
            raise RuntimeError("记忆AI未配置")
        return await client.chat([{"role": "user", "content": prompt}], temperature=0.3)

    async def identify_intent(self, user_input: str) -> str:
        """
        意图识别
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: 意图类型
        """
        client = self.get_client("intent")
        if not client:
            return "dialogue"  # 默认为对话
        return await client.chat([{"role": "user", "content": user_input}], temperature=0.1)

    async def analyze_image(self, image_url: str, user_text: str = "") -> str:
        """
        视觉AI分析图片
        
        Args:
            image_url: 图片URL
            user_text: 用户文本（可选）
            
        Returns:
            str: 图片描述
        """
        client = self.get_client("vision")
        if not client:
            # 如果没有配置 vision AI，返回空，让系统使用多模态模式
            return ""

        try:
            prompt = "请详细描述这张图片的内容，包括图片中的物体、文字、场景、人物表情等。"
            if user_text:
                prompt += f"\n\n用户的描述或问题：{user_text}"

            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ]

            result = await client.chat(messages, temperature=0.3)
            self.logger.debug(f"视觉AI分析图片成功: {result[:100]}...")
            return result
        except Exception as e:
            self.logger.warning(f"视觉AI分析图片失败: {e}")
            return ""

    async def should_reply(self, recent_messages: List[Dict[str, str]], current_message: str, bot_name: str = "", reply_keywords: List[str] = None) -> bool:
        """
        AI判断是否需要回复
        
        Args:
            recent_messages: 最近的消息历史
            current_message: 当前消息
            bot_name: 机器人名字
            reply_keywords: 回复关键词列表
            
        Returns:
            bool: 是否应该回复
        """
        client = self.get_client("reply_judge")
        if not client:
            # 如果没有配置reply_judge，默认不回复（除非匹配关键词）
            if reply_keywords:
                for keyword in reply_keywords:
                    if keyword in current_message:
                        return True
            return False

        try:
            # 构建对话上下文
            context = []
            for msg in recent_messages[-8:]:  # 最近8条消息
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context.append(f"{role}: {content}")

            context_str = "\n".join(context)

            prompt = f"""你正在群聊中参与互动。根据最近的对话历史，判断是否需要回复这条消息。

【角色定位】
|- 你是一个普通群友，不是机器人助手
|- 除非有明显需要回应的情况，否则保持安静
|- 不需要每条消息都回复
|- 回复要自然、随意，像真人一样

【最近对话历史】
{context_str}

【用户最新消息】
{current_message}
{f"【有人提到了你（{bot_name}）】" if bot_name and bot_name in current_message else ""}

【回复判断标准】（满足以下条件才回复）：
1. 用户在向你提问（直接或间接）
2. 用户提到你的名字，需要回应
3. 对话正在讨论你感兴趣或了解的话题
4. 适当的幽默回应可以活跃气氛
5. 之前提到的事情有更新或结论

【不回复的情况]：
1. 普通打招呼（如:"在吗"、"大家好"）
2. 表情符号、纯表情回复
3. 简单的"好的"、"嗯"、"收到"
4. 与你无关的话题讨论
5. 连续短时间内多次回复会显得不自然

【输出格式】
只回答"回复"或"不回复"，不要解释。

是否需要回复："""

            result = await client.chat([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=10)
            should = "不回复" not in result
            self.logger.debug(f"AI回复判断: {should} (判断结果: {result.strip()})")
            return should
        except Exception as e:
            self.logger.warning(f"回复判断失败: {e}，使用默认判断")
            return False

    async def should_continue_conversation(self, recent_messages: List[Dict[str, str]], bot_name: str = "") -> bool:
        """
        分析对话是否应该继续（对话连续性分析）
        
        分析AI回复后的3条消息，判断是否包含回复或提到与AI相关的内容。
        如果有，则可以继续一轮对话，直到没有相关话题。
        
        Args:
            recent_messages: 最近的消息历史（包括AI的回复）
            bot_name: 机器人名字
            
        Returns:
            bool: 是否应该继续对话
        """
        client = self.get_client("reply_judge")
        if not client:
            # 如果没有配置reply_judge，默认不继续
            return False

        try:
            # 获取最近的消息（最多8条，包括AI的回复）
            context = []
            for msg in recent_messages[-8:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                context.append(f"{role}: {content}")

            context_str = "\n".join(context)

            prompt = f"""你正在群聊中，刚刚发了一条消息。请分析后续的消息，判断是否需要继续回复。

【角色定位】
|- 你是一个普通群友，正在参与对话
|- 避免连续过多回复，显得不自然
|- 只有当话题真正围绕你时才继续

【最近对话历史】
{context_str}

{f"【你的名字】{bot_name}" if bot_name else ""}

【判断标准】
只有满足以下条件时，才继续回复：
1. 后续消息中有人@你或提到你的名字
2. 后续消息中有人直接回复你（如"对啊"、"是啊"、"确实"等）
3. 后续消息中有人针对你提出的问题或观点进行讨论
4. 话题明确围绕你刚才的内容展开

【不应该继续的情况】
1. 后续消息只是普通聊天，与你无关
2. 对话已经转移到其他话题
3. 有人只是随意的附和，不需要回应
4. 你已经连续回复了多次

【输出格式】
只回答"继续"或"停止"，不要解释。

是否继续对话："""

            result = await client.chat([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=10)
            should_continue = "继续" in result
            self.logger.debug(f"对话连续性分析: {should_continue} (判断结果: {result.strip()})")
            return should_continue
        except Exception as e:
            self.logger.warning(f"对话连续性分析失败: {e}，默认不继续")
            return False

    async def test_all_connections(self) -> Dict[str, bool]:
        """
        测试所有AI连接
        
        Returns:
            Dict[str, bool]: 各AI连接状态
        """
        results = {}
        for ai_type, client in self.ai_clients.items():
            results[ai_type] = await client.test_connection()
        return results
