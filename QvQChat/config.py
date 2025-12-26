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
            
            # 回复策略配置
            "reply_strategy": {
                "auto_reply": False,  # 是否自动回复
                "reply_on_mention": True,  # 被@时回复
                "reply_on_keyword": [],  # 关键词触发列表
                "reply_probability": 0.1,  # 概率回复（0-1）
                "min_reply_interval": 5,  # 最小回复间隔（秒）
                "ignore_commands": True,  # 忽略命令（以/开头）
            },
            
            # 对话AI配置
            "dialogue": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4o",  # 使用支持视觉的模型
                "temperature": 0.7,
                "max_tokens": 500,
                "system_prompt": """你是一个智能AI助手，支持图片理解。
回复要求：
1. 简短精炼，通常1-2句话，不超过100字
2. 不要使用Markdown格式（如**加粗**、`代码`、-列表、#标题等）
3. 自然口语化，直接回答
4. 利用记忆和上下文，理解对话流程，智能把握回复时机
5. 群聊场景注意氛围，适当参与互动；私聊场景可以更自由表达
6. 如果有图片，根据图片内容自然回复，不要专门说明"这是一张图片\""""
            },

            # 回复判断AI配置（智能判断是否需要回复）
            "reply_judge": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.1,
                "max_tokens": 100,
                "system_prompt": """你是一个对话分析助手。仔细分析对话上下文，严格判断用户的最新消息是否需要AI回复。

严格判断标准（满足任一条件才回复）：
1. 【必须】消息中明确提问（包含"吗"、"呢"、"什么"、"怎么"、"为什么"、"？"、"?"等问句特征）
2. 【必须】用户直接@机器人或呼唤机器人名字
3. 【必须】用户明确发出指令或请求（如"帮我"、"请"、"能否"）
4. 【必须】对话长时间中断后用户主动开口（超过10条消息沉默后）

【绝对不回复的情况】：
1. 纯表情符号或简单的打招呼（如"哈哈"、"233"、"[图片]"）
2. 对话中的简短确认回应（如"嗯"、"好"、"知道了"、"OK"、"收到"）
3. 用户只是分享消息、发表状态，无互动意图
4. 对话中的插话、随意的附和
5. 普通的日常聊天，没有明确的互动需求
6. 用户已经连续发了很多消息，机器人刚回复过（避免刷屏）

重要提示：
- 宁可错过回复，也不要乱回复
- 默认应该是false（不回复），只有确信需要互动时才true
- 结合对话上下文判断，不要只看单条消息

输出格式：只回复"true"或"false"，不要包含其他内容。"""
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
            "memory_mode": "sender_only"  # sender_only: 只记忆发送者, group: 记忆群公共信息
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
