"""
QvQChat 公共工具模块

提供跨模块共享的工具函数。
"""
import re
from typing import List, Dict, Any, Optional
import aiohttp
from datetime import datetime
from pathlib import Path

def parse_multi_messages(text: str) -> List[Dict[str, Any]]:
    """
    解析多条消息（带延迟）

    支持每条消息都可以包含语音标签。

    Args:
        text: 包含多条消息格式的文本

    Returns:
        List[Dict[str, Any]]: 消息列表，每条消息包含content和delay
    """
    # 先解析所有语音标签的位置（使用栈来确保配对正确）
    voice_blocks = _parse_voice_tags_with_stack(text)

    # 检查是否有未关闭的语音标签
    if voice_blocks and voice_blocks[-1].get("is_unclosed", False):
        from ErisPulse.Core import logger
        logger.warning("未关闭的语音标签")
        return [{"content": text.strip(), "delay": 0}]
    # 按照 <|wait time="N"|> 分割消息，但跳过语音标签内部的分隔符
    parts = []
    current_start = 0

    # 找到所有的 wait 分隔符
    for match in re.finditer(r'<\|\s*wait\s+time="(\d+)"\s*\|>', text):
        match_pos = match.start()

        # 检查这个分隔符是否在任何语音标签内部
        is_inside_voice = False
        for voice_block in voice_blocks:
            if voice_block["start"] < match_pos < voice_block["end"]:
                is_inside_voice = True
                break

        if not is_inside_voice:
            # 这是一个有效的分隔符
            parts.append(text[current_start:match_pos].strip())
            parts.append(match.group(1))  # 延迟时间
            current_start = match.end()

    # 添加最后一部分
    parts.append(text[current_start:].strip())

    # 构建消息列表
    messages = []
    current_msg = parts[0] if parts else text

    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            if current_msg:
                messages.append({"content": current_msg, "delay": 0})
            current_msg = parts[i + 1]

    if current_msg:
        messages.append({"content": current_msg, "delay": 0})

    # 设置延迟时间
    for i in range(len(messages)):
        if i > 0 and i * 2 - 1 < len(parts):
            messages[i]["delay"] = int(parts[i * 2 - 1])

    # 如果没有分隔符，返回单条消息
    if len(messages) <= 1:
        return [{"content": text.strip(), "delay": 0}]

    # 最多返回3条消息
    return messages[:3]


def _parse_voice_tags_with_stack(text: str) -> List[Dict[str, Any]]:
    """
    使用栈解析所有语音标签，确保配对正确

    Args:
        text: 包含语音标签的文本

    Returns:
        List[Dict[str, Any]]: 语音块列表，每个包含 start, end, style, content
    """
    voice_blocks = []
    stack = []  # 存储开启标签的位置和风格

    # 匹配开始标签：<|voice style="...">
    start_pattern = re.compile(r'<\|\s*voice\s+style\s*=\s*["\']([^"\']*)["\']\s*\|>', re.DOTALL)
    # 匹配结束标签：</voice>
    end_pattern = re.compile(r'<\|\s*/\s*voice\s*\|>', re.DOTALL)

    i = 0
    while i < len(text):
        # 查找下一个开始标签
        start_match = start_pattern.search(text, i)
        # 查找下一个结束标签
        end_match = end_pattern.search(text, i)

        if not start_match and not end_match:
            break

        if start_match and (not end_match or start_match.start() < end_match.start()):
            # 找到开始标签
            stack.append({
                "start": start_match.start(),
                "end": start_match.end(),
                "style": start_match.group(1).strip(),
                "content_start": start_match.end()
            })
            i = start_match.end()
        elif end_match:
            # 找到结束标签
            if stack:
                # 与最近的开始标签配对
                start_block = stack[-1]
                voice_blocks.append({
                    "start": start_block["start"],
                    "end": end_match.end(),
                    "style": start_block["style"],
                    "content": text[start_block["content_start"]:end_match.start()].strip()
                })
                stack.pop()
            else:
                # 没有匹配的开始标签，多余的结束标签
                voice_blocks.append({
                    "start": end_match.start(),
                    "end": end_match.end(),
                    "style": "",
                    "content": ""
                })
            i = end_match.end()

    # 处理栈中未关闭的标签
    for block in stack:
        voice_blocks.append({
            "start": block["start"],
            "end": len(text),  # 到文本末尾
            "style": block["style"],
            "content": text[block["content_start"]:].strip(),
            "is_unclosed": True
        })

    return voice_blocks


