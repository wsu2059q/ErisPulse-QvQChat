import time
import asyncio
from typing import Dict, List, Optional, Any
from ErisPulse import sdk

from .config import QvQConfig
from .memory import QvQMemory
from .ai_client import QvQAIManager
from .intent import QvQIntent
from .state import QvQState
from .handler import QvQHandler
from .commands import QvQCommands
from .utils import remove_markdown, parse_multi_messages, record_voice, parse_speak_tags


class Main:
    """
    QvQChat 智能对话模块主类
    
    核心功能：
    - 智能对话：使用多AI协作实现自然对话
    - 记忆系统：自动提取、保存和查询用户记忆
    - 意图识别：自动识别用户意图并执行相应操作
    - 窥屏模式：群聊默默观察，适时回复
    
    AI自主判断执行：
    - 不再依赖 /command 格式
    - 用户直接用自然语言描述操作
    - AI智能识别并执行系统操作
    """

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
        self.commands = QvQCommands(self.sdk, self.memory, self.config, self.logger, self)

        # 消息计数器和时间戳（用于窥屏模式）
        self._message_count = {}
        self._last_reply_time = {}
        self._hourly_reply_count = {}  # 每小时回复计数
        self._last_hour_reset = {}  # 每个会话的上次重置时间

        # 图片缓存（用于处理图片和文本分开发送的情况）
        # key: 会话标识, value: {"image_urls": List[str], "timestamp": float}
        self._image_cache = {}
        self._IMAGE_CACHE_EXPIRE = 60  # 图片缓存过期时间（秒）

        # 活跃模式（临时关闭窥屏模式）
        # key: 会话标识, value: {"end_time": float, "duration_minutes": int}
        self._active_mode = {}

        # 检查API配置
        self._check_api_config()

        # 注册意图处理器
        self._register_intent_handlers()

        # 注册命令系统
        self.commands.register_all()

        # 注册消息事件监听
        self._register_event_handlers()

        self.logger.info("QvQChat 模块已初始化")
    
    def _check_api_config(self) -> None:
        """
        检查API配置
        
        验证必需的AI配置，给出友好的提示信息。
        
        AI说明：
        - dialogue: 对话AI（必需）
        - intent: 意图识别AI（必需）
        - intent_execution: 意图执行AI（必需，替代命令系统）
        - memory: 记忆提取AI（可选，自动复用dialogue配置）
        - reply_judge: 回复判断AI（可选，自动复用dialogue配置）
        - vision: 视觉AI（可选，自动复用dialogue配置）
        - voice: 语音合成AI（可选，需要单独配置）
        """
        ai_types = ["dialogue", "memory", "intent", "intent_execution", "reply_judge", "vision"]
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
            # 未配置的AI会复用dialogue配置
            self.logger.info(
                f"以下AI将复用dialogue配置: {', '.join(missing_apis)}"
            )

        # 检查语音配置
        voice_enabled = self.config.get("voice.enabled", False)
        if voice_enabled:
            self.logger.info("语音功能已启用（支持QQ平台）")
        else:
            self.logger.info("语音功能未启用")

    @staticmethod
    def should_eager_load() -> bool:
        """
        是否应该立即加载
        
        Returns:
            bool: True
        """
        return True
    
    def _register_intent_handlers(self) -> None:
        """
        注册意图处理器

        将意图类型映射到对应的处理函数。
        """
        # 核心意图：普通对话（记忆自然融入对话）
        self.intent.register_handler("dialogue", self.handler.handle_dialogue)

        # 记忆相关意图（用户主动要求）
        self.intent.register_handler("memory_add", self.handler.handle_memory_add)
        self.intent.register_handler("memory_delete", self.handler.handle_memory_delete)

    def _register_event_handlers(self) -> None:
        """
        注册事件监听器
        
        注册消息事件处理器以响应用户消息。
        """
        self.sdk.adapter.on("message")(self._handle_message)
        self.logger.info("已注册消息事件处理器")
    
    def _get_session_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取会话唯一标识

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 会话唯一标识
        """
        if group_id:
            # 群聊：使用群ID，所有用户共享同一个会话历史
            return f"group:{group_id}"
        # 私聊：使用用户ID
        return f"user:{user_id}"

    def _get_reply_count_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取回复计数器key

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 计数器key
        """
        if group_id:
            # 群聊：使用群ID，所有用户共享计数器
            return f"group:{group_id}"
        # 私聊：使用用户ID
        return f"user:{user_id}"

    def _get_cached_images(self, user_id: str, group_id: Optional[str] = None) -> List[str]:
        """
        获取会话缓存的图片URL（自动清理过期缓存）

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            List[str]: 图片URL列表
        """
        session_key = self._get_reply_count_key(user_id, group_id)
        current_time = time.time()

        # 清理过期的缓存
        self._image_cache = {
            k: v for k, v in self._image_cache.items()
            if current_time - v["timestamp"] < self._IMAGE_CACHE_EXPIRE
        }

        # 获取当前会话的图片
        cached_data = self._image_cache.get(session_key)
        if cached_data:
            return cached_data["image_urls"]
        return []

    def _cache_images(self, user_id: str, image_urls: List[str], group_id: Optional[str] = None) -> None:
        """
        缓存图片URL

        Args:
            user_id: 用户ID
            image_urls: 图片URL列表
            group_id: 群ID（可选）
        """
        if not image_urls:
            return

        session_key = self._get_reply_count_key(user_id, group_id)
        self._image_cache[session_key] = {
            "image_urls": image_urls,
            "timestamp": time.time()
        }
        self.logger.debug(f"已缓存 {len(image_urls)} 张图片，过期时间 {self._IMAGE_CACHE_EXPIRE} 秒")

    def enable_active_mode(self, user_id: str, duration_minutes: int = 10, group_id: Optional[str] = None) -> str:
        """
        启用活跃模式（临时关闭窥屏模式，积极参与聊天）

        Args:
            user_id: 用户ID
            duration_minutes: 持续时间（分钟），默认10分钟
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self._get_reply_count_key(user_id, group_id)
        end_time = time.time() + duration_minutes * 60

        self._active_mode[session_key] = {
            "end_time": end_time,
            "duration_minutes": duration_minutes
        }

        # 构建会话描述
        if group_id:
            session_desc = f"群聊 {group_id}"
        else:
            session_desc = f"私聊 {user_id}"

        self.logger.info(f"✓ {session_desc} 已启用活跃模式，持续 {duration_minutes} 分钟")
        return f"活跃模式已启用！我会积极参与聊天，{duration_minutes}分钟后自动切回窥屏模式~"

    def disable_active_mode(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        手动关闭活跃模式

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self._get_reply_count_key(user_id, group_id)

        if session_key in self._active_mode:
            del self._active_mode[session_key]

            # 构建会话描述
            if group_id:
                session_desc = f"群聊 {group_id}"
            else:
                session_desc = f"私聊 {user_id}"

            self.logger.info(f"✓ {session_desc} 已手动关闭活跃模式，切换回窥屏模式")
            return "活跃模式已关闭，切换回窥屏模式~"
        else:
            return "当前没有启用活跃模式哦"

    def get_active_mode_status(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取活跃模式状态

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self._get_reply_count_key(user_id, group_id)
        active_mode_data = self._active_mode.get(session_key)

        if active_mode_data:
            current_time = time.time()
            remaining_seconds = int(active_mode_data["end_time"] - current_time)

            if remaining_seconds > 0:
                remaining_minutes = remaining_seconds // 60
                remaining_seconds = remaining_seconds % 60
                return f"活跃模式生效中~ 还剩 {remaining_minutes}分{remaining_seconds}秒"
            else:
                # 已过期，清除缓存
                del self._active_mode[session_key]
                return "活跃模式已结束，当前是窥屏模式"

        return "当前是窥屏模式，使用 /活跃模式 命令可以临时切换到活跃模式"

    def get_all_active_modes(self) -> str:
        """
        获取所有处于活跃模式的会话

        Returns:
            str: 所有活跃会话的状态信息
        """
        if not self._active_mode:
            return "当前没有会话处于活跃模式~"

        current_time = time.time()
        active_sessions = []

        for session_key, data in self._active_mode.items():
            remaining_seconds = int(data["end_time"] - current_time)

            if remaining_seconds > 0:
                # 解析会话key
                if session_key.startswith("group:"):
                    group_id = session_key[6:]  # 去掉 "group:" 前缀
                    desc = f"群聊 {group_id}"
                else:
                    user_id = session_key[5:] if session_key.startswith("user:") else session_key
                    desc = f"私聊 {user_id}"

                remaining_minutes = remaining_seconds // 60
                remaining_seconds = remaining_seconds % 60
                active_sessions.append(f"• {desc} - 剩余 {remaining_minutes}分{remaining_seconds}秒")

        if not active_sessions:
            return "当前没有会话处于活跃模式~"

        result = "【活跃模式会话列表】\n" + "\n".join(active_sessions)
        self.logger.info(f"查询活跃模式，共 {len(active_sessions)} 个会话处于活跃状态")
        return result

    async def _should_reply(self, data: Dict[str, Any], alt_message: str, user_id: str, group_id: Optional[str]) -> bool:
        """
        判断是否应该回复（私聊积极回复，群聊窥屏模式）

        Args:
            data: 消息数据
            alt_message: 消息文本
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: 是否应该回复
        """
        import random

        # 私聊场景：不使用窥屏模式，使用AI智能判断
        if not group_id:
            return await self._should_reply_ai(data, alt_message, user_id, group_id)

        # 检查是否处于活跃模式
        session_key = self._get_reply_count_key(user_id, group_id)
        active_mode_data = self._active_mode.get(session_key)

        if active_mode_data:
            current_time = time.time()
            if current_time < active_mode_data["end_time"]:
                # 活跃模式生效中，使用AI判断（积极参与聊天）
                remaining_minutes = int((active_mode_data["end_time"] - current_time) / 60)

                # 构建会话描述
                if group_id:
                    session_desc = f"群聊 {group_id}"
                else:
                    session_desc = f"私聊 {user_id}"

                self.logger.debug(f"活跃模式生效中 [{session_desc}]，剩余 {remaining_minutes} 分钟")
                return await self._should_reply_ai(data, alt_message, user_id, group_id)
            else:
                # 活跃模式已过期，清除缓存
                del self._active_mode[session_key]

                # 构建会话描述
                if group_id:
                    session_desc = f"群聊 {group_id}"
                else:
                    session_desc = f"私聊 {user_id}"

                self.logger.info(f"✓ {session_desc} 活跃模式已结束，自动切换回窥屏模式")

        # 群聊场景：检查窥屏模式是否启用
        stalker_config = self.config.get("stalker_mode", {})
        if not stalker_config.get("enabled", True):
            # 如果未启用窥屏模式，使用AI判断
            return await self._should_reply_ai(data, alt_message, user_id, group_id)

        session_key = self._get_reply_count_key(user_id, group_id)
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
        """
        AI智能判断是否应该回复
        
        Args:
            data: 消息数据
            alt_message: 消息文本
            user_id: 用户ID
            group_id: 群ID（可选）
            
        Returns:
            bool: 是否应该回复
        """
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
            session_key = self._get_reply_count_key(user_id, group_id)
            last_reply = self._last_reply_time.get(session_key, 0)
            min_interval = self.config.get("min_reply_interval", 10)  # 默认10秒
            if time.time() - last_reply < min_interval:
                self.logger.debug(f"回复间隔不足 {min_interval} 秒，跳过回复")
                return False

        return should_reply

    def _extract_images_from_message(self, data: Dict[str, Any]) -> List[str]:
        """
        从消息中提取图片URL
        
        Args:
            data: 消息数据
            
        Returns:
            List[str]: 图片URL列表
        """
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
        """
        处理消息事件

        这是消息处理的主入口，负责：
        1. 识别用户意图
        2. 判断是否需要回复
        3. 调用相应的处理器
        4. 发送回复

        Args:
            data: 消息数据字典
        """
        try:
            # 获取消息内容
            alt_message = data.get("alt_message", "").strip()

            # 检查是否包含图片
            image_urls = self._extract_images_from_message(data)

            # 获取会话信息
            detail_type = data.get("detail_type", "private")
            user_id = str(data.get("user_id", ""))
            group_id = str(data.get("group_id", "")) if detail_type == "group" else None

            if not user_id:
                return

            # 如果有图片，缓存起来（等待可能的文本消息）
            if image_urls:
                self._cache_images(user_id, image_urls, group_id)

            # 如果只有图片没有文字，使用默认文字
            if not alt_message and image_urls:
                alt_message = "[图片]"

            if not alt_message:
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

            # 识别意图和判断是否回复（并行执行）
            identify_task = self.intent.identify_intent(alt_message)
            should_reply_task = self._should_reply(data, alt_message, user_id, group_id)
            intent_data, should_reply = await asyncio.gather(identify_task, should_reply_task)

            self.logger.debug(
                f"用户 {user_nickname}({user_id}) 意图: {intent_data['intent']} "
                f"(置信度: {intent_data['confidence']})"
            )

            # 累积消息到短期记忆（无论是否回复）
            await self.memory.add_short_term_memory(user_id, "user", alt_message, group_id, user_nickname)

            # 窥屏模式下，不回复时直接返回
            if not should_reply and (group_id and self.config.get("stalker_mode", {}).get("enabled", True)):
                self.logger.debug("AI判断不需要回复")
                return

            # 准备回复时，获取缓存的图片（包括本次消息的图片和之前缓存的图片）
            cached_image_urls = self._get_cached_images(user_id, group_id)
            all_image_urls = list(set(image_urls + cached_image_urls))  # 去重

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
            intent_data["params"]["image_urls"] = all_image_urls
            intent_data["params"]["context_info"] = context_info
            response = await self.intent.handle_intent(intent_data, user_id, group_id)

            # 如果返回None，表示不需要回复
            if response is None:
                return

            # 移除Markdown格式
            response = remove_markdown(response)

            # 发送响应
            await self._send_response(data, response, platform)

            # 记录回复时间
            session_key = self._get_reply_count_key(user_id, group_id)
            self._last_reply_time[session_key] = time.time()

            # 清除已使用的图片缓存
            if session_key in self._image_cache:
                del self._image_cache[session_key]
                self.logger.debug("已清除已使用的图片缓存")

        except Exception as e:
            self.logger.error(f"处理消息时出错: {e}")

    async def _send_response(
        self,
        data: Dict[str, Any],
        response: str,
        platform: Optional[str]
    ) -> None:
        """
        发送响应消息（支持多条消息和语音标签）

        支持：
        1. <speak> 标签：将标签外的文本作为普通消息，标签内的内容作为语音
        2. [语音] 标记：旧版兼容，将标记后的内容转为语音发送
        3. [间隔:N] 标记：多条消息之间的延迟

        Args:
            data: 消息数据
            response: 响应内容
            platform: 平台类型
        """
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
            messages = parse_multi_messages(response)

            # 逐条发送
            for i, msg_info in enumerate(messages):
                msg_content = msg_info["content"]
                delay = msg_info["delay"]

                if i > 0 and delay > 0:
                    import asyncio
                    await asyncio.sleep(delay)

                # 解析 <speak> 标签
                speak_result = parse_speak_tags(msg_content)

                if speak_result["has_speak"]:
                    # 有 <speak> 标签，将文本和语音分开发送
                    # 检查平台是否支持语音
                    support_voice = platform in self.config.get("voice.platforms", ["qq", "onebot11"])

                    # 发送 <speak> 标签外的文本
                    if speak_result["text"]:
                        await adapter.Send.To(target_type, target_id).Text(speak_result["text"])
                        self.logger.info(f"已发送文本响应到 {platform} - {detail_type} - {target_id} (消息 {i+1}/{len(messages)})")

                    # 发送 <speak> 标签内的语音
                    if speak_result["voice_content"] and support_voice:
                        voice_file = await record_voice(speak_result["voice_content"], self.config.config, self.logger)
                        if voice_file:
                            try:
                                from pathlib import Path
                                voice_path = Path(voice_file)
                                if voice_path.exists():
                                    # 尝试多种方式发送语音
                                    voice_sent = False

                                    # 方法1: 使用适配器的 Upload 方法
                                    try:
                                        uploaded_url = await adapter.Upload.Local(str(voice_path))
                                        if uploaded_url:
                                            await adapter.Send.To(target_type, target_id).Voice(uploaded_url)
                                            self.logger.info(f"已发送语音到 {platform} - {detail_type} - {target_id} (消息 {i+1}/{len(messages)})")
                                            voice_sent = True
                                    except Exception as upload_err:
                                        self.logger.debug(f"Upload方法失败: {upload_err}")

                                    # 方法2: 使用 base64 编码
                                    if not voice_sent:
                                        try:
                                            with open(voice_path, 'rb') as f:
                                                import base64
                                                voice_data = base64.b64encode(f.read()).decode('utf-8')
                                                await adapter.Send.To(target_type, target_id).Voice(f'base64://{voice_data}')
                                                self.logger.info(f"已发送语音(base64)到 {platform} - {detail_type} - {target_id} (消息 {i+1}/{len(messages)})")
                                                voice_sent = True
                                        except Exception as base64_err:
                                            self.logger.debug(f"base64方式失败: {base64_err}")

                                    # 方法3: 直接发送本地文件路径（最后尝试）
                                    if not voice_sent:
                                        try:
                                            await adapter.Send.To(target_type, target_id).Voice(str(voice_path))
                                            self.logger.info(f"已发送语音(本地)到 {platform} - {detail_type} - {target_id} (消息 {i+1}/{len(messages)})")
                                        except Exception as local_err:
                                            self.logger.warning(f"所有发送方式均失败，跳过语音发送: {local_err}")
                                else:
                                    self.logger.warning("语音文件不存在，跳过语音发送")
                            except Exception as voice_error:
                                self.logger.warning(f"语音发送失败: {voice_error}")
                        else:
                            self.logger.warning("语音生成失败，跳过语音发送")
                    elif speak_result["voice_content"] and not support_voice:
                        self.logger.debug(f"平台 {platform} 不支持语音，跳过语音发送")
                else:
                    # 发送普通文本消息
                    await adapter.Send.To(target_type, target_id).Text(msg_content.strip())
                    self.logger.info(f"已发送响应到 {platform} - {detail_type} - {target_id} (消息 {i+1}/{len(messages)})")

        except Exception as e:
            self.logger.error(f"发送响应失败: {e}")
