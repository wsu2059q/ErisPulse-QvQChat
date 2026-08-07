"""
QvQChat 提示词注入管线

提供统一的提示词构建框架，替代散落的 _build_system_prompt / _build_scene_prompt。

核心组件：
- PromptPipeline: 注册注入器，按优先级排序拼接
- Injector: 注入器基类
- PromptContext: 上下文数据
- TimeNarrator: AI 时间叙述器（替代硬编码时间函数）
"""

from .base import Injector, PromptContext, PromptPipeline
from .time_narrator import TimeNarrator
from .injectors import (
    IdentityInjector,
    RuleInjector,
    SceneInjector,
    KnowledgeInjector,
    TimeInjector,
    MoodInjector,
    ToolInjector,
    VoiceInjector,
    ProactiveInjector,
    create_default_injectors,
)

__all__ = [
    "Injector",
    "PromptContext",
    "PromptPipeline",
    "TimeNarrator",
    "IdentityInjector",
    "RuleInjector",
    "SceneInjector",
    "KnowledgeInjector",
    "TimeInjector",
    "MoodInjector",
    "ToolInjector",
    "VoiceInjector",
    "ProactiveInjector",
    "create_default_injectors",
]
