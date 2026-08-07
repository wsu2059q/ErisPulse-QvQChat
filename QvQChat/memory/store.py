"""
记忆存储层

负责记忆的持久化 CRUD、去重、衰减。
保持与 dashboard 直接操作 sdk.storage 的完全兼容（键名+字典结构不变）。
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ErisPulse import sdk


class MemoryStore:
    """记忆存储层"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.storage = sdk.storage

    # ==================== 存储键 ====================

    @staticmethod
    def _user_key(user_id: str) -> str:
        return f"qvc:user:{user_id}:memory"

    @staticmethod
    def _group_key(group_id: str) -> str:
        return f"qvc:group:{group_id}:memory"

    @staticmethod
    def _session_key(user_id: str, group_id: Optional[str] = None) -> str:
        chat_id = user_id if not group_id else f"group:{group_id}"
        return f"qvc:session:{chat_id}"

    # ==================== 用户记忆 ====================

    async def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        return self.storage.get(
            self._user_key(user_id),
            {
                "short_term": [],
                "long_term": [],
                "semantic": [],
                "last_updated": datetime.now().isoformat(),
            },
        )

    async def set_user_memory(self, user_id: str, memory: Dict[str, Any]) -> None:
        memory["last_updated"] = datetime.now().isoformat()
        self.storage.set(self._user_key(user_id), memory)

    async def add_long_term(
        self,
        user_id: str,
        content: str,
        tags: Optional[List[str]] = None,
        important: bool = False,
    ) -> bool:
        """添加长期记忆，返回是否实际添加（未去重跳过）

        改进：精确归一化匹配优先，字符集重叠阈值提高到 0.9
        """
        memory = await self.get_user_memory(user_id)

        dedup_enabled = self.config.get("memory.dedup_enabled", True)
        if dedup_enabled:
            for entry in memory["long_term"]:
                if self._is_duplicate(content, entry.get("content", "")):
                    self.logger.debug(f"记忆去重: 跳过「{content[:30]}」")
                    return False

        entry = {
            "content": content,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat(),
            "importance": 1.5 if important else 1.0,
            "important": important,
        }
        memory["long_term"].append(entry)

        decay_enabled = self.config.get("memory.decay_enabled", True)
        if decay_enabled:
            self._apply_decay(memory)

        max_per_user = self.config.get("memory.max_per_user", 100)
        if len(memory["long_term"]) > max_per_user:
            memory["long_term"] = memory["long_term"][-max_per_user:]

        await self.set_user_memory(user_id, memory)
        return True

    async def delete_long_term(self, user_id: str, index: int) -> bool:
        memory = await self.get_user_memory(user_id)
        if 0 <= index < len(memory["long_term"]):
            memory["long_term"].pop(index)
            await self.set_user_memory(user_id, memory)
            return True
        return False

    async def find_and_delete(self, user_id: str, query: str) -> int:
        """按关键词查找并删除匹配的记忆，返回删除条数"""
        memory = await self.get_user_memory(user_id)
        query_lower = query.lower().strip()
        original_len = len(memory["long_term"])
        memory["long_term"] = [
            e for e in memory["long_term"]
            if query_lower not in e.get("content", "").lower()
        ]
        deleted = original_len - len(memory["long_term"])
        if deleted > 0:
            await self.set_user_memory(user_id, memory)
        return deleted

    # ==================== 群记忆 ====================

    async def get_group_memory(self, group_id: str) -> Dict[str, Any]:
        return self.storage.get(
            self._group_key(group_id),
            {
                "sender_memory": {},
                "shared_context": [],
                "last_updated": datetime.now().isoformat(),
            },
        )

    async def set_group_memory(self, group_id: str, memory: Dict[str, Any]) -> None:
        memory["last_updated"] = datetime.now().isoformat()
        self.storage.set(self._group_key(group_id), memory)

    async def add_group_memory(
        self, group_id: str, sender_id: str, content: str, is_context: bool = False
    ) -> None:
        memory = await self.get_group_memory(group_id)

        if is_context:
            memory["shared_context"].append(
                {"content": content, "timestamp": datetime.now().isoformat()}
            )
            if len(memory["shared_context"]) > 20:
                memory["shared_context"] = memory["shared_context"][-20:]
        else:
            if sender_id not in memory["sender_memory"]:
                memory["sender_memory"][sender_id] = []
            memory["sender_memory"][sender_id].append(
                {"content": content, "timestamp": datetime.now().isoformat()}
            )
            if len(memory["sender_memory"][sender_id]) > 10:
                memory["sender_memory"][sender_id] = memory["sender_memory"][sender_id][-10:]

        await self.set_group_memory(group_id, memory)

    # ==================== 会话历史 ====================

    async def add_session_message(
        self,
        user_id: str,
        role: str,
        content: str,
        group_id: Optional[str] = None,
        user_nickname: Optional[str] = None,
    ) -> None:
        session_key = self._session_key(user_id, group_id)
        session = self.storage.get(session_key, [])

        if group_id and role == "user":
            sender = user_nickname if user_nickname else user_id
            content = f"【群友】{sender}: {content}"

        session.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )

        max_length = self.config.get("max_history_length", 20)
        if len(session) > max_length:
            session = session[-max_length:]

        self.storage.set(session_key, session)

    async def get_session_history(
        self, user_id: str, group_id: Optional[str] = None
    ) -> List[Dict[str, str]]:
        session_key = self._session_key(user_id, group_id)
        session = self.storage.get(session_key, [])
        return [{"role": m["role"], "content": m["content"]} for m in session]

    async def get_session_history_detailed(
        self, user_id: str, group_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        session_key = self._session_key(user_id, group_id)
        return self.storage.get(session_key, [])

    async def clear_session(
        self, user_id: str, group_id: Optional[str] = None
    ) -> None:
        session_key = self._session_key(user_id, group_id)
        self.storage.set(session_key, [])

    # ==================== 内部方法 ====================

    @staticmethod
    def _normalize(text: str) -> str:
        """归一化文本：去空白、转小写"""
        return re.sub(r"\s+", "", text).lower().strip()

    def _is_duplicate(self, new_content: str, existing: str) -> bool:
        """改进的去重判断

        优先级：
        1. 归一化后精确匹配
        2. 包含关系（短的被长的包含）
        3. 字符集重叠（阈值 0.9，比旧版 0.75 更严格）
        """
        new = self._normalize(new_content)
        old = self._normalize(existing)
        if not new or not old:
            return False

        if new == old:
            return True
        if new in old or old in new:
            return True

        new_set = set(new)
        old_set = set(old)
        if not new_set or not old_set:
            return False
        overlap = len(new_set & old_set) / max(len(new_set | old_set), 1)
        return overlap > 0.9

    def _apply_decay(self, memory: Dict[str, Any]) -> None:
        """记忆衰减：移除过旧且不重要的记忆（important 标记的永不衰减）"""
        decay_days = self.config.get("memory.decay_days", 30)
        if decay_days <= 0:
            return
        now = datetime.now()
        kept = []
        for entry in memory.get("long_term", []):
            if entry.get("important"):
                kept.append(entry)
                continue
            ts = entry.get("timestamp", "")
            if not ts:
                kept.append(entry)
                continue
            try:
                entry_time = datetime.fromisoformat(ts)
                if (now - entry_time).days <= decay_days:
                    kept.append(entry)
                else:
                    self.logger.debug(
                        f"记忆衰减: 移除{(now - entry_time).days}天前的记忆「{entry.get('content', '')[:30]}」"
                    )
            except Exception:
                kept.append(entry)
        memory["long_term"] = kept
