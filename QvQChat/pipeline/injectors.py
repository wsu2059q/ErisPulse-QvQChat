"""
提示词注入器集合

9 个内置注入器，按 priority 排序：
  Identity(10) → Rule(20) → Scene(30) → Knowledge(50)
  → Time(60) → Mood(70) → Tool(80) → Voice(90) → Proactive(100)

记忆注入（priority 40）由 Core.py 的 _build_memory_context 独立处理，
作为单独的 system 消息注入（因为它依赖当前消息做相关性检索）。
"""

from typing import Any

from .base import Injector, PromptContext
from .time_narrator import TimeNarrator


# ==================== 身份与规则 ====================

# 无人格绑定时的普通人基线
_FALLBACK_IDENTITY = (
    "你是一个真实的普通人，不是AI助手。"
    "你有自己的生活、喜好和脾气：会累、会烦、会摸鱼，有喜欢的和不爽的东西。"
    "聊天是因为恰好想聊，不是服务谁。别自我介绍，别问「有什么可以帮你的」。"
)


class IdentityInjector(Injector):
    """多智能体人格注入"""

    id = "identity"
    priority = 10

    async def build(self, ctx: PromptContext) -> str:
        """
        构建身份提示词：绑定智能体 → 群自定义 → 内置普通人基线

        :param ctx: 提示词上下文
        :return: str 身份提示词
        """
        if not self.config.get("multi_agent.enabled", True):
            return _FALLBACK_IDENTITY

        session_key = self.main.session.get_session_key(ctx.user_id, ctx.group_id)
        agent_prompt = self.main.multi_agent.get_effective_prompt(session_key)
        if agent_prompt:
            return agent_prompt

        if ctx.group_id:
            group_prompt = self.config.get_group_config(ctx.group_id).get("system_prompt", "")
            if group_prompt:
                return group_prompt

        return _FALLBACK_IDENTITY


class RuleInjector(Injector):
    """对话格式规则注入（dialogue 行为提示词）"""

    id = "rule"
    priority = 20

    async def build(self, ctx: PromptContext) -> str:
        """
        构建回复格式规则片段

        :param ctx: 提示词上下文（群自定义提示词存在时跳过）
        :return: str 格式规则片段
        """
        if ctx.group_id:
            group_prompt = self.config.get_group_config(ctx.group_id).get("system_prompt", "")
            if group_prompt:
                return ""

        rules = self.main.behavior_manager.get_behavior_prompt("dialogue")
        return rules or "口语化、简短、不要用任何格式。"


# ==================== 场景 ====================


class SceneInjector(Injector):
    """场景上下文（群聊/私聊、对方昵称、被@感知）"""

    id = "scene"
    priority = 30

    async def build(self, ctx: PromptContext) -> str:
        """
        构建场景上下文片段

        :param ctx: 提示词上下文
        :return: str 场景描述片段
        """
        parts = []
        parts.append("当前在群聊中。" if ctx.is_group else "当前在私聊中。")

        if ctx.user_nickname:
            parts.append(f"对方: {ctx.user_nickname}")

        if ctx.is_mentioned:
            parts.append("【你被@了】对方专门@了你，这条消息是直接对你说的，请务必回复。")

        return "\n".join(parts) if len(parts) > 1 else parts[0] if parts else ""


# ==================== 知识库 ====================


class KnowledgeInjector(Injector):
    """知识库上下文注入"""

    id = "knowledge"
    priority = 50

    async def build(self, ctx: PromptContext) -> str:
        """
        构建知识库上下文片段

        :param ctx: 提示词上下文
        :return: str 知识库内容，无命中或功能关闭时返回空字符串
        """
        if not self.config.get("knowledge_base.enabled", True):
            return ""

        max_tokens = self.config.get("knowledge_base.max_context_tokens", 2000)
        keyword = ctx.user_input if self.config.get("knowledge_base.auto_search", True) else None
        kb_ctx = self.main.knowledge_base.build_context(max_tokens=max_tokens, keyword=keyword)
        return kb_ctx or ""


# ==================== 时间叙述（AI 驱动） ====================


class TimeInjector(Injector):
    """AI 时间叙述注入

    按 pipeline.time_inject_probability 概率注入（不注入保持对话随机性），
    叙述按小时缓存，由 TimeNarrator 生成。
    """

    id = "time"
    priority = 60

    def __init__(self, main_module: Any = None):
        super().__init__(main_module)
        self._narrator: TimeNarrator | None = None

    def _get_narrator(self) -> TimeNarrator:
        """{!--< internal-use >!--} 懒加载时间叙述器"""
        if self._narrator is None:
            self._narrator = TimeNarrator(
                self.main.ai_engine, self.config, self.logger
            )
        return self._narrator

    async def build(self, ctx: PromptContext) -> str:
        """
        构建时间叙述片段

        :param ctx: 提示词上下文（is_proactive 时强制生成）
        :return: str 时间叙述，功能关闭时返回空字符串
        """
        if not self.config.get("pipeline.time_enabled", True):
            return ""
        narrator = self._get_narrator()
        return await narrator.narrate(force=ctx.is_proactive)


