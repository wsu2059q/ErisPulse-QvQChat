"""
AI 时间叙述器

由 AI 生成自然、多样的时间感知叙述，替代硬编码时间段文案。
按小时缓存控制 AI 调用成本，失败时降级到静态描述。
"""

import random
import time
from datetime import datetime
from typing import Optional, Tuple


class TimeNarrator:
    """AI 时间叙述器

    - 概率注入（pipeline.time_inject_probability，默认 0.7）
    - 按小时缓存（pipeline.time_cache_ttl，默认 3600 秒）
    - 生成失败时降级到静态时间描述

    :param ai_engine: AIEngine 实例
    :param config: QvQConfig 配置包装器
    :param logger: 日志记录器
    """

    def __init__(self, ai_engine, config, logger):
        self.ai_engine = ai_engine
        self.config = config
        self.logger = logger
        self._cache: dict[str, Tuple[str, float]] = {}

    async def narrate(self, force: bool = False) -> str:
        """
        获取时间叙述文本

        :param force: 跳过概率检查（主动发起场景使用）
        :return: str 时间叙述文本，未命中概率或生成失败时可能为空
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
        """
        {!--< internal-use >!--} 调用 dialogue 行为生成一句时间叙述

        :param now: 当前时间
        :return: str 叙述文本，失败时降级到 _fallback
        """
        hour = now.hour

        prompt = (
            f"现在是{hour}点{now.minute}分。"
            "用一句话描述这个时间段「你」（一个在聊天的人）的身体状态或心情，"
            "别用「现在是」开头，别每次都提睡觉和困。"
            "口语化、简短、每次换一种说法。只输出这一句话。"
        )

        try:
            # 用 dialogue 行为生成时间叙述（不复用 memory 行为，避免混淆）
            result = await self.ai_engine.dialogue(
                [{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=100,
            )
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
        """
        {!--< internal-use >!--} AI 生成失败时的静态时间段描述

        :param hour: 小时（0-23）
        :return: str 兜底叙述文本
        """
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
