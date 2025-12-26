import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from ErisPulse import sdk


class QvQMemory:
    """
    记忆管理系统
    
    负责管理用户的记忆，包括：
    - 短期记忆：最近的对话历史
    - 长期记忆：重要信息
    - 群记忆：群聊中的共享记忆
    """
    
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = sdk.logger.get_child("QvQMemory")
        self.storage = sdk.storage
        self._memory_cache = {}
        self._last_cleanup = {}
    
    def _get_user_memory_key(self, user_id: str) -> str:
        """
        获取用户记忆存储键
        
        Args:
            user_id: 用户ID
            
        Returns:
            str: 存储键
        """
        return f"qvc:user:{user_id}:memory"
    
    def _get_group_memory_key(self, group_id: str) -> str:
        """
        获取群记忆存储键
        
        Args:
            group_id: 群ID
            
        Returns:
            str: 存储键
        """
        return f"qvc:group:{group_id}:memory"
    
    def _get_group_context_key(self, group_id: str) -> str:
        """
        获取群上下文存储键
        
        Args:
            group_id: 群ID
            
        Returns:
            str: 存储键
        """
        return f"qvc:group:{group_id}:context"
    
    def _get_session_key(self, chat_id: str) -> str:
        """
        获取会话存储键
        
        Args:
            chat_id: 会话ID
            
        Returns:
            str: 存储键
        """
        return f"qvc:session:{chat_id}"
    
    async def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户记忆
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 用户记忆字典
        """
        key = self._get_user_memory_key(user_id)
        memory = self.storage.get(key, {
            "short_term": [],  # 短期记忆（最近对话）
            "long_term": [],   # 长期记忆（重要信息）
            "semantic": [],     # 语义记忆（关键概念）
            "last_updated": datetime.now().isoformat()
        })
        return memory
    
    async def set_user_memory(self, user_id: str, memory: Dict[str, Any]) -> None:
        """
        设置用户记忆
        
        Args:
            user_id: 用户ID
            memory: 记忆字典
        """
        key = self._get_user_memory_key(user_id)
        memory["last_updated"] = datetime.now().isoformat()
        self.storage.set(key, memory)
        self._memory_cache[key] = memory
    
    async def get_group_memory(self, group_id: str) -> Dict[str, Any]:
        """
        获取群记忆
        
        Args:
            group_id: 群ID
            
        Returns:
            Dict[str, Any]: 群记忆字典
        """
        key = self._get_group_memory_key(group_id)
        memory = self.storage.get(key, {
            "sender_memory": {},  # 发送者记忆 {user_id: memory}
            "shared_context": [],  # 群共享上下文
            "last_updated": datetime.now().isoformat()
        })
        return memory
    
    async def set_group_memory(self, group_id: str, memory: Dict[str, Any]) -> None:
        """
        设置群记忆
        
        Args:
            group_id: 群ID
            memory: 记忆字典
        """
        key = self._get_group_memory_key(group_id)
        memory["last_updated"] = datetime.now().isoformat()
        self.storage.set(key, memory)
        self._memory_cache[key] = memory
    
    async def add_short_term_memory(
        self,
        user_id: str,
        role: str,
        content: str,
        group_id: Optional[str] = None,
        user_nickname: Optional[str] = None
    ) -> None:
        """
        添加短期记忆（会话历史）

        Args:
            user_id: 用户ID
            role: 角色（user/assistant）
            content: 内容
            group_id: 群ID（可选）
            user_nickname: 用户昵称（可选）
        """
        # 群聊使用group_id作为key（所有用户共享会话历史），私聊使用user_id
        memory_key = self._get_session_key(user_id if not group_id else f"group:{group_id}")
        session = self.storage.get(memory_key, [])

        # 对于群聊，在消息中添加发送者信息以区分不同用户
        if group_id and role == "user":
            # 优先使用昵称，如果没有则使用ID
            sender = user_nickname if user_nickname else user_id
            content = f"[{sender}]: {content}"

        session.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        max_length = self.config.get("max_history_length", 20)
        if len(session) > max_length:
            session = session[-max_length:]

        self.storage.set(memory_key, session)
    
    async def get_session_history(self, user_id: str, group_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        获取会话历史

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            List[Dict[str, str]]: 会话历史列表
        """
        # 群聊使用group_id作为key（所有用户共享会话历史），私聊使用user_id
        session_key = self._get_session_key(user_id if not group_id else f"group:{group_id}")
        session = self.storage.get(session_key, [])
        return [{"role": msg["role"], "content": msg["content"]} for msg in session]
    
    async def clear_session(self, user_id: str, group_id: Optional[str] = None) -> None:
        """
        清除会话历史

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
        """
        # 群聊使用group_id作为key（所有用户共享会话历史），私聊使用user_id
        session_key = self._get_session_key(user_id if not group_id else f"group:{group_id}")
        self.storage.set(session_key, [])
    
    async def add_long_term_memory(self, user_id: str, content: str, tags: List[str] = None) -> None:
        """
        添加长期记忆
        
        Args:
            user_id: 用户ID
            content: 记忆内容
            tags: 标签列表（可选）
        """
        memory = await self.get_user_memory(user_id)
        
        long_term_entry = {
            "content": content,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat(),
            "importance": 1.0
        }
        
        memory["long_term"].append(long_term_entry)
        
        max_tokens = self.config.get("max_memory_tokens", 10000)
        if len(memory["long_term"]) * 100 > max_tokens:  # 估算
            memory["long_term"] = memory["long_term"][-50:]
        
        await self.set_user_memory(user_id, memory)
    
    async def add_group_memory(
        self,
        group_id: str,
        sender_id: str,
        content: str,
        is_context: bool = False
    ) -> None:
        """
        添加群记忆
        
        Args:
            group_id: 群ID
            sender_id: 发送者ID
            content: 内容
            is_context: 是否为共享上下文
        """
        memory = await self.get_group_memory(group_id)
        
        if is_context:
            memory["shared_context"].append({
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            if len(memory["shared_context"]) > 20:
                memory["shared_context"] = memory["shared_context"][-20:]
        else:
            if sender_id not in memory["sender_memory"]:
                memory["sender_memory"][sender_id] = []
            
            memory["sender_memory"][sender_id].append({
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            
            if len(memory["sender_memory"][sender_id]) > 10:
                memory["sender_memory"][sender_id] = memory["sender_memory"][sender_id][-10:]
        
        await self.set_group_memory(group_id, memory)
    
    async def search_memory(
        self,
        user_id: str,
        query: str,
        group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索记忆

        Args:
            user_id: 用户ID
            query: 查询词
            group_id: 群ID（可选）

        Returns:
            List[Dict[str, Any]]: 搜索结果列表
        """
        results = []

        # 搜索用户个人长期记忆
        user_memory = await self.get_user_memory(user_id)
        for entry in user_memory.get("long_term", []):
            if query.lower() in entry["content"].lower():
                results.append({
                    "source": "long_term",
                    "content": entry["content"],
                    "timestamp": entry["timestamp"]
                })

        # 如果在群聊中，搜索该用户在群中的记忆
        if group_id:
            group_memory = await self.get_group_memory(group_id)

            # 只搜索发送者的群记忆，不搜索其他人的记忆
            if sender_memory := group_memory.get("sender_memory", {}).get(user_id, []):
                for entry in sender_memory:
                    if query.lower() in entry["content"].lower():
                        results.append({
                            "source": "group_sender",
                            "content": entry["content"],
                            "timestamp": entry["timestamp"]
                        })

            # 搜索群公共上下文（所有用户共享）
            for entry in group_memory.get("shared_context", []):
                if query.lower() in entry["content"].lower():
                    results.append({
                        "source": "group_context",
                        "content": entry["content"],
                        "timestamp": entry["timestamp"]
                    })

        return results[:10]  # 返回最多10条结果
    
    async def compress_memory(self, user_id: str, ai_client) -> str:
        """
        压缩记忆
        
        Args:
            user_id: 用户ID
            ai_client: AI客户端
            
        Returns:
            str: 压缩结果
        """
        memory = await self.get_user_memory(user_id)
        
        if not memory["long_term"]:
            return "没有需要压缩的记忆"
        
        memories = [entry["content"] for entry in memory["long_term"]]
        prompt = f"""请总结并压缩以下记忆，提取关键信息，删除冗余内容：

{json.dumps(memories, ensure_ascii=False, indent=2)}

要求：
1. 保留最重要的信息
2. 合并相似的记忆
3. 使用简洁的语言
4. 返回JSON格式的记忆列表"""
        
        try:
            response = await ai_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            # 尝试解析响应
            try:
                compressed = json.loads(response)
                memory["long_term"] = [{
                    "content": entry if isinstance(entry, str) else json.dumps(entry),
                    "tags": ["compressed"],
                    "timestamp": datetime.now().isoformat(),
                    "importance": 1.0
                } for entry in (compressed if isinstance(compressed, list) else [compressed])]
                await self.set_user_memory(user_id, memory)
                return "记忆已成功压缩"
            except json.JSONDecodeError:
                # 如果解析失败，直接使用响应
                memory["long_term"] = [{
                    "content": response,
                    "tags": ["compressed"],
                    "timestamp": datetime.now().isoformat(),
                    "importance": 1.0
                }]
                await self.set_user_memory(user_id, memory)
                return "记忆已压缩（使用AI生成的总结）"
                
        except Exception as e:
            self.logger.error(f"压缩记忆失败: {e}")
            return f"压缩记忆失败: {e}"
    
    async def delete_memory(self, user_id: str, memory_index: int, group_id: Optional[str] = None) -> bool:
        """
        删除记忆
        
        Args:
            user_id: 用户ID
            memory_index: 记忆索引
            group_id: 群ID（可选）
            
        Returns:
            bool: 是否删除成功
        """
        if group_id:
            memory = await self.get_group_memory(group_id)
            if user_id in memory["sender_memory"]:
                if 0 <= memory_index < len(memory["sender_memory"][user_id]):
                    memory["sender_memory"][user_id].pop(memory_index)
                    await self.set_group_memory(group_id, memory)
                    return True
        else:
            memory = await self.get_user_memory(user_id)
            if 0 <= memory_index < len(memory["long_term"]):
                memory["long_term"].pop(memory_index)
                await self.set_user_memory(user_id, memory)
                return True
        
        return False
    
    async def get_memory_summary(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取记忆摘要
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            str: 记忆摘要
        """
        user_memory = await self.get_user_memory(user_id)
        summary = f"用户记忆: {len(user_memory['long_term'])} 条长期记忆\n"
        
        if group_id:
            group_memory = await self.get_group_memory(group_id)
            sender_count = len(group_memory.get("sender_memory", {}).get(user_id, []))
            context_count = len(group_memory.get("shared_context", []))
            summary += f"群聊记忆: {sender_count} 条发送者记忆, {context_count} 条共享上下文\n"
        
        return summary
    
    async def export_memory(self, user_id: str, group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        导出记忆
        
        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            Dict[str, Any]: 导出数据
        """
        export_data = {
            "user_id": user_id,
            "group_id": group_id,
            "user_memory": await self.get_user_memory(user_id)
        }
        
        if group_id:
            export_data["group_memory"] = await self.get_group_memory(group_id)
            export_data["session_history"] = await self.get_session_history(user_id, group_id)
        else:
            export_data["session_history"] = await self.get_session_history(user_id)
        
        return export_data
