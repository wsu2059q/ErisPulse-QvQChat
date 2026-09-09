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

        # 会话元数据（用于主动发起对话）
        self._session_meta: Dict[str, Dict[str, str]] = {}

        # 主动发起对话相关
        self._last_incoming: Dict[str, float] = {}          # session_key -> 最后一条他人消息时间
        self._proactive_count: Dict[str, int] = {}          # session_key -> 今日主动发起次数
        self._proactive_count_date: Dict[str, str] = {}     # session_key -> 计数对应的日期
        self._last_proactive: Dict[str, float] = {}         # session_key -> 上次主动发起时间

        # 冲动值（主动发起的内驱力：聊天越热越想说话，随时间自然消退）
        self._urge: Dict[str, float] = {}                   # session_key -> 冲动值
        self._urge_ts: Dict[str, float] = {}                # session_key -> 上次累积时间
        self._global_proactive_count: int = 0               # 今日全局主动发起次数
        self._global_proactive_date: str = ""

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

    def get_last_reply_time_by_key(self, session_key: str) -> float:
        """通过会话键获取最后回复时间"""
        return self._last_reply_time.get(session_key, 0)

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

    # ==================== 会话元数据 ====================

    def update_session_meta(
        self, session_key: str, platform: str, target_type: str, target_id: str
    ) -> None:
        """更新会话元数据（平台/目标，用于主动发起对话）"""
        self._session_meta[session_key] = {
            "platform": platform,
            "target_type": target_type,
            "target_id": target_id,
        }

    def get_session_meta(self, session_key: str) -> Dict[str, str]:
        """获取会话元数据"""
        return self._session_meta.get(session_key, {})

    def get_all_session_keys(self) -> List[str]:
        """获取所有有元数据的会话键"""
        return list(self._session_meta.keys())

    # ==================== 主动发起对话支持 ====================

    def update_last_incoming(self, session_key: str) -> None:
        """
        记录会话最后一条他人消息时间

        :param session_key: 会话标识
        """
        self._last_incoming[session_key] = time.time()

    def get_last_incoming_time(self, session_key: str) -> float:
        """
        获取会话最后一条他人消息时间

        :param session_key: 会话标识
        :return: float Unix 时间戳，无记录返回 0
        """
        # 优先用 _last_incoming（覆盖群聊+私聊）
        t = self._last_incoming.get(session_key, 0)
        if t > 0:
            return t
        # 回退：群聊可从 _group_silence 取（历史信号，兼容旧逻辑）
        if session_key.startswith("group:"):
            data = self._group_silence.get(session_key, {})
            return data.get("last_message_time", 0)
        return 0

    def check_proactive_daily_limit(self, session_key: str, max_per_day: int) -> bool:
        """
        检查会话今日主动发起次数是否已达上限（按自然日计数）

        :param session_key: 会话标识
        :param max_per_day: 每日上限次数
        :return: bool 未达上限返回 True
        """
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        if self._proactive_count_date.get(session_key) != today:
            self._proactive_count_date[session_key] = today
            self._proactive_count[session_key] = 0
        return self._proactive_count.get(session_key, 0) < max_per_day

    def increment_proactive_count(self, session_key: str) -> None:
        """
        会话主动发起计数递增

        :param session_key: 会话标识
        """
        self._proactive_count[session_key] = (
            self._proactive_count.get(session_key, 0) + 1
        )

    def check_global_proactive_limit(self, max_per_day: int) -> bool:
        """
        检查今日全局主动发起次数是否已达上限（按自然日计数）

        :param max_per_day: 每日全局上限次数
        :return: bool 未达上限返回 True
        """
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        if self._global_proactive_date != today:
            self._global_proactive_date = today
            self._global_proactive_count = 0
        return self._global_proactive_count < max_per_day

    def increment_global_proactive(self) -> None:
        """全局主动发起计数递增"""
        self._global_proactive_count += 1

    # ==================== 冲动值 ====================

    # 冲动值半衰期（秒）
    URGE_HALF_LIFE = 7200.0
    # 冲动值上限
    URGE_MAX = 2.0

    def _decayed_urge(self, session_key: str, now: float) -> float:
        """
        {!--< internal-use >!--} 计算按半衰期衰减后的冲动值

        :param session_key: 会话标识
        :param now: 当前 Unix 时间戳
        :return: float 衰减后的冲动值
        """
        urge = self._urge.get(session_key, 0.0)
        ts = self._urge_ts.get(session_key, 0)
        if urge <= 0 or ts <= 0:
            return max(urge, 0.0)
        elapsed = now - ts
        if elapsed <= 0:
            return urge
        return urge * (0.5 ** (elapsed / self.URGE_HALF_LIFE))

    def add_urge(self, session_key: str, message: str) -> float:
        """
        根据新消息累积会话冲动值（主动发起的内驱力指标）

        权重：基础 0.06；提问 +0.12；感叹号 +0.05；长消息(>=20字) +0.04。
        触发阈值为 1.0，由 human_state.proactive_message.urge_threshold 配置。

        :param session_key: 会话标识
        :param message: 消息文本
        :return: float 累积后的冲动值（上限 2.0）
        """
        now = time.time()
        urge = self._decayed_urge(session_key, now)

        t = (message or "").strip()
        if t:
            urge += 0.06
            if self._is_question(t):
                urge += 0.12
            if "!" in t or "！" in t:
                urge += 0.05
            if len(t) >= 20:
                urge += 0.04

        urge = min(urge, self.URGE_MAX)
        self._urge[session_key] = urge
        self._urge_ts[session_key] = now
        return urge

    def get_urge(self, session_key: str) -> float:
        """
        获取会话当前冲动值（含时间衰减）

        :param session_key: 会话标识
        :return: float 当前冲动值
        """
        return self._decayed_urge(session_key, time.time())

    def reset_urge(self, session_key: str) -> None:
        """
        冲动值清零（主动发送成功后调用）

        :param session_key: 会话标识
        """
        self._urge[session_key] = 0.0
        self._urge_ts[session_key] = time.time()

    def decay_urge(self, session_key: str, factor: float = 0.5) -> None:
        """
        冲动值按系数衰减（AI 选择沉默后调用，避免下一轮检查立即重复触发）

        :param session_key: 会话标识
        :param factor: 衰减系数，0~1
        """
        now = time.time()
        urge = self._decayed_urge(session_key, now) * factor
        self._urge[session_key] = urge
        self._urge_ts[session_key] = now

    def mark_proactive_sent(self, session_key: str) -> None:
        """
        记录主动发起时间（未回复冷却的判断依据）

        :param session_key: 会话标识
        """
        self._last_proactive[session_key] = time.time()

    def is_proactive_pending_reply(
        self, session_key: str, cooldown_hours: float
    ) -> bool:
        """
        判断上次主动发起是否仍未被回复且处于冷却期内

        主动消息发出后无任何来消息视为未回复，冷却期内该会话不再
        参与主动发起；期间对方有来消息则不冷却。

        :param session_key: 会话标识
        :param cooldown_hours: 冷却时长（小时）
        :return: bool 处于冷却期返回 True
        """
        sent_at = self._last_proactive.get(session_key, 0)
        if not sent_at:
            return False
        last_incoming = self.get_last_incoming_time(session_key)
        if last_incoming > sent_at:
            return False
        return time.time() - sent_at < cooldown_hours * 3600

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
            stalker = {**stalker, "default_probability": float(stalker.get("default_probability", 0.03)) * 2,
                       "hot_topic_probability": float(stalker.get("hot_topic_probability", 0.3)) * 2}

        # 每小时限制
        max_per_hour = int(stalker.get("max_replies_per_hour", 8))
        if not self.check_hourly_limit(user_id, group_id, max_per_hour):
            self.logger.debug("每小时回复上限已达")
            return False

        # 层级2：提问检测（零成本）
        is_question = self._is_question(alt_message)
        if is_question:
            question_prob = float(stalker.get("question_probability", 0.6))
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
        silence_threshold = float(stalker.get("silence_threshold_minutes", 30))
        silence_duration = self.get_group_silence_duration(user_id, group_id)
        if silence_duration > silence_threshold * 60:
            # 沉寂后第一条消息，用AI判断
            self.logger.debug(f"群内沉寂{int(silence_duration / 60)}分钟，AI判断")
            should = await self._should_reply_ai(
                ai_engine, data, alt_message, user_id, group_id, bot_nicknames
            )
            if should:
                self.increment_hourly_count(user_id, group_id)
            return should

        # 层级4：消息间隔 + 概率
        min_messages = int(stalker.get("min_messages_between_replies", 15))
        count = self.get_message_count(user_id, group_id)
        if count < min_messages:
            self.increment_message_count(user_id, group_id)
            return False

        self.reset_message_count(user_id, group_id)

        # 基础概率 + 热度加成
        base_prob = float(stalker.get("default_probability", 0.03))
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
                ai_engine, data, alt_message, user_id, group_id, bot_nicknames
            )
            self.logger.info(f"AI判断结果: {'回复' if should else '不回复'} (热度:{heat:.2f})")
            if should:
                self.increment_hourly_count(user_id, group_id)
            return should

        # 表情/表情包触发（不消耗AI，纯随机）
        sticker_prob = float(stalker.get("sticker_emoji_probability", 0))
        if sticker_prob > 0 and random.random() < sticker_prob:
            if heat > 0.3:
                self.logger.info(f"表情触发 ({sticker_prob}, 热度:{heat:.2f})")
                self.increment_hourly_count(user_id, group_id)
                return True

        return False

    async def _should_reply_ai(
        self, ai_engine, data, alt_message, user_id, group_id, bot_nicknames
    ) -> bool:
        """AI智能判断是否回复"""
        from ..chat.memory import QvQMemory

        memory = QvQMemory(self.config, None)
        history = await memory.get_session_history(user_id, group_id)

        # 检查@（仅使用事件 self.user_id）
        self_user_id = str(data.get("self", {}).get("user_id", ""))
        segments = data.get("message", [])
        is_mentioned = False
        mention_info = ""
        for seg in segments:
            if seg.get("type") == "mention":
                uid = str(seg.get("data", {}).get("user_id", ""))
                nick = seg.get("data", {}).get("nickname", "")
                if uid and uid == self_user_id:
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
