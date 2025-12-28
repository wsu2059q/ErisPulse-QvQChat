import time
import asyncio
from typing import Dict, List, Optional, Any
from ErisPulse import sdk
from ErisPulse.Core.Event import message

from .config import QvQConfig
from .memory import QvQMemory
from .ai_client import QvQAIManager
from .intent import QvQIntent
from .state import QvQState
from .handler import QvQHandler
from .commands import QvQCommands


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

        # 初始化消息发送器
        from .utils import MessageSender
        self.message_sender = MessageSender(self.sdk.adapter, self.config.config, self.logger)

        # 消息计数器和时间戳（用于窥屏模式）
        self._message_count = {}
        self._last_reply_time = {}
        self._hourly_reply_count = {}  # 每小时回复计数
        self._last_hour_reset = {}  # 每个会话的上次重置时间

        # 群内沉寂跟踪（用于沉寂后的特殊判断）
        # key: 会话标识, value: {"last_message_time": float}
        self._group_silence = {}

        # 图片缓存（用于处理图片和文本分开发送的情况）
        # key: 会话标识, value: {"image_urls": List[str], "timestamp": float}
        self._image_cache = {}
        self._IMAGE_CACHE_EXPIRE = 60  # 图片缓存过期时间（秒）

        # 活跃模式（临时关闭窥屏模式）
        # key: 会话标识, value: {"end_time": float, "duration_minutes": int}
        self._active_mode = {}

        # AI启用状态（可以临时禁用AI）
        # key: 会话标识, value: bool (True表示启用，False表示禁用)
        self._ai_disabled = {}

        # 速率限制跟踪（防止刷token）
        # key: 会话标识, value: {"tokens": int, "start_time": float}
        self._rate_limit_tracking = {}

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
        - memory: 记忆提取AI（可选，可复用dialogue的api_key）
        - reply_judge: 回复判断AI（可选，可复用dialogue的api_key）
        - vision: 视觉AI（可选，可复用dialogue的api_key）
        - voice: 语音合成AI（可选，需要单独配置）
        """
        ai_types = ["dialogue", "memory", "intent", "intent_execution", "reply_judge", "vision"]

        # 检查每个AI是否有独立配置
        configured_ais = []  # 有独立model配置的AI
        shared_api_ais = []  # 复用dialogue api_key的AI
        missing_config_ais = []  # 完全没有配置的AI

        for ai_type in ai_types:
            ai_config = self.config.get(ai_type, {})

            # 判断AI是否有配置
            has_own_model = bool(ai_config.get("model"))
            has_own_api_key = bool(ai_config.get("api_key") and ai_config.get("api_key").strip() and ai_config.get("api_key") != "your-api-key")

            if ai_type == "dialogue":
                # dialogue必须有自己的配置
                if has_own_api_key:
                    configured_ais.append(ai_type)
                else:
                    missing_config_ais.append(ai_type)
            else:
                # 其他AI可以复用dialogue的api_key
                if has_own_model or has_own_api_key:
                    # 有自己的model或api_key配置
                    if has_own_api_key:
                        configured_ais.append(ai_type)
                    else:
                        # 只有model配置，api_key会复用dialogue的
                        shared_api_ais.append(ai_type)
                else:
                    # 完全没有配置
                    missing_config_ais.append(ai_type)

        # 输出配置状态
        if configured_ais:
            self.logger.info(f"独立配置的AI: {', '.join(configured_ais)}")
        if shared_api_ais:
            self.logger.info(f"复用dialogue API密钥的AI: {', '.join(shared_api_ais)}")

        # 只警告dialogue未配置
        if "dialogue" in missing_config_ais:
            self.logger.error(
                "对话AI未配置API密钥。QvQChat将无法正常工作。"
                "请在config.toml中配置[QvQChat.dialogue].api_key"
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

                # 尝试获取昵称（有的平台会提供）
                mention_nickname = mention_data.get("nickname", "")

                mentions.append({
                    "user_id": str(mention_user_id),
                    "nickname": mention_nickname or f"用户{mention_user_id}"
                })

        return mentions

    def _register_event_handlers(self) -> None:
        """
        注册事件监听器

        注册消息事件处理器以响应用户消息。
        """
        message.on_message(priority=999)(self._handle_message)
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

    def _check_message_length(self, message: str, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        检查消息长度是否超过限制（防止恶意刷屏）

        Args:
            message: 消息内容
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: 是否允许处理（True=允许，False=拒绝）
        """
        max_length = self.config.get("max_message_length", 1000)
        if len(message) > max_length:
            session_desc = f"群聊 {group_id}" if group_id else f"私聊 {user_id}"
            self.logger.warning(
                f"消息长度超过限制 ({len(message)} > {max_length})，忽略此消息。"
                f"会话: {session_desc}"
            )
            return False
        return True

    def _check_rate_limit(self, estimated_tokens: int, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        检查速率限制（防止刷token）

        Args:
            estimated_tokens: 估计的token数
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: 是否允许处理（True=允许，False=拒绝）
        """
        session_key = self._get_reply_count_key(user_id, group_id)
        current_time = time.time()

        # 获取速率限制配置
        max_tokens = self.config.get("rate_limit_tokens", 20000)
        window_seconds = self.config.get("rate_limit_window", 60)

        # 获取或初始化跟踪数据
        tracking = self._rate_limit_tracking.get(session_key)

        if not tracking or current_time - tracking["start_time"] > window_seconds:
            # 时间窗口已过期，重置计数
            self._rate_limit_tracking[session_key] = {
                "tokens": estimated_tokens,
                "start_time": current_time
            }
            return True

        # 检查是否超过速率限制
        if tracking["tokens"] + estimated_tokens > max_tokens:
            session_desc = f"群聊 {group_id}" if group_id else f"私聊 {user_id}"
            self.logger.warning(
                f"超过速率限制 (窗口内已有 {tracking['tokens']} tokens，"
                f"本次估计 {estimated_tokens} tokens，限制 {max_tokens} tokens/{window_seconds}秒)，"
                f"忽略此消息。会话: {session_desc}"
            )
            return False

        # 更新计数
        tracking["tokens"] += estimated_tokens
        return True

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量（粗略估计：1 token ≈ 1.5 中文字符 或 4 英文字符）

        Args:
            text: 文本内容

        Returns:
            int: 估计的token数
        """
        # 简单估算：中文字符 * 0.7 + 英文字符 * 0.25
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        estimated_tokens = int(chinese_chars * 0.7 + other_chars * 0.25)
        return max(estimated_tokens, 1)  # 至少1个token

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

    def enable_ai(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        启用AI

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self._get_reply_count_key(user_id, group_id)

        # 更新群配置
        if group_id:
            group_config = self.config.get_group_config(group_id)
            group_config["enable_ai"] = True
            self.config.set_group_config(group_id, group_config)
            session_desc = f"群聊 {group_id}"
        else:
            # 私聊直接从禁用列表中移除
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
        session_key = self._get_reply_count_key(user_id, group_id)

        # 更新群配置
        if group_id:
            group_config = self.config.get_group_config(group_id)
            group_config["enable_ai"] = False
            self.config.set_group_config(group_id, group_config)
            session_desc = f"群聊 {group_id}"
        else:
            # 私聊直接添加到禁用列表
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
        # 群聊使用配置
        if group_id:
            group_config = self.config.get_group_config(group_id)
            return group_config.get("enable_ai", True)

        # 私聊使用临时禁用列表
        session_key = self._get_reply_count_key(user_id, group_id)
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

    async def _should_reply(self, data: Dict[str, Any], alt_message: str, user_id: str, group_id: Optional[str]) -> bool:
        """
        判断是否应该回复

        判断逻辑：
        1. 私聊场景 → AI智能判断
        2. 群聊活跃模式 → AI智能判断
        3. 群聊窥屏模式 → 概率判断（只在达到最小消息间隔后）

        Args:
            data: 消息数据
            alt_message: 消息文本
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: 是否应该回复
        """
        import random

        # 私聊场景：使用AI智能判断
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
                self.logger.debug(f"活跃模式生效中，剩余 {remaining_minutes} 分钟")
                return await self._should_reply_ai(data, alt_message, user_id, group_id)
            else:
                # 活跃模式已过期，清除缓存
                del self._active_mode[session_key]
                self.logger.info("活跃模式已结束，自动切换回窥屏模式")

        # 群聊场景：检查窥屏模式是否启用
        stalker_config = self.config.get("stalker_mode", {})
        if not stalker_config.get("enabled", True):
            # 如果未启用窥屏模式，使用AI判断
            return await self._should_reply_ai(data, alt_message, user_id, group_id)
        
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

        # 检查是否被@（不受消息间隔限制）
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

        # 检查关键词匹配（不受消息间隔限制）
        reply_keywords = self.config.get("reply_strategy", {}).get("reply_on_keyword", [])
        keyword_matched = any(kw in alt_message for kw in reply_keywords)
        if keyword_matched:
            keyword_prob = stalker_config.get("keyword_probability", 0.5)
            if random.random() < keyword_prob:
                self._hourly_reply_count[session_key] = hourly_count + 1
                return True

        # 检查群内沉寂情况（特殊处理）
        silence_threshold = stalker_config.get("silence_threshold_minutes", 30)  # 默认30分钟
        last_message_time = self._group_silence.get(session_key, {}).get("last_message_time", 0)

        # 如果群内沉寂超过阈值，使用AI智能判断（不受消息间隔限制）
        if current_time - last_message_time > silence_threshold * 60:
            self.logger.info(f"群内沉寂 {int((current_time - last_message_time) / 60)} 分钟，使用AI判断")
            should_reply_ai = await self._should_reply_ai(data, alt_message, user_id, group_id)
            if should_reply_ai:
                self._hourly_reply_count[session_key] = hourly_count + 1
                return True
            else:
                self.logger.debug("AI判断不需要回复")
                return False

        # 检查消息间隔（仅对默认概率回复有效）
        min_messages = stalker_config.get("min_messages_between_replies", 15)
        last_msg_count = self._message_count.get(session_key, min_messages)

        if last_msg_count < min_messages:
            self._message_count[session_key] = last_msg_count + 1
            self.logger.debug(f"消息间隔不足 ({last_msg_count}/{min_messages})，继续沉默")
            return False

        # 达到最小间隔，开始默认概率判断
        self._message_count[session_key] = 0  # 重置计数器

        # 默认低概率回复（窥屏模式的核心）
        default_prob = stalker_config.get("default_probability", 0.03)
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
        bot_nicknames = self.config.get("bot_nicknames", [])

        is_mentioned = False
        mention_info = ""

        for segment in message_segments:
            if segment.get("type") == "mention":
                mention_user = str(segment.get("data", {}).get("user_id", ""))
                mention_nickname = segment.get("data", {}).get("nickname", "")

                if str(mention_user) in [str(bid) for bid in bot_ids]:
                    is_mentioned = True
                    # 构建@信息，让AI知道@的是谁
                    mention_info = f" @{mention_nickname or f'用户{mention_user}'} "
                    break

        # 构建增强的消息（包含@信息）
        enhanced_message = alt_message
        if is_mentioned and mention_info:
            # 将@信息添加到消息开头，让AI清楚知道被@了
            enhanced_message = f"{mention_info}{alt_message}"
            self.logger.debug(f"被@机器人，增强消息: {enhanced_message}")

        # 获取机器人名字
        bot_name = str(data.get("self", {}).get("user_nickname", ""))
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

    async def _continue_conversation_if_needed(
        self,
        user_id: str,
        group_id: str,
        _last_ai_response: str,
        platform: str
    ) -> None:
        """
        AI回复后的持续监听机制

        监听后续3条消息，判断是否应该继续对话。
        如果有相关内容，则继续一轮对话，直到没有相关话题。

        Args:
            user_id: 用户ID
            group_id: 群ID
            _last_ai_response: 上一次AI回复内容（暂未使用）
            platform: 平台类型
        """
        try:
            stalker_config = self.config.get("stalker_mode", {})

            # 检查是否启用对话连续性分析
            if not stalker_config.get("continue_conversation_enabled", True):
                return

            # 获取配置参数
            max_messages_to_monitor = stalker_config.get("continue_max_messages", 3)  # 最多监听3条消息
            max_duration_seconds = stalker_config.get("continue_max_duration", 120)  # 最多2分钟
            bot_name = self.config.get("bot_nicknames", [""])[0]

            # 获取当前的会话历史（包括刚刚的AI回复）
            session_history = await self.memory.get_session_history(user_id, group_id)
            initial_history_length = len(session_history)

            # 开始监听
            start_time = time.time()
            messages_monitored = 0
            consecutive_replies = 0
            max_consecutive_replies = 2  # 最多连续回复2次

            while messages_monitored < max_messages_to_monitor:
                # 检查时间限制
                if time.time() - start_time > max_duration_seconds:
                    self.logger.debug("对话连续性监听超时")
                    break

                # 等待一段时间再检查（避免频繁检查）
                await asyncio.sleep(2)

                # 获取最新的会话历史
                current_history = await self.memory.get_session_history(user_id, group_id)
                new_messages = current_history[initial_history_length:]

                if len(new_messages) > messages_monitored:
                    # 有新消息
                    messages_monitored += 1

                    # 使用AI分析是否应该继续
                    should_continue = await self.ai_manager.should_continue_conversation(
                        current_history[-8:],  # 最近8条消息
                        bot_name
                    )

                    if should_continue and consecutive_replies < max_consecutive_replies:
                        self.logger.info(f"检测到对话延续，准备继续回复（已连续回复{consecutive_replies + 1}次）")
                        consecutive_replies += 1

                        # 生成继续回复
                        system_prompt = self.config.get_effective_system_prompt(user_id, group_id)
                        messages = []
                        if system_prompt:
                            messages.append({"role": "system", "content": system_prompt})

                        # 添加会话历史（最近15条）
                        messages.extend(current_history[-15:])

                        # 调用对话AI
                        response = await self.ai_manager.dialogue(messages)

                        # 移除Markdown格式
                        from .utils import remove_markdown
                        response = remove_markdown(response)

                        # 发送回复
                        adapter = getattr(self.sdk.adapter, platform)
                        await adapter.Send.To("group", group_id).Text(response)
                        self.logger.info(f"已发送延续回复到 {platform} - 群聊 {group_id}")

                        # 保存AI回复到会话历史
                        await self.memory.add_short_term_memory(user_id, "assistant", response, group_id, bot_name)

                        # 更新初始历史长度
                        initial_history_length = len(await self.memory.get_session_history(user_id, group_id))
                    else:
                        # 不需要继续，停止监听
                        self.logger.debug("对话已结束，停止延续监听")
                        break
                else:
                    # 没有新消息，继续等待
                    continue

            if consecutive_replies >= max_consecutive_replies:
                self.logger.info(f"已达到最大连续回复次数（{max_consecutive_replies}次），停止延续对话")

        except Exception as e:
            self.logger.error(f"对话连续性监听出错: {e}")

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

            # 检查消息长度（防止恶意刷屏）
            if not self._check_message_length(alt_message, user_id, group_id):
                # 消息过长，直接返回
                return

            # 检查AI是否启用
            if not self.is_ai_enabled(user_id, group_id):
                self.logger.debug(f"AI已禁用，会话: {user_id if not group_id else group_id}")
                # AI禁用时不处理，但仍可响应命令
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

            # 累积消息到短期记忆（无论是否回复）
            # 解析消息段，检查是否包含@机器人
            message_segments = data.get("message", [])
            bot_ids = self.config.get("bot_ids", [])
            bot_nicknames = self.config.get("bot_nicknames", [])

            # 构建增强的消息文本（包含@信息）
            enhanced_message = alt_message

            # 检查是否有@机器人
            for segment in message_segments:
                if segment.get("type") == "mention":
                    mention_user = str(segment.get("data", {}).get("user_id", ""))
                    mention_nickname = segment.get("data", {}).get("nickname", "")

                    # 检查是否@了机器人
                    if str(mention_user) in [str(bid) for bid in bot_ids]:
                        # 将@信息转换为可读文本
                        mention_text = f"@{mention_nickname or f'用户{mention_user}'}"
                        # 替换 alt_message 中的@为具体文本
                        enhanced_message = alt_message.replace("@", mention_text, 1)
                        self.logger.debug(f"检测到@机器人: {mention_text}")
                        break

            # 存储增强的消息（包含清晰的@信息）
            await self.memory.add_short_term_memory(user_id, "user", enhanced_message, group_id, user_nickname)

            # 更新群内沉寂时间
            if group_id:
                session_key = self._get_reply_count_key(user_id, group_id)
                self._group_silence[session_key] = {"last_message_time": time.time()}

            # 先判断是否需要回复
            should_reply = await self._should_reply(data, alt_message, user_id, group_id)

            # 窥屏模式下，不回复时直接返回（不进行意图识别，节省AI请求）
            if not should_reply and (group_id and self.config.get("stalker_mode", {}).get("enabled", True)):
                self.logger.debug("AI判断不需要回复")
                return

            # 判断完应该回复后，进行记忆总结（个人和群记忆）
            await self.handler.extract_and_save_memory(user_id, await self.memory.get_session_history(user_id, group_id), "", group_id)

            # 需要回复时，进行速率限制检查
            # 估算这次对话需要的token（包括会话历史）
            estimated_tokens = self._estimate_tokens(alt_message) * 2  # 粗略估算：输入+输出
            if not self._check_rate_limit(estimated_tokens, user_id, group_id):
                # 超过速率限制，不进行回复
                return

            # 需要回复时，才进行意图识别
            intent_data = await self.intent.identify_intent(alt_message)
            self.logger.debug(
                f"用户 {user_nickname}({user_id}) 意图: {intent_data['intent']} "
                f"(置信度: {intent_data['confidence']})"
            )

            # 准备回复时，获取缓存的图片（包括本次消息的图片和之前缓存的图片）
            cached_image_urls = self._get_cached_images(user_id, group_id)
            all_image_urls = list(set(image_urls + cached_image_urls))  # 去重

            # 提取@（mention）信息
            mentions = self._extract_mentions_from_message(data)

            # 构建上下文信息（参考 event-conversion.md 标准）
            context_info = {
                "user_nickname": user_nickname,
                "user_id": user_id,
                "group_name": data.get("group_name", ""),
                "group_id": group_id,
                "bot_nickname": bot_nickname,
                "platform": platform,
                "is_group": detail_type == "group",
                "mentions": mentions,  # @的用户列表
                "message_segments": data.get("message", []),  # 原始消息段
                "time": data.get("time", 0)  # 消息时间戳
            }

            # 处理意图并回复（传递图片URL和上下文信息）
            intent_data["params"]["image_urls"] = all_image_urls
            intent_data["params"]["context_info"] = context_info
            response = await self.intent.handle_intent(intent_data, user_id, group_id)

            # 如果返回None，表示不需要回复
            if response is None:
                return

            # 发送响应
            await self._send_response(data, response, platform)

            # 记录回复时间
            session_key = self._get_reply_count_key(user_id, group_id)
            self._last_reply_time[session_key] = time.time()

            # 清除已使用的图片缓存
            if session_key in self._image_cache:
                del self._image_cache[session_key]
                self.logger.debug("已清除已使用的图片缓存")

            # AI回复后的持续监听（群聊模式）
            if group_id:
                await self._continue_conversation_if_needed(user_id, group_id, response, platform)

        except Exception as e:
            self.logger.error(f"处理消息时出错: {e}")

    async def _send_response(
        self,
        data: Dict[str, Any],
        response: str,
        platform: Optional[str]
    ) -> None:
        """
        发送响应消息（支持多消息和多语音组合）

        支持格式：
        1. <|wait time="N"|>：多消息分隔符，N为延迟秒数（1-5秒），最多3条消息
        2. <|voice style="...">...</|voice>：语音标签，每条消息可包含一个语音标签
           - style：语音风格（方言、语气等，可用自然语言描述）
           - 标签内：语音正文内容
           - 最终格式：风格<|endofprompt|>正文
           - 每条消息都可以独立包含语音，支持一次发送多条语音

        示例组合：
        ```
        第一句文本 <|voice style="开心的语气"|>第一句语音<|/voice|>
        <|wait time="2"|>
        第二句文本 <|voice style="撒娇的语气"|>第二句语音<|/voice|>
        ```

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
            self.logger.error(f"发送响应失败: {e}")
