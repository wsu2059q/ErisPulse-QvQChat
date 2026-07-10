"""
QvQChat - 智能对话模块

基于行为系统的多模型 AI 对话模块：
- 模型池 + 行为绑定（多模型冗余备用）
- 多智能体人格系统
- 知识库自动注入
- MCP 工具（stdio 服务器 + HTTP 端点）
- 表情包系统（用户上传，AI 自主选择发送）
- Dashboard 全功能管理面板
- 预测模式（低token模式）
"""

from .Core import Main

__version__ = "2.1.0"
__all__ = ["Main"]
