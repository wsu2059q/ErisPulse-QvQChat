from typing import Dict, Any, Optional
from datetime import datetime
from ErisPulse import sdk


class QvQState:
    """
    对话状态管理器
    
    负责管理对话状态，包括：
    - 当前主题
    - 交互计数
    - 情绪状态
    - 上下文关键词
    """
    
    def __init__(self, config_manager, logger):
        self.config = config_manager
        self.logger = logger.get_child("QvQState")
        self.storage = sdk.storage
        
        # 对话状态
        self.conversation_states: Dict[str, Dict[str, Any]] = {}
        self.state_lock = None  # 简化为None，因为ErisPulse SDK的storage应该是线程安全的
    
    def _get_state_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取状态存储键
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            str: 状态键
        """
        if group_id:
            return f"qvc:state:{group_id}:{user_id}"
        return f"qvc:state:{user_id}"
    
    async def get_state(self, user_id: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取用户状态
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            Dict[str, Any]: 状态字典
        """
        key = self._get_state_key(user_id, group_id)
        state = self.storage.get(key, {
            "current_topic": None,
            "last_topic": None,
            "topic_start_time": None,
            "interaction_count": 0,
            "last_interaction": None,
            "mood": "neutral",
            "context_keywords": [],
            "pending_actions": []
        })
        return state
    
    async def update_state(self, user_id: str, group_id: Optional[str] = None, **kwargs) -> None:
        """
        更新状态
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            **kwargs: 要更新的状态字段
        """
        key = self._get_state_key(user_id, group_id)
        state = await self.get_state(user_id, group_id)
        
        for k, v in kwargs.items():
            state[k] = v
        
        state["last_interaction"] = datetime.now().isoformat()
        self.storage.set(key, state)
    
    async def increment_interaction(self, user_id: str, group_id: Optional[str] = None) -> None:
        """
        增加交互计数
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
        """
        state = await self.get_state(user_id, group_id)
        state["interaction_count"] = state.get("interaction_count", 0) + 1
        await self.update_state(user_id, group_id, interaction_count=state["interaction_count"])
    
    async def update_topic(self, user_id: str, topic: str, group_id: Optional[str] = None) -> None:
        """
        更新对话主题
        
        Args:
            user_id: 用户ID
            topic: 新主题
            group_id: 群ID（可选）
        """
        state = await self.get_state(user_id, group_id)
        
        if state["current_topic"] != topic:
            await self.update_state(
                user_id, group_id,
                last_topic=state["current_topic"],
                current_topic=topic,
                topic_start_time=datetime.now().isoformat()
            )
    
    async def add_context_keyword(self, user_id: str, keyword: str, group_id: Optional[str] = None) -> None:
        """
        添加上下文关键词
        
        Args:
            user_id: 用户ID
            keyword: 关键词
            group_id: 群ID（可选）
        """
        state = await self.get_state(user_id, group_id)
        keywords = state.get("context_keywords", [])
        
        if keyword.lower() not in [k.lower() for k in keywords]:
            keywords.append(keyword)
            if len(keywords) > 10:
                keywords = keywords[-10:]
            
            await self.update_state(user_id, group_id, context_keywords=keywords)
    
    async def update_mood(self, user_id: str, mood: str, group_id: Optional[str] = None) -> None:
        """
        更新情绪状态
        
        Args:
            user_id: 用户ID
            mood: 情绪（happy/sad/angry/neutral/excited/frustrated）
            group_id: 群ID（可选）
        """
        valid_moods = ["happy", "sad", "angry", "neutral", "excited", "frustrated"]
        if mood.lower() in valid_moods:
            await self.update_state(user_id, group_id, mood=mood.lower())
    
    async def get_topic_duration(self, user_id: str, group_id: Optional[str] = None) -> Optional[float]:
        """
        获取当前主题持续时间（秒）
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            Optional[float]: 持续时间（秒）
        """
        state = await self.get_state(user_id, group_id)
        start_time = state.get("topic_start_time")
        
        if start_time:
            try:
                start = datetime.fromisoformat(start_time)
                duration = (datetime.now() - start).total_seconds()
                return duration
            except Exception:
                pass
        
        return None
    
    async def should_change_topic(self, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        判断是否应该切换主题
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            bool: 是否应该切换主题
        """
        duration = await self.get_topic_duration(user_id, group_id)
        return duration and duration > 300  # 5分钟
