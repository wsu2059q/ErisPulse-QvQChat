from __future__ import annotations

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _s(**simple) -> dict:
    return simple


def _takumi_available(ctx: ToolContext) -> bool:
    try:
        return "Takumi" in ctx.sdk.module
    except Exception:
        return False


async def render_image(ctx: ToolContext, html: str, width: int = 800,
                       image_format: str = "png", stylesheets: list | None = None) -> str:


    if not _takumi_available(ctx):
        return texts.t("render_unavailable")
    if not html or not html.strip():
        return texts.t("render_need_html")
    fmt = str(image_format or "png").lower()
    if fmt not in ("png", "jpeg"):
        fmt = "png"
    try:
        result = await ctx.sdk.module.call(
            "Takumi",
            "render_card",
            html=html,
            width=int(width or 800),
            height=0,
            image_format=fmt,
            stylesheets=stylesheets or None,
        )
    except Exception as e:
        return texts.t("tool_error", name="render_image", error=str(e))
    path = result.get("path") if isinstance(result, dict) else None
    if not path:
        return texts.t("tool_error", name="render_image", error="render returned no path")
    return utils.to_text({"image_path": str(path), "bytes": result.get("bytes", 0)})


def register(registry: ToolRegistry, main) -> None:
    try:
        if "Takumi" not in main.sdk.module:
            return
    except Exception:
        return
    registry.register(Tool(
        name="render_image",
        access="admin",
        description="Render HTML/CSS into an image file via the Takumi extension — best for long text as a picture (cards, posters, tables, reports). Returns image_path: the model also receives the rendered image for review, and you can send it with send_message's image_url.",
        parameters=_schema(
            {
                "html": _s(type="string", description="Complete HTML document or body fragment; inline CSS works, keep width friendly for chat (≤900)"),
                "width": _s(type="integer", description="Viewport width in px, default 800"),
                "image_format": _s(type="string", description="png (default) or jpeg"),
                "stylesheets": _s(type="array", description="Optional CSS strings applied as extra stylesheets"),
            },
            ["html"],
        ),
        handler=render_image,
    ))
