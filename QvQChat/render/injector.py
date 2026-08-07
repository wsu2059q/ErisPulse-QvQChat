"""
渲染能力注入器

在 AI 提示词中注入渲染能力说明 + 风格建议（可配置关闭）。
仅当 Takumi 可用且 render 功能启用时生效。
"""

import random
from typing import Any

from ..pipeline.base import Injector, PromptContext


class RenderInjector(Injector):
    """教 AI 使用渲染能力 + 建议风格"""

    id = "render"
    priority = 55

    def __init__(self, main_module: Any = None):
        super().__init__(main_module)
        self._render_manager = None

    def _get_manager(self):
        if self._render_manager is None:
            self._render_manager = self.main.render_manager
        return self._render_manager

    async def build(self, ctx: PromptContext) -> str:
        rm = self._get_manager()
        if not rm.is_available():
            return ""

        # 风格建议注入可配置关闭
        if not self.config.get("render.style_inject", True):
            return ""

        prob = self.config.get("render.inject_probability", 0.5)
        if random.random() >= prob:
            return ""

        style_guide = rm.get_style_guide()
        return (
            "【渲染能力】你可以用图片渲染输出视觉效果"
            "（仅当对方要求画/做张卡片/海报，或你想配张图时使用）。\n"
            "用法：在回复中内嵌 <|render|><div>内容</div>||css||.card{样式}</|render|>，"
            "会自动渲染成图片发送；正常文字照常发送。\n"
            + style_guide
        )
