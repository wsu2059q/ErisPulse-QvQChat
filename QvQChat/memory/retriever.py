"""
记忆检索层

按相关性（关键词命中 × 时间衰减 × 重要度）排序获取记忆，
替代旧的"取最后N条"策略，让注入提示词的记忆更精准。
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class MemoryRetriever:
    """记忆检索层"""

    def __init__(self, store, logger):
        self.store = store
        self.logger = logger

    async def retrieve_user_memories(
        self,
        user_id: str,
        query: str = "",
        top_k: int = 8,
    ) -> List[Dict[str, Any]]:
        """检索用户长期记忆（按相关性排序）

        :param query: 当前消息（用于关键词匹配），空则按时间倒序
        :param top_k: 最多返回条数
        :return: 排序后的记忆条目列表
        """
        memory = await self.store.get_user_memory(user_id)
        long_term = memory.get("long_term", [])
        if not long_term:
            return []

        if not query.strip():
            return long_term[-top_k:]

        scored = []
        for entry in long_term:
            score = self._score_entry(entry, query)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        result = [e for s, e in scored[:top_k] if s > 0]
        if not result:
            result = long_term[-top_k:]
        return result

    async def retrieve_group_sender_memories(
        self,
        group_id: str,
        sender_id: str,
        query: str = "",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索群内某发送者的记忆"""
        memory = await self.store.get_group_memory(group_id)
        sender_mem = memory.get("sender_memory", {}).get(sender_id, [])
        if not sender_mem:
            return []

        if not query.strip():
            return sender_mem[-top_k:]

        scored = []
        for entry in sender_mem:
            score = self._score_entry(entry, query)
            scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for s, e in scored[:top_k] if s > 0]

    def _score_entry(self, entry: Dict[str, Any], query: str) -> float:
        """打分 = 关键词命中 × 时间衰减 × 重要度加成"""
        content = entry.get("content", "")
        kw_score = self._keyword_score(content, query)
        recency = self._recency_score(entry.get("timestamp", ""))
        important = 1.5 if entry.get("important") else 1.0
        return kw_score * recency * important

    @staticmethod
    def _keyword_score(content: str, query: str) -> float:
        """关键词命中分数（基于有意义的词/字符重叠）"""
        if not content or not query:
            return 0.0

        content_lower = content.lower()
        query_lower = query.lower()

        query_words = set(re.findall(r"[\u4e00-\u9fff]{1,3}|[a-zA-Z]{2,}", query_lower))
        if not query_words:
            query_words = set(query_lower.split())

        if not query_words:
            return 0.0

        hits = sum(1 for w in query_words if w in content_lower)
        return hits / max(len(query_words), 1)

    @staticmethod
    def _recency_score(timestamp: str) -> float:
        """时间衰减分数：越新分数越高（30天内 1.0→0.3 线性衰减，超30天 0.1）"""
        if not timestamp:
            return 0.5
        try:
            ts = datetime.fromisoformat(timestamp)
            days = (datetime.now() - ts).days
            if days <= 0:
                return 1.0
            if days <= 30:
                return 1.0 - 0.7 * (days / 30)
            return 0.1
        except Exception:
            return 0.5
