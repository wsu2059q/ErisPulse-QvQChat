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
            "clear_command": "/qvc clear",
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
                "message_threshold": 5,  # 累积N条消息后回复
                "min_reply_interval": 5,  # 最小回复间隔（秒）
                "ignore_commands": True,  # 忽略命令（以/开头）
            },
            
            # 对话AI配置
            "dialogue": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 500,
                "system_prompt": """你是一个智能AI助手。
回复要求：
1. 简短精炼，通常1-2句话，不超过100字
2. 不要使用Markdown格式（如**加粗**、`代码`、-列表、#标题等）
3. 自然口语化，直接回答
4. 利用记忆和上下文，理解对话流程，智能把握回复时机
5. 群聊场景注意氛围，适当参与互动；私聊场景可以更自由表达"""
            },

            # 视觉AI配置
            "vision": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-4-vision-preview",
                "temperature": 0.3,
                "max_tokens": 300,
                "system_prompt": "你是一个视觉描述助手。用简洁的语言描述图片内容，不超过50字。"
            },

            # 回复判断AI配置（智能判断是否需要回复）
            "reply_judge": {
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
                "model": "gpt-3.5-turbo",
                "temperature": 0.1,
                "max_tokens": 100,
                "system_prompt": """你是一个对话分析助手。分析用户的最新消息，判断是否需要AI回复。

判断标准：
1. 明确的问题、请求、指令 - 需要回复
2. @机器人或叫机器人名字 - 需要回复
3. 对话中断后重新开始 - 需要回复
4. 情绪强烈的表达 - 需要回复
5. 纯表情或简单的打招呼 - 可以不回复
6. 对话中的简短回应（如"嗯"、"好"） - 可以不回复
7. 只是消息分享，没有互动意图 - 可以不回复

输出格式：只回复"true"或"false"，不要其他内容。"""
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
                "system_prompt": """你是一个意图识别助手。请识别用户的意图，从以下选项中选择最合适的一个：

1. dialogue - 普通对话
2. memory_query - 查询历史记忆
3. memory_add - 添加新记忆
4. memory_delete - 删除记忆
5. system_control - 系统控制（切换模型、配置等）
6. group_config - 群聊配置
7. prompt_custom - 自定义提示词
8. style_change - 改变对话风格
9. export - 导出记忆

只返回意图类型，不要包含其他内容。"""
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
        # vision AI如果未配置，则使用dialogue的配置
        if ai_type == "vision":
            vision_config = self.get("vision", {})
            if not vision_config.get("api_key"):
                dialogue_config = self.get("dialogue", {})
                vision_config = dialogue_config.copy()
                vision_config["model"] = vision_config.get("model", "gpt-4-vision-preview")
                vision_config["max_tokens"] = 300
            return vision_config
        # reply_judge AI如果未配置，则使用dialogue的配置
        elif ai_type == "reply_judge":
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
    
    def save(self) -> None:
        """保存配置"""
        sdk.env.setConfig("QvQChat", self.config)
