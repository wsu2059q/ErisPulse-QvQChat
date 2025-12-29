"""
QvQChat 公共工具模块

提供跨模块共享的工具函数。
"""
import re
from typing import List, Dict, Any, Optional
import aiohttp
from datetime import datetime
from pathlib import Path

def get_session_description(
    user_id: str,
    user_nickname: str = "",
    group_id: Optional[str] = None,
    group_name: str = ""
) -> str:
    """
    获取会话描述字符串（用于日志记录）

    Args:
        user_id: 用户ID
        user_nickname: 用户昵称
        group_id: 群ID（可选）
        group_name: 群名称（可选）

    Returns:
        str: 会话描述字符串
    """
    user_desc = f"{user_nickname}({user_id})" if user_nickname else user_id

    if group_id:
        if group_name:
            return f"群聊 [{group_name}]({group_id}) - 用户 {user_desc}"
        else:
            return f"群聊 ({group_id}) - 用户 {user_desc}"
    else:
        return f"私聊 - 用户 {user_desc}"

def truncate_message(message: str, max_length: int = 100) -> str:
    """
    截断消息字符串用于日志记录

    Args:
        message: 原始消息
        max_length: 最大长度

    Returns:
        str: 截断后的消息
    """
    if len(message) <= max_length:
        return message
    return message[:max_length] + "..."

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
        logger.warning("未关闭的语音标签，按单条消息处理")
        return [{"content": text.strip(), "delay": 0}]

    # 按照 <|wait time="N"|> 分割消息，但跳过语音标签内部的分隔符
    parts = []
    current_start = 0

    # 找到所有的 wait 分隔符（使用更精确的正则）
    wait_pattern = re.compile(r'<\|\s*wait\s+time\s*=\s*"(\d+)"\s*\|>', re.IGNORECASE)

    for match in wait_pattern.finditer(text):
        match_pos = match.start()

        # 检查这个分隔符是否在任何语音标签内部
        is_inside_voice = any(
            voice_block["start"] < match_pos < voice_block["end"]
            for voice_block in voice_blocks
        )

        if not is_inside_voice:
            # 这是一个有效的分隔符
            parts.append(text[current_start:match_pos].strip())
            parts.append(match.group(1))  # 延迟时间
            current_start = match.end()

    # 添加最后一部分
    parts.append(text[current_start:].strip())

    # 如果没有找到分隔符，返回单条消息
    if len(parts) == 1:
        return [{"content": parts[0].strip() if parts else text.strip(), "delay": 0}]

    # 构建消息列表（每条消息+对应的延迟时间）
    messages = []

    # parts 格式: [msg1, delay1, msg2, delay2, msg3, ...]
    # 取出消息内容，延迟时间是下一条消息的等待时间
    for i in range(0, len(parts) - 1, 2):
        msg_content = parts[i].strip()
        if msg_content:  # 只添加非空消息
            # 获取下一条消息的延迟时间（如果有）
            delay = int(parts[i + 1]) if i + 1 < len(parts) else 0
            messages.append({"content": msg_content, "delay": delay})

    # 如果最后一条消息被遗漏了，添加它
    if len(parts) % 2 == 1 and parts[-1].strip():
        messages.append({"content": parts[-1].strip(), "delay": 0})

    # 最多返回3条消息
    if len(messages) > 3:
        from ErisPulse.Core import logger
        logger.warning("消息超过3条，只发送前3条")
        messages = messages[:3]

    return messages


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

    # 匹配开始标签：<|voice style="..."|>
    start_pattern = re.compile(r'<\|\s*voice\s+style\s*=\s*["\']([^"\']*)["\']\s*\|>', re.DOTALL)
    # 匹配结束标签：<|/voice|>
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
    解析 <|voice style="..."|> 标签，提取文本内容和语音内容

    使用栈方法解析，确保正确处理嵌套和多个语音标签。
    每条消息只能有一个语音标签。

    Args:
        text: 可能包含 <|voice|> 标签的文本

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


