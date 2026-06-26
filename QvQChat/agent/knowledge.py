"""
知识库管理器

支持管理知识文档，将知识内容注入到 AI 对话上下文中。
支持分类、标签、启用/禁用控制。
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk


class KnowledgeBase:
    """
    知识库管理器

    管理知识条目，支持：
    - 按分类组织知识文档
    - 标签标记
    - 启用/禁用控制
    - 搜索匹配
    - 内容注入到对话上下文
    """

    STORAGE_KEY = "QvQChat.knowledge_base"

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("KnowledgeBase")
        self.storage = sdk.storage
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """从存储加载知识库数据"""
        data = self.storage.get(self.STORAGE_KEY, {})
        self._entries = data.get("entries", {})

    def _save(self) -> None:
        """保存知识库数据到存储"""
        self.storage.set(self.STORAGE_KEY, {"entries": self._entries})

    def list_entries(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出知识条目

        Args:
            category: 可选的分类过滤

        Returns:
            知识条目列表
        """
        entries = list(self._entries.values())
        if category:
            entries = [e for e in entries if e.get("category") == category]
        # 按更新时间倒序
        entries.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return entries

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """获取指定知识条目"""
        return self._entries.get(entry_id)

    def create_entry(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建知识条目

        Args:
            data: 包含 title/content/category/tags/enabled 的字典

        Returns:
            创建的知识条目
        """
        entry_id = f"kb_{uuid.uuid4().hex[:8]}"
        now = time.time()
        entry = {
            "id": entry_id,
            "title": data.get("title", "未命名文档"),
            "content": data.get("content", ""),
            "category": data.get("category", "通用"),
            "tags": data.get("tags", []),
            "enabled": data.get("enabled", True),
            "priority": data.get("priority", 0),
            "created_at": now,
            "updated_at": now,
        }
        self._entries[entry_id] = entry
        self._save()
        self.logger.info(f"创建知识条目: {entry['title']} ({entry_id})")
        return entry

    def update_entry(
        self, entry_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        更新知识条目

        Args:
            entry_id: 条目ID
            data: 要更新的字段

        Returns:
            更新后的条目
        """
        entry = self._entries.get(entry_id)
        if not entry:
            return None

        for key in ("title", "content", "category", "tags", "enabled", "priority"):
            if key in data:
                entry[key] = data[key]

        entry["updated_at"] = time.time()
        self._save()
        self.logger.info(f"更新知识条目: {entry.get('title')} ({entry_id})")
        return entry

    def delete_entry(self, entry_id: str) -> bool:
        """删除知识条目"""
        if entry_id not in self._entries:
            return False
        del self._entries[entry_id]
        self._save()
        self.logger.info(f"删除知识条目: {entry_id}")
        return True

    def list_categories(self) -> List[str]:
        """列出所有分类"""
        categories = set()
        for entry in self._entries.values():
            cat = entry.get("category", "通用")
            if cat:
                categories.add(cat)
        return sorted(categories)

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索知识条目（标题+内容匹配）

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的知识条目列表
        """
        keyword_lower = keyword.lower()
        results = []
        for entry in self._entries.values():
            if not entry.get("enabled", True):
                continue
            title = entry.get("title", "").lower()
            content = entry.get("content", "").lower()
            tags = [str(t).lower() for t in entry.get("tags", [])]
            if (
                keyword_lower in title
                or keyword_lower in content
                or keyword_lower in tags
            ):
                results.append(entry)
        results.sort(key=lambda x: x.get("priority", 0), reverse=True)
        return results

    def build_context(
        self, max_tokens: int = 2000, keyword: Optional[str] = None
    ) -> str:
        """
        构建知识库上下文文本

        将启用状态的知识条目组装成上下文文本，用于注入到 system prompt。

        Args:
            max_tokens: 最大 token 数（粗略估算）
            keyword: 可选的关键词过滤（只包含匹配的条目）

        Returns:
            格式化的知识上下文文本
        """
        if keyword:
            entries = self.search(keyword)
        else:
            entries = [e for e in self._entries.values() if e.get("enabled", True)]
            entries.sort(key=lambda x: x.get("priority", 0), reverse=True)

        if not entries:
            return ""

        parts = []
        char_count = 0
        char_limit = max_tokens * 3  # 粗略估算：1 token ≈ 3 字符

        for entry in entries:
            if char_count >= char_limit:
                break

            title = entry.get("title", "")
            content = entry.get("content", "")
            category = entry.get("category", "")

            header = f"【{title}】"
            if category:
                header = f"【{category} > {title}】"

            part = f"{header}\n{content}"
            parts.append(part)
            char_count += len(part)

        if not parts:
            return ""

        return (
            "--- 知识库参考信息 ---\n\n"
            + "\n\n".join(parts)
            + "\n\n--- 知识库参考信息结束 ---"
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        total = len(self._entries)
        enabled = sum(1 for e in self._entries.values() if e.get("enabled", True))
        categories = len(self.list_categories())
        total_chars = sum(len(e.get("content", "")) for e in self._entries.values())
        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "categories": categories,
            "total_chars": total_chars,
        }
