"""
主动发起对话管理器

冲动值驱动的主动消息编排：会话冲动值由 SessionManager 维护，
本模块负责周期检查触发门槛并执行主动消息的生成与发送。

触发门槛（全部满足才开口）：
1. 睡眠作息（sleep_schedule 启用时睡眠时段跳过）
2. 全局每日上限
3. 沉寂门槛（距上次 AI 回复）
4. 冲动值阈值
5. 单会话每日上限
6. 未回复冷却（上次主动开口未被回复时跳过）
"""

import asyncio
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..pipeline import PromptContext
from ..utils import truncate_message


class ProactiveManager:
    """主动发起对话管理器

    :param main: QvQChat 主模块实例，提供 config/session/ai_engine/memory/
        pipeline/message_sender/stats 等依赖
    """

    # 检查循环初始延迟（秒）
    STARTUP_DELAY = 60
    # 检查间隔抖动幅度（乘以基准间隔）
    INTERVAL_JITTER = (0.7, 1.3)
    # 一轮检查最多主动开口的会话数
    MAX_SEND_PER_ROUND = 1

    def __init__(self, main):
        self.main = main
        self.config = main.config
        self.logger = main.logger.get_child("Proactive")

    # ==================== 循环 ====================

    async def loop(self) -> None:
        """主动发起检查主循环，间隔 = check_interval_minutes × 随机抖动"""
        await asyncio.sleep(self.STARTUP_DELAY)
        while True:
            try:
                await self.check()
            except Exception as e:
                self.logger.debug(f"主动发起循环出错: {e}")
            base = int(self.config.get(
                "human_state.proactive_message.check_interval_minutes", 30
            ))
            lo, hi = self.INTERVAL_JITTER
            interval = max(base, 5) * random.uniform(lo, hi)
            await asyncio.sleep(interval * 60)

    # ==================== 触发判定 ====================

    async def check(self) -> None:
        """执行一轮主动发起检查，命中候选会话时触发发送"""
        cfg = self.config.get("human_state.proactive_message", {})
        if not cfg.get("enabled", False):
            return
        if not self.main.ai_engine.is_available("dialogue"):
            return

        min_threshold = float(cfg.get("min_silence_hours", 6)) * 3600
        max_per_day = int(cfg.get("max_per_day", 1))
        global_max = int(cfg.get("global_max_per_day", 3))
        urge_threshold = float(cfg.get("urge_threshold", 1.0))
        cooldown_hours = float(cfg.get("unanswered_cooldown_hours", 12))

        session = self.main.session

        if self.is_asleep():
            self.logger.debug("睡眠作息中，跳过主动发起检查")
            return
        if not session.check_global_proactive_limit(global_max):
            self.logger.debug(f"主动发起已达全局每日上限({global_max})，跳过")
            return

        now = time.time()
        candidates: List[tuple] = []

        for session_key in session.get_all_session_keys():
            meta = session.get_session_meta(session_key)
            if not meta:
                continue

            # 沉寂门槛（距上次 AI 回复）
            last_reply = session.get_last_reply_time_by_key(session_key)
            if last_reply and now - last_reply < min_threshold:
                continue

            # 冲动值门槛
            urge = session.get_urge(session_key)
            if urge < urge_threshold:
                continue

            # 单会话每日上限
            if not session.check_proactive_daily_limit(session_key, max_per_day):
                self.logger.debug(f"{session_key} 主动发起已达每日上限({max_per_day})，跳过")
                continue

            # 未回复冷却
            if session.is_proactive_pending_reply(session_key, cooldown_hours):
                self.logger.debug(f"{session_key} 上次主动开口未被回复，冷却中")
                continue

            candidates.append((session_key, meta, urge))

        if not candidates:
            return

        # 一轮最多开口一次，取冲动值最高的会话
        candidates.sort(key=lambda x: x[2], reverse=True)
        session_key, meta, urge = candidates[0]
        self.logger.debug(
            f"主动发起候选 {session_key}（冲动值 {urge:.2f} ≥ {urge_threshold}）"
        )
        await self.send(session_key, meta)

    # ==================== 发送 ====================

    async def send(self, session_key: str, meta: Dict[str, str]) -> None:
        """对指定会话生成并发送主动消息

        流程：拉取带时间戳的历史 → 计算真实时间跨度 → 管线构建提示词
        → AI 生成（可输出沉默）→ 发送 → 更新冲动值与计数。

        :param session_key: 会话标识
        :param meta: 会话元数据（platform/target_type/target_id）
        """
        main = self.main
        platform = meta.get("platform", "")
        target_type = meta.get("target_type", "user")
        target_id = meta.get("target_id", "")
        if not platform or not target_id:
            return

        try:
            is_group = target_type == "group"
            user_id = "" if is_group else target_id
            group_id = target_id if is_group else None

            detailed = await main.memory.get_session_history_detailed(
                user_id or target_id, group_id
            )

            now = time.time()
            last_reply = main.session.get_last_reply_time_by_key(session_key)
            reply_silence = now - last_reply if last_reply else None
            last_incoming = main.session.get_last_incoming_time(session_key)
            incoming_silence = now - last_incoming if last_incoming else None

            ctx = PromptContext(
                user_id=user_id or target_id,
                group_id=group_id,
                platform=platform,
                is_group=is_group,
                is_proactive=True,
                reply_gap=self._humanize_duration(reply_silence),
                incoming_gap=self._humanize_duration(incoming_silence),
            )
            system_prompt = await main.pipeline.build(ctx)

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_prompt or "你是一个真实的普通人。"},
            ]
            if detailed:
                now_ts = time.time()
                for msg in detailed[-5:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    age = self._iso_to_age_seconds(msg.get("timestamp", ""), now_ts)
                    label = self._format_history_label(age, role)
                    if label:
                        content = f"{label} {content}".strip()
                    messages.append({"role": role, "content": content})

            response = await main.ai_engine.dialogue(messages)
            if not response or not isinstance(response, str):
                return
            response = response.strip()

            # AI 选择沉默：冲动值减半，避免下一轮检查立即重复触发
            if not response or main.humanizer.is_skip_response(response):
                self.logger.info(
                    f"主动发起选择沉默 - {session_key} - {truncate_message(response, 40)}"
                )
                main.session.decay_urge(session_key, 0.5)
                return

            delay = main.humanizer.calc_typing_delay(response)
            if delay > 0:
                await asyncio.sleep(delay)

            await main.message_sender.send(platform, target_type, target_id, response)
            main._stats["total_replies"] += 1

            # 冲动释放 + 计数 + 记录开口时间（未回复冷却判断依据）
            main.session.reset_urge(session_key)
            main.session.mark_proactive_sent(session_key)
            main.session.increment_proactive_count(session_key)
            main.session.increment_global_proactive()
            main.session.update_last_reply_time(user_id or target_id, group_id)

            bot_names = self.config.get("bot_nicknames", [])
            bot_name = bot_names[0] if bot_names else ""
            clean_resp = main.humanizer.clean_response_for_history(response)
            await main.memory.add_short_term_memory(
                user_id or target_id, "assistant", clean_resp, group_id, bot_name
            )
            self.logger.info(
                f"主动发起对话 - {session_key} - {truncate_message(response, 60)}"
            )
        except Exception as e:
            self.logger.debug(f"主动发起对话失败: {e}")

    # ==================== 工具方法 ====================

    def is_asleep(self) -> bool:
        """判定当前是否处于 sleep_schedule 配置的睡眠时段"""
        cfg = self.config.get("human_state.sleep_schedule", {})
        if not cfg.get("enabled", False):
            return False

        hour = datetime.now().hour
        sleep_time = int(cfg.get("sleep_time", 2))
        wake_time = int(cfg.get("wake_time", 8))
        if sleep_time > wake_time:
            return hour >= sleep_time or hour < wake_time
        return sleep_time <= hour < wake_time

    @staticmethod
    def _humanize_duration(seconds: Optional[float]) -> str:
        """{!--< internal-use >!--} 把秒数转成可读时长（x分钟/x小时/x天）"""
        if seconds is None or seconds < 0:
            return "未知"
        mins = int(seconds / 60)
        if mins < 1:
            return "不到1分钟"
        if mins < 60:
            return f"{mins}分钟"
        hours = mins / 60
        if hours < 24:
            return f"{hours:.1f}小时"
        return f"{hours / 24:.1f}天"

    @staticmethod
    def _iso_to_age_seconds(ts_iso: str, now_ts: float) -> Optional[float]:
        """{!--< internal-use >!--} ISO 时间戳转距现在秒数，解析失败返回 None"""
        if not ts_iso:
            return None
        try:
            return now_ts - datetime.fromisoformat(ts_iso).timestamp()
        except Exception:
            return None

    @staticmethod
    def _format_history_label(age_seconds: Optional[float], role: str) -> str:
        """{!--< internal-use >!--} 按消息年龄生成时效性标签，让 AI 感知话题陈旧程度"""
        if age_seconds is None or age_seconds < 0:
            return ""
        mins = age_seconds / 60
        if mins < 5:
            tag = "刚刚"
        elif mins < 60:
            tag = f"{int(mins)}分钟前"
        elif mins < 1440:
            tag = f"{mins / 60:.1f}小时前 · 话题已结束"
            if role == "user":
                tag += " · 不要直接回应这条"
        else:
            tag = f"{mins / 1440:.1f}天前 · 已过时"
        return f"【{tag}】"
