from __future__ import annotations

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry
from ..utils import format_ts, parse_schedule


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


SCHEDULE_HELP = (
    "Formats: 'cron:minute hour day month weekday' (e.g. cron:0 9 * * 1-5) | "
    "'at:YYYY-MM-DD HH:MM' one-shot | 'in:30m' one-shot delay (m/h/d) | 'every:2h' interval. "
    "Set jitter_minutes>0 for randomized trigger (fires within N minutes after schedule time, "
    "e.g. 'daily around 16:23' -> cron:23 16 * * * + jitter_minutes=30)"
)


async def create_scheduled_task(ctx: ToolContext, name: str, schedule: str, platform: str,
                                target_type: str, target_id: str, prompt: str, persona: str = "",
                                jitter_minutes: float = 0) -> str:
    try:
        parsed = parse_schedule(schedule)
    except ValueError as e:
        return f"{texts.t('schedule_invalid', error=str(e))} | {SCHEDULE_HELP}"
    scheduler = ctx.main.scheduler
    task = scheduler.add(
        {
            "name": name,
            "schedule": parsed,
            "schedule_raw": schedule,
            "platform": platform,
            "target_type": target_type,
            "target_id": target_id,
            "prompt": prompt,
            "persona": persona or "",
            "chat_key": ctx.chat_key,
            "created_by": ctx.user_id,
            "origin": ctx.origin,
            "jitter_minutes": max(0.0, float(jitter_minutes or 0)),
        }
    )
    return texts.t("task_created", id=task["id"], next=format_ts(task["next_run"]))


async def list_scheduled_tasks(ctx: ToolContext) -> str:
    scheduler = ctx.main.scheduler
    tasks = scheduler.list()
    return utils.to_text(
        [
            {
                "id": task["id"],
                "name": task.get("name", ""),
                "schedule": task.get("schedule_raw", ""),
                "next": format_ts(task.get("next_run", 0)),
                "target": f"{task.get('platform', '')}/{task.get('target_type', '')}/{task.get('target_id', '')}",
                "prompt": task.get("prompt", ""),
                "jitter_minutes": float(task.get("jitter_minutes") or 0),
            }
            for task in tasks
        ]
    )


async def run_scheduled_task(ctx: ToolContext, task_id: str) -> str:
    """手动触发一次：立即执行任务（不影响后续计划时间）。"""
    name = ctx.main.scheduler.run_now(str(task_id))
    if not name:
        return texts.t("task_not_found", id=task_id)
    return texts.t("task_triggered", name=name, id=task_id)


async def cancel_scheduled_task(ctx: ToolContext, task_id: str) -> str:
    scheduler = ctx.main.scheduler
    if scheduler.cancel(task_id):
        return texts.t("task_cancelled", id=task_id)
    return texts.t("task_not_found", id=task_id)


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="create_scheduled_task",
        access="safe",
        description="Create a scheduled task: at the scheduled time the agent runs the prompt and sends the result to the target. " + SCHEDULE_HELP,
        parameters=_schema(
            {
                "name": _s(type="string", description="Short task name"),
                "schedule": _s(type="string", description=SCHEDULE_HELP),
                "platform": _s(type="string", description="Target platform"),
                "target_type": _s(type="string", description="user / group / channel"),
                "target_id": _s(type="string", description="Target id"),
                "prompt": _s(type="string", description="What the agent should do at trigger time"),
                "persona": _s(type="string", description="Optional persona id"),
                "jitter_minutes": _s(type="number", description="Randomized trigger window in minutes (0 = exact; fires at a random time within N minutes after schedule)"),
            },
            ["name", "schedule", "platform", "target_type", "target_id", "prompt"],
        ),
        handler=create_scheduled_task,
    ))
    registry.register(Tool(
        name="list_scheduled_tasks",
        access="safe",
        description="List all scheduled tasks.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=list_scheduled_tasks,
    ))
    registry.register(Tool(
        name="run_scheduled_task",
        access="safe",
        description="Manually trigger a scheduled task once right now (does not change its schedule).",
        parameters=_schema(
            {"task_id": _s(type="string", description="Task id")},
            ["task_id"],
        ),
        handler=run_scheduled_task,
    ))
    registry.register(Tool(
        name="cancel_scheduled_task",
        access="safe",
        description="Cancel a scheduled task by id.",
        parameters=_schema(
            {"task_id": _s(type="string", description="Task id")},
            ["task_id"],
        ),
        handler=cancel_scheduled_task,
    ))
