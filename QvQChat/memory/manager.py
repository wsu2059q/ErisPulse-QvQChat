"""
记忆管理器（门面层）

统一对外接口，100% 兼容旧 QvQMemory 的方法签名。
内部委托给 store / retriever / extractor / intent 四层。
"""

from typing import Any, Dict, List, Optional

from .extractor import MemoryExtractor
from .intent import IntentRouter, IntentResult
from .retriever import MemoryRetriever
from .store import MemoryStore


class MemoryManager:
    """记忆管理器（门面）

    旧代码通过 QvQMemory 别名使用此类，方法签名完全兼容。
    新代码可直接使用 retrieve_relevant / handle_intent 等增强方法。
    """

    def __init__(self, config, ai_engine=None):
        self.config = config
        self.ai_engine = ai_engine
        from ErisPulse import sdk
        self.logger = sdk.logger.get_child("QvQMemory")

        self.store = MemoryStore(config, self.logger)
        self.retriever = MemoryRetriever(self.store, self.logger)
        self.extractor = MemoryExtractor(self.store, ai_engine, config, self.logger)
        self.intent = IntentRouter(self.store, ai_engine, self.logger, config)

    # ==================== 会话历史（兼容旧 API） ====================

    async def add_short_term_memory(
        self,
        user_id: str,
        role: str,
        content: str,
        group_id: Optional[str] = None,
        user_nickname: Optional[str] = None,
    ) -> None:
        await self.store.add_session_message(
            user_id, role, content, group_id, user_nickname
        )

    async def get_session_history(
        self, user_id: str, group_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        return await self.store.get_session_history(user_id, group_id)

    async def get_session_history_detailed(
        self, user_id: str, group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        return await self.store.get_session_history_detailed(user_id, group_id)

    async def clear_session(
        self, user_id: str, group_id: Optional[str] = None
    ) -> None:
        await self.store.clear_session(user_id, group_id)

    # ==================== 用户记忆（兼容旧 API） ====================

    async def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        return await self.store.get_user_memory(user_id)

    async def set_user_memory(self, user_id: str, memory: Dict[str, Any]) -> None:
        await self.store.set_user_memory(user_id, memory)

    async def add_long_term_memory(
        self,
        user_id: str,
        content: str,
        tags: Optional[List[str]] = None,
    ) -> None:
        await self.store.add_long_term(user_id, content, tags, important=False)

    async def delete_memory(
        self, user_id: str, memory_index: int, group_id: Optional[str] = None
    ) -> bool:
        if group_id:
            return False
        return await self.store.delete_long_term(user_id, memory_index)

    # ==================== 群记忆（兼容旧 API） ====================

    async def get_group_memory(self, group_id: str) -> Dict[str, Any]:
        return await self.store.get_group_memory(group_id)

    async def set_group_memory(self, group_id: str, memory: Dict[str, Any]) -> None:
        await self.store.set_group_memory(group_id, memory)

    async def add_group_memory(
        self,
        group_id: str,
        sender_id: str,
        content: str,
        is_context: bool = False,
    ) -> None:
        await self.store.add_group_memory(group_id, sender_id, content, is_context)

    # ==================== 增强方法（新 API） ====================

    async def retrieve_relevant(
        self,
        user_id: str,
        query: str,
        group_id: Optional[str] = None,
        top_k: int = 8,
    ) -> List[Dict[str, Any]]:
        """按相关性检索记忆（替代旧的取最后N条）"""
        user_mems = await self.retriever.retrieve_user_memories(
            user_id, query, top_k
        )

        if group_id:
            sender_mems = await self.retriever.retrieve_group_sender_memories(
                group_id, user_id, query, top_k=5
            )
            return {"user": user_mems, "sender": sender_mems}

        return {"user": user_mems, "sender": []}

    async def classify_intent(
        self, user_id: str, message: str, group_id: Optional[str] = None
    ) -> IntentResult:
        """识别消息意图（dialogue/memory_add/memory_delete）"""
        return await self.intent.classify(user_id, message, group_id)

    async def handle_memory_intent(
        self, user_id: str, message: str, group_id: Optional[str] = None
    ) -> Optional[str]:
        """处理记忆意图，返回回复文本（None 表示正常对话，无需拦截）"""
        result = await self.intent.classify(user_id, message, group_id)

        if result.intent == "memory_add":
            return await self.intent.handle_add(user_id, result.content, group_id)
        elif result.intent == "memory_delete":
            return await self.intent.handle_delete(user_id, result.content, group_id)

        return None

    async def extract_from_history(
        self, user_id: str, group_id: Optional[str] = None
    ) -> int:
        """自动提取记忆"""
        return await self.extractor.extract_from_history(user_id, group_id)

    # ==================== 辅助方法（兼容旧 API） ====================

    async def search_memory(
        self, user_id: str, query: str, group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """搜索记忆（旧 API，内部改用 retriever）"""
        results = []
        for entry in await self.retriever.retrieve_user_memories(user_id, query, top_k=10):
            results.append({
                "source": "long_term",
                "content": entry.get("content", ""),
                "timestamp": entry.get("timestamp", ""),
            })
        if group_id:
            for entry in await self.retriever.retrieve_group_sender_memories(
                group_id, user_id, query, top_k=5
            ):
                results.append({
                    "source": "group_sender",
                    "content": entry.get("content", ""),
                    "timestamp": entry.get("timestamp", ""),
                })
        return results

    async def get_memory_summary(
        self, user_id: str, group_id: Optional[str] = None
    ) -> str:
        user_memory = await self.get_user_memory(user_id)
        summary = f"用户记忆: {len(user_memory['long_term'])} 条长期记忆\n"
        if group_id:
            group_memory = await self.get_group_memory(group_id)
            sender_count = len(group_memory.get("sender_memory", {}).get(user_id, []))
            context_count = len(group_memory.get("shared_context", []))
            summary += f"群聊记忆: {sender_count} 条发送者记忆, {context_count} 条共享上下文\n"
        return summary

    async def export_memory(
        self, user_id: str, group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        export_data = {
            "user_id": user_id,
            "group_id": group_id,
            "user_memory": await self.get_user_memory(user_id),
        }
        if group_id:
            export_data["group_memory"] = await self.get_group_memory(group_id)
            export_data["session_history"] = await self.get_session_history(user_id, group_id)
        else:
            export_data["session_history"] = await self.get_session_history(user_id)
        return export_data

    async def compress_memory(self, user_id: str, ai_client) -> str:
        """压缩记忆（旧 API，保留兼容）"""
        import json
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
                messages=[{"role": "user", "content": prompt}], temperature=0.3
            )
            try:
                compressed = json.loads(response)
                memory["long_term"] = [
                    {
                        "content": entry if isinstance(entry, str) else json.dumps(entry),
                        "tags": ["compressed"],
                        "timestamp": memory.get("last_updated", ""),
                        "importance": 1.0,
                    }
                    for entry in (compressed if isinstance(compressed, list) else [compressed])
                ]
                await self.set_user_memory(user_id, memory)
                return "记忆已成功压缩"
            except json.JSONDecodeError:
                memory["long_term"] = [
                    {
                        "content": response,
                        "tags": ["compressed"],
                        "timestamp": memory.get("last_updated", ""),
                        "importance": 1.0,
                    }
                ]
                await self.set_user_memory(user_id, memory)
                return "记忆已压缩（使用AI生成的总结）"
        except Exception as e:
            self.logger.error(f"压缩记忆失败: {e}")
            return f"压缩记忆失败: {e}"
