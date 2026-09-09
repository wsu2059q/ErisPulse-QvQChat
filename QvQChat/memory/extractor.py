"""
记忆提取层

负责从对话历史中自动提取值得长期记忆的信息。
Phase 1 已修复 memory_process 的模型 fallback，
本层提供更清晰的提取编排和日志。

提取提示词要求模型输出 JSON 数组（content + importance + category），
保存前按 importance 阈值过滤，并注入已有记忆做去重感知。
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

from ErisPulse import i18n


class MemoryExtractor:
    """记忆提取层"""

    # 模型可能输出的"无记忆"变体（防止误存垃圾）
    NONE_MARKERS = {
        "无", "没有", "没有值得记忆的内容", "无值得记忆的内容",
        "暂无", "[]", "null", "none",
    }

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

        # 节流：每 N 条消息提取一次（0 表示每次都提取）
        interval = int(self.config.get("memory.extract_interval", 0))
        if interval > 0 and len(history) % interval != 0:
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

        # 已有记忆（供模型去重感知，避免重复提取）
        existing = await self.store.get_user_memory(user_id)
        existing_list = [
            e.get("content", "")
            for e in existing.get("long_term", [])
        ]
        if existing_list:
            existing_text = "\n".join(f"- {c}" for c in existing_list[-20:])
        else:
            existing_text = "（无）"

        prompt = self._build_prompt(dialogue_text, existing_text)

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

        items = self._parse_result(result)
        if not items:
            self.logger.debug(
                i18n.t("QvQChat.memory_extract_none")
            )
            return 0

        threshold = float(self.config.get("memory.importance_threshold", 3))
        count = 0
        for item in items:
            content = (item.get("content") or "").strip()
            if not content:
                continue
            try:
                importance = float(item.get("importance", threshold))
            except (TypeError, ValueError):
                importance = threshold
            if importance < threshold:
                continue

            category = (item.get("category") or "").strip()
            tags = [category] if category else None
            added = await self.store.add_long_term(
                user_id, content, tags=tags, important=importance >= 4
            )
            if added:
                count += 1
            if group_id:
                group_cfg = self.config.get_group_config(group_id)
                if group_cfg.get("memory_mode", "mixed") in ("mixed", "sender_only"):
                    await self.store.add_group_memory(group_id, user_id, content)

        if count > 0:
            self.logger.info(
                i18n.t("QvQChat.memory_extract_done", count=count)
            )
        else:
            self.logger.debug(
                i18n.t("QvQChat.memory_extract_none")
            )

        return count

    def _build_prompt(self, dialogue_text: str, existing_text: str) -> str:
        """构建提取提示词"""
        return (
            "你是记忆提取助手。从对话中提取【值得长期记忆】的关键信息。\n"
            "\n"
            "【必须提取】\n"
            "- 个人信息：生日、职业、住址、感情状态（分手/恋爱/结婚）、家人关系、疾病\n"
            "- 重大事件：分手、搬家、换工作、生病、考试、获奖、失败经历\n"
            "- 偏好与习惯：喜欢/不喜欢的人事物、作息、饮食、娱乐\n"
            "- 明确的约定、承诺、目标\n"
            "\n"
            "【不要提取】\n"
            "- 纯数字、单字、表情、测试性消息、打招呼\n"
            "- 普通闲聊、客套话、AI 自己的回复内容\n"
            "- 已出现在【已有记忆】里的信息\n"
            "\n"
            "【输出格式】只输出一个 JSON 数组，不要输出任何其他内容：\n"
            '[{"content": "用户今天分手了", "importance": 5, "category": "事件"}]\n'
            "content 用简洁的一句话描述；importance 范围 1-5（5 为重大事件/强偏好）；"
            "category 可选（事件/偏好/个人信息/关系/其他）。\n"
            "如果没有任何值得记忆的，只输出 []\n"
            "\n"
            f"【已有记忆】\n{existing_text}\n"
            "\n"
            f"【对话】\n{dialogue_text}"
        )

    def _parse_result(self, result: str) -> List[Dict[str, Any]]:
        """解析模型输出，优先 JSON，失败时降级解析 "- " 行"""
        if not result:
            return []

        text = result.strip()
        if text in self.NONE_MARKERS:
            return []

        # 去除可能的 markdown 代码围栏
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            return []
        except (json.JSONDecodeError, ValueError):
            pass

        # 降级解析 "- content" 行（兼容旧格式输出）
        items = []
        for line in text.split("\n"):
            line = line.strip().lstrip("-*·▸").strip()
            if not line or line in self.NONE_MARKERS:
                continue
            items.append({"content": line, "importance": 3})
        return items
