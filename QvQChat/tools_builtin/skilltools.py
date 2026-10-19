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
