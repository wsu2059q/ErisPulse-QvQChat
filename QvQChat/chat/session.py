"""
会话管理器

合并了会话跟踪、速率限制、活跃模式和回复判断。

回复策略设计（多层级）：
1. 零成本检查：@机器人、叫名字、活跃模式
2. 关键词检查：包含配置的触发关键词
3. 概率检查：基于热度、沉寂、消息间隔
4. AI检查：仅在以上都不确定时才消耗 token
"""

import random
import re
import time
from typing import Any, Dict, List, Optional


class SessionManager:
    """会话管理器"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("Session")

        self._message_count: Dict[str, int] = {}
        self._last_reply_time: Dict[str, float] = {}
        self._hourly_reply_count: Dict[str, int] = {}
        self._last_hour_reset: Dict[str, float] = {}
        self._group_silence: Dict[str, Dict[str, float]] = {}
        self._image_cache: Dict[str, Dict[str, Any]] = {}
        self._IMAGE_CACHE_EXPIRE = 60

        self._active_mode: Dict[str, Dict[str, Any]] = {}
        self._rate_limit_tracking: Dict[str, Dict[str, Any]] = {}
        self._prediction_buffer: Dict[str, List[str]] = {}

        # 话题热度跟踪
        self._topic_heat: Dict[str, float] = {}  # session_key -> heat score
        self._last_msg_time: Dict[str, float] = {}

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
        self._image_cache.pop(self.get_session_key(user_id, group_id), None)

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
        return len(message) <= self.config.get("max_message_length", 1000)

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

    # ==================== 话题热度 ====================

    def update_topic_heat(self, session_key: str, message: str) -> float:
        """
        更新话题热度

        热度影响因素：
        - 消息频率（越密越热）
        - 问号（提问升温）
        - 感叹号（情绪升温）

        Returns:
            当前热度值 (0.0 ~ 1.0+)
        """
        now = time.time()
        prev_time = self._last_msg_time.get(session_key, 0)
        self._last_msg_time[session_key] = now

        # 计算热度增量
        heat_delta = 0.05  # 基础增量

        # 消息频率：间隔越短热度越高
        if prev_time > 0:
            gap = now - prev_time
            if gap < 5:
                heat_delta += 0.15
            elif gap < 15:
                heat_delta += 0.08
            elif gap < 30:
                heat_delta += 0.03

        # 问号升温（有人在提问）
        if "?" in message or "？" in message:
            heat_delta += 0.1

        # 感叹号升温（情绪激烈）
        if "!" in message or "！" in message:
            heat_delta += 0.05

        # 累加热度并衰减
        current = self._topic_heat.get(session_key, 0)
        # 自然衰减（根据距上次消息的时间）
        if prev_time > 0:
            decay = min((now - prev_time) / 60, 1) * 0.5  # 每分钟衰减50%
            current *= 1 - decay

        current += heat_delta
        self._topic_heat[session_key] = min(current, 2.0)  # 上限2.0
        return self._topic_heat[session_key]

    def get_topic_heat(self, session_key: str) -> float:
        """获取当前话题热度"""
        return self._topic_heat.get(session_key, 0)

    # ==================== 预测模式 ====================

    def add_prediction_message(self, session_key: str, message: str) -> List[str]:
        if session_key not in self._prediction_buffer:
            self._prediction_buffer[session_key] = []
        self._prediction_buffer[session_key].append(message)
        return self._prediction_buffer[session_key]

    def get_prediction_buffer(self, session_key: str) -> List[str]:
        return self._prediction_buffer.get(session_key, [])

    def clear_prediction_buffer(self, session_key: str) -> None:
        self._prediction_buffer.pop(session_key, None)

    # ==================== 回复判断 ====================

    # 提问模式关键词（命中则高概率回复）
    QUESTION_PATTERNS = [
        r"怎么",
        r"为什么",
        r"什么",
        r"是不是",
        r"能不能",
        r"可以吗",
        r"多少",
        r"哪里",
        r"哪个",
        r"谁",
        r"何时",
        r"\?$",
        r"\？$",
        r"吗[？?]?",
        r"呢[？?]?",
    ]

    def _is_question(self, text: str) -> bool:
        """零成本判断消息是否是提问"""
        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    async def should_reply(
        self,
        ai_engine,
        data: Dict[str, Any],
        alt_message: str,
        user_id: str,
        group_id: Optional[str],
        bot_ids: List[str],
        bot_nicknames: List[str],
    ) -> bool:
        """
        群聊回复判断（多层级策略）

        层级1：零成本检查（@、叫名字、活跃模式）-> 已在 Core 中处理
        层级2：提问检测（零成本关键词）
        层级3：话题热度（基于消息频率）
        层级4：概率检查（窥屏核心）
        层级5：AI判断（仅在前4层都不确定时）

        Returns:
            bool: 是否应该回复
        """
        stalker = self.config.get("stalker_mode", {})
        session_key = self.get_session_key(user_id, group_id)

        heat = self.update_topic_heat(session_key, alt_message)

        # 根据模式调整参数
        mode = stalker.get("mode", "balanced")
        mode_mult = {"conservative": 0, "balanced": 1, "active": 2}.get(mode, 1)
        if mode_mult == 0:  # 保守模式
            stalker = {**stalker, "default_probability": 0, "hot_topic_probability": 0,
                       "sticker_emoji_probability": 0, "question_probability": 0.5}
        elif mode_mult == 2:  # 积极模式
            stalker = {**stalker, "default_probability": stalker.get("default_probability", 0.03) * 2,
                       "hot_topic_probability": stalker.get("hot_topic_probability", 0.3) * 2}

        # 每小时限制
        max_per_hour = stalker.get("max_replies_per_hour", 8)
        if not self.check_hourly_limit(user_id, group_id, max_per_hour):
            self.logger.debug("每小时回复上限已达")
            return False

        # 层级2：提问检测（零成本）
        is_question = self._is_question(alt_message)
        if is_question:
            question_prob = stalker.get("question_probability", 0.6)
            if heat > 0.5:
                question_prob = min(question_prob + 0.3, 0.95)
            if random.random() < question_prob:
                self.logger.debug(f"提问消息，概率回复 (热度:{heat:.2f})")
                self.increment_hourly_count(user_id, group_id)
                return True

        # 层级3：高热度话题 → 提高AI判断概率，不直接回复
        heat_flag = heat > 0.8 and random.random() < min(heat * 0.3, 0.7)
        if heat_flag:
            self.logger.info(f"话题热度高 ({heat:.2f})，走AI判断")

        # 层级4：沉寂后唤醒
        silence_threshold = stalker.get("silence_threshold_minutes", 30)
        silence_duration = self.get_group_silence_duration(user_id, group_id)
        if silence_duration > silence_threshold * 60:
            # 沉寂后第一条消息，用AI判断
            self.logger.debug(f"群内沉寂{int(silence_duration / 60)}分钟，AI判断")
            should = await self._should_reply_ai(
                ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
            )
            if should:
                self.increment_hourly_count(user_id, group_id)
            return should

        # 层级4：消息间隔 + 概率
        min_messages = stalker.get("min_messages_between_replies", 15)
        count = self.get_message_count(user_id, group_id)
        if count < min_messages:
            self.increment_message_count(user_id, group_id)
            return False

        self.reset_message_count(user_id, group_id)

        # 基础概率 + 热度加成
        base_prob = stalker.get("default_probability", 0.03)
        heat_bonus = min(heat * 0.05, 0.15)
        final_prob = base_prob + heat_bonus

        if random.random() < final_prob:
            self.logger.info(f"概率命中 ({final_prob:.3f}, 热度:{heat:.2f})")
            self.increment_hourly_count(user_id, group_id)
            return True

        # 热度标志触发AI判断（替代之前直接回复）
        if heat_flag:
            self.logger.info(f"热度标志触发AI判断 (热度:{heat:.2f})")
            should = await self._should_reply_ai(
                ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
            )
            self.logger.info(f"AI判断结果: {'回复' if should else '不回复'} (热度:{heat:.2f})")
            if should:
                self.increment_hourly_count(user_id, group_id)
            return should

        # 表情/表情包触发（不消耗AI，纯随机）
        sticker_prob = stalker.get("sticker_emoji_probability", 0)
        if sticker_prob > 0 and random.random() < sticker_prob:
            if heat > 0.3:
                self.logger.info(f"表情触发 ({sticker_prob}, 热度:{heat:.2f})")
                self.increment_hourly_count(user_id, group_id)
                return True

        return False

    async def _should_reply_ai(
        self, ai_engine, data, alt_message, user_id, group_id, bot_ids, bot_nicknames
    ) -> bool:
        """AI智能判断是否回复"""
        from ..chat.memory import QvQMemory

        memory = QvQMemory(self.config, None)
        history = await memory.get_session_history(user_id, group_id)

        # 检查@（优先使用事件 self.user_id）
        self_user_id = str(data.get("self", {}).get("user_id", ""))
        all_bot_ids = {self_user_id} | {str(b) for b in bot_ids if b}
        segments = data.get("message", [])
        is_mentioned = False
        mention_info = ""
        for seg in segments:
            if seg.get("type") == "mention":
                uid = str(seg.get("data", {}).get("user_id", ""))
                nick = seg.get("data", {}).get("nickname", "")
                if uid and uid in all_bot_ids:
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

        try:
            should = await ai_engine.should_reply(history, enhanced, bot_name)
        except Exception:
            return False

        # 回复间隔检查
        if should:
            last = self.get_last_reply_time(user_id, group_id)
            min_interval = self.config.get("min_reply_interval", 10)
            if time.time() - last < min_interval:
                return False

        return should
