"""
兼容性垫片：QvQMemory → MemoryManager

记忆子系统已重构为五层架构（QvQChat.memory 包）。
此文件保留是为了不破坏现有 import（from .chat.memory import QvQMemory）。
"""

from ..memory import MemoryManager as QvQMemory

__all__ = ["QvQMemory"]
