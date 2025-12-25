import asyncio
import random
import time
from typing import Dict, List, Optional, Any
from ErisPulse import sdk

from .config import QvQConfig
from .memory import QvQMemory
from .ai_client import QvQAIManager
from .intent import QvQIntent
from .state import QvQState
from .handler import QvQHandler


class Main:
    """QvQChat 智能对话模块主类"""

    def __init__(self):
        self.sdk = sdk
        self.logger = sdk.logger.get_child("QvQChat")

        # 初始化各个组件
        self.config = QvQConfig()
        self.memory = QvQMemory(self.config)
        self.ai_manager = QvQAIManager(self.config, self.logger)
        self.state = QvQState(self.config, self.logger)
        self.intent = QvQIntent(self.ai_manager, self.config, self.logger)
        self.handler = QvQHandler(
            self.config, self.memory, self.ai_manager,
            self.state, self.logger
        )

        # 消息计数器和时间戳
        self._message_count = {}
        self._last_reply_time = {}

        # 检查API配置
        self._check_api_config()

        # 注册意图处理器
        self._register_intent_handlers()

        # 注册消息事件监听
        self._register_event_handlers()

        self.logger.info("QvQChat 模块已初始化")
    
    def _check_api_config(self) -> None:
        """检查API配置"""
        ai_types = ["dialogue", "memory", "query", "intent", "vision", "reply_judge"]
        configured_ais = []
        missing_apis = []

        for ai_type in ai_types:
            api_key = self.config.get(f"{ai_type}.api_key", "")
            if api_key and api_key.strip() and api_key != "your-api-key":
                configured_ais.append(ai_type)
            else:
                missing_apis.append(ai_type)

        if configured_ais:
            self.logger.info(f"已配置的AI: {', '.join(configured_ais)}")

        # 只警告dialogue未配置，其他AI可以复用dialogue的配置
        if "dialogue" in missing_apis:
            self.logger.error(
                "对话AI未配置API密钥。QvQChat将无法正常工作。"
                "请在config.toml中配置[QvQChat.dialogue].api_key"
            )
        elif missing_apis:
            # vision和reply_judge未配置时可以复用dialogue的配置
            optional_missing = [ai for ai in missing_apis if ai not in ["dialogue", "vision", "reply_judge"]]
            if optional_missing:
                self.logger.warning(
                    f"未配置API密钥的AI: {', '.join(optional_missing)}。"
                    f"请在config.toml中配置[QvQChat.{ai_type}].api_key"
                )
            else:
                self.logger.info(
                    "vision和reply_judge将复用dialogue的配置"
                )
    
    @staticmethod
    def should_eager_load() -> bool:
        return True
    
    def _register_intent_handlers(self) -> None:
        """注册意图处理器"""
        self.intent.register_handler("dialogue", self.handler.handle_dialogue)
        self.intent.register_handler("memory_query", self.handler.handle_memory_query)
        self.intent.register_handler("memory_add", self.handler.handle_memory_add)
        self.intent.register_handler("memory_management", self.handler.handle_memory_management)
        self.intent.register_handler("system_control", self.handler.handle_system_control)
        self.intent.register_handler("group_config", self.handler.handle_group_config)
        self.intent.register_handler("prompt_custom", self.handler.handle_prompt_custom)
        self.intent.register_handler("style_change", self.handler.handle_style_change)
        self.intent.register_handler("session_clear", self.handler.handle_session_clear)
        self.intent.register_handler("export", self.handler.handle_export)
        self.intent.register_handler("help", self.handler.handle_help)
    
    def _register_event_handlers(self) -> None:
        """注册事件监听器"""
        self.sdk.adapter.on("message")(self._handle_message)
        self.logger.info("已注册消息事件处理器")
    
    def _get_session_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        """获取会话唯一标识"""
        if group_id:
            return f"{group_id}:{user_id}"
        return user_id

    async def _should_reply(self, data: Dict[str, Any], alt_message: str, user_id: str, group_id: Optional[str]) -> bool:
        """智能判断是否应该回复"""
        strategy = self.config.get("reply_strategy", {})

        # 命令总是回复
        if strategy.get("ignore_commands", True) and alt_message.startswith("/"):
            return True

        # 被@时回复（检查配置中的bot_ids）
        if strategy.get("reply_on_mention", False):
            message_segments = data.get("message", [])
            bot_ids = self.config.get("bot_ids", [])
            for segment in message_segments:
                if segment.get("type") == "mention":
                    mention_user = str(segment.get("data", {}).get("user_id", ""))
                    if str(mention_user) in [str(bid) for bid in bot_ids]:
                        return True

        # 关键词触发
        keywords = strategy.get("reply_on_keyword", [])
        if keywords:
            for keyword in keywords:
                if keyword.lower() in alt_message.lower():
                    return True

        # 检查是否被昵称呼叫（检查配置中的bot_nicknames）
        bot_nicknames = self.config.get("bot_nicknames", [])
        if bot_nicknames:
            for nickname in bot_nicknames:
                if nickname in alt_message:
                    return True

        # 获取最近的会话历史，用于AI判断
        session_history = await self.memory.get_session_history(user_id, group_id)

        # 获取机器人名字（默认为self的昵称，如果配置了bot_nicknames则使用第一个）
        bot_name = str(data.get("self", {}).get("user_nickname", ""))
        if bot_nicknames:
            bot_name = bot_nicknames[0]

        # 使用AI智能判断
        should_reply = await self.ai_manager.should_reply(session_history, alt_message, bot_name)
        self.logger.debug(f"AI判断是否需要回复: {should_reply}")

        # 检查回复间隔，避免刷屏
        if should_reply:
            session_key = self._get_session_key(user_id, group_id)
            last_reply = self._last_reply_time.get(session_key, 0)
            min_interval = strategy.get("min_reply_interval", 5)
            if time.time() - last_reply < min_interval:
                self.logger.debug(f"回复间隔不足 {min_interval} 秒，跳过回复")
                return False

        return should_reply

    def _extract_images_from_message(self, data: Dict[str, Any]) -> List[str]:
        """从消息中提取图片URL"""
        image_urls = []
        message_segments = data.get("message", [])
        for segment in message_segments:
            if segment.get("type") == "image":
                # 尝试获取图片URL
                image_data = segment.get("data", {})
                url = image_data.get("url") or image_data.get("file")
                if url:
                    image_urls.append(url)
        return image_urls

    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """处理消息事件"""
        try:
            # 获取消息内容
            alt_message = data.get("alt_message", "").strip()

            # 检查是否包含图片
            image_urls = self._extract_images_from_message(data)

            # 如果只有图片没有文字，使用默认文字
            if not alt_message and image_urls:
                alt_message = "[图片]"

            if not alt_message:
                return

            # 获取会话信息
            detail_type = data.get("detail_type", "private")
            user_id = str(data.get("user_id", ""))
            group_id = str(data.get("group_id", "")) if detail_type == "group" else None

            if not user_id:
                return

            # 获取平台信息
            platform = data.get("self", {}).get("platform", None)
            if not platform:
                return

            # 获取用户昵称
            user_nickname = data.get("user_nickname", user_id)

            # 检查API配置
            if not self.ai_manager.get_client("dialogue"):
                self.logger.warning("对话AI未配置，请检查API密钥")
                await self._send_response(data, "AI服务未配置，请联系管理员配置API密钥。", platform)
                return

            # 如果有图片，先使用视觉AI描述
            image_description = ""
            if image_urls and self.ai_manager.get_client("vision"):
                try:
                    image_description = await self.ai_manager.describe_image(image_urls[0])
                    self.logger.debug(f"图片描述: {image_description}")
                except Exception as e:
                    self.logger.warning(f"视觉AI处理失败: {e}")

            # 构建增强的消息输入（包含图片描述）
            enhanced_input = alt_message
            if image_description:
                enhanced_input = f"{alt_message}（图片内容：{image_description}）"

            # 识别意图
            intent_data = await self.intent.identify_intent(enhanced_input, user_id, group_id)
            self.logger.debug(
                f"用户 {user_nickname}({user_id}) 意图: {intent_data['intent']} "
                f"(置信度: {intent_data['confidence']})"
            )

            # 命令总是执行并回复
            if intent_data["intent"] in ["system_control", "memory_management", "group_config",
                                         "prompt_custom", "style_change", "session_clear", "export", "help"]:
                response = await self.intent.handle_intent(intent_data, user_id, group_id)
                response = self._remove_markdown(response)
                await self._send_response(data, response, platform)
                return

            # 检查是否需要回复（AI智能判断）
            should_reply = await self._should_reply(data, alt_message, user_id, group_id)

            # 累积消息到短期记忆（无论是否回复）
            await self.memory.add_short_term_memory(user_id, "user", enhanced_input, group_id)

            # 根据策略决定是否回复
            if not should_reply:
                self.logger.debug(f"AI判断不需要回复")
                return

            # 处理意图并回复
            response = await self.intent.handle_intent(intent_data, user_id, group_id)

            # 移除Markdown格式
            response = self._remove_markdown(response)

            # 发送响应
            await self._send_response(data, response, platform)

            # 记录回复时间
            session_key = self._get_session_key(user_id, group_id)
            self._last_reply_time[session_key] = time.time()

        except Exception as e:
            self.logger.error(f"处理消息时出错: {e}")

    def _remove_markdown(self, text: str) -> str:
        """移除Markdown格式"""
        import re
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
    
    async def _send_response(
        self,
        data: Dict[str, Any],
        response: str,
        platform: Optional[str]
    ) -> None:
        """发送响应消息"""
        try:
            if not platform:
                return
            
            adapter = getattr(self.sdk.adapter, platform)
            if not adapter:
                self.logger.warning(f"未找到适配器: {platform}")
                return
            
            detail_type = data.get("detail_type", "private")
            
            if detail_type == "private":
                target_type = "user"
                target_id = data.get("user_id")
            else:
                target_type = "group"
                target_id = data.get("group_id")
            
            if not target_id:
                return
            
            # 发送消息
            await adapter.Send.To(target_type, target_id).Text(response.strip())
            self.logger.info(f"已发送响应到 {platform} - {detail_type} - {target_id}")
            
        except Exception as e:
            self.logger.error(f"发送响应失败: {e}")