# ==================== 情绪/精力 ====================


class MoodInjector(Injector):
    """人类状态（情绪/精力）注入"""

    id = "mood"
    priority = 70

    async def build(self, ctx: PromptContext) -> str:
        """
        构建情绪/精力状态片段

        :param ctx: 提示词上下文
        :return: str 状态描述，功能关闭时返回空字符串
        """
        state_cfg = self.config.get("human_state", {})
        if not state_cfg.get("enabled", True):
            return ""
        if not self.config.get("humanize.mood_aware", True):
            return ""

        session_key = "global"
        state = self.main._get_human_state(session_key)
        mood_desc = self.main._mood_to_text(state["mood"])
        energy_desc = self.main._energy_to_text(state["energy"])
        return (
            f"你现在的状态: {mood_desc}，{energy_desc}"
            "（让状态自然透进语气里——开心话多、累了话少、烦躁冲一点，"
            "别直接跟对方汇报你的状态）"
        )


# ==================== 工具 ====================


class ToolInjector(Injector):
    """MCP 工具使用提示注入"""

    id = "tool"
    priority = 80

    async def build(self, ctx: PromptContext) -> str:
        """
        构建工具使用提示片段

        :param ctx: 提示词上下文
        :return: str 工具提示，无可用工具时返回空字符串
        """
        if not self.config.get("mcp.enabled", True):
            return ""
        if self.main.mcp_manager.get_stats().get("total", 0) == 0:
            return ""
        return (
            "【工具使用】你可以调用工具查询信息。"
            "获取足够信息后请用文字回复，不要持续调工具。"
        )


# ==================== 语音 ====================


class VoiceInjector(Injector):
    """语音功能使用提示注入"""

    id = "voice"
    priority = 90

    async def build(self, ctx: PromptContext) -> str:
        """
        构建语音能力提示片段

        :param ctx: 提示词上下文
        :return: str 语音提示，功能关闭或平台不支持时返回空字符串
        """
        if not self.config.get("voice.enabled", False):
            return ""
        if not self.main._platform_supports_voice(ctx.platform):
            return ""
        return (
            "你已经启用了语音功能，这是真实的可用功能。"
            '在回复中用 <|voice style="语气"|>文本<|/voice|> 格式就能发送语音。'
            "style 可以用自然语言描述任何效果（欢快、撒娇、四川话等）。"
        )


# ==================== 主动发起 ====================


class ProactiveInjector(Injector):
    """主动发起对话上下文注入

    提供时间跨度感知与任务定位，并对开场白做反模板约束
    （禁止说烂的固定开场，允许输出 (沉默) 跳过本次发起）。
    """

    id = "proactive"
    priority = 100

    # 禁用的模板化开场白
    _CLICHE_OPENERS = "早啊、早上好、晚安、在吗、在干嘛、好困啊、睡不着、又是新的一天"

    async def build(self, ctx: PromptContext) -> str:
        """
        构建主动发起场景的提示词片段

        :param ctx: 提示词上下文
        :return: str 提示词片段，非主动发起场景返回空字符串
        """
        if not ctx.is_proactive:
            return ""

        parts = []

        if ctx.reply_gap:
            parts.append(f"距离你上次开口说话：{ctx.reply_gap}")
        if ctx.incoming_gap:
            parts.append(f"距离对方最后一条消息：{ctx.incoming_gap}")

        parts.append(
            "【这是主动发起，不是回复】你刷着手机忽然想起这一个人/这个群，"
            "想说点什么——不是回应谁刚说的话，是你自己想开口。"
        )
        parts.append(
            "规矩就一条：像真人。想到什么说什么，1~2句，口语化。\n"
            f"- 这些说烂了的开场禁止使用：{self._CLICHE_OPENERS}。\n"
            "- 要么说点具体的、有内容的，要么干脆不说。\n"
            "- 没有真正想说的就只输出「(沉默)」，沉默不丢人，尬聊才丢人。\n"
            "- 不要解释你为什么突然说话，不要回头接历史里的话题。"
        )
        parts.append("【下面的历史仅供回忆上下文，禁止直接回应】")

        return "\n".join(parts)


# ==================== 注册所有注入器 ====================


def create_default_injectors(main_module: Any) -> list[Injector]:
    """
    创建全部内置注入器实例

    :param main_module: QvQChat 主模块实例
    :return: list[Injector] 按 priority 升序可用的注入器列表
    """
    return [
        IdentityInjector(main_module),
        RuleInjector(main_module),
        SceneInjector(main_module),
        KnowledgeInjector(main_module),
        TimeInjector(main_module),
        MoodInjector(main_module),
        ToolInjector(main_module),
        VoiceInjector(main_module),
        ProactiveInjector(main_module),
    ]
