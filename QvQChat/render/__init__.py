"""
QvQChat 渲染子系统

让 AI 具备图片渲染能力（基于 ErisPulse-Takumi / takumi-py）。
软依赖：Takumi 模块未安装时渲染能力自动禁用。

触发方式：
- AI 输出 <|render|><div>...</div>||css||CSS</|render|> 自由 HTML 渲染
- 渲染风格建议可通过配置关闭（render.style_inject=false）
"""

from .manager import RenderManager
from .tag_parser import parse_render_tags, RenderRequest

__all__ = ["RenderManager", "parse_render_tags", "RenderRequest"]
