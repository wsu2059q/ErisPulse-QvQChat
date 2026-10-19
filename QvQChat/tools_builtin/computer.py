from __future__ import annotations

import os
import re
from pathlib import Path

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry

_DANGER_PATTERNS = [
    r"\brm\s+(?:-[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*f",
    r"\brm\s+-rf?",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\{\s*:\|:&\s*\};:",
    r"\b(?:shutdown|reboot|poweroff|halt)\b",
    r"\bformat\s+[a-zA-Z]:",
    r"\bdel\s+/[sq]",
    r"\brd\s+/s",
    r"\breg\s+(?:add|delete|import)",
    r"\bschtasks\b",
    r"\bnet\s+(?:user|localgroup)\b",
    r"\btaskkill\s+/f",
    r"\bRemove-Item\b[^|]*-Recurse[^|]*-Force",
    r"\bSet-ExecutionPolicy\b",
    r"\bInvoke-Expression\b",
    r"\bchmod\s+777\b",
    r"\buser(?:del|mod)\b",
    r"\bpasswd\b",
    r">\s*/dev/sd[a-z]",
    r"\bCI-?CD\b",
]


def _level(ctx: ToolContext) -> str:
    return getattr(ctx.config, "security_level", "standard") or "standard"


def _resolve_allowed(ctx: ToolContext, path: str) -> str:
    resolved = str(Path(path).expanduser().resolve())
    if _level(ctx) == "permissive":
        return resolved
    bases = [str(Path(b).expanduser().resolve()) for b in (getattr(ctx.config, "work_dirs", []) or [])]
    if not bases:
        bases = [str(Path.cwd().resolve())]
    for base in bases:
        left = os.path.normcase(resolved)
        right = os.path.normcase(base)
        if left == right or left.startswith(right + os.sep):
            return resolved
    raise PermissionError(texts.t("path_not_allowed", path=path))


def _is_dangerous(ctx: ToolContext, command: str) -> bool:
    patterns = list(_DANGER_PATTERNS) + list(getattr(ctx.config, "blocked_patterns", []) or [])
    return any(re.search(p, command, re.IGNORECASE) for p in patterns)


def _is_blocked(ctx: ToolContext, command: str) -> bool:
    return any(
        re.search(p, command, re.IGNORECASE)
        for p in (getattr(ctx.config, "blocked_patterns", []) or [])
    )


def _needs_confirm(ctx: ToolContext) -> bool:
    return not getattr(ctx.config, "trust_agent", False)


_DEFAULT_SENSITIVE = ["config", ".env", "*.key", "*.pem", "*.db", "*.sqlite*", "id_rsa"]

_DEFAULT_SAFE_COMMANDS = ["ping *"]


def _is_safe_command(ctx: ToolContext, command: str) -> bool:
    import fnmatch

    lowered = " ".join(command.strip().lower().split())
    patterns = list(_DEFAULT_SAFE_COMMANDS) + [
        str(p) for p in (getattr(ctx.config, "safe_commands", []) or [])
    ]
    return any(fnmatch.fnmatch(lowered, p.lower()) for p in patterns)


def _is_sensitive(ctx: ToolContext, resolved: str) -> bool:
    import fnmatch

    lowered = resolved.lower().replace("\\", "/")
    patterns = list(_DEFAULT_SENSITIVE) + [
        str(p).lower() for p in (getattr(ctx.config, "sensitive_paths", []) or [])
    ]
    parts = lowered.split("/")
    for pattern in patterns:
        pattern = pattern.lower()
        if pattern in ("config", ".env"):
            if pattern in parts or any(part.startswith(pattern) for part in parts):
                return True
        elif fnmatch.fnmatch(lowered, f"*{pattern}*") or lowered.endswith(pattern.lstrip("*")):
            return True
    return False


def _audit(ctx: ToolContext, tool: str, detail: dict) -> None:
    if ctx.main is not None:
        ctx.main.audit(tool, detail, ctx)


async def read_file(ctx: ToolContext, path: str, max_bytes: int = 65536) -> str:
    try:
        resolved = _resolve_allowed(ctx, path)
    except PermissionError as e:
        return str(e)
    if _is_sensitive(ctx, resolved) and not ctx.main.is_admin(ctx.user_id, ctx.origin, ctx.platform):
        return texts.t("sensitive_read_denied")
    target = Path(resolved)
    if not target.is_file():
        return texts.t("file_not_found", path=path)
    size = target.stat().st_size
    data = target.read_bytes()[: max_bytes if max_bytes > 0 else 65536]
    _audit(ctx, "read_file", {"path": resolved, "size": size})
    body = utils.decode_bytes(data)
    notice = "\n" + texts.t("file_too_large", limit=max_bytes) if size > len(data) else ""
    return body + notice


async def list_dir(ctx: ToolContext, path: str = ".") -> str:
    try:
        resolved = _resolve_allowed(ctx, path)
    except PermissionError as e:
        return str(e)
    target = Path(resolved)
    if not target.exists():
        return texts.t("file_not_found", path=path)
    _audit(ctx, "list_dir", {"path": resolved})
    items = []
    for entry in sorted(target.iterdir())[:200]:
        kind = "dir" if entry.is_dir() else "file"
        size = entry.stat().st_size if entry.is_file() else 0
        items.append({"name": entry.name, "type": kind, "size": size})
    return utils.to_text(items)


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


