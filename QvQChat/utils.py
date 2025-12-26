"""
QvQChat 公共工具模块

提供跨模块共享的工具函数。
"""
import re
from typing import List, Dict, Any, Optional
import aiohttp
from datetime import datetime
from pathlib import Path


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


def parse_speak_tags(text: str) -> Dict[str, Any]:
    """
    解析 <speak> 标签，提取文本内容和语音内容

    Args:
        text: 可能包含 <speak> 标签的文本

    Returns:
        Dict[str, Any]: 包含 text 和 voice_content 的字典
            - text: <speak> 标签外的文本内容
            - voice_content: <speak> 标签内的语音内容（包含 <|endofprompt|> 标签）
            - has_speak: 是否包含 <speak> 标签
    """
    result = {
        "text": text,
        "voice_content": None,
        "has_speak": False
    }

    # 查找 <speak> 标签
    speak_pattern = r'<speak>(.*?)</speak>'
    matches = re.findall(speak_pattern, text, re.DOTALL)

    if matches:
        result["has_speak"] = True
        # 提取最后一个 <speak> 标签的内容作为语音内容
        result["voice_content"] = matches[-1].strip()

        # 移除所有 <speak> 标签，保留标签外的文本
        text_without_speak = re.sub(speak_pattern, '', text, flags=re.DOTALL)
        result["text"] = text_without_speak.strip()

    return result


async def record_voice(text: str, config: Dict[str, Any], logger) -> Optional[str]:
    """
    生成语音（使用SiliconFlow API）

    支持通过 <|endofprompt|> 标签控制语音生成特性：
    - 标签前是语音特性描述（如方言、语气等）
    - 标签后是实际要朗读的文本

    Args:
        text: 要转换为语音的文本（可包含 <|endofprompt|> 标签）
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

        # 处理 <|endofprompt|> 标签
        voice_text = text
        voice_prompt = ""

        if "<|endofprompt|>" in text:
            parts = text.split("<|endofprompt|>", 1)
            if len(parts) == 2:
                voice_prompt = parts[0].strip()
                voice_text = parts[1].strip()
                logger.debug(f"语音特性: {voice_prompt}, 语音文本: {voice_text}")

        data = {
            "model": voice_config.get("model", "FunAudioLLM/CosyVoice2-0.5B"),
            "input": voice_text,
            "voice": voice_config.get("voice", "speech:amer:nu5h6ye36m:ahldwvelhofwpcqcxoky"),
            "response_format": "mp3",
            "speed": voice_config.get("speed", 1.0),
            "gain": voice_config.get("gain", 0.0),
            "sample_rate": voice_config.get("sample_rate", 44100)
        }

        # 如果有语音特性提示，可以在这里添加到请求参数中
        # 例如，某些TTS服务支持 prompt 或 instruction 参数
        if voice_prompt:
            # 如果API支持prompt参数，可以添加
            # data["prompt"] = voice_prompt
            logger.debug(f"应用语音特性: {voice_prompt}")

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
