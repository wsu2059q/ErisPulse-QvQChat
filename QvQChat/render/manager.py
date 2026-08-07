"""
渲染管理器

负责：
- 软依赖 ErisPulse-Takumi（通过 sdk.module.get("Takumi") 获取，未装则禁用）
- 模板渲染（内置 + 自定义）
- 自由 HTML 渲染
- 输出保存到 data/QvQChat/renders/
"""

import os
import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk

from .tag_parser import RenderRequest
from .templates import build_template_html, get_builtin_template, get_template_catalog_text


class RenderManager:
    """渲染管理器"""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("Render")
        self.storage = sdk.storage
        self._takumi = None
        self._render_dir = self._ensure_render_dir()
        self._custom_templates: Dict[str, Dict[str, Any]] = self._load_custom_templates()

    # ==================== 能力检测 ====================

    @property
    def takumi(self):
        """懒加载 Takumi 模块（软依赖）"""
        if self._takumi is not None:
            return self._takumi
        try:
            self._takumi = sdk.module.get("Takumi")
        except Exception:
            self._takumi = None
        if self._takumi is None:
            self.logger.warning(
                "Takumi 模块未安装，渲染能力已禁用。执行 epsdk install Takumi 启用。"
            )
        return self._takumi

    def is_available(self) -> bool:
        """渲染能力是否可用"""
        return bool(self.takumi) and self.config.get("render.enabled", True)

    def list_available(self) -> bool:
        return self.is_available()

    # ==================== 目录与存储 ====================

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
        """保存渲染输出，返回文件路径"""
        if not os.path.exists(self._render_dir):
            os.makedirs(self._render_dir, exist_ok=True)
        fname = f"render_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
        path = os.path.join(self._render_dir, fname)
        with open(path, "wb") as f:
            f.write(image_bytes)
        return path

    # ==================== 模板管理 ====================

    def _load_custom_templates(self) -> Dict[str, Dict[str, Any]]:
        data = self.storage.get("QvQChat.render_templates", {})
        return data if isinstance(data, dict) else {}

    def _save_custom_templates(self) -> None:
        self.storage.set("QvQChat.render_templates", self._custom_templates)

    def get_template_names(self) -> List[str]:
        from .templates import BUILTIN_TEMPLATES
        return list(BUILTIN_TEMPLATES.keys()) + list(self._custom_templates.keys())

    def get_all_templates(self) -> List[Dict[str, Any]]:
        """返回所有模板（内置 + 自定义）"""
        from .templates import BUILTIN_TEMPLATES
        result = []
        for name, tpl in BUILTIN_TEMPLATES.items():
            result.append({
                "name": name,
                "description": tpl.get("description", ""),
                "params": tpl.get("params", {}),
                "builtin": True,
                "html": tpl.get("html", ""),
                "css": tpl.get("css", ""),
            })
        for name, tpl in self._custom_templates.items():
            result.append({
                "name": name,
                "description": tpl.get("description", ""),
                "params": tpl.get("params", {}),
                "builtin": False,
                "html": tpl.get("html", ""),
                "css": tpl.get("css", ""),
            })
        return result

    def save_template(self, name: str, html: str, css: str, description: str = "") -> None:
        """保存/更新自定义模板"""
        if not name or not html:
            return
        self._custom_templates[name] = {
            "description": description or name,
            "html": html,
            "css": css,
            "params": {},
        }
        self._save_custom_templates()
        self.logger.info(f"保存自定义渲染模板: {name}")

    def delete_template(self, name: str) -> bool:
        """删除自定义模板"""
        if name in self._custom_templates:
            del self._custom_templates[name]
            self._save_custom_templates()
            return True
        return False

    # ==================== 渲染 ====================

    async def render(self, req: RenderRequest) -> Optional[str]:
        """执行渲染请求，返回图片文件路径（失败返回 None）"""
        if not self.is_available():
            self.logger.debug("渲染不可用（Takumi 未安装或已禁用）")
            return None

        takumi = self.takumi
        try:
            if req.kind == "template":
                html = self._build_template(req.template_name, req.params)
                if not html:
                    self.logger.warning(f"模板渲染失败: 未知模板 {req.template_name}")
                    return None
                css = self._get_template_css(req.template_name)
                return await self._render_html(takumi, html, css)
            else:
                return await self._render_html(takumi, req.html, req.css)
        except Exception as e:
            self.logger.warning(f"渲染失败: {e}")
            return None

    def _build_template(self, name: str, params: Dict[str, Any]) -> Optional[str]:
        """构建模板 HTML（内置 + 自定义）"""
        if get_builtin_template(name):
            return build_template_html(name, params)
        tpl = self._custom_templates.get(name)
        if not tpl:
            return None
        html = tpl.get("html", "")
        for k, v in (params or {}).items():
            html = html.replace("{" + k + "}", str(v))
        return html

    def _get_template_css(self, name: str) -> str:
        tpl = get_builtin_template(name)
        if tpl:
            return tpl.get("css", "")
        tpl = self._custom_templates.get(name)
        return tpl.get("css", "") if tpl else ""

    async def _render_html(self, takumi, html: str, css: str) -> Optional[str]:
        """通过 Takumi 渲染 HTML → 保存 → 返回路径"""
        fmt = self.config.get("render.output_format", "png")
        width = self.config.get("render.default_width", 800)
        height = self.config.get("render.default_height", 600)

        stylesheets = [css] if css else None

        try:
            img_bytes = await takumi.render_html(
                html,
                stylesheets=stylesheets,
                width=width,
                height=height,
                format=fmt,
                lang="zh-CN",
            )
            if isinstance(img_bytes, bytes) and img_bytes:
                path = self._save_output(img_bytes, fmt)
                self.logger.info(f"渲染完成: {path}")
                return path
        except Exception as e:
            self.logger.warning(f"Takumi 渲染异常: {e}")

        # Takumi 模块可能是同步接口，尝试直接调用
        try:
            img_bytes = takumi.render_html(
                html,
                stylesheets=stylesheets,
                width=width,
                height=height,
                format=fmt,
                lang="zh-CN",
            )
            if isinstance(img_bytes, bytes) and img_bytes:
                path = self._save_output(img_bytes, fmt)
                self.logger.info(f"渲染完成(sync): {path}")
                return path
        except Exception as e:
            self.logger.warning(f"Takumi 同步渲染异常: {e}")

        return None

    def get_catalog_text(self) -> str:
        """获取模板目录（供 AI 提示词注入）"""
        return get_template_catalog_text()
