from __future__ import annotations

import time
from types import SimpleNamespace
import uuid

from .. import texts, utils
from ..agent.runner import AgentRunner
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


async def spawn_agent(ctx: ToolContext, task: str, tools: list[str] | None = None, max_rounds: int = 8) -> str:
    """派生一个子智能体：独立会话独立上下文，完成后把结论交回，过程历史可在会话页查看。"""
    if str(ctx.chat_key or "").startswith("sub:"):
        return texts.t("subagent_no_nest")
    main = ctx.main
    if main is None:
        return texts.t("tool_error", name="spawn_agent", error="no main")
    task = str(task or "").strip()
    if not task:
        return texts.t("tool_param_error", name="spawn_agent", error="task is empty")
    sub_key = "sub:" + str(ctx.chat_key) + ":" + uuid.uuid4().hex[:8]
    data = vars(main.cfg).copy()
    data["max_tool_rounds"] = max(1, min(int(max_rounds or 8), 15))
    sub_cfg = SimpleNamespace(**data)
    sub_ctx = ToolContext(
        main=main,
        sdk=ctx.sdk,
        config=sub_cfg,
        chat_key=sub_key,
        session_key=sub_key,
        platform="sub",
        detail_type="private",
        target_id="agent",
        user_id=ctx.user_id,
        origin=ctx.origin,
    )
    system = texts.t("subagent_system", task=utils.truncate(task, 500))
    runner = AgentRunner(main.pool, main.registry, sub_cfg)
    main.sessions.append(sub_key, "user", task)
    main.sessions.set_group_name(sub_key, utils.truncate(task, 40))
    started = time.monotonic()
    try:
        result = await runner.run(system=system, messages=[], ctx=sub_ctx, persona_tools=[str(t) for t in (tools or [])] or None)
    except Exception as e:
        return texts.t("tool_error", name="spawn_agent", error=f"{type(e).__name__}: {e}")
    answer = (result.text or "").strip() or "-"
    main.sessions.append(sub_key, "assistant", answer, trace=result.tool_trace)
    ms = int((time.monotonic() - started) * 1000)
    meta = texts.t("subagent_meta", session=sub_key, tools=len(result.tool_trace), ms=ms)
    return answer + "\n\n" + meta


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="spawn_agent",
        access="admin",
        description="Spawn a sub-agent with an isolated session/context to explore a task independently and report back its conclusion. The sub-agent's full process history is kept as its own session (prefix 'sub:') for review.",
        parameters=_schema(
            {
                "task": _s(type="string", description="Self-contained task description for the sub-agent"),
                "tools": _s(type="array", items=_s(type="string"), description="Optional tool-name whitelist for the sub-agent"),
                "max_rounds": _s(type="integer", description="Max tool rounds for the sub-agent (1-15, default 8)"),
            },
            ["task"],
        ),
        handler=spawn_agent,
        danger=False,
    ))
