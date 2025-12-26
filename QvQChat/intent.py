import re
from typing import Dict, Optional, Callable


class QvQIntent:
    """意图识别处理器"""
    
    def __init__(self, ai_manager, config_manager, logger):
        self.ai_manager = ai_manager
        self.config = config_manager
        self.logger = logger.get_child("QvQIntent")

        # 意图处理器映射
        self.intent_handlers: Dict[str, Callable] = {}

        # 查询关键词
        self.query_keywords = [
            "记得", "记录", "忘记", "说过", "提到",
            "history", "记忆", "历史", "之前", "刚才"
        ]

        # 命令模式匹配（动态生成）
        self._build_command_patterns()

    def _build_command_patterns(self) -> None:
        """构建命令模式（支持动态命令前缀）"""
        prefix = self.config.get_command_prefix()
        # 转义前缀中的特殊字符
        escaped_prefix = re.escape(prefix)

        self.command_patterns = {
            rf"^{escaped_prefix}\s+config$": "system_control",
            rf"^{escaped_prefix}\s+model\s+(\w+)$": "system_control",
            rf"^{escaped_prefix}\s+memory\s+(\w+)(?:\s+(.+))?$": "memory_management",
            rf"^{escaped_prefix}\s+group\s+(\w+)(?:\s+(.+))?$": "group_config",
            rf"^{escaped_prefix}\s+prompt\s+(.+)$": "prompt_custom",
            rf"^{escaped_prefix}\s+style\s+(.+)$": "style_change",
            rf"^{escaped_prefix}\s+clear$": "session_clear",
            rf"^{escaped_prefix}\s+export$": "export",
            rf"^{escaped_prefix}\s+help$": "help",
        }
        self.logger.info(f"命令模式已构建，前缀: {prefix}")

    def rebuild_patterns(self) -> None:
        """重新构建命令模式（配置更新后调用）"""
        self._build_command_patterns()
    
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
        prefix = self.config.get_command_prefix()
        return f"""命令列表：

基础命令：
{prefix} clear       - 清除当前会话历史
{prefix} help        - 显示帮助信息

记忆管理：
{prefix} memory list      - 查看记忆摘要
{prefix} memory search <关键词>  - 搜索记忆
{prefix} memory compress  - 压缩整理记忆
{prefix} memory delete <索引>   - 删除指定记忆

系统控制：
{prefix} config           - 查看当前配置
{prefix} model <类型>     - 切换AI模型（dialogue/memory/query）
{prefix} export           - 导出记忆

群聊配置（仅在群聊中可用）：
{prefix} group info       - 查看群配置
{prefix} group prompt <内容>   - 设置群提示词
{prefix} group style <风格>   - 设置对话风格

个性化：
{prefix} prompt <内容>    - 自定义个人提示词
{prefix} style <风格>      - 设置对话风格（友好/专业/幽默等）

示例：
{prefix} memory search 我昨天说过什么
{prefix} group prompt 你是一个专业的技术顾问
{prefix} style 幽默
{prefix} model dialogue
"""
