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
        self._hourly_reply_count = {}  # 每小时回复计数
        self._last_hour_reset = {}  # 每个会话的上次重置时间

        # 检查API配置
        self._check_api_config()

        # 注册意图处理器
        self._register_intent_handlers()

        # 注册消息事件监听
        self._register_event_handlers()

        self.logger.info("QvQChat 模块已初始化")
    
    def _check_api_config(self) -> None:
        """检查API配置"""
        ai_types = ["dialogue", "memory", "query", "intent", "reply_judge"]
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
            # reply_judge未配置时可以复用dialogue的配置
            optional_missing = [ai for ai in missing_apis if ai not in ["dialogue", "reply_judge"]]
            if optional_missing:
                self.logger.warning(
                    f"未配置API密钥的AI: {', '.join(optional_missing)}。"
                    f"请在config.toml中配置[QvQChat.{ai_type}].api_key"
                )
            else:
                    self.logger.info(
                    "reply_judge将复用dialogue的配置"
                )

    @staticmethod
    def should_eager_load() -> bool:
        return True
    
    def _register_intent_handlers(self) -> None:
        """注册意图处理器"""
        self.intent.register_handler("dialogue", self.handler.handle_dialogue)
        self.intent.register_handler("memory_query", self.handler.handle_memory_query)
        self.intent.register_handler("memory_add", self.handler.handle_memory_add)
        self.intent.register_handler("memory_delete", self.handler.handle_memory_delete)
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
        """判断是否应该回复（私聊积极回复，群聊窥屏模式）"""
        import random

        # 命令总是执行
        if alt_message.startswith("/"):
            return True

        # 私聊场景：不使用窥屏模式，使用AI智能判断
        if not group_id:
            return await self._should_reply_ai(data, alt_message, user_id, group_id)

        # 群聊场景：检查窥屏模式是否启用
        stalker_config = self.config.get("stalker_mode", {})
        if not stalker_config.get("enabled", True):
            # 如果未启用窥屏模式，使用AI判断
            return await self._should_reply_ai(data, alt_message, user_id, group_id)

        session_key = self._get_session_key(user_id, group_id)
        current_time = time.time()

        # 重置每小时计数器（每个会话独立）
        last_reset = self._last_hour_reset.get(session_key, 0)
        if current_time - last_reset > 3600:  # 1小时
            self._hourly_reply_count[session_key] = 0
            self._last_hour_reset[session_key] = current_time
            self.logger.debug(f"会话 {session_key} 每小时计数器已重置")

        # 检查每小时回复限制
        hourly_count = self._hourly_reply_count.get(session_key, 0)
        max_per_hour = stalker_config.get("max_replies_per_hour", 8)
        if hourly_count >= max_per_hour:
            self.logger.debug(f"每小时回复次数已达上限 ({max_per_hour})，跳过回复")
            return False

        # 检查是否被@
        message_segments = data.get("message", [])
        bot_ids = self.config.get("bot_ids", [])
        bot_nicknames = self.config.get("bot_nicknames", [])
        is_mentioned = False

        # 检查@
        for segment in message_segments:
            if segment.get("type") == "mention":
                mention_user = str(segment.get("data", {}).get("user_id", ""))
                if str(mention_user) in [str(bid) for bid in bot_ids]:
                    is_mentioned = True
                    break

        # 检查是否叫名字
        bot_name = bot_nicknames[0] if bot_nicknames else ""
        if not is_mentioned and bot_name and bot_name in alt_message:
            is_mentioned = True

        # 被@时按较高概率回复
        if is_mentioned:
            mention_prob = stalker_config.get("mention_probability", 0.8)
            if random.random() < mention_prob:
                self._hourly_reply_count[session_key] = hourly_count + 1
                return True
            else:
                self.logger.debug("被@但未通过概率检查，不回复")
                return False

        # 检查关键词匹配
        reply_keywords = self.config.get("reply_strategy", {}).get("reply_on_keyword", [])
        keyword_matched = any(kw in alt_message for kw in reply_keywords)
        if keyword_matched:
            keyword_prob = stalker_config.get("keyword_probability", 0.5)
            if random.random() < keyword_prob:
                self._hourly_reply_count[session_key] = hourly_count + 1
                return True

        # 检查是否是提问
        is_question = any(marker in alt_message for marker in ["？", "?", "吗", "呢", "什么", "怎么", "为什么"])
        if is_question:
            # 提问时使用概率回复
            question_prob = stalker_config.get("question_probability", 0.4)
            if random.random() < question_prob:
                self._hourly_reply_count[session_key] = hourly_count + 1
                return True

        # 检查消息间隔（从较高值开始，允许第一次就回复）
        min_messages = stalker_config.get("min_messages_between_replies", 15)
        last_msg_count = self._message_count.get(session_key, min_messages)  # 初始化为 min_messages，允许第一次回复
        if last_msg_count < min_messages:
            self._message_count[session_key] = last_msg_count + 1
            self.logger.debug(f"消息间隔不足 ({last_msg_count}/{min_messages})，继续沉默")
            return False

        # 默认低概率回复（窥屏模式的核心）
        default_prob = stalker_config.get("default_probability", 0.03)
        self._message_count[session_key] = 0  # 重置计数器

        if random.random() < default_prob:
            self._hourly_reply_count[session_key] = hourly_count + 1
            return True

        return False

    async def _should_reply_ai(self, data: Dict[str, Any], alt_message: str, user_id: str, group_id: Optional[str]) -> bool:
        """AI智能判断是否应该回复（兼容旧逻辑）"""
        # 获取最近的会话历史
        session_history = await self.memory.get_session_history(user_id, group_id)

        # 检查是否被@（将此信息传给AI判断）
        message_segments = data.get("message", [])
        bot_ids = self.config.get("bot_ids", [])
        is_mentioned = False
        for segment in message_segments:
            if segment.get("type") == "mention":
                mention_user = str(segment.get("data", {}).get("user_id", ""))
                if str(mention_user) in [str(bid) for bid in bot_ids]:
                    is_mentioned = True
                    break

        # 如果被@了，在消息中添加标记让AI知道
        enhanced_message = alt_message
        if is_mentioned:
            bot_nicknames = self.config.get("bot_nicknames", [])
            bot_name = bot_nicknames[0] if bot_nicknames else ""
            if bot_name and bot_name not in alt_message:
                enhanced_message = f"(@{bot_name}) {alt_message}"

        # 获取机器人名字
        bot_name = str(data.get("self", {}).get("user_nickname", ""))
        bot_nicknames = self.config.get("bot_nicknames", [])
        if bot_nicknames:
            bot_name = bot_nicknames[0]

        # 获取回复关键词配置
        reply_keywords = self.config.get("reply_strategy", {}).get("reply_on_keyword", [])

        # 使用AI智能判断
        should_reply = await self.ai_manager.should_reply(session_history, enhanced_message, bot_name, reply_keywords)
        self.logger.debug(f"AI判断是否需要回复: {should_reply}")

        # 检查回复间隔，避免刷屏
        if should_reply:
            session_key = self._get_session_key(user_id, group_id)
            last_reply = self._last_reply_time.get(session_key, 0)
            min_interval = self.config.get("min_reply_interval", 10)  # 默认10秒
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

            # 获取机器人昵称
            bot_nicknames = self.config.get("bot_nicknames", [])
            bot_nickname = bot_nicknames[0] if bot_nicknames else ""

            # 检查API配置
            if not self.ai_manager.get_client("dialogue"):
                self.logger.warning("对话AI未配置，请检查API密钥")
                await self._send_response(data, "AI服务未配置，请联系管理员配置API密钥。", platform)
                return

            # 识别意图
            intent_data = await self.intent.identify_intent(alt_message, user_id, group_id)
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
            await self.memory.add_short_term_memory(user_id, "user", alt_message, group_id)

            # 获取会话历史（包含刚添加的用户消息）
            session_history = await self.memory.get_session_history(user_id, group_id)

            # 窥屏模式下，即使不回复也要提取和保存重要记忆
            if not should_reply and (group_id and self.config.get("stalker_mode", {}).get("enabled", True)):
                # 不回复时，基于对话历史提取记忆（没有 AI 回复）
                await self.handler.extract_and_save_memory(user_id, session_history, "", group_id)
                self.logger.debug("AI判断不需要回复，但已保存记忆")
                return

            # 构建上下文信息
            context_info = {
                "user_nickname": user_nickname,
                "user_id": user_id,
                "group_name": data.get("group_name", ""),
                "group_id": group_id,
                "bot_nickname": bot_nickname,
                "platform": platform,
                "is_group": detail_type == "group"
            }

            # 处理意图并回复（传递图片URL和上下文信息）
            intent_data["params"]["image_urls"] = image_urls
            intent_data["params"]["context_info"] = context_info
            response = await self.intent.handle_intent(intent_data, user_id, group_id)

            # 如果返回None，表示不需要回复
            if response is None:
                return

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
        """发送响应消息（支持多条消息）"""
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

            # 解析多条消息
            messages = self._parse_multi_messages(response)

            # 逐条发送
            for i, msg_info in enumerate(messages):
                msg_content = msg_info["content"]
                delay = msg_info["delay"]

                if i > 0 and delay > 0:
                    import asyncio
                    await asyncio.sleep(delay)

                # 发送消息
                await adapter.Send.To(target_type, target_id).Text(msg_content.strip())
                self.logger.info(f"已发送响应到 {platform} - {detail_type} - {target_id} (消息 {i+1}/{len(messages)})")

        except Exception as e:
            self.logger.error(f"发送响应失败: {e}")

    def _parse_multi_messages(self, text: str) -> list:
        """解析多条消息（带延迟）"""
        import re

        # 尝试解析多消息格式：消息1\n\n[间隔:3]\n\n消息2
        pattern = r'\[间隔:(\d+)\]'
        parts = re.split(pattern, text)

        messages = []
        current_msg = parts[0].strip()

        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                delay = int(parts[i])
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
                    messages[i]["delay"] = int(parts[i * 2 - 1])

        # 最多返回3条消息
        return messages[:3]
