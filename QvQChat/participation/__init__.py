"""群聊参与决策（核心侧扩展点）：qvq_decision 提供者管理 + 输出预算护栏。

- :class:`ParticipationManager`：生态提供者发现/并发问询/聚合策略 + 决策观测
- :class:`SpeechBudget`：每群小时上限/冷却/全局日限（storage 持久化），插话与主动发言共用
"""
from .budget import KIND_INTERJECT, KIND_PROACTIVE, SpeechBudget
from .manager import (
    DECISION_SERVICE,
    OBSERVE_EVENT,
    PARTICIPATION_EVENT,
    ParticipationManager,
)

__all__ = [
    "KIND_INTERJECT",
    "KIND_PROACTIVE",
    "SpeechBudget",
    "ParticipationManager",
    "DECISION_SERVICE",
    "OBSERVE_EVENT",
    "PARTICIPATION_EVENT",
]
