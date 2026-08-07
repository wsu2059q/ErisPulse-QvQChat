"""
AI 时间叙述器

替代硬编码的 _get_time_description / _get_proactive_motivation。
让 AI 生成自然、多样的时间感知叙述，按小时缓存控制成本。
"""

import random
import time
from datetime import datetime
from typing import Optional, Tuple


class TimeNarrator:
    """AI 时间叙述器

    - 概率注入（默认 70%，30% 不注入 → 更拟人）
    - 按小时缓存（同一小时内复用，控制 AI 调用成本）
    - 失败时优雅降级到简单时间描述
    """

    def __init__(self, ai_engine, config, logger):
        self.ai_engine = ai_engine
        self.config = config
        self.logger = logger
        self._cache: dict[str, Tuple[str, float]] = {}

    async def narrate(self, force: bool = False) -> str:
        """获取时间叙述

        :param force: 强制注入（跳过概率检查，用于主动发起）
        :return: 时间叙述文本（可能为空）
        """
        if not force:
            inject_prob = self.config.get("pipeline.time_inject_probability", 0.7)
            if random.random() >= inject_prob:
                return ""

        now = datetime.now()
        cache_key = str(now.hour)

        ttl = self.config.get("pipeline.time_cache_ttl", 3600)
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[1]) < ttl:
            return cached[0]

        narration = await self._generate(now)
        if narration:
            self._cache[cache_key] = (narration, time.time())
        return narration

    async def _generate(self, now: datetime) -> str:
        """让 AI 生成一句时间叙述"""
        hour = now.hour

        prompt = (
            f"现在是{hour}点{now.minute}分。"
            "用一句话自然地描述这个时间段「你」（一个在聊天的人）的状态，"
            "比如「现在是清晨，你刚醒还有点迷糊」「深夜了，你还醒着，有点睡不着」。"
            "要求：口语化、简短、每次换一种说法。只输出这一句话。"
        )

        try:
            result = await self.ai_engine.memory_process(prompt)
            if result and isinstance(result, str):
                cleaned = result.strip().strip("\"'""''「」""")
                if cleaned and len(cleaned) < 100:
                    return cleaned
                return cleaned[:80]
        except Exception as e:
            self.logger.debug(f"AI时间叙述失败: {e}")

        return self._fallback(hour)

    @staticmethod
    def _fallback(hour: int) -> str:
        """AI 失败时的简单兜底"""
        if 5 <= hour < 8:
            return "清晨，你刚醒"
        elif 8 <= hour < 12:
            return "上午，你精神还行"
        elif 12 <= hour < 14:
            return "中午，你在吃饭"
        elif 14 <= hour < 18:
            return "下午，你有点犯困"
        elif 18 <= hour < 22:
            return "晚上，你比较放松"
        elif 22 <= hour < 24:
            return "深夜，你还醒着"
        else:
            return "半夜，你睡不着"