class MessageSender:
    """
    统一的消息发送处理器

    支持多消息、多语音组合发送，自动处理延迟和平台适配。

    支持格式：
    1. <|wait time="N"|>：多消息分隔符，N为延迟秒数（1-5秒），最多3条消息
    2. <|voice style="...">...</|voice>：语音标签，每条消息可包含一个语音标签
       - style：语音风格（方言、语气等，可用自然语言描述）
       - 标签内：语音正文内容
       - 最终格式：风格<|endofprompt|>正文

    示例组合：
    ```
    第一句文本 <|voice style="开心的语气"|>第一句语音<|/voice|>
    <|wait time="2"|>
    第二句文本 <|voice style="撒娇的语气"|>第二句语音<|/voice|>
    ```
    """

    def __init__(self, sdk_adapter, config: Dict[str, Any], logger):
        """
        初始化消息发送器

        Args:
            sdk_adapter: SDK适配器对象
            config: 配置字典
            logger: 日志记录器
        """
        self.sdk_adapter = sdk_adapter
        self.config = config
        self.logger = logger

    async def send(
        self,
        platform: str,
        target_type: str,
        target_id: str,
        response: str
    ) -> None:
        """
        发送响应消息（支持多消息和多语音组合）

        Args:
            platform: 平台类型（qq, onebot11等）
            target_type: 目标类型（user 或 group）
            target_id: 目标ID（用户ID或群ID）
            response: 响应内容
        """
        if not platform:
            self.logger.warning("平台类型为空，无法发送消息")
            return

        # 获取适配器
        adapter = getattr(self.sdk_adapter, platform, None)
        if not adapter:
            self.logger.warning(f"未找到适配器: {platform}")
            return

        # 解析多条消息
        messages = parse_multi_messages(response)

        if not messages:
            self.logger.warning("解析消息失败，消息为空")
            return

        # 逐条发送
        for i, msg_info in enumerate(messages):
            msg_content = msg_info["content"]
            delay = msg_info["delay"]

            # 延迟发送（除第一条消息外）
            if i > 0 and delay > 0:
                import asyncio
                await asyncio.sleep(delay)

            await self._send_single_message(
                adapter, target_type, target_id, msg_content, platform, i + 1, len(messages)
            )

    async def _send_single_message(
        self,
        adapter,
        target_type: str,
        target_id: str,
        message: str,
        platform: str,
        msg_index: int,
        total_messages: int
    ) -> None:
        """
        发送单条消息（可能包含文本和语音）

        Args:
            adapter: 适配器对象
            target_type: 目标类型
            target_id: 目标ID
            message: 消息内容
            platform: 平台类型
            msg_index: 当前消息序号
            total_messages: 总消息数
        """
        try:
            # 解析语音标签
            speak_result = parse_speak_tags(message)

            # 检查平台是否支持语音
            support_voice = platform in self.config.get("voice.platforms", ["qq", "onebot11"])

            if speak_result["has_voice"]:
                # 有语音标签，发送文本和语音
                await self._send_text_and_voice(
                    adapter, target_type, target_id,
                    speak_result["text"],
                    speak_result["voice_style"],
                    speak_result["voice_content"],
                    support_voice,
                    platform,
                    msg_index,
                    total_messages
                )
            else:
                # 只发送文本
                await adapter.Send.To(target_type, target_id).Text(message.strip())
                self.logger.info(
                    f"已发送文本到 {platform} - {target_type} - {target_id} "
                    f"(消息 {msg_index}/{total_messages})"
                )

        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")

    async def _send_text_and_voice(
        self,
        adapter,
        target_type: str,
        target_id: str,
        text: str,
        voice_style: Optional[str],
        voice_content: Optional[str],
        support_voice: bool,
        platform: str,
        msg_index: int,
        total_messages: int
    ) -> None:
        """
        发送文本和语音

        Args:
            adapter: 适配器对象
            target_type: 目标类型
            target_id: 目标ID
            text: 文本内容
            voice_style: 语音风格
            voice_content: 语音内容
            support_voice: 是否支持语音
            platform: 平台类型
            msg_index: 当前消息序号
            total_messages: 总消息数
        """
        # 发送文本
        if text:
            await adapter.Send.To(target_type, target_id).Text(text)
            self.logger.info(
                f"已发送文本到 {platform} - {target_type} - {target_id} "
                f"(消息 {msg_index}/{total_messages})"
            )

        # 发送语音
        if voice_content and support_voice:
            voice_file = await record_voice(voice_style, voice_content, self.config, self.logger)
            if voice_file:
                voice_path = Path(voice_file)
                if voice_path.exists():
                    await self._send_voice_file(adapter, target_type, target_id, voice_file, platform, msg_index, total_messages)
                else:
                    self.logger.warning("语音文件不存在，跳过语音发送")
            else:
                self.logger.warning("语音生成失败，跳过语音发送")
        elif voice_content and not support_voice:
            self.logger.debug(f"平台 {platform} 不支持语音，跳过语音发送")

    async def _send_voice_file(
        self,
        adapter,
        target_type: str,
        target_id: str,
        voice_file: str,
        platform: str,
        msg_index: int,
        total_messages: int
    ) -> None:
        """
        发送语音文件（尝试多种方式）

        Args:
            adapter: 适配器对象
            target_type: 目标类型
            target_id: 目标ID
            voice_file: 语音文件路径
            platform: 平台类型
            msg_index: 当前消息序号
            total_messages: 总消息数
        """
        voice_path = Path(voice_file)
        voice_sent = False

        # 方法1: 使用 base64 编码
        try:
            with open(voice_path, 'rb') as f:
                import base64
                voice_data = base64.b64encode(f.read()).decode('utf-8')
                await adapter.Send.To(target_type, target_id).Voice(f'base64://{voice_data:.128f}')
                self.logger.info(
                    f"已发送语音(base64)到 {platform} - {target_type} - {target_id} "
                    f"(消息 {msg_index}/{total_messages})"
                )
                voice_sent = True
        except Exception as base64_err:
            self.logger.debug(f"base64方式失败: {base64_err}")

        # 方法2: 直接发送本地文件路径（最后尝试）
        if not voice_sent:
            try:
                await adapter.Send.To(target_type, target_id).Voice(str(voice_path))
                self.logger.info(
                    f"已发送语音(本地)到 {platform} - {target_type} - {target_id} "
                    f"(消息 {msg_index}/{total_messages})"
                )
                voice_sent = True
            except Exception as local_err:
                self.logger.warning(f"所有发送方式均失败，跳过语音发送: {local_err}")
