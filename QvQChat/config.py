from typing import Dict, Any, Optional
from ErisPulse import sdk


class QvQConfig:
    """配置管理器"""

    def __init__(self):
        self.config = self._load_config()
        self.storage = sdk.storage
        self.logger = sdk.logger.get_child("QvQConfig")
    
    def _load_config(self) -> Dict[str, Any]:
        """加载或创建默认配置"""
        config = sdk.env.getConfig("QvQChat")
        if not config:
            default_config = self._get_default_config()
            sdk.env.setConfig("QvQChat", default_config)
            return default_config
        return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            # 基础配置
            "command_prefix": "/qvc",  # 命令前缀
            "max_history_length": 20,
            "memory_cleanup_interval": 86400,
            "enable_vector_search": False,
            "max_memory_tokens": 10000,
            "memory_compression_threshold": 5,

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
            },
            
            # 对话AI配置
            "dialogue": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o",  # 使用支持视觉的模型
                "temperature": 0.7,
                "max_tokens": 500,
                "system_prompt": """你是一个普通群友，和大家一起聊天。

【重要】回复策略（像真人一样）：
- 默认保持安静，不要每条消息都回复
- 只在真正需要回应的时候说话
- 简短自然，1-2句话，不要太长
- 不要使用任何格式（不要加粗、代码、列表、标题等）
- 用口语化的方式，像真人聊天一样

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

【多消息回复格式】：
如果你想说多句话，用这种格式：
第一句话
[间隔:3]
第二句话
[间隔:2]
第三句话

数字表示秒数，最多3条消息，每条间隔1-5秒。

【如果发送图片】：
自然地回复图片内容，不要说"这是一张图片"或类似的话。

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
- 你是一个普通群友，和大家一起聊天
- 默认保持安静，只在真正需要的时候回复
- 不要每条消息都回复

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
- 默认不回复（false）
- 只有在明确需要回应时才回复（true）
- 宁可错过，也不要乱回复

输出格式：只回复"true"或"false"，不要解释。"""
            },
            
            # 记忆AI配置
            "memory": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.3,
                "max_tokens": 1000,
                "system_prompt": "你是一个记忆整理助手，负责总结、压缩和整理对话记忆。提取关键信息，删除冗余内容。"
            },
            
            # 查询AI配置
            "query": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.3,
                "max_tokens": 1000,
                "system_prompt": "你是一个记忆查询助手，负责从记忆中检索相关信息。"
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
1. dialogue - 普通对话交流（提问、聊天、日常交流）
2. memory_query - 明确要求查询历史记忆（如"我记得我昨天说过"、"查一下我之前说的"）
3. memory_add - 明确要求记住某些信息（如"记住这件事"、"记下来"、"这是重要信息"）
4. memory_delete - 明确要求删除记忆（如"忘记这件事"、"删掉这段记忆"）
5. system_control - 系统控制指令（如"切换模型"、"修改配置"、"设置风格"、"重启系统"）
6. group_config - 群聊配置相关（如"群设置"、"群提示词"、"改变群设定"）
7. prompt_custom - 自定义提示词（如"把提示词改成..."、"换个提示词"）
8. style_change - 改变对话风格（如"变专业点"、"幽默一点"、"换个风格"）
9. export - 导出记忆（如"导出我的记忆"、"备份记忆"）

重要提示（避免误判）：
- 【严格】只有明确提及"记忆"、"查询"、"记住"、"忘记"、"删除"等关键词时才归类为memory相关意图
- 【严格】不要把普通对话误识别为记忆相关意图
- 【严格】不要把"我昨天"、"记得"等口语化表达误判为记忆查询，除非明确要求"查一下"
- 【默认】所有普通交流、提问、闲聊都归类为dialogue
- 【默认】没有明确指令的情况下，归类为dialogue

只返回意图类型名称（如dialogue），不要包含其他内容。"""
            },
            
            # 用户个性化配置（运行时生成）
            "users": {},
            
            # 群配置（运行时生成）
            "groups": {}
        }

    def get_memory_mode_description(self, mode: str) -> str:
        """获取记忆模式描述"""
        descriptions = {
            "mixed": "混合模式：同时保存发送者个人记忆和群公共记忆",
            "sender_only": "仅发送者模式：只保存发送者的个人记忆"
        }
        return descriptions.get(mode, "未知模式")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        sdk.env.setConfig("QvQChat", self.config)
    
    def get_ai_config(self, ai_type: str) -> Dict[str, Any]:
        """获取指定AI的配置"""
        # reply_judge AI如果未配置，则使用dialogue的配置
        if ai_type == "reply_judge":
            judge_config = self.get("reply_judge", {})
            if not judge_config.get("api_key"):
                dialogue_config = self.get("dialogue", {})
                judge_config = dialogue_config.copy()
                judge_config["temperature"] = 0.1
                judge_config["max_tokens"] = 100
            return judge_config
        return self.get(ai_type, {})
    
    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        """获取用户配置（使用storage存储）"""
        key = f"QvQChat.users.{user_id}"
        user_config = self.storage.get(key, {
            "style": "友好",
            "preferences": {}
        })
        return user_config

    def set_user_config(self, user_id: str, config: Dict[str, Any]) -> None:
        """设置用户配置（使用storage存储）"""
        key = f"QvQChat.users.{user_id}"
        self.storage.set(key, config)

    def get_group_config(self, group_id: str) -> Dict[str, Any]:
        """获取群配置（使用storage存储）"""
        key = f"QvQChat.groups.{group_id}"
        group_config = self.storage.get(key, {
            "system_prompt": "",
            "model_overrides": {},
            "enable_memory": True,
            "memory_mode": "mixed"  # mixed: 混合模式（发送者记忆+群公共记忆）, sender_only: 只记忆发送者
        })
        return group_config

    def set_group_config(self, group_id: str, config: Dict[str, Any]) -> None:
        """设置群配置（使用storage存储）"""
        key = f"QvQChat.groups.{group_id}"
        self.storage.set(key, config)
    
    def get_effective_system_prompt(self, user_id: str, group_id: Optional[str] = None) -> str:
        """获取有效的系统提示词（群配置优先）"""
        base_prompt = self.get("dialogue.system_prompt", "")
        
        if group_id:
            group_config = self.get_group_config(group_id)
            if group_config.get("system_prompt"):
                return group_config["system_prompt"]
        
        user_config = self.get_user_config(user_id)
        if user_config.get("custom_prompt"):
            return user_config["custom_prompt"]
        
        return base_prompt
    
    def get_effective_model_config(self, ai_type: str, user_id: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """获取有效的模型配置（群配置 > 用户配置 > 默认配置）"""
        base_config = self.get_ai_config(ai_type).copy()
        
        if group_id:
            group_config = self.get_group_config(group_id)
            overrides = group_config.get("model_overrides", {}).get(ai_type, {})
            base_config.update(overrides)
        
        return base_config
    
    def get_command_prefix(self) -> str:
        """获取命令前缀"""
        return self.get("command_prefix", "/qvc")
