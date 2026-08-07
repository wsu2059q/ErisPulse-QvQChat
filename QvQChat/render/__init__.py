"""
QvQChat 渲染子系统

让 AI 具备图片渲染能力（基于 ErisPulse-Takumi / takumi-py）。
软依赖：Takumi 模块未安装时渲染能力自动禁用。

两种触发方式：
- 模板渲染：AI 输出 <|render|>tpl:模板名||key=value|...|</|render|>
- 自由 HTML：AI 输出 <|render|>HTML||css||CSS</|render|>
"""

from .manager import RenderManager
from .tag_parser import parse_render_tags, RenderRequest
from .templates import get_builtin_template

__all__ = ["RenderManager", "parse_render_tags", "RenderRequest", "get_builtin_template"]
