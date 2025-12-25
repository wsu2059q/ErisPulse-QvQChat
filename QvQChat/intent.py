import re
from typing import Dict, List, Optional, Callable
from ErisPulse import sdk


class QvQIntent:
    """意图识别处理器"""
    
    def __init__(self, ai_manager, config_manager, logger):
        self.ai_manager = ai_manager
        self.config = config_manager
        self.logger = logger.get_child("QvQIntent")
        
        # 意图处理器映射
        self.intent_handlers: Dict[str, Callable] = {}
        
        # 命令模式匹配
        self.command_patterns = {
            r"^/qvc\s+config$": "system_control",
            r"^/qvc\s+model\s+(\w+)$": "system_control",
            r"^/qvc\s+memory\s+(\w+)(?:\s+(.+))?$": "memory_management",
            r"^/qvc\s+group\s+(\w+)(?:\s+(.+))?$": "group_config",
            r"^/qvc\s+prompt\s+(.+)$": "prompt_custom",
            r"^/qvc\s+style\s+(.+)$": "style_change",
            r"^/qvc\s+clear$": "session_clear",
            r"^/qvc\s+export$": "export",
            r"^/qvc\s+help$": "help",
        }
        
        # 查询关键词
        self.query_keywords = [
            "记得", "记录", "忘记", "说过", "提到",
            "history", "记忆", "历史", "之前", "刚才"
        ]
    
    def register_handler(self, intent_type: str, handler: Callable) -> None:
        """注册意图处理器"""
        self.intent_handlers[intent_type] = handler
    
    async def identify_intent(self, user_input: str, user_id: str, group_id: Optional[str] = None) -> Dict[str, any]:
        """识别用户意图"""
        user_input = user_input.strip()
        intent = "dialogue"
        confidence = 0.5
        extracted_params = {}
        
        # 1. 检查命令模式
        for pattern, intent_type in self.command_patterns.items():
            match = re.match(pattern, user_input, re.IGNORECASE)
            if match:
                intent = intent_type
                confidence = 1.0
                extracted_params = {
                    "command": user_input,
                    "groups": match.groups()
                }
                break
        
        # 2. 检查查询关键词
        if intent == "dialogue":
            for keyword in self.query_keywords:
                if keyword.lower() in user_input.lower():
                    intent = "memory_query"
                    confidence = 0.7
                    extracted_params["query"] = user_input
                    break
        
        # 3. 使用AI识别（如果需要更精确的识别且客户端可用）
        if intent == "dialogue" and self.ai_manager.get_client("intent"):
            try:
                ai_intent = await self.ai_manager.identify_intent(user_input)
                if ai_intent and ai_intent.strip() in [
                    "dialogue", "memory_query", "memory_add", "memory_delete",
                    "system_control", "group_config", "prompt_custom",
                    "style_change", "export"
                ]:
                    intent = ai_intent.strip()
                    confidence = 0.8
            except Exception as e:
                self.logger.debug(f"AI意图识别失败，使用规则识别: {e}")
        
        return {
            "intent": intent,
            "confidence": confidence,
            "params": extracted_params,
            "raw_input": user_input
        }
    
    async def handle_intent(self, intent_data: Dict[str, any], user_id: str, group_id: Optional[str] = None) -> str:
        """处理意图"""
        intent = intent_data["intent"]
        params = intent_data["params"]
        
        handler = self.intent_handlers.get(intent)
        if handler:
            try:
                return await handler(user_id, group_id, params, intent_data)
            except Exception as e:
                self.logger.error(f"处理意图 {intent} 失败: {e}")
                return f"处理请求时出错: {e}"
        else:
            return f"未知的意图类型: {intent}"
    
    def get_help_text(self) -> str:
        """获取帮助文本"""
        return """QvQChat 智能助手命令列表：

基础命令：
/qvc clear       - 清除当前会话历史
/qvc help        - 显示帮助信息

记忆管理：
/qvc memory list      - 查看记忆摘要
/qvc memory search <关键词>  - 搜索记忆
/qvc memory compress  - 压缩整理记忆
/qvc memory delete <索引>   - 删除指定记忆

系统控制：
/qvc config           - 查看当前配置
/qvc model <类型>     - 切换AI模型（dialogue/memory/query）
/qvc export           - 导出记忆

群聊配置（仅在群聊中可用）：
/qvc group info       - 查看群配置
/qvc group prompt <内容>   - 设置群提示词
/qvc group style <风格>   - 设置对话风格

个性化：
/qvc prompt <内容>    - 自定义个人提示词
/qvc style <风格>      - 设置对话风格（友好/专业/幽默等）

示例：
/qvc memory search 我昨天说过什么
/qvc group prompt 你是一个专业的技术顾问
/qvc style 幽默
/qvc model dialogue
"""
