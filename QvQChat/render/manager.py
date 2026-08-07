"""
渲染管理器

负责：
- 软依赖 ErisPulse-Takumi（通过 sdk.module.get("Takumi") 获取，未装则禁用）
- 自由 HTML 渲染（AI 用 <|render|> 标签提供 HTML+CSS）
- 自动高度：用 measure_html 测量内容高度，避免被裁切
- 输出保存到 data/QvQChat/renders/
"""

import inspect
import os
import time
import uuid
from typing import Any, Dict, Optional

from ErisPulse import sdk

from .tag_parser import RenderRequest


class RenderManager:
    """渲染管理器"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("Render")
        self.storage = sdk.storage
        self._takumi = None
        self._render_dir = self._ensure_render_dir()

    # ==================== 能力检测 ====================

    @property
    def takumi(self):
        """懒加载 Takumi 模块（软依赖）"""
        if self._takumi is not None:
            return self._takumi
        try:
            self._takumi = sdk.module.get("Takumi")
        except Exception as e:
            self.logger.warning(f"加载 Takumi 模块异常: {e}")
            self._takumi = None
        if self._takumi is None:
            self.logger.warning(
                "Takumi 模块未找到，渲染能力已禁用。执行 epsdk install Takumi 启用。"
            )
        return self._takumi

    def is_available(self) -> bool:
        """渲染能力是否可用"""
        return bool(self.takumi) and self.config.get("render.enabled", True)

    # ==================== 目录 ====================

    def _ensure_render_dir(self) -> str:
        try:
            base = self.config.get("render.save_dir", "data/QvQChat/renders")
            if not os.path.isabs(base):
                base = os.path.join(os.getcwd(), base)
            os.makedirs(base, exist_ok=True)
            return base
        except Exception:
            return os.path.join(os.getcwd(), "data", "QvQChat", "renders")

    def _save_output(self, image_bytes: bytes, ext: str = "png") -> str:
        if not os.path.exists(self._render_dir):
            os.makedirs(self._render_dir, exist_ok=True)
        fname = f"render_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
        path = os.path.join(self._render_dir, fname)
        with open(path, "wb") as f:
            f.write(image_bytes)
        return path

    # ==================== 渲染 ====================

    async def render(self, req: RenderRequest) -> Optional[str]:
        """执行渲染请求，返回图片文件路径（失败返回 None）"""
        if not self.is_available():
            self.logger.debug("渲染不可用（Takumi 未安装或已禁用）")
            return None

        takumi = self.takumi
        try:
            return await self._render_html(takumi, req.html, req.css)
        except Exception as e:
            self.logger.warning(f"渲染失败: {e}")
            return None

    async def _render_html(self, takumi, html: str, css: str) -> Optional[str]:
        """通过 Takumi 渲染 HTML → 保存 → 返回路径"""
        fmt = self.config.get("render.output_format", "png")
        width = int(self.config.get("render.default_width", 800))
        height = int(self.config.get("render.default_height", 600))

        stylesheets = [css] if css else None

        # 自动高度：height=None 让 takumi 按内容自动适配（不裁切）
        if self.config.get("render.auto_height", True):
            height = None

        kwargs = dict(
            html=html,
            stylesheets=stylesheets,
            width=width,
            height=height,
            format=fmt,
            lang="zh-CN",
        )

        self.logger.debug(
            f"渲染请求: html={len(html)}字符, css={len(css or '')}字符, "
            f"stylesheets={'有' if stylesheets else '无'}"
        )

        fn = getattr(takumi, "render_html")
        result = fn(**kwargs)
        if inspect.isawaitable(result):
            result = await result

        if isinstance(result, bytes) and result:
            path = self._save_output(result, fmt)
            self.logger.info(f"渲染完成: {path} ({width}x{height})")
            return path

        self.logger.warning("Takumi 渲染返回空结果")
        return None

    # ==================== 风格建议 ====================

    def get_style_guide(self) -> str:
        """获取渲染风格建议（注入 AI 提示词，可在配置中关闭）"""
        return (
            "【渲染能力】使用 <|render|><div>内容</div>||css||CSS</|render|> "
            "渲染图片时，遵循以下设计原则：\n"
            "1. 配色：先定 2-4 个协调色（深底+高对比强调色，或浅底+柔和强调色），"
            "用 hex 值。避免默认的米色底+陶土色衬线这类 AI 模板感。\n"
            "2. 排版有主次，标题和正文区分字号/字重。\n"
            "3. 布局：紧凑、留白克制；卡片用圆角+内边距；别堆砌装饰。\n"
            "4. 文字必须用 HTML（div/span），绝不要用 SVG <text>（不渲染）。"
        )
