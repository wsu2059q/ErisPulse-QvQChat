"""
QvQChat 公共工具模块

提供跨模块共享的工具函数。
"""
import re
from typing import List, Dict, Any


def remove_markdown(text: str) -> str:
    """
    移除Markdown格式

    Args:
        text: 原始文本

    Returns:
        str: 移除Markdown后的文本
    """
    if not text:
        return text
    # 移除粗体 **text** 或 __text__
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    # 移除斜体 *text* 或 _text_
    text = re.sub(r'\*(?!\*)(.*?)\*(?!\*)', r'\1', text)
    text = re.sub(r'_(?!_)(.*?)_(?!_)', r'\1', text)
    # 移除代码 `code`
    text = re.sub(r'`(.*?)`', r'\1', text)
    # 移除代码块 ```code```
    text = re.sub(r'```[\s\S]*?```', '', text)
    # 移除标题 # heading
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # 移除列表标记 - 或 *
    text = re.sub(r'^[\s]*[-*]\s+', '', text, flags=re.MULTILINE)
    # 移除有序列表 1.
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 移除链接 [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # 移除多余的空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def parse_multi_messages(text: str) -> List[Dict[str, Any]]:
    """
    解析多条消息（带延迟）

    Args:
        text: 包含多条消息格式的文本

    Returns:
        List[Dict[str, Any]]: 消息列表，每条消息包含content和delay
    """
    # 尝试解析多消息格式：消息1\n\n[间隔:3]\n\n消息2
    pattern = r'\[间隔:(\d+)\]'
    parts = re.split(pattern, text)

    messages = []
    current_msg = parts[0].strip()

    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            next_msg = parts[i + 1].strip()

            if current_msg:
                messages.append({"content": current_msg, "delay": 0})
            current_msg = next_msg

    if current_msg:
        messages.append({"content": current_msg, "delay": 0})

    # 如果没有找到间隔标记，返回单条消息
    if len(messages) <= 1:
        if len(messages) == 0:
            return [{"content": text.strip(), "delay": 0}]
    else:
        # 设置延迟
        for i in range(len(messages)):
            if i > 0 and i * 2 - 1 < len(parts):
                delay = int(parts[i * 2 - 1])
                messages[i]["delay"] = delay

    # 最多返回3条消息
    return messages[:3]
