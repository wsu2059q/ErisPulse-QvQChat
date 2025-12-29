"""
回复判断器

负责判断是否应该回复：
- 速率限制检查
- 消息长度检查
- 窥屏模式概率判断
- AI智能判断
"""
import time
import random
from typing import Dict, Any, Optional


class ReplyJudge:
    """
    回复判断器

    判断是否应该回复消息，包括速率限制、消息长度检查、窥屏模式判断等。
    """

    def __init__(self, config, ai_manager, session_manager, logger):
        self.config = config
        self.ai_manager = ai_manager
        self.session_manager = session_manager
        self.logger = logger.get_child("ReplyJudge")

    def check_message_length(self, message: str, user_id: str, group_id: Optional[str] = None) -> bool:
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
            session_key = self.session_manager.get_reply_count_key(user_id, group_id)
            self.logger.warning(
                f"消息长度超过限制 ({len(message)} > {max_length})，忽略此消息。"
                f"会话: {session_key}"
            )
            return False
        return True

    def check_rate_limit(self, estimated_tokens: int, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        检查速率限制（防止刷token）

        Args:
            estimated_tokens: 估计的token数
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: 是否允许处理（True=允许，False=拒绝）
        """
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)
        current_time = time.time()

        # 获取速率限制配置
        max_tokens = self.config.get("rate_limit_tokens", 20000)
        window_seconds = self.config.get("rate_limit_window", 60)

        # 获取或初始化跟踪数据（使用session_manager的内部状态）
        if not hasattr(self, '_rate_limit_tracking'):
            self._rate_limit_tracking = {}

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

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量（粗略估计：1 token ≈ 1.5 中文字符 或 4 英文字符）

        Args:
            text: 文本内容

        Returns:
            int: 估计的token数
        """
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars
        estimated_tokens = int(chinese_chars * 0.7 + other_chars * 0.25)
        return max(estimated_tokens, 1)  # 至少1个token

    async def should_reply(
        self,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str],
        is_ai_enabled: bool
    ) -> bool:
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
            is_ai_enabled: AI是否启用

        Returns:
            bool: 是否应该回复
        """
        # 检查AI是否启用
        if not is_ai_enabled:
            return False

        # 私聊场景：使用AI智能判断
        if not group_id:
            return await self._should_reply_ai(data, alt_message, user_id, group_id)

        # 检查是否处于活跃模式
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)
        if hasattr(self, 'active_mode_manager') and self.active_mode_manager.is_active_mode(user_id, group_id):
            # 活跃模式生效中，使用AI判断（积极参与聊天）
            return await self._should_reply_ai(data, alt_message, user_id, group_id)

        # 群聊场景：检查窥屏模式是否启用
        stalker_config = self.config.get("stalker_mode", {})
        if not stalker_config.get("enabled", True):
            # 如果未启用窥屏模式，使用AI判断
            return await self._should_reply_ai(data, alt_message, user_id, group_id)

        # 窥屏模式概率判断
        return await self._should_reply_stalker_mode(data, alt_message, user_id, group_id)

    async def _should_reply_ai(
        self,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str]
    ) -> bool:
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
        from .memory import QvQMemory
        memory = QvQMemory(self.config)
        session_history = await memory.get_session_history(user_id, group_id)

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
            session_key = self.session_manager.get_reply_count_key(user_id, group_id)
            last_reply = self.session_manager.get_last_reply_time(user_id, group_id)
            min_interval = self.config.get("min_reply_interval", 10)  # 默认10秒
            if time.time() - last_reply < min_interval:
                self.logger.debug(f"回复间隔不足 {min_interval} 秒，跳过回复")
                return False

        return should_reply

    async def _should_reply_stalker_mode(
        self,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str]
    ) -> bool:
        """
        窥屏模式判断是否应该回复（概率判断）

        Args:
            data: 消息数据
            alt_message: 消息文本
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: 是否应该回复
        """
        stalker_config = self.config.get("stalker_mode", {})
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)

        # 检查每小时回复限制
        max_per_hour = stalker_config.get("max_replies_per_hour", 8)
        if not self.session_manager.reset_and_check_hourly_limit(user_id, group_id, max_per_hour):
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
                self.session_manager.increment_hourly_count(user_id, group_id)
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
                self.session_manager.increment_hourly_count(user_id, group_id)
                return True

        # 检查群内沉寂情况（特殊处理）
        silence_threshold = stalker_config.get("silence_threshold_minutes", 30)  # 默认30分钟
        silence_duration = self.session_manager.get_group_silence_duration(user_id, group_id)

        # 如果群内沉寂超过阈值，使用AI智能判断（不受消息间隔限制）
        if silence_duration > silence_threshold * 60:
            self.logger.info(f"群内沉寂 {int(silence_duration / 60)} 分钟，使用AI判断")
            should_reply_ai = await self._should_reply_ai(data, alt_message, user_id, group_id)
            if should_reply_ai:
                self.session_manager.increment_hourly_count(user_id, group_id)
                return True
            else:
                self.logger.debug("AI判断不需要回复")
                return False

        # 检查消息间隔（仅对默认概率回复有效）
        min_messages = stalker_config.get("min_messages_between_replies", 15)
        current_count = self.session_manager.get_message_count(user_id, group_id)

        if current_count < min_messages:
            self.session_manager.increment_message_count(user_id, group_id)
            self.logger.debug(f"消息间隔不足 ({current_count}/{min_messages})，继续沉默")
            return False

        # 达到最小间隔，开始默认概率判断
        self.session_manager.reset_message_count(user_id, group_id)  # 重置计数器

        # 默认低概率回复（窥屏模式的核心）
        default_prob = stalker_config.get("default_probability", 0.03)
        if random.random() < default_prob:
            self.session_manager.increment_hourly_count(user_id, group_id)
            return True

        return False
