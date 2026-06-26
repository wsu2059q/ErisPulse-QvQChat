"""
会话管理器

合并了会话跟踪、速率限制、活跃模式和回复判断。
"""

import random
import time
from typing import Any, Dict, List, Optional


class SessionManager:
    """
    会话管理器

    职责：
    - 会话标识管理
    - 消息计数和回复时间跟踪
    - 每小时回复限制
    - 图片缓存
    - 群内沉寂跟踪
    - 活跃模式管理（临时关闭窥屏模式）
    - 回复判断（概率 + AI）
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("Session")

        # 消息计数器和时间戳
        self._message_count: Dict[str, int] = {}
        self._last_reply_time: Dict[str, float] = {}
        self._hourly_reply_count: Dict[str, int] = {}
        self._last_hour_reset: Dict[str, float] = {}
        self._group_silence: Dict[str, Dict[str, float]] = {}
        self._image_cache: Dict[str, Dict[str, Any]] = {}
        self._IMAGE_CACHE_EXPIRE = 60

        # 活跃模式
        self._active_mode: Dict[str, Dict[str, Any]] = {}

        # 速率限制
        self._rate_limit_tracking: Dict[str, Dict[str, Any]] = {}

        # 预测模式缓冲区（低token模式）
        self._prediction_buffer: Dict[str, List[str]] = {}

    # ==================== 会话标识 ====================

    def get_session_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        if group_id:
            return f"group:{group_id}"
        return f"user:{user_id}"

    # ==================== 图片缓存 ====================

    def cache_images(
        self, user_id: str, image_urls: List[str], group_id: Optional[str] = None
    ) -> None:
        if not image_urls:
            return
        key = self.get_session_key(user_id, group_id)
        self._image_cache[key] = {"image_urls": image_urls, "timestamp": time.time()}

    def get_cached_images(
        self, user_id: str, group_id: Optional[str] = None
    ) -> List[str]:
        key = self.get_session_key(user_id, group_id)
        cached = self._image_cache.get(key)
        if not cached:
            return []
        if time.time() - cached["timestamp"] >= self._IMAGE_CACHE_EXPIRE:
            del self._image_cache[key]
            return []
        return cached["image_urls"]

    def clear_cached_images(self, user_id: str, group_id: Optional[str] = None) -> None:
        key = self.get_session_key(user_id, group_id)
        self._image_cache.pop(key, None)

    # ==================== 消息计数 ====================

    def increment_message_count(
        self, user_id: str, group_id: Optional[str] = None
    ) -> int:
        key = self.get_session_key(user_id, group_id)
        self._message_count[key] = self._message_count.get(key, 0) + 1
        return self._message_count[key]

    def get_message_count(self, user_id: str, group_id: Optional[str] = None) -> int:
        return self._message_count.get(self.get_session_key(user_id, group_id), 0)

    def reset_message_count(self, user_id: str, group_id: Optional[str] = None) -> None:
        self._message_count[self.get_session_key(user_id, group_id)] = 0

    def get_last_reply_time(
        self, user_id: str, group_id: Optional[str] = None
    ) -> float:
        return self._last_reply_time.get(self.get_session_key(user_id, group_id), 0)

    def update_last_reply_time(
        self, user_id: str, group_id: Optional[str] = None
    ) -> None:
        self._last_reply_time[self.get_session_key(user_id, group_id)] = time.time()

    # ==================== 群内沉寂 ====================

    def update_group_silence(
        self, user_id: str, group_id: Optional[str] = None
    ) -> None:
        if not group_id:
            return
        self._group_silence[self.get_session_key(user_id, group_id)] = {
            "last_message_time": time.time()
        }

    def get_group_silence_duration(
        self, user_id: str, group_id: Optional[str] = None
    ) -> float:
        if not group_id:
            return 0
        data = self._group_silence.get(self.get_session_key(user_id, group_id), {})
        last = data.get("last_message_time", 0)
        return time.time() - last if last else 0

    # ==================== 每小时限制 ====================

    def check_hourly_limit(
        self, user_id: str, group_id: Optional[str] = None, max_per_hour: int = 8
    ) -> bool:
        key = self.get_session_key(user_id, group_id)
        now = time.time()
        if now - self._last_hour_reset.get(key, 0) > 3600:
            self._hourly_reply_count[key] = 0
            self._last_hour_reset[key] = now
        return self._hourly_reply_count.get(key, 0) < max_per_hour

    def increment_hourly_count(
        self, user_id: str, group_id: Optional[str] = None
    ) -> int:
        key = self.get_session_key(user_id, group_id)
        self._hourly_reply_count[key] = self._hourly_reply_count.get(key, 0) + 1
        return self._hourly_reply_count[key]

    # ==================== 活跃模式 ====================

    def enable_active_mode(
        self, user_id: str, duration_minutes: int = 10, group_id: Optional[str] = None
    ) -> str:
        key = self.get_session_key(user_id, group_id)
        self._active_mode[key] = {
            "end_time": time.time() + duration_minutes * 60,
            "duration_minutes": duration_minutes,
        }
        desc = f"群聊 {group_id}" if group_id else f"私聊 {user_id}"
        self.logger.info(f"{desc} 已启用活跃模式，持续 {duration_minutes} 分钟")
        return f"活跃模式已启用，{duration_minutes}分钟后自动切回窥屏模式"

    def disable_active_mode(self, user_id: str, group_id: Optional[str] = None) -> str:
        key = self.get_session_key(user_id, group_id)
        if key in self._active_mode:
            del self._active_mode[key]
            return "活跃模式已关闭，切换回窥屏模式"
        return "当前没有启用活跃模式"

    def is_active_mode(self, user_id: str, group_id: Optional[str] = None) -> bool:
        key = self.get_session_key(user_id, group_id)
        data = self._active_mode.get(key)
        if data:
            if time.time() < data["end_time"]:
                return True
            del self._active_mode[key]
        return False

    def get_active_mode_status(
        self, user_id: str, group_id: Optional[str] = None
    ) -> str:
        key = self.get_session_key(user_id, group_id)
        data = self._active_mode.get(key)
        if data:
            remaining = int(data["end_time"] - time.time())
            if remaining > 0:
                return f"活跃模式生效中，剩余 {remaining // 60}分{remaining % 60}秒"
            del self._active_mode[key]
        return "当前是窥屏模式"

    def get_all_active_modes(self) -> str:
        if not self._active_mode:
            return "当前没有会话处于活跃模式"
        now = time.time()
        sessions = []
        for key, data in self._active_mode.items():
            remaining = int(data["end_time"] - now)
            if remaining > 0:
                desc = (
                    f"群聊 {key[6:]}" if key.startswith("group:") else f"私聊 {key[5:]}"
                )
                sessions.append(
                    f"- {desc} - 剩余 {remaining // 60}分{remaining % 60}秒"
                )
        return "\n".join(sessions) if sessions else "当前没有会话处于活跃模式"

    # ==================== 速率限制 ====================

    def check_message_length(self, message: str) -> bool:
        max_len = self.config.get("max_message_length", 1000)
        return len(message) <= max_len

    def check_rate_limit(
        self, estimated_tokens: int, user_id: str, group_id: Optional[str] = None
    ) -> bool:
        key = self.get_session_key(user_id, group_id)
        now = time.time()
        max_tokens = self.config.get("rate_limit_tokens", 20000)
        window = self.config.get("rate_limit_window", 60)
        tracking = self._rate_limit_tracking.get(key)
        if not tracking or now - tracking["start_time"] > window:
            self._rate_limit_tracking[key] = {
                "tokens": estimated_tokens,
                "start_time": now,
            }
            return True
        if tracking["tokens"] + estimated_tokens > max_tokens:
            return False
        tracking["tokens"] += estimated_tokens
        return True

    @staticmethod
    def estimate_tokens(text: str) -> int:
        chinese = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        other = len(text) - chinese
        return max(int(chinese * 0.7 + other * 0.25), 1)

    # ==================== 预测模式（低token模式） ====================

    def add_prediction_message(self, session_key: str, message: str) -> List[str]:
        """添加消息到预测缓冲区，返回当前缓冲区"""
        if session_key not in self._prediction_buffer:
            self._prediction_buffer[session_key] = []
        self._prediction_buffer[session_key].append(message)
        return self._prediction_buffer[session_key]

    def get_prediction_buffer(self, session_key: str) -> List[str]:
        return self._prediction_buffer.get(session_key, [])

    def clear_prediction_buffer(self, session_key: str) -> None:
        self._prediction_buffer.pop(session_key, None)

    # ==================== 回复判断 ====================

    async def should_reply(
        self,
        ai_engine,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str],
        bot_ids: List[str],
        bot_nicknames: List[str],
        is_ai_enabled: bool,
    ) -> bool:
        """
        判断是否应该回复

        逻辑：
        1. AI未启用 -> 不回复
        2. 私聊 -> AI判断
        3. 活跃模式 -> AI判断
        4. 窥屏模式关闭 -> AI判断
        5. 窥屏模式 -> 概率判断
        """
        if not is_ai_enabled:
            return False

        # 私聊或活跃模式：AI判断
        if not group_id or self.is_active_mode(user_id, group_id):
            return await self._should_reply_ai(
                ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
            )

        # 窥屏模式未启用：AI判断
        stalker = self.config.get("stalker_mode", {})
        if not stalker.get("enabled", True):
            return await self._should_reply_ai(
                ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
            )

        # 窥屏模式概率判断
        return await self._should_reply_stalker(
            ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
        )

    async def _should_reply_ai(
        self, ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
    ) -> bool:
        """AI智能判断是否回复"""
        from ..chat.memory import QvQMemory

        memory = QvQMemory(self.config, None)
        history = await memory.get_session_history(user_id, group_id)

        # 检查@
        segments = data.get("message", [])
        is_mentioned = False
        mention_info = ""
        for seg in segments:
            if seg.get("type") == "mention":
                uid = str(seg.get("data", {}).get("user_id", ""))
                nick = seg.get("data", {}).get("nickname", "")
                if uid in [str(b) for b in bot_ids]:
                    is_mentioned = True
                    mention_info = f" @{nick or uid} "
                    break

        enhanced = alt_message
        if is_mentioned and mention_info:
            enhanced = f"{mention_info}{alt_message}"

        bot_name = (
            bot_nicknames[0]
            if bot_nicknames
            else str(data.get("self", {}).get("user_nickname", ""))
        )
        should = await ai_engine.should_reply(history, enhanced, bot_name)

        if should:
            last = self.get_last_reply_time(user_id, group_id)
            min_interval = self.config.get("min_reply_interval", 10)
            if time.time() - last < min_interval:
                return False

        return should

    async def _should_reply_stalker(
        self, ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
    ) -> bool:
        """窥屏模式概率判断"""
        stalker = self.config.get("stalker_mode", {})

        # 每小时限制
        max_per_hour = stalker.get("max_replies_per_hour", 8)
        if not self.check_hourly_limit(user_id, group_id, max_per_hour):
            return False

        # 检查@
        segments = data.get("message", [])
        is_mentioned = False
        for seg in segments:
            if seg.get("type") == "mention":
                if str(seg.get("data", {}).get("user_id", "")) in [
                    str(b) for b in bot_ids
                ]:
                    is_mentioned = True
                    break

        bot_name = bot_nicknames[0] if bot_nicknames else ""
        if not is_mentioned and bot_name and bot_name in alt_message:
            is_mentioned = True

        if is_mentioned:
            if random.random() < stalker.get("mention_probability", 0.8):
                self.increment_hourly_count(user_id, group_id)
                return True
            return False

        # 群内沉寂检查
        silence_threshold = stalker.get("silence_threshold_minutes", 30)
        silence_duration = self.get_group_silence_duration(user_id, group_id)
        if silence_duration > silence_threshold * 60:
            should = await self._should_reply_ai(
                ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
            )
            if should:
                self.increment_hourly_count(user_id, group_id)
            return should

        # 消息间隔检查
        min_messages = stalker.get("min_messages_between_replies", 15)
        count = self.get_message_count(user_id, group_id)
        if count < min_messages:
            self.increment_message_count(user_id, group_id)
            return False

        self.reset_message_count(user_id, group_id)

        if random.random() < stalker.get("default_probability", 0.03):
            self.increment_hourly_count(user_id, group_id)
            return True

        return False