async def view_image(ctx: ToolContext, path: str) -> str:

    try:
        resolved = _resolve_allowed(ctx, path)
    except PermissionError as e:
        return str(e)
    if _is_sensitive(ctx, resolved) and not ctx.main.is_admin(ctx.user_id, ctx.origin, ctx.platform):
        return texts.t("sensitive_read_denied")
    target = Path(resolved)
    if not target.is_file():
        return texts.t("file_not_found", path=path)
    if target.suffix.lower() not in _IMAGE_SUFFIXES:
        return texts.t("image_type_unsupported", path=path)
    if target.stat().st_size > 8 * 1024 * 1024:
        return texts.t("image_too_large", path=path)
    _audit(ctx, "view_image", {"path": resolved})
    return utils.to_text({"image_path": resolved})


async def write_file(ctx: ToolContext, path: str, content: str, append: bool = False) -> str:
    if not ctx.main.is_admin(ctx.user_id, ctx.origin, ctx.platform):
        return texts.t("needs_admin")
    if _level(ctx) == "strict" and _needs_confirm(ctx):
        granted = await ctx.confirm(
            texts.t("confirm_prompt", content=f"write {path} ({len(content.encode('utf-8'))} bytes)"),
            timeout=int(getattr(ctx.config, "confirm_timeout", 60)),
        )
        if not granted:
            _audit(ctx, "write_file_denied", {"path": path})
            return texts.t("confirm_declined")
    try:
        resolved = _resolve_allowed(ctx, path)
    except PermissionError as e:
        return str(e)
    target = Path(resolved)
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(target, mode, encoding="utf-8", newline="") as f:
        f.write(content)
    _audit(ctx, "write_file", {"path": resolved, "bytes": len(content.encode("utf-8"))})
    return texts.t("write_done", path=resolved, bytes=len(content.encode("utf-8")))


async def run_command(ctx: ToolContext, command: str, cwd: str = "", timeout: int = 0) -> str:
    if _level(ctx) == "strict":
        return texts.t("computer_denied")
    if _is_blocked(ctx, command):
        _audit(ctx, "run_command_blocked", {"command": command})
        return texts.t("command_blocked", command=command)
    safe = _is_safe_command(ctx, command)
    if not safe and not ctx.main.is_admin(ctx.user_id, ctx.origin, ctx.platform):
        return texts.t("needs_admin")
    if _level(ctx) == "standard" and _is_dangerous(ctx, command) and not safe and _needs_confirm(ctx):
        granted = await ctx.confirm(texts.t("confirm_prompt", content=command), timeout=int(getattr(ctx.config, "confirm_timeout", 60)))
        if not granted:
            _audit(ctx, "run_command_denied", {"command": command})
            return texts.t("confirm_declined")
    workdir: str | None = None
    if cwd:
        try:
            workdir = _resolve_allowed(ctx, cwd)
        except PermissionError as e:
            return str(e)
    effective_timeout = float(timeout if timeout and timeout > 0 else getattr(ctx.config, "command_timeout", 60))
    _audit(ctx, "run_command", {"command": command, "cwd": workdir or "", "timeout": effective_timeout})
    outcome = await utils.run_process(command, cwd=workdir, timeout=effective_timeout, shell=True)
    header = texts.t("command_finished", code=outcome["code"])
    return f"{header}\n{outcome['output']}"


def _s(**simple) -> dict:
    return simple


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="run_command",
        access="admin",
        description="Run a shell command on the host machine. Subject to security level: strict forbids, standard confirms dangerous ones, permissive runs audited.",
        parameters=_schema(
            {
                "command": _s(type="string", description="The shell command"),
                "cwd": _s(type="string", description="Working directory"),
                "timeout": _s(type="integer", description="Timeout in seconds, default from config"),
            },
            ["command"],
        ),
        handler=run_command,
        danger=True,
    ))
    registry.register(Tool(
        name="read_file",
        access="safe",
        description="Read a text file from the host machine within allowed directories.",
        parameters=_schema(
            {
                "path": _s(type="string", description="File path"),
                "max_bytes": _s(type="integer", description="Max bytes to read, default 65536"),
            },
            ["path"],
        ),
        handler=read_file,
    ))
    registry.register(Tool(
        name="write_file",
        access="admin",
        description="Write or append content to a file on the host machine. Admin only; strict level asks confirmation.",
        parameters=_schema(
            {
                "path": _s(type="string", description="File path"),
                "content": _s(type="string", description="Content to write"),
                "append": _s(type="boolean", description="Append instead of overwrite"),
            },
            ["path", "content"],
        ),
        handler=write_file,
        danger=True,
    ))
    registry.register(Tool(
        name="list_dir",
        access="safe",
        description="List a directory on the host machine within allowed directories.",
        parameters=_schema(
            {"path": _s(type="string", description="Directory path, default current") },
            [],
        ),
        handler=list_dir,
    ))
    registry.register(Tool(
        name="view_image",
        access="safe",
        description="Open a local image file as visual input and view it (use the image path given with attachment messages). Requires a vision-capable model.",
        parameters=_schema(
            {"path": _s(type="string", description="Image file path (png/jpg/jpeg/gif/webp/bmp)")},
            ["path"],
        ),
        handler=view_image,
    ))
