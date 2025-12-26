from typing import Dict, Optional, Callable


class QvQIntent:
    """
    意图识别处理器
    
    负责识别用户输入的意图，并路由到对应的处理器。
    
    意图类型：
    - dialogue: 普通对话交流
    - memory_query: 查询历史记忆
    - memory_add: 记住某些信息
    - memory_delete: 删除记忆
    - intent_execution: 系统操作指令
    """
    
    def __init__(self, ai_manager, config_manager, logger):
        self.ai_manager = ai_manager
        self.config = config_manager
        self.logger = logger.get_child("QvQIntent")

        # 意图处理器映射
        self.intent_handlers: Dict[str, Callable] = {}

        # 查询关键词（用于规则匹配）
        self.query_keywords = [
            "记得", "记录", "忘记", "说过", "提到",
            "history", "记忆", "历史", "之前", "刚才"
        ]
    
    def register_handler(self, intent_type: str, handler: Callable) -> None:
        """
        注册意图处理器
        
        Args:
            intent_type: 意图类型
            handler: 处理函数
        """
        self.intent_handlers[intent_type] = handler
    
    async def identify_intent(self, user_input: str) -> Dict[str, any]:
        """
        识别用户意图

        使用AI进行意图识别，结合规则匹配提高准确性。

        Args:
            user_input: 用户输入

        Returns:
            Dict[str, any]: 包含intent、confidence、params、raw_input
        """
        user_input = user_input.strip()
        intent = "dialogue"
        confidence = 0.1
        extracted_params = {}

        # 1. 检查查询关键词（规则匹配）
        for keyword in self.query_keywords:
            if keyword.lower() in user_input.lower():
                intent = "memory_query"
                confidence = 0.7
                extracted_params["query"] = user_input
                break

        # 2. 使用AI识别（更精确，如果没有intent客户端则使用规则结果）
        if self.ai_manager.get_client("intent"):
            try:
                ai_intent = await self.ai_manager.identify_intent(user_input)
                if ai_intent and ai_intent.strip() in [
                    "dialogue", "memory_query", "memory_add", "memory_delete",
                    "intent_execution"
                ]:
                    intent = ai_intent.strip()
                    confidence = 0.9
            except Exception as e:
                self.logger.warning(f"AI意图识别失败，使用规则识别: {e}")

        return {
            "intent": intent,
            "confidence": confidence,
            "params": extracted_params,
            "raw_input": user_input
        }
    
    async def handle_intent(self, intent_data: Dict[str, any], user_id: str, group_id: Optional[str] = None) -> str:
        """
        处理意图
        
        根据识别的意图调用对应的处理器。
        
        Args:
            intent_data: 意图数据
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            str: 处理结果
        """
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