def parse_speak_tags(text: str) -> Dict[str, Any]:
    """
    解析 <|voice style="..."> 标签，提取文本内容和语音内容

    使用栈方法解析，确保正确处理嵌套和多个语音标签。
    每条消息只能有一个语音标签。

    Args:
        text: 可能包含 <|voice> 标签的文本

    Returns:
        Dict[str, Any]: 包含 text, voice_style, voice_content 和 has_voice 的字典
            - text: 标签外的文本内容
            - voice_style: 语音风格描述（从 style 属性提取）
            - voice_content: 语音内容（正文）
            - has_voice: 是否包含语音标签
    """
    result = {
        "text": text,
        "voice_style": None,
        "voice_content": None,
        "has_voice": False
    }

    # 使用栈方法解析语音标签
    voice_blocks = _parse_voice_tags_with_stack(text)

    if voice_blocks:
        # 取第一个有效的语音标签
        first_voice = voice_blocks[0]

        # 检查是否是未关闭的标签
        if first_voice.get("is_unclosed", False):
            from ErisPulse.Core import logger
            logger.warning("检测到未关闭的语音标签，使用标签后的所有内容作为语音")

        result["has_voice"] = True
        result["voice_style"] = first_voice["style"]
        result["voice_content"] = first_voice["content"]

        # 移除语音标签，保留文本
        voice_tag = text[first_voice["start"]:first_voice["end"]]
        result["text"] = text.replace(voice_tag, "", 1).strip()

    return result


async def record_voice(voice_style: str, voice_content: str, config: Dict[str, Any], logger) -> Optional[str]:
    """
    生成语音（使用SiliconFlow API）

    语音最终格式：风格描述<|endofprompt|>语音正文
    例如：用撒娇的语气说这句话<|endofprompt|>主人你怎么现在才来找我玩喵~

    Args:
        voice_style: 语音风格描述（方言、语气等）
        voice_content: 语音正文内容
        config: 配置字典（包含语音API配置）
        logger: 日志记录器

    Returns:
        Optional[str]: 语音文件路径，失败返回None
    """
    try:
        # 获取语音配置
        voice_config = config.get("voice", {})
        if not voice_config.get("enabled", False):
            logger.debug("语音功能未启用")
            return None

        api_url = voice_config.get("api_url", "https://api.siliconflow.cn/v1/audio/speech")
        api_key = voice_config.get("api_key", "")

        if not api_key:
            logger.warning("语音API密钥未配置")
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # 构建最终语音文本：风格<|endofprompt|>正文
        if voice_style:
            voice_text = f"{voice_style}<|endofprompt|>{voice_content}"
        else:
            voice_text = voice_content

        logger.debug(f"语音风格: {voice_style}, 语音正文: {voice_content}")

        data = {
            "model": voice_config.get("model", "FunAudioLLM/CosyVoice2-0.5B"),
            "input": voice_text,
            "voice": voice_config.get("voice", "speech:amer:nu5h6ye36m:ahldwvelhofwpcqcxoky"),
            "response_format": "mp3",
            "speed": voice_config.get("speed", 1.0),
            "gain": voice_config.get("gain", 0.0),
            "sample_rate": voice_config.get("sample_rate", 44100)
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, headers=headers, json=data) as response:
                response.raise_for_status()
                file_name = f"voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"

                # 获取临时文件夹
                import tempfile
                temp_folder = tempfile.gettempdir()
                speech_file_path = Path(temp_folder) / file_name

                with open(speech_file_path, "wb") as f:
                    f.write(await response.read())

                logger.info(f"语音生成成功: {speech_file_path}")
                return str(speech_file_path)

    except Exception as e:
        logger.error(f"语音生成失败: {e}")
        return None
