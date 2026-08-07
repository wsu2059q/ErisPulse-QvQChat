"""
记忆意图路由

识别用户消息中的记忆操作意图（记住/忘记），
支持正则快速匹配 + AI 意图分类（可选）。

接入后说"记住我喜欢猫"会被直接存储，不再只是普通对话。
"""

import re
from typing import Any, Dict, Optional

from ErisPulse import i18n


class IntentResult:
    """意图识别结果"""

    __slots__ = ("intent", "content", "response")

    def __init__(self, intent: str, content: str = "", response: str = ""):
        self.intent = intent      # dialogue / memory_add / memory_delete
        self.content = content    # 提取出的记忆内容
        self.response = response  # 给用户的回复文本


class IntentRouter:
    """记忆意图路由"""

    ADD_PATTERNS = [
        re.compile(r"^(?:你)?(?:帮我)?记住[：:：]?\s*(.+)"),
        re.compile(r"^(?:你)?(?:帮我)?记下来[：:：]?\s*(.+)"),
        re.compile(r"^(?:你)?(?:帮我)?记一下[：:：]?\s*(.+)"),
        re.compile(r"^(?:你)?(?:帮我)?(?:把|将)?(.+?)记下来"),
        re.compile(r"^别忘了(.+)"),
        re.compile(r"^不要忘记(.+)"),
        re.compile(r"^(?:你)?(?:帮我)??(?:把|将)(.+)记住"),
    ]

    DELETE_PATTERNS = [
        re.compile(r"^(?:你)?(?:帮我)?(?:忘记|忘掉|忘了吧)[：:：]?\s*(.+)"),
        re.compile(r"^(?:你)?(?:帮我)?删除记忆[：:：]?\s*(.+)"),
        re.compile(r"^(?:你)?(?:帮我)?清空记忆\s*(.*)"),
        re.compile(r"^(?:你)?(?:帮我)?忘掉(?:关于|有关)?(.+)"),
    ]

    QUESTION_PATTERN = re.compile(r"[?？]|吗$|了吗$|了没$|了么$|没有$")

    def __init__(self, store, ai_engine, logger, config=None):
        self.store = store
        self.ai_engine = ai_engine
        self.logger = logger
        self.config = config

    async def classify(self, user_id: str, message: str, group_id: Optional[str] = None) -> IntentResult:
        """识别意图并处理

        :return: IntentResult（intent=dialogue 时 content/response 为空）
        """
        # 正则快速匹配（记住/忘记）——零延迟
        result = self._regex_classify(message)
        if result:
            return result

        # AI 意图分类（走行为系统，有短超时保护防止阻塞）
        if self.ai_engine and self.ai_engine.is_available("intent"):
            result = await self._ai_classify(user_id, message, group_id)
            if result:
                return result

        return IntentResult(intent="dialogue")

    def _regex_classify(self, message: str) -> Optional[IntentResult]:
        """正则快速匹配"""
        msg = message.strip()

        for pattern in self.DELETE_PATTERNS:
            m = pattern.match(msg)
            if m:
                content = m.group(1).strip().rstrip("。.!！?？")
                if content:
                    return IntentResult(
                        intent="memory_delete",
                        content=content,
                    )

        for pattern in self.ADD_PATTERNS:
            m = pattern.match(msg)
            if m:
                content = m.group(1).strip().rstrip("。.!！?？")
                if not content:
                    continue
                if self.QUESTION_PATTERN.search(msg):
                    continue
                return IntentResult(
                    intent="memory_add",
                    content=content,
                )

        return None

    async def _ai_classify(
        self, user_id: str, message: str, group_id: Optional[str]
    ) -> Optional[IntentResult]:
        """AI 意图分类（走行为系统，5s 超时保护防止阻塞消息流）"""
        import asyncio
        try:
            intent = await asyncio.wait_for(
                self.ai_engine.identify_intent(message),
                timeout=5,
            )
            intent = intent.strip().lower() if isinstance(intent, str) else "dialogue"

            if intent == "memory_add":
                content = await self._extract_content(message, "记住的内容")
                if content:
                    return IntentResult(intent="memory_add", content=content)
            elif intent == "memory_delete":
                content = await self._extract_content(message, "忘记的内容")
                if content:
                    return IntentResult(intent="memory_delete", content=content)
        except asyncio.TimeoutError:
            self.logger.debug("AI意图分类超时(5s)，跳过")
        except Exception as e:
            self.logger.debug(f"AI意图分类失败: {e}")

        return None

    async def _extract_content(self, message: str, desc: str) -> str:
        """从消息中提取记忆目标内容（简化版：取去掉指令词后的部分）"""
        for pattern in self.ADD_PATTERNS + self.DELETE_PATTERNS:
            m = pattern.match(message.strip())
            if m:
                return m.group(1).strip().rstrip("。.!！?？")
        return message.strip()

    async def handle_add(
        self, user_id: str, content: str, group_id: Optional[str] = None
    ) -> str:
        """处理记忆添加"""
        added = await self.store.add_long_term(
            user_id, content, important=True
        )
        if added:
            self.logger.info(f"显式记忆保存: user={user_id} content={content[:40]}")
            return i18n.t(
                "QvQChat.memory_explicit_saved",
                default=f"记住了：{content}",
                content=content,
            )
        return i18n.t(
            "QvQChat.memory_explicit_duplicate",
            default="这条我已经记过了",
        )

    async def handle_delete(
        self, user_id: str, content: str, group_id: Optional[str] = None
    ) -> str:
        """处理记忆删除"""
        deleted = await self.store.find_and_delete(user_id, content)
        if deleted > 0:
            self.logger.info(
                f"显式记忆删除: user={user_id} query={content[:40]} count={deleted}"
            )
            return i18n.t(
                "QvQChat.memory_explicit_deleted",
                default=f"已忘记关于「{content}」的记忆",
                content=content,
                count=deleted,
            )
        return i18n.t(
            "QvQChat.memory_explicit_not_found",
            default=f"没有找到关于「{content}」的记忆",
            content=content,
        )
