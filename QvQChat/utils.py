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

    Args:
        text: 包含多条消息格式的文本

    Returns:
        List[Dict[str, Any]]: 消息列表，每条消息包含content和delay
    """
    # 尝试解析多消息格式：消息1\n\n<|wait time="1"|>\n\n消息2
    pattern = r'<\|wait\s+time="(\d+)"\|>'
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


def parse_speak_tags(text: str) -> Dict[str, Any]:
    """
    解析 <|voice style="..."> 标签，提取文本内容和语音内容

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

    # 查找 <|voice style="..."> 标签
    voice_pattern = r'<\|voice\s+style="([^"]*)"\|>(.*?)<\|/voice\|>'
    matches = re.findall(voice_pattern, text, re.DOTALL)

    if matches:
        result["has_voice"] = True
        # 提取最后一个语音标签的内容
        voice_style, voice_content = matches[-1]
        result["voice_style"] = voice_style.strip()
        result["voice_content"] = voice_content.strip()

        # 移除所有语音标签，保留标签外的文本
        text_without_voice = re.sub(voice_pattern, '', text, flags=re.DOTALL)
        result["text"] = text_without_voice.strip()

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
