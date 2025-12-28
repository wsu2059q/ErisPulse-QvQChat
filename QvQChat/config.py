from typing import Dict, Any, Optional
from ErisPulse import sdk


class QvQConfig:
    """
    配置管理器
    
    负责加载、保存和管理QvQChat的所有配置项。
    使用ErisPulse SDK提供的存储接口持久化配置。
    
    配置简化说明：
    - 只需配置dialogue的API密钥
    - 其他AI（intent、memory等）默认使用dialogue配置
    - 如需使用不同的API密钥，可单独配置
    """

    def __init__(self):
        self.config = self._load_config()
        self.storage = sdk.storage
        self.logger = sdk.logger.get_child("QvQConfig")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载或创建默认配置
        
        Returns:
            Dict[str, Any]: 配置字典
        """
        config = sdk.env.getConfig("QvQChat")
        if not config:
            default_config = self._get_default_config()
            sdk.env.setConfig("QvQChat", default_config)
            return default_config
        return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置

        Returns:
            Dict[str, Any]: 默认配置字典
        """
        return {
            # 基础配置
            "max_history_length": 20,  # 最大会话历史长度
            "memory_cleanup_interval": 86400,  # 记忆清理间隔（秒）
            "enable_vector_search": False,  # 是否启用向量搜索
            "max_memory_tokens": 10000,  # 最大记忆tokens数
            "memory_compression_threshold": 5,  # 记忆压缩阈值

            # 消息限制配置（防止恶意刷屏）
            "max_message_length": 1000,  # 忽略长度超过此值的消息（字符数）
            "rate_limit_tokens": 20000,  # 短时间内允许的最大token数
            "rate_limit_window": 60,  # 时间窗口（秒）
            "ignore_command_messages": True,  # 忽略以指令前缀开头的消息（防止AI响应指令消息）


            # 管理员配置
            "admin": {
                "admins": [],  # 管理员用户ID列表
            },

            # 机器人识别配置
            "bot_nicknames": [],  # 机器人昵称列表（用于文本匹配）
            "bot_ids": [],  # 机器人ID列表（用于@匹配）

            # 窥屏模式配置（默认默默观察，偶尔活跃）
            "stalker_mode": {
                "enabled": True,  # 启用窥屏模式
                "default_probability": 0.03,  # 默认回复概率（3%，很低）
                "mention_probability": 0.8,  # 被@时回复概率（80%）
                "keyword_probability": 0.5,  # 匹配关键词时回复概率（50%）
                "question_probability": 0.4,  # 提问时回复概率（40%）
                "min_messages_between_replies": 15,  # 两次回复之间至少间隔多少条消息
                "max_replies_per_hour": 8,  # 每小时最多回复次数
                "silence_threshold_minutes": 30,  # 群内沉寂阈值（分钟）
            },

            # 对话连续性配置（AI回复后的持续监听）
            "continue_conversation": {
                "enabled": True,  # 启用对话连续性分析
                "max_messages": 3,  # 最多监听多少条后续消息
                "max_duration": 120,  # 监听时长限制（秒）
            },
            
            # 对话AI配置（必需配置，其他AI默认使用此配置）
            "dialogue": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o",  # 使用支持视觉的模型
                "temperature": 0.7,
                "max_tokens": 500,
                "system_prompt": """你是一个普通群友，和大家一起聊天。

【重要】回复策略（像真人一样）：
|- 默认保持安静，不要每条消息都回复
|- 只在真正需要回应的时候说话
|- 简短自然，1-2句话，不要太长
|- 不要使用任何格式（不要加粗、代码、列表、标题等）
|- 用口语化的方式，像真人聊天一样

【什么情况才回复】：
1. 别人直接向你提问
2. 别人@你或叫你的名字
3. 讨论到你熟悉的话题，可以发表看法
4. 看到有趣的笑话，可以配合一下
5. 之前提到的事情有新消息

【绝对不要回复】：
1. 纯打招呼（"大家好"、"在吗"）
2. 表情符号或简单的哈哈、233
3. 没什么实质内容的闲聊
4. 与你无关的话题

记住：你是一个普通群友，不是助手，不要表现得太积极主动。"""
            },

            # 回复判断AI配置（智能判断是否需要回复）
            "reply_judge": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.1,
                "max_tokens": 100,
                "system_prompt": """你是一个普通群友，判断是否需要回复这条消息。

【你的角色】
|- 你是一个普通群友，和大家一起聊天
|- 默认保持安静，只在真正需要的时候回复
|- 不要每条消息都回复

【必须回复的情况】（满足任一）：
1. 有人直接向你提问（"你怎么看？"、"对吧？"）
2. 有人@你或叫你的名字
3. 话题与你直接相关（如讨论你之前提到的事）

【可能回复的情况】（根据概率判断）：
1. 别人分享有趣的事情，可以简单回应（概率低）
2. 讨论你熟悉的话题，可以发表看法（概率低）

【绝对不回复的情况】：
1. 纯打招呼（"大家好"、"在吗"、"有人吗"）
2. 表情符号、"哈哈"、"233"等
3. 简单的"嗯"、"好"、"OK"、"收到"
4. 普通闲聊，没有互动需求
5. 你刚回复过不久，避免刷屏

【判断逻辑】
|- 默认不回复（false）
|- 只有在明确需要回应时才回复（true）
|- 宁可错过，也不要乱回复

输出格式：只回复"true"或"false"，不要解释。"""
            },
            
            # 记忆AI配置（智能提取重要信息）
            "memory": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.3,
                "max_tokens": 1000,
                "system_prompt": "你是一个记忆整理助手，负责总结、压缩和整理对话记忆。提取关键信息，删除冗余内容。"
            },

            # 视觉AI配置（用于分析图片内容）
            "vision": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o",
                "temperature": 0.3,
                "max_tokens": 300,
                "system_prompt": "你是一个图片分析助手。请详细描述图片的内容，包括图片中的物体、文字、场景、人物表情等。如果有多张图片，请分别描述每张图片。"
            },

            # 语音合成配置（用于生成语音）
            "voice": {
                "enabled": False,  # 是否启用语音
                "api_url": "https://api.siliconflow.cn/v1/audio/speech",
                "api_key": "",  # SiliconFlow API密钥
                "model": "FunAudioLLM/CosyVoice2-0.5B",
                "voice": "speech:amer:nu5h6ye36m:ahldwvelhofwpcqcxoky",  # 语音音色
                "speed": 1.0,
                "gain": 0.0,
                "sample_rate": 44100,
                "platforms": ["qq", "onebot11"],  # 支持的平台
            },
            
            # 意图识别AI配置
            "intent": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.1,
                "max_tokens": 500,
                "system_prompt": """你是一个意图识别助手。识别用户意图时，请仔细分析消息内容和上下文。

意图分类（选择最匹配的）：
1. dialogue - 普通对话交流（提问、聊天、日常交流、询问记忆等）
   - 例如："你记得我的生日吗？"、"我之前说过什么？"、"我喜欢什么？"
   - 记忆自然融入对话，不需要特殊意图

2. memory_add - 用户主动要求记住某些信息（用户明确说"记住"、"记下来"）
   - 例如："记住这个"、"这件事要记下来"、"把这条信息保存"

3. memory_delete - 用户主动要求删除记忆
   - 例如："忘记这件事"、"删掉这条记忆"

重要判断规则：
- 【默认】所有普通交流、提问、闲聊都归类为dialogue（包括询问记忆）
- 【严格】只有用户明确说"记住"、"记下来"、"保存"时才归类为memory_add
- 【严格】只有用户明确说"忘记"、"删除"时才归类为memory_delete
- 【严格】不要把"记得"、"记得吗"等询问误判为memory_add或memory_delete

只返回意图类型名称（如dialogue），不要包含其他内容。"""
            },
            
            # 用户个性化配置（运行时生成）
            "users": {},
            
            # 群配置（运行时生成）
            "groups": {}
        }

    def get_memory_mode_description(self, mode: str) -> str:
        """
        获取记忆模式描述
        
        Args:
            mode: 记忆模式（mixed或sender_only）
            
        Returns:
            str: 模式描述文本
        """
        descriptions = {
            "mixed": "混合模式：同时保存发送者个人记忆和群公共记忆",
            "sender_only": "仅发送者模式：只保存发送者的个人记忆"
        }
        return descriptions.get(mode, "未知模式")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项（支持点号分隔的嵌套键）
        
        Args:
            key: 配置键，如"dialogue.model"
            default: 默认值
            
        Returns:
            Any: 配置值或默认值
        """
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置项（支持点号分隔的嵌套键）
        
        Args:
            key: 配置键，如"dialogue.model"
            value: 要设置的值
        """
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        sdk.env.setConfig("QvQChat", self.config)
    
    def get_ai_config(self, ai_type: str) -> Dict[str, Any]:
        """
        获取指定AI的配置

        智能配置合并逻辑：
        - 优先使用AI自身的配置（model、temperature、max_tokens等）
        - 如果AI未配置api_key，复用dialogue的api_key
        - 如果AI未配置base_url，复用dialogue的base_url
        - 其他参数使用AI自身的配置，没有才从dialogue获取

        Args:
            ai_type: AI类型（dialogue、memory、intent等）

        Returns:
            Dict[str, Any]: AI配置字典
        """
        ai_config = self.get(ai_type, {})
        dialogue_config = self.get("dialogue", {})

        # 如果AI未配置api_key，从dialogue获取
        if not ai_config.get("api_key") and dialogue_config.get("api_key"):
            ai_config["api_key"] = dialogue_config["api_key"]

        # 如果AI未配置base_url，从dialogue获取
        if not ai_config.get("base_url") and dialogue_config.get("base_url"):
            ai_config["base_url"] = dialogue_config["base_url"]

        # 为特定AI类型设置合理的默认参数（如果未配置）
        if ai_type == "reply_judge":
            ai_config.setdefault("temperature", 0.1)
            ai_config.setdefault("max_tokens", 100)
        elif ai_type == "vision":
            ai_config.setdefault("temperature", 0.3)
            ai_config.setdefault("max_tokens", 300)
        elif ai_type == "intent":
            ai_config.setdefault("temperature", 0.1)
            ai_config.setdefault("max_tokens", 500)
        elif ai_type == "memory":
            ai_config.setdefault("temperature", 0.3)
            ai_config.setdefault("max_tokens", 1000)

        return ai_config
    
    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户配置（使用storage存储）
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 用户配置字典
        """
        key = f"QvQChat.users.{user_id}"
        user_config = self.storage.get(key, {
            "style": "友好",
            "preferences": {}
        })
        return user_config

    def set_user_config(self, user_id: str, config: Dict[str, Any]) -> None:
        """
        设置用户配置（使用storage存储）
        
        Args:
            user_id: 用户ID
            config: 用户配置字典
        """
        key = f"QvQChat.users.{user_id}"
        self.storage.set(key, config)

    def get_group_config(self, group_id: str) -> Dict[str, Any]:
        """
        获取群配置（使用storage存储）
        
        Args:
            group_id: 群ID
            
        Returns:
            Dict[str, Any]: 群配置字典
        """
        key = f"QvQChat.groups.{group_id}"
        group_config = self.storage.get(key, {
            "system_prompt": "",
            "model_overrides": {},
            "enable_memory": True,
            "memory_mode": "mixed",  # mixed: 混合模式（发送者记忆+群公共记忆）, sender_only: 只记忆发送者
            "enable_ai": True  # 是否启用AI
        })
        return group_config

    def set_group_config(self, group_id: str, config: Dict[str, Any]) -> None:
        """
        设置群配置（使用storage存储）
        
        Args:
            group_id: 群ID
            config: 群配置字典
        """
        key = f"QvQChat.groups.{group_id}"
        self.storage.set(key, config)
    
    def get_effective_system_prompt(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取有效的系统提示词（优先级：群配置 > 用户配置 > 默认配置）
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            str: 系统提示词
        """
        base_prompt = self.get("dialogue.system_prompt", "")
        
        if group_id:
            group_config = self.get_group_config(group_id)
            if group_config.get("system_prompt"):
                return group_config["system_prompt"]
        
        user_config = self.get_user_config(user_id)
        if user_config.get("custom_prompt"):
            return user_config["custom_prompt"]
        
        return base_prompt
    
    def get_effective_model_config(self, ai_type: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取有效的模型配置（优先级：群配置 > 默认配置）
        
        Args:
            ai_type: AI类型
            group_id: 群ID（可选）
            
        Returns:
            Dict[str, Any]: 模型配置字典
        """
        base_config = self.get_ai_config(ai_type).copy()
        
        if group_id:
            group_config = self.get_group_config(group_id)
            overrides = group_config.get("model_overrides", {}).get(ai_type, {})
            base_config.update(overrides)
        
        return base_config
