from __future__ import annotations

import asyncio
import contextlib
import io
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


async def run_python(ctx: ToolContext, code: str, timeout: int = 30) -> str:
    if getattr(ctx.config, "security_level", "standard") == "strict":
        return texts.t("code_denied")
    if not ctx.main.is_admin(ctx.user_id, ctx.origin, ctx.platform):
        return texts.t("needs_admin")
    if getattr(ctx.config, "security_level", "standard") == "standard" and not getattr(ctx.config, "trust_agent", False):
        granted = await ctx.confirm(
            texts.t("confirm_prompt", content=utils.truncate(code, 600)),
            timeout=int(getattr(ctx.config, "confirm_timeout", 60)),
        )
        if not granted:
            if ctx.main is not None:
                ctx.main.audit("run_python_denied", {"preview": utils.truncate(code, 120)}, ctx)
            return texts.t("confirm_declined")
    workdir = Path(tempfile.mkdtemp(prefix="qvq_run_"))
    try:
        script = workdir / "main.py"
        script.write_text(code, encoding="utf-8")
        if ctx.main is not None:
            ctx.main.audit("run_python", {"bytes": len(code.encode("utf-8"))}, ctx)
        outcome = await utils.run_process(
            [sys.executable, "-X", "utf8", str(script)],
            cwd=str(workdir),
            timeout=float(timeout if timeout and timeout > 0 else 30),
        )
        header = texts.t("command_finished", code=outcome["code"])
        return f"{header}\n{outcome['output']}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def run_python_sdk(ctx: ToolContext, code: str, timeout: int = 30) -> str:
    """在主进程内执行代码：可访问 sdk/main/config 等运行时对象。"""
    if getattr(ctx.config, "security_level", "standard") == "strict":
        return texts.t("code_denied")
    if not ctx.main.is_admin(ctx.user_id, ctx.origin, ctx.platform):
        return texts.t("needs_admin")
    if getattr(ctx.config, "security_level", "standard") == "standard" and not getattr(ctx.config, "trust_agent", False):
        granted = await ctx.confirm(
            texts.t("confirm_prompt", content=utils.truncate(code, 600)),
            timeout=int(getattr(ctx.config, "confirm_timeout", 60)),
        )
        if not granted:
            if ctx.main is not None:
                ctx.main.audit("run_python_sdk_denied", {"preview": utils.truncate(code, 120)}, ctx)
            return texts.t("confirm_declined")
    if ctx.main is not None:
        ctx.main.audit("run_python_sdk", {"bytes": len(code.encode("utf-8"))}, ctx)
    limit = float(timeout if timeout and timeout > 0 else 30)
    buf = io.StringIO()
    globs: dict = {
        "sdk": ctx.sdk,
        "main": ctx.main,
        "config": ctx.config,
        "ctx": ctx,
        "asyncio": asyncio,
        "__name__": "__qvq_sdk__",
    }
    started = time.monotonic()

    def _define() -> None:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(compile(code, "<qvq-sdk>", "exec"), globs)  # noqa: S102 - 受权限门控的进程内执行

    try:
        await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, _define), timeout=limit)
        # 用户代码里定义的 main() 会覆盖注入的模块实例；按身份区分
        entry = None
        candidate = globs.get("main")
        if candidate is not None and candidate is not ctx.main:
            entry = candidate
        result = None
        if entry is not None:
            if asyncio.iscoroutine(entry):
                result = await asyncio.wait_for(entry, timeout=limit)
            else:
                result = await asyncio.wait_for(entry(), timeout=limit)
    except asyncio.TimeoutError:
        return texts.t("tool_timeout", name="run_python_sdk", seconds=int(limit))
    except Exception:
        buf.seek(0)
        return f"{texts.t('command_finished', code=1)}\n{buf.getvalue()}\n{traceback.format_exc()}"
    ms = int((time.monotonic() - started) * 1000)
    output = buf.getvalue().strip()
    parts = [texts.t("command_finished", code=0) + f" ({ms}ms)"]
    if output:
        parts.append(output)
    if result is not None:
        parts.append("=> " + utils.truncate(repr(result), 4000))
    return "\n".join(parts)


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="run_python",
        description="Execute a standalone Python script on the host machine in a temp directory and return its stdout/stderr. Security rules apply.",
        parameters=_schema(
            {
                "code": _s(type="string", description="Python source code to run"),
                "timeout": _s(type="integer", description="Timeout in seconds, default 30"),
            },
            ["code"],
        ),
        handler=run_python,
        danger=True,
    ))
    registry.register(Tool(
        name="run_python_sdk",
        description=(
            "Execute Python code INSIDE the running ErisPulse bot process (not a subprocess). "
            "Available globals: sdk (ErisPulse SDK: sdk.module / sdk.adapter / sdk.storage / sdk.lifecycle / sdk.client), "
            "main (this agent module instance), config, ctx, asyncio. "
            "Use it to call live modules/adapters/services, read/write storage, or inspect runtime state. "
            "Top-level await is not allowed; define `async def main():` and it will be awaited automatically (its return value is reported). "
            "Security rules apply (admin / confirmation)."
        ),
        parameters=_schema(
            {
                "code": _s(type="string", description="Python source code; optionally define async def main() for async operations"),
                "timeout": _s(type="integer", description="Timeout in seconds, default 30"),
            },
            ["code"],
        ),
        handler=run_python_sdk,
        danger=True,
    ))
