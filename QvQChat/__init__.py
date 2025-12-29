"""
QvQChat - 智能对话模块

支持：
- 多AI协作对话
- 智能记忆系统
- 意图识别
- 窥屏模式
- 活跃模式
- 语音合成

模块结构：
- Main: 主模块类（继承 BaseModule）
- Config: 配置管理器
- Memory: 记忆管理器
- AIManager: AI客户端管理器
- Intent: 意图识别器
- Handler: 意图处理器
- Commands: 命令处理器
- State: 状态管理器
- SessionManager: 会话管理器
- ActiveModeManager: 活跃模式管理器
- ReplyJudge: 回复判断器
- Utils: 工具函数和MessageSender
"""

from .Core import Main

__version__ = "1.0.0"
__all__ = ["Main"]
