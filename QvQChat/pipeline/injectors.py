"""
提示词注入器集合

10 个内置注入器，按 priority 排序：
  Identity(10) → Rule(20) → Scene(30) → Knowledge(50)
  → Time(60) → Mood(70) → Tool(80) → Voice(90) → Proactive(100)

记忆注入（priority 40）由 Core.py 的 _build_memory_context 独立处理，
作为单独的 system 消息注入（因为它依赖当前消息做相关性检索）。
"""

from typing import Any

from .base import Injector, PromptContext
from .time_narrator import TimeNarrator


# ==================== 身份与规则 ====================


class IdentityInjector(Injector):
    """多智能体人格注入"""

    id = "identity"
    priority = 10

    async def build(self, ctx: PromptContext) -> str:
        if not self.config.get("multi_agent.enabled", True):
            return "你是一个真实的普通人，不是AI助手。"

        session_key = self.main.session.get_session_key(ctx.user_id, ctx.group_id)
        agent_prompt = self.main.multi_agent.get_effective_prompt(session_key)
        if agent_prompt:
            return agent_prompt

        if ctx.group_id:
            group_prompt = self.config.get_group_config(ctx.group_id).get("system_prompt", "")
            if group_prompt:
                return group_prompt

        return "你是一个真实的普通人，不是AI助手。"


class RuleInjector(Injector):
    """对话格式规则注入（dialogue 行为提示词）"""

    id = "rule"
    priority = 20

    async def build(self, ctx: PromptContext) -> str:
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
        if not self.config.get("knowledge_base.enabled", True):
            return ""

        max_tokens = self.config.get("knowledge_base.max_context_tokens", 2000)
        keyword = ctx.user_input if self.config.get("knowledge_base.auto_search", True) else None
        kb_ctx = self.main.knowledge_base.build_context(max_tokens=max_tokens, keyword=keyword)
        return kb_ctx or ""


# ==================== 时间叙述（AI 驱动） ====================


class TimeInjector(Injector):
    """AI 时间叙述注入（替代硬编码 _get_time_description）

    70% 概率注入（30% 不注入更拟人），按小时缓存。
    """

    id = "time"
    priority = 60

    def __init__(self, main_module: Any = None):
        super().__init__(main_module)
        self._narrator: TimeNarrator | None = None

    def _get_narrator(self) -> TimeNarrator:
        if self._narrator is None:
            self._narrator = TimeNarrator(
                self.main.ai_engine, self.config, self.logger
            )
        return self._narrator

    async def build(self, ctx: PromptContext) -> str:
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
        state_cfg = self.config.get("human_state", {})
        if not state_cfg.get("enabled", True):
            return ""
        if not self.config.get("humanize.mood_aware", True):
            return ""

        session_key = "global"
        state = self.main._get_human_state(session_key)
        mood_desc = self.main._mood_to_text(state["mood"])
        energy_desc = self.main._energy_to_text(state["energy"])
        return f"你现在的状态: {mood_desc}，{energy_desc}"


# ==================== 工具 ====================


class ToolInjector(Injector):
    """MCP 工具使用提示"""

    id = "tool"
    priority = 80

    async def build(self, ctx: PromptContext) -> str:
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
    """语音功能使用提示"""

    id = "voice"
    priority = 90

    async def build(self, ctx: PromptContext) -> str:
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
    """主动发起对话上下文（精简版，替代几百字模板）

    只给：时间叙述 + 状态 + 沉默时长 + 简短任务定位 + 历史参考约束。
    """

    id = "proactive"
    priority = 100

    async def build(self, ctx: PromptContext) -> str:
        if not ctx.is_proactive:
            return ""

        parts = []

        if ctx.reply_gap:
            parts.append(f"距离你上次开口说话：{ctx.reply_gap}")
        if ctx.incoming_gap:
            parts.append(f"距离对方最后一条消息：{ctx.incoming_gap}")

        parts.append(
            "【这是主动发起，不是回复】你想起来要说点什么"
            "——不是在回应别人刚说的话，是自己突然想开口。"
        )
        parts.append(
            "1~2句，简短自然口语化。"
            "不要解释为什么突然说话。"
            "不要回头接最后一条消息。"
            "如果实在没什么想说的，只输出「(沉默)」。"
        )
        parts.append("【下面的历史仅供回忆上下文，禁止直接回应】")

        return "\n".join(parts)


# ==================== 注册所有注入器 ====================


def create_default_injectors(main_module: Any) -> list[Injector]:
    """创建所有默认注入器"""
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
