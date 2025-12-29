"""
QvQChat 主模块

标准化改造后的主模块，符合 ErisPulse 规范：
- 继承 BaseModule
- 实现 on_load/on_unload 生命周期
- 清晰的职责划分
"""
import asyncio
from typing import Dict, Any, Optional, List

from ErisPulse import sdk
from ErisPulse.Core.Bases import BaseModule
from ErisPulse.Core.Event import message
import time

from .config import QvQConfig
from .memory import QvQMemory
from .ai_client import QvQAIManager
from .intent import QvQIntent
from .state import QvQState
from .handler import QvQHandler
from .commands import QvQCommands
from .utils import get_session_description, truncate_message, MessageSender
from .session_manager import SessionManager
from .active_mode_manager import ActiveModeManager
from .reply_judge import ReplyJudge


class Main(BaseModule):
    """
    QvQChat 智能对话模块主类
    
    核心功能：
    - 智能对话：使用多AI协作实现自然对话
    - 记忆系统：自动提取、保存和查询用户记忆
    - 意图识别：自动识别用户意图并执行相应操作
    - 窥屏模式：群聊默默观察，适时回复
    
    符合 ErisPulse 标准：
    - 继承 BaseModule
    - 实现 on_load/on_unload 生命周期
    - 使用标准事件系统
    """

    def __init__(self):
        self.sdk = sdk
        self.logger = sdk.logger.get_child("QvQChat")

        # 初始化各个组件
        self.config = QvQConfig()
        self.memory = QvQMemory(self.config)
        self.ai_manager = QvQAIManager(self.config, self.logger)
        self.state = QvQState(self.config, self.logger)
        
        # 初始化新的管理器
        self.session_manager = SessionManager(self.config, self.logger)
        self.active_mode_manager = ActiveModeManager(self.session_manager, self.logger)
        
        # 初始化回复判断器（需要 active_mode_manager）
        self.reply_judge = ReplyJudge(self.config, self.ai_manager, self.session_manager, self.logger)
        self.reply_judge.active_mode_manager = self.active_mode_manager
        
        self.intent = QvQIntent(self.ai_manager, self.config, self.logger)
        self.handler = QvQHandler(
            self.config, self.memory, self.ai_manager,
            self.state, self.logger
        )
        self.commands = None  # 将在 on_load 中初始化

        # 初始化消息发送器
        self.message_sender = MessageSender(self.sdk.adapter, self.config.config, self.logger)

        # AI启用状态
        self._ai_disabled: Dict[str, bool] = {}

        # 检查API配置
        self._check_api_config()

        self.logger.info("QvQChat 模块初始化完成")

    @staticmethod
    def should_eager_load() -> bool:
        """
        是否应该立即加载

        Returns:
            bool: True（此模块需要立即加载）
        """
        return True

    async def on_load(self, event: Dict[str, Any]) -> bool:
        """
        模块加载时调用

        负责初始化资源、注册事件处理器等。

        Args:
            event: 加载事件

        Returns:
            bool: 是否加载成功
        """
        try:
            # 初始化命令系统
            self.commands = QvQCommands(self.sdk, self.memory, self.config, self.logger, self)

            # 注册意图处理器
            self._register_intent_handlers()

            # 注册命令系统
            self.commands.register_all()

            # 注册消息事件监听
            self._register_event_handlers()

            self.logger.info("QvQChat 模块已加载")
            return True
        except Exception as e:
            self.logger.error(f"QvQChat 模块加载失败: {e}")
            return False

    async def on_unload(self, event: Dict[str, Any]) -> bool:
        """
        模块卸载时调用

        负责清理资源、注销事件处理器等。

        Args:
            event: 卸载事件

        Returns:
            bool: 是否卸载成功
        """
        try:
            self.logger.info("QvQChat 模块已卸载")
            return True
        except Exception as e:
            self.logger.error(f"QvQChat 模块卸载失败: {e}")
            return False

    def _check_api_config(self) -> None:
        """
        检查API配置

        验证必需的AI配置，给出友好的提示信息。
        """
        ai_types = ["dialogue", "memory", "intent", "intent_execution", "reply_judge", "vision"]

        # 检查每个AI是否有独立配置
        configured_ais = []
        shared_api_ais = []
        missing_config_ais = []

        for ai_type in ai_types:
            ai_config = self.config.get(ai_type, {})

            has_own_model = bool(ai_config.get("model"))
            has_own_api_key = bool(ai_config.get("api_key") and ai_config.get("api_key").strip() and ai_config.get("api_key") != "your-api-key")

            if ai_type == "dialogue":
                if has_own_api_key:
                    configured_ais.append(ai_type)
                else:
                    missing_config_ais.append(ai_type)
            else:
                if has_own_model or has_own_api_key:
                    if has_own_api_key:
                        configured_ais.append(ai_type)
                    else:
                        shared_api_ais.append(ai_type)
                else:
                    missing_config_ais.append(ai_type)

        if configured_ais:
            self.logger.info(f"独立配置的AI: {', '.join(configured_ais)}")
        if shared_api_ais:
            self.logger.info(f"复用dialogue API密钥的AI: {', '.join(shared_api_ais)}")

        if "dialogue" in missing_config_ais:
            self.logger.error(
                "对话AI未配置API密钥。QvQChat将无法正常工作。"
                "请在config.toml中配置[QvQChat.dialogue].api_key"
            )

        voice_enabled = self.config.get("voice.enabled", False)
        if voice_enabled:
            self.logger.info("语音功能已启用（支持QQ平台）")
        else:
            self.logger.info("语音功能未启用")

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
        message.on_message(priority=999)(self._handle_message)
        self.logger.info("已注册消息事件处理器")

    def _extract_mentions_from_message(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从消息段中提取@（mention）信息

        Args:
            data: 消息数据

        Returns:
            List[Dict[str, Any]]: @信息列表，每个包含 user_id, nickname
        """
        mentions = []
        message_segments = data.get("message", [])

        for segment in message_segments:
            if segment.get("type") == "mention":
                mention_data = segment.get("data", {})
                mention_user_id = mention_data.get("user_id", "")

                mention_nickname = mention_data.get("nickname", "")

                mentions.append({
                    "user_id": str(mention_user_id),
                    "nickname": mention_nickname or f"用户{mention_user_id}"
                })

        return mentions

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
                image_data = segment.get("data", {})
                url = image_data.get("url") or image_data.get("file")
                if url:
                    image_urls.append(url)
        return image_urls

    # ==================== AI控制方法 ====================

    def enable_ai(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        启用AI

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)

        if group_id:
            group_config = self.config.get_group_config(group_id)
            group_config["enable_ai"] = True
            self.config.set_group_config(group_id, group_config)
            session_desc = f"群聊 {group_id}"
        else:
            if session_key in self._ai_disabled:
                del self._ai_disabled[session_key]
            session_desc = f"私聊 {user_id}"

        self.logger.info(f"✓ {session_desc} 已启用AI")
        return "AI已启用，我会正常回复消息~"

    def disable_ai(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        禁用AI

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)

        if group_id:
            group_config = self.config.get_group_config(group_id)
            group_config["enable_ai"] = False
            self.config.set_group_config(group_id, group_config)
            session_desc = f"群聊 {group_id}"
        else:
            self._ai_disabled[session_key] = True
            session_desc = f"私聊 {user_id}"

        self.logger.info(f"✓ {session_desc} 已禁用AI")
        return "AI已禁用，我不再主动回复（命令仍可用）"

    def is_ai_enabled(self, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        检查AI是否启用

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: AI是否启用
        """
        if group_id:
            group_config = self.config.get_group_config(group_id)
            return group_config.get("enable_ai", True)

        session_key = self.session_manager.get_reply_count_key(user_id, group_id)
        return session_key not in self._ai_disabled

    def get_ai_status(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取AI状态

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        if group_id:
            group_config = self.config.get_group_config(group_id)
            enabled = group_config.get("enable_ai", True)
            status = "已启用" if enabled else "已禁用"
            return f"群聊 {group_id} 的AI状态：{status}"
        else:
            enabled = self.is_ai_enabled(user_id, None)
            status = "已启用" if enabled else "已禁用"
            return f"私聊的AI状态：{status}"

    # ==================== 活跃模式代理方法 ====================

    def enable_active_mode(self, user_id: str, duration_minutes: int = 10, group_id: Optional[str] = None) -> str:
        """启用活跃模式（代理到 active_mode_manager）"""
        return self.active_mode_manager.enable_active_mode(user_id, duration_minutes, group_id)

    def disable_active_mode(self, user_id: str, group_id: Optional[str] = None) -> str:
        """禁用活跃模式（代理到 active_mode_manager）"""
        return self.active_mode_manager.disable_active_mode(user_id, group_id)

    def get_active_mode_status(self, user_id: str, group_id: Optional[str] = None) -> str:
        """获取活跃模式状态（代理到 active_mode_manager）"""
        return self.active_mode_manager.get_active_mode_status(user_id, group_id)

    def get_all_active_modes(self) -> str:
        """获取所有活跃会话（代理到 active_mode_manager）"""
        return self.active_mode_manager.get_all_active_modes()

    # ==================== 消息处理 ====================

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
            user_nickname = data.get("user_nickname", user_id)
            group_name = data.get("group_name", "")
            platform = data.get("self", {}).get("platform", "")

            # 检查是否是指令消息
            if self.config.get("ignore_command_messages", True):
                command_prefix = sdk.env.getConfig("ErisPulse.event.command.prefix", "/")
                case_sensitive = sdk.env.getConfig("ErisPulse.event.command.case_sensitive", False)
                allow_space_prefix = sdk.env.getConfig("ErisPulse.event.command.allow_space_prefix", False)

                message_to_check = alt_message
                if allow_space_prefix:
                    message_to_check = alt_message.lstrip()

                if not case_sensitive:
                    prefix_check = message_to_check.lower().startswith(command_prefix.lower())
                else:
                    prefix_check = message_to_check.startswith(command_prefix)

                if prefix_check:
                    self.logger.debug(f"🚫 忽略指令消息 - {detail_type} - 内容: {alt_message[:50]}")
                    return

            # 记录接收到的消息
            session_desc = get_session_description(user_id, user_nickname, group_id, group_name)
            message_preview = truncate_message(alt_message, 100)
            image_info = f" [图片: {len(image_urls)}张]" if image_urls else ""
            self.logger.debug(f"📨 接收消息 - {session_desc} - 平台: {platform} - 内容: {message_preview}{image_info}")

            if not user_id:
                return

            # 检查消息长度
            if not self.reply_judge.check_message_length(alt_message, user_id, group_id):
                return

            # 检查AI是否启用
            if not self.is_ai_enabled(user_id, group_id):
                self.logger.debug(f"AI已禁用，会话: {user_id if not group_id else group_id}")
                return

            # 如果有图片，缓存起来
            if image_urls:
                self.session_manager.cache_images(user_id, image_urls, group_id)

            # 如果只有图片没有文字，使用默认文字
            if not alt_message and image_urls:
                alt_message = "[图片]"

            if not alt_message:
                return

            # 获取平台信息
            if not platform:
                return

            # 获取机器人昵称
            bot_nicknames = self.config.get("bot_nicknames", [])
            bot_nickname = bot_nicknames[0] if bot_nicknames else ""

            # 检查API配置
            if not self.ai_manager.get_client("dialogue"):
                self.logger.warning("对话AI未配置，请检查API密钥")
                await self._send_response(data, "AI服务未配置，请联系管理员配置API密钥。", platform)
                return

            # 累积消息到短期记忆
            message_segments = data.get("message", [])
            bot_ids = self.config.get("bot_ids", [])

            enhanced_message = alt_message

            for segment in message_segments:
                if segment.get("type") == "mention":
                    mention_user = str(segment.get("data", {}).get("user_id", ""))
                    mention_nickname = segment.get("data", {}).get("nickname", "")

                    if str(mention_user) in [str(bid) for bid in bot_ids]:
                        mention_text = f"@{mention_nickname or f'用户{mention_user}'}"
                        enhanced_message = alt_message.replace("@", mention_text, 1)
                        self.logger.debug(f"检测到@机器人: {mention_text}")
                        break

            await self.memory.add_short_term_memory(user_id, "user", enhanced_message, group_id, user_nickname)

            # 更新群内沉寂时间
            if group_id:
                self.session_manager.update_group_silence(user_id, group_id)

            # 先判断是否需要回复
            should_reply = await self.reply_judge.should_reply(data, alt_message, user_id, group_id, self.is_ai_enabled(user_id, group_id))

            if should_reply:
                self.logger.info(f"💬 开始处理消息 - {session_desc} - 内容: {message_preview}{image_info}")

            # 窥屏模式下，不回复时直接返回
            if not should_reply and (group_id and self.config.get("stalker_mode", {}).get("enabled", True)):
                return

            # 判断完应该回复后，进行记忆总结
            await self.handler.extract_and_save_memory(user_id, await self.memory.get_session_history(user_id, group_id), "", group_id)

            # 速率限制检查
            estimated_tokens = self.reply_judge.estimate_tokens(alt_message) * 2
            if not self.reply_judge.check_rate_limit(estimated_tokens, user_id, group_id):
                return

            # 进行意图识别
            intent_data = await self.intent.identify_intent(alt_message)
            self.logger.info(
                f"🧠 意图识别 - {session_desc} - 意图: {intent_data['intent']} "
                f"(置信度: {intent_data['confidence']:.2f})"
            )

            # 准备回复时，获取缓存的图片
            cached_image_urls = self.session_manager.get_cached_images(user_id, group_id)
            all_image_urls = list(set(image_urls + cached_image_urls))

            # 提取@（mention）信息
            mentions = self._extract_mentions_from_message(data)

            # 构建上下文信息
            context_info = {
                "user_nickname": user_nickname,
                "user_id": user_id,
                "group_name": data.get("group_name", ""),
                "group_id": group_id,
                "bot_nickname": bot_nickname,
                "platform": platform,
                "is_group": detail_type == "group",
                "mentions": mentions,
                "message_segments": data.get("message", []),
                "time": data.get("time", 0)
            }

            # 处理意图并回复
            intent_data["params"]["image_urls"] = all_image_urls
            intent_data["params"]["context_info"] = context_info
            response = await self.intent.handle_intent(intent_data, user_id, group_id)

            if response is None:
                return

            # 发送响应
            response_preview = truncate_message(response, 150)
            self.logger.info(f"💬 准备发送回复 - {session_desc} - 内容: {response_preview}")
            await self._send_response(data, response, platform)
            self.logger.info(f"✅ 回复已发送 - {session_desc}")

            # 记录回复时间
            self.session_manager.update_last_reply_time(user_id, group_id)

            # 清除已使用的图片缓存
            self.session_manager.clear_cached_images(user_id, group_id)

            # AI回复后的持续监听（群聊模式）
            if group_id:
                await self._continue_conversation_if_needed(user_id, group_id, platform)

        except Exception as e:
            self.logger.error(f"处理消息时出错: {e}")

    async def _send_response(
        self,
        data: Dict[str, Any],
        response: str,
        platform: Optional[str]
    ) -> None:
        """
        发送响应消息（使用 MessageSender）

        Args:
            data: 消息数据
            response: 响应内容
            platform: 平台类型
        """
        try:
            if not platform:
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

            # 使用统一的消息发送器
            await self.message_sender.send(platform, target_type, target_id, response)

        except Exception as e:
            self.logger.error(f"❌ 发送响应失败: {e}")

    async def _continue_conversation_if_needed(
        self,
        user_id: str,
        group_id: str,
        platform: str
    ) -> None:
        """
        AI回复后的持续监听机制

        监听后续3条消息，判断是否应该继续对话。

        Args:
            user_id: 用户ID
            group_id: 群ID
            platform: 平台类型
        """
        try:
            stalker_config = self.config.get("stalker_mode", {})

            if not stalker_config.get("continue_conversation_enabled", True):
                return

            max_messages_to_monitor = stalker_config.get("continue_max_messages", 3)
            max_duration_seconds = stalker_config.get("continue_max_duration", 120)
            bot_name = self.config.get("bot_nicknames", [""])[0]

            session_history = await self.memory.get_session_history(user_id, group_id)
            initial_history_length = len(session_history)

            start_time = time.time()
            messages_monitored = 0
            consecutive_replies = 0
            max_consecutive_replies = 2

            while messages_monitored < max_messages_to_monitor:
                if time.time() - start_time > max_duration_seconds:
                    self.logger.debug("对话连续性监听超时")
                    break

                await asyncio.sleep(2)

                current_history = await self.memory.get_session_history(user_id, group_id)
                new_messages = current_history[initial_history_length:]

                if len(new_messages) > messages_monitored:
                    messages_monitored += 1

                    should_continue = await self.ai_manager.should_continue_conversation(
                        current_history[-8:],
                        bot_name
                    )

                    if should_continue and consecutive_replies < max_consecutive_replies:
                        session_desc = get_session_description(user_id, "", group_id, "")
                        self.logger.info(f"检测到对话延续，准备继续回复（已连续回复{consecutive_replies + 1}次）")
                        consecutive_replies += 1

                        base_system_prompt = self.config.get_effective_system_prompt(user_id, group_id)
                        enhanced_system_prompt = base_system_prompt
                        if base_system_prompt:
                            enhanced_system_prompt += "\n\n【重要】回复时直接说内容，不要加「Amer：」或「xxx：」这样的前缀，你的消息会直接发出去，不需要加名字。"

                        messages = []
                        if enhanced_system_prompt:
                            messages.append({"role": "system", "content": enhanced_system_prompt})

                        messages.extend(current_history[-15:])

                        response = await self.ai_manager.dialogue(messages)

                        response_preview = truncate_message(response, 150)
                        self.logger.info(f"🔄 延续回复生成 - {session_desc} - 内容: {response_preview}")

                        await self.message_sender.send(platform, "group", group_id, response)
                        self.logger.info(f"✅ 延续回复已发送 - {session_desc}")

                        await self.memory.add_short_term_memory(user_id, "assistant", response, group_id, bot_name)

                        initial_history_length = len(await self.memory.get_session_history(user_id, group_id))
                    else:
                        self.logger.debug("对话已结束，停止延续监听")
                        break
                else:
                    continue

            if consecutive_replies >= max_consecutive_replies:
                self.logger.info(f"已达到最大连续回复次数（{max_consecutive_replies}次），停止延续对话")

        except Exception as e:
            self.logger.error(f"对话连续性监听出错: {e}")
