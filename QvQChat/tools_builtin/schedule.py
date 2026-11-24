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
                                jitter_minutes: float = 0, account: str = "",
                                model: str = "", task_kind: str = "") -> str:
    try:
        parsed = parse_schedule(schedule)
    except ValueError as e:
        return f"{texts.t('schedule_invalid', error=str(e))} | {SCHEDULE_HELP}"
    scheduler = ctx.main.scheduler
    task = await scheduler.add(
        {
            "name": name,
            "schedule": parsed,
            "schedule_raw": schedule,
            "platform": platform,
            "target_type": target_type,
            "target_id": target_id,
            "prompt": prompt,
            "persona": persona or "",
# 触发账户身份：缺省取创建者会话的 @账户（多账户下不发就会落到适配器默认账户）
            "account": str(account or "") or str(getattr(ctx, "self_id", "") or ""),
            "chat_key": ctx.chat_key,
            "created_by": ctx.user_id,
            "origin": ctx.origin,
            "jitter_minutes": max(0.0, float(jitter_minutes or 0)),
            "model": str(model or ""),
            "task_kind": str(task_kind or ""),
        }
    )
    return texts.t("task_created", id=task["id"], next=format_ts(task["next_run"]))


async def list_scheduled_tasks(ctx: ToolContext) -> str:
    scheduler = ctx.main.scheduler
    tasks = await scheduler.list()
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
    name = await ctx.main.scheduler.run_now(str(task_id))
    if not name:
        return texts.t("task_not_found", id=task_id)
    return texts.t("task_triggered", name=name, id=task_id)


async def cancel_scheduled_task(ctx: ToolContext, task_id: str) -> str:
    scheduler = ctx.main.scheduler
    if await scheduler.cancel(task_id):
        return texts.t("task_cancelled", id=task_id)
    return texts.t("task_not_found", id=task_id)


async def update_scheduled_task(ctx: ToolContext, task_id: str, name: str = "", schedule: str = "",
                                prompt: str = "", platform: str = "", target_type: str = "",
                                target_id: str = "", persona: str = "", model: str = "",
                                jitter_minutes: float = -1) -> str:
    """
    按 id 编辑定时任务，仅提供的字段变更，其余保留。

    :param ctx: [ToolContext] 工具上下文
    :param task_id: [str] 任务 id
    :param name: [str] 新名称 (默认: ""，保留)
    :param schedule: [str] 新计划表达式 (默认: ""，保留)
    :param prompt: [str] 新触发提示词 (默认: ""，保留)
    :param platform: [str] 新目标平台 (默认: ""，保留)
    :param target_type: [str] user / group / channel (默认: ""，保留)
    :param target_id: [str] 新目标 id (默认: ""，保留)
    :param persona: [str] 新人格 id (默认: ""，保留)
    :param model: [str] 新模型 id (默认: ""，保留)
    :param jitter_minutes: [float] 新触发抖动分钟数，-1 保留现值 (默认: -1)
    :return: [str] 更新结果 JSON；系统内置任务返回对应配置键指引
    """
    scheduler = ctx.main.scheduler
    old = next((t for t in await scheduler.list() if t.get("id") == str(task_id)), None)
    if old is None:
        return texts.t("task_not_found", id=task_id)
    if str(old.get("name") or "").startswith("qvq:"):
        key = "profile_consolidate_hours" if old.get("name") == "qvq:profile_consolidate" else "storage_maintain_hours"
        return texts.t("task_sys_edit_hint", config=key)
    try:
        parsed = parse_schedule(schedule) if schedule else old["schedule"]
    except ValueError as e:
        return f"{texts.t('schedule_invalid', error=str(e))} | {SCHEDULE_HELP}"
    task = await scheduler.add({
        "id": old["id"],
        "name": name or old.get("name", ""),
        "schedule": parsed,
        "schedule_raw": schedule or old.get("schedule_raw", ""),
        "platform": platform or old.get("platform", ""),
        "target_type": target_type or old.get("target_type", "user"),
        "target_id": target_id or old.get("target_id", ""),
        "prompt": prompt or old.get("prompt", ""),
        "persona": persona or old.get("persona", ""),
        "account": old.get("account", ""),
        "chat_key": old.get("chat_key", ""),
        "created_by": old.get("created_by", ""),
        "jitter_minutes": float(jitter_minutes) if jitter_minutes >= 0 else float(old.get("jitter_minutes") or 0),
        "model": model or old.get("model", ""),
        "task_kind": old.get("task_kind", "chat"),
    })
    return utils.to_text({"ok": True, "task": {"id": task["id"], "name": task.get("name", ""), "schedule": task.get("schedule_raw", ""), "next": format_ts(task.get("next_run", 0))}})


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
                "account": _s(type="string", description="Bot account id to send with (multi-account backends). Omit = the account of the chat where you create this task. Wrong account = message goes out as the WRONG bot"),
                "model": _s(type="string", description="Optional model id (provider:model) for this task"),
                "task_kind": _s(type="string", description="Optional task kind for model routing (e.g. chat/deep/summary)"),
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
    registry.register(Tool(
        name="update_scheduled_task",
        access="safe",
        description="Edit a scheduled task by id: only the fields you provide change, everything else is kept. Built-in qvq: tasks are config-managed (the tool will point you at the right config key). " + SCHEDULE_HELP,
        parameters=_schema(
            {
                "task_id": _s(type="string", description="Task id (from list_scheduled_tasks)"),
                "name": _s(type="string", description="New task name"),
                "schedule": _s(type="string", description="New schedule. " + SCHEDULE_HELP),
                "prompt": _s(type="string", description="New trigger-time prompt"),
                "platform": _s(type="string", description="New target platform"),
                "target_type": _s(type="string", description="user / group / channel"),
                "target_id": _s(type="string", description="New target id"),
                "persona": _s(type="string", description="New persona id"),
                "model": _s(type="string", description="New model id (provider:model)"),
                "jitter_minutes": _s(type="number", description="New randomized trigger window in minutes (-1 = keep current)"),
            },
            ["task_id"],
        ),
        handler=update_scheduled_task,
    ))
