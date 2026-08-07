"""
记忆提取层

负责从对话历史中自动提取值得长期记忆的信息。
Phase 1 已修复 memory_process 的模型 fallback，
本层提供更清晰的提取编排和日志。
"""

import asyncio
from typing import Any, Dict, List, Optional

from ErisPulse import i18n


class MemoryExtractor:
    """记忆提取层"""

    def __init__(self, store, ai_engine, config, logger):
        self.store = store
        self.ai_engine = ai_engine
        self.config = config
        self.logger = logger

    async def extract_from_history(
        self, user_id: str, group_id: Optional[str] = None
    ) -> int:
        """从对话历史提取记忆

        :return: 提取的记忆条数
        """
        history = await self.store.get_session_history(user_id, group_id)

        min_history = self.config.get("memory.extract_min_history", 4)
        if len(history) < min_history:
            return 0

        recent = history[-8:]
        dialogue_lines = []
        for m in recent:
            content = m.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."
            role = "我" if m.get("role") == "assistant" else "对方"
            dialogue_lines.append(f"{role}: {content}")
        dialogue_text = "\n".join(dialogue_lines)

        prompt = (
            "从以下对话中提取值得长期记忆的关键信息"
            "（个人信息、偏好、重要事件、关系等）。\n"
            "如果没有值得记忆的就回复'无'。\n"
            "每条记忆一行，用 - 开头。\n\n"
            f"{dialogue_text}"
        )

        memory_timeout = float(self.config.get("memory.timeout", 60.0))
        try:
            result = await asyncio.wait_for(
                self.ai_engine.memory_process(prompt),
                timeout=memory_timeout,
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                i18n.t(
                    "QvQChat.memory_extract_timeout",
                    seconds=int(memory_timeout),
                )
            )
            return 0
        except Exception as e:
            self.logger.debug(f"记忆提取异常: {e}")
            return 0

        if not result or not result.strip() or result.strip() == "无":
            self.logger.debug(
                i18n.t("QvQChat.memory_extract_none")
            )
            return 0

        lines = [
            line.strip().lstrip("-").strip()
            for line in result.split("\n")
            if line.strip() and line.strip() != "无"
        ]

        count = 0
        for line in lines:
            added = await self.store.add_long_term(user_id, line)
            if added:
                count += 1
            if group_id:
                group_cfg = self.config.get_group_config(group_id)
                if group_cfg.get("memory_mode", "mixed") in ("mixed", "sender_only"):
                    await self.store.add_group_memory(group_id, user_id, line)

        if count > 0:
            self.logger.info(
                i18n.t("QvQChat.memory_extract_done", count=count)
            )
        else:
            self.logger.debug(
                i18n.t("QvQChat.memory_extract_none")
            )

        return count
