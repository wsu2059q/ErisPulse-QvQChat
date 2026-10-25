from __future__ import annotations

from .. import texts
from ..agent.tools import Tool, ToolRegistry


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _s(**simple) -> dict:
    return simple


async def load_skill(ctx, name: str) -> str:
    skill = ctx.main.skills.get_skill(name)
    if skill is None:
        return texts.t("skills_not_found", name=name)
    body = skill.get("body") or ""
    if not body:
        return texts.t("skills_no_body", name=name)
    from ..utils import truncate

    return truncate(body, 8000)


async def list_skills(ctx) -> str:
    skills = ctx.main.skills.list_skills()
    enabled = [s for s in skills if s.get("enabled")]
    if not enabled:
        return texts.t("skills_none_enabled")
    return "\n".join(f"- {s['name']}: {s.get('description') or ''}" for s in enabled)


async def save_skill(ctx, name: str, description: str, content: str) -> str:
    """技能自动习得落盘口：把一次运行中总结的做法保存为用户技能（dashboard 来源）。"""
    main = ctx.main
    manager = getattr(main, "skills", None)
    if manager is None:
        return texts.t("tool_error", name="save_skill", error="no skill manager")
    name = str(name or "").strip()
    description = str(description or "").strip()
    content = str(content or "").strip()
    if not name:
        return texts.t("skills_name_required")
    if not content:
        return texts.t("tool_param_error", name="save_skill", error="content is empty")
    try:
        manager.save_skill(name, description, content)
    except Exception as e:
        return texts.t("tool_error", name="save_skill", error=f"{type(e).__name__}: {e}")
    if getattr(main, "audit", None) is not None:
        try:
            main.audit("save_skill", {"name": name, "chars": len(content)}, ctx)
        except Exception:
            pass
    return texts.t("skill_saved", name=name)


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="load_skill",
        access="admin",
        description="Load the full instructions of a skill by name. Skills and their descriptions are listed in your system prompt; use this when a task matches a skill.",
        parameters=_schema({"name": _s(type="string", description="Skill name")}, ["name"]),
        handler=load_skill,
    ))
    registry.register(Tool(
        name="list_skills",
        access="admin",
        description="List currently enabled skills with their descriptions.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=list_skills,
    ))
    registry.register(Tool(
        name="save_skill",
        access="admin",
        danger=True,
        description="Save a reusable skill (numbered steps for a task routine) as a user skill. Use when the user asks to remember a workflow you just performed (\"记住这个做法/以后都这样\"). name: short lowercase-hyphen id; description: one line; content: the numbered steps with tools and key arguments.",
        parameters=_schema(
            {
                "name": _s(type="string", description="Short skill id (lowercase, hyphens, e.g. deploy-site)"),
                "description": _s(type="string", description="One-line description of when to use this skill"),
                "content": _s(type="string", description="Skill body: numbered steps with tools and key arguments"),
            },
            ["name", "description", "content"],
        ),
        handler=save_skill,
    ))
