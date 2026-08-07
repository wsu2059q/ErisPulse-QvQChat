"""
QvQChat 记忆子系统

五层架构：
- store: 存储层（CRUD + 去重 + 衰减）
- retriever: 检索层（相关性排序）
- extractor: 提取层（自动提取）
- intent: 意图层（记住/忘记指令路由）
- manager: 门面层（统一 API，兼容旧 QvQMemory）
"""

from .manager import MemoryManager
from .intent import IntentResult, IntentRouter
from .store import MemoryStore
from .retriever import MemoryRetriever
from .extractor import MemoryExtractor

__all__ = [
    "MemoryManager",
    "IntentResult",
    "IntentRouter",
    "MemoryStore",
    "MemoryRetriever",
    "MemoryExtractor",
]
