"""
渲染能力注入器

在 AI 提示词中注入渲染能力说明 + 模板目录。
仅当 Takumi 可用且 render 功能启用时生效。
"""

from typing import Any

from ..pipeline.base import Injector, PromptContext


class RenderInjector(Injector):
    """教 AI 使用渲染能力"""

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

        prob = self.config.get("render.inject_probability", 0.5)
        import random
        if random.random() >= prob:
            return ""

        catalog = rm.get_catalog_text()
        parts = [
            "【渲染能力】你可以用图片渲染输出视觉效果（仅当对方要求画/做张卡片/海报，或你想配张图时使用）。",
            "用法1（模板，推荐）：在回复中内嵌 <|render|>tpl:模板名||key=值||key2=值</|render|>，会自动渲染成图片发送。",
            "可用模板：\n" + catalog,
            "用法2（自由 HTML）：<|render|><div>内容</div>||css||.div{样式}</|render|>，可自由写 HTML+CSS。",
            "提示：渲染标签会从文本中移除并替换为图片，正常文字照常发送。",
        ]
        return "\n".join(parts)
