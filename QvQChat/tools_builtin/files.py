"""文件工作区沙箱：AI 的全部文件活动框死在 data/QvQChat/work/<会话>/。

多人平台下任何群友都能触发 AI——文件工具的价值（处理并回发文件）与风险
（任意文件外泄/写入）都极高。规则：

- 沙箱内：读/写/列/删/下载/打包 对所有人开放（safe）——这是"AI 有用"的部分
- 沙箱外：一律拒绝（管理员也不例外：主人在群里说话 ≠ 授权任意文件操作）
- 敏感名（cfg.sensitive_paths，如 *.env/*.db/config*）即使落在沙箱内也拒绝读取
- 下载禁内网/回环地址 + 大小上限；zip 解压防路径穿越与炸弹
- 全部写/删/下载/发送走 audit 审计
"""
from __future__ import annotations

import fnmatch
import ipaddress
import re as _re
import socket
import urllib.request
import zipfile
from pathlib import Path

from .. import utils
from .agent import Tool, ToolContext

SANDBOX_ROOT = Path("data/QvQChat/work")
_UNSAFE_NAME_RE = _re.compile(r"[^A-Za-z0-9._-]+")
ZIP_MAX_MEMBERS = 500
ZIP_MAX_TOTAL_BYTES = 100 * 1024 * 1024
DOWNLOAD_CHUNK = 64 * 1024


def sandbox_root(ctx: ToolContext) -> Path:
    """本会话的工作区根目录（按需创建）。chat_key 中的非法字符替换为 _。"""
    base = str(getattr(ctx.config, "file_workdir", "") or SANDBOX_ROOT)
    name = _UNSAFE_NAME_RE.sub("_", str(getattr(ctx, "chat_key", "") or "default"))
    root = (Path(base).resolve() / name)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _extra_send_dirs(ctx: ToolContext) -> list[Path]:
    """file_extra_dirs 配置解析为绝对路径列表（相对路径按框架工作目录）。"""
    result = []
    for item in getattr(ctx.config, "file_extra_dirs", []) or []:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            result.append(Path(text).expanduser().resolve())
        except OSError:
            continue
    return result


def sandbox_resolve(ctx: ToolContext, path: str, *, must_exist: bool = False,
                    allow_extra: bool = False) -> Path:
    """把相对路径解析到沙箱内；越界抛 ValueError（消息可直接回给模型）。

    绝对路径/包含 .. 的路径在 resolve 后必须仍位于沙箱根之下。
    allow_extra=True（发送场景）：file_extra_dirs 白名单目录内的文件也放行——
    生态模块（如 TTS 缓存）的产物要能直接发给用户；写入/删除不受此豁免。
    """
    root = sandbox_root(ctx).resolve()
    text = str(path or "").strip()
    if not text:
        raise ValueError("path is required")
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve()
    except OSError as e:
        raise ValueError(f"invalid path: {path} ({e})")
    if resolved != root and root not in resolved.parents:
        if allow_extra:
            for extra in _extra_send_dirs(ctx):
                if resolved == extra or extra in resolved.parents:
                    return resolved
        raise ValueError(f"path escapes the work sandbox: {path} (all file paths must stay inside list_files root)")
    if must_exist and not resolved.exists():
        raise ValueError(f"file not found: {path} (use list_files to inspect the sandbox)")
    return resolved


def _sensitive_match(ctx: ToolContext, path: Path) -> str | None:
    """命中 sensitive_paths 黑名单则返回命中的模式（读取拦截用）。"""
    patterns = getattr(ctx.config, "sensitive_paths", []) or []
    text = str(path)
    name = path.name
    for pattern in patterns:
        pat = str(pattern).strip()
        if not pat:
            continue
        if fnmatch.fnmatch(text, pat) or fnmatch.fnmatch(name, pat):
            return pat
        # 点开头的模式（.env/.db 等）按后缀语义：creds.env 命中 .env
        if pat.startswith(".") and name.endswith(pat):
            return pat
    return None


def _audit(ctx: ToolContext, action: str, detail: dict) -> None:
    audit = getattr(ctx.main, "audit", None)
    if callable(audit):
        try:
            audit(f"file_{action}", detail, ctx)
        except Exception:
            pass


def _check_public_url(url: str) -> str | None:
    """SSRF 防护：仅允许 http(s)；主机名与解析出的 IP 不得是内网/回环/链路本地。"""
    text = str(url or "").strip()
    if not text.lower().startswith(("http://", "https://")):
        return "only http/https URLs are supported"
    host = (_re.match(r"https?://([^/@:]+)", text) or [None, ""])[1].strip().lower()
    if not host:
        return "invalid URL host"
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        return f"blocked host: {host}"
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception as e:
        return f"cannot resolve host: {e}"
    for info in infos:
        ip_text = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return f"blocked address: {host} -> {ip_text}"
    return None


async def list_files(ctx: ToolContext, subdir: str = "") -> str:
    root = sandbox_root(ctx)
    target = sandbox_resolve(ctx, subdir or ".", must_exist=True)
    if not target.is_dir():
        raise ValueError(f"not a directory: {subdir}")
    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        try:
            size = item.stat().st_size if item.is_file() else None
        except OSError:
            size = None
        entries.append({
            "name": item.name + ("/" if item.is_dir() else ""),
            "bytes": size,
        })
    return utils.to_text({
        "sandbox": str(root),
        "cwd": str(target.relative_to(root)) or ".",
        "entries": entries,
    })


async def read_file(ctx: ToolContext, path: str) -> str:
    target = sandbox_resolve(ctx, path, must_exist=True)
    if target.is_dir():
        raise ValueError(f"{path} is a directory (use list_files)")
    hit = _sensitive_match(ctx, target)
    if hit:
        _audit(ctx, "read_denied", {"path": str(target), "pattern": hit})
        raise ValueError(f"blocked by sensitive-path policy (matched '{hit}'): reading this file is not allowed")
    limit = max(1000, int(getattr(ctx.config, "file_max_read_chars", 20000) or 20000))
    data = target.read_bytes()
    if len(data) > limit * 4 and b"\0" in data[:4096]:
        return f"[binary file, {len(data)} bytes — text preview not available]"
    text = data.decode("utf-8", errors="replace")
    if len(text) > limit:
        text = text[:limit] + f"\n…[truncated at {limit} chars, total {len(text)}]"
    return text


async def write_file(ctx: ToolContext, path: str, content: str, append: bool = False) -> str:
    target = sandbox_resolve(ctx, path)
    limit = max(1000, int(getattr(ctx.config, "file_max_write_chars", 200000) or 200000))
    content = str(content or "")
    if len(content) > limit:
        raise ValueError(f"content too large ({len(content)} chars, limit {limit})")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a" if append else "w", encoding="utf-8") as fh:
        fh.write(content)
    _audit(ctx, "write", {"path": str(target), "bytes": len(content), "append": bool(append)})
    return f"written: {target.relative_to(sandbox_root(ctx))} ({len(content)} chars)"


async def delete_file(ctx: ToolContext, path: str) -> str:
    target = sandbox_resolve(ctx, path, must_exist=True)
    if target == sandbox_root(ctx).resolve():
        raise ValueError("cannot delete the sandbox root")
    if target.is_dir():
        raise ValueError(f"{path} is a directory; delete files one by one")
    target.unlink()
    _audit(ctx, "delete", {"path": str(target)})
    return f"deleted: {path}"


async def download_file(ctx: ToolContext, url: str, path: str = "") -> str:
    blocked = _check_public_url(url)
    if blocked:
        _audit(ctx, "download_denied", {"url": url, "reason": blocked})
        raise ValueError(f"download blocked: {blocked}")
    limit_bytes = max(1, int(getattr(ctx.config, "file_max_download_mb", 20) or 20)) * 1024 * 1024
    target = sandbox_resolve(ctx, path or (_re.sub(r"[^A-Za-z0-9._-]+", "_", url.rsplit("/", 1)[-1] or "download.bin")))
    if target.is_dir():
        raise ValueError(f"{path} is a directory")
    req = urllib.request.Request(url, headers={"User-Agent": "QvQChat/4.4"})
    total = 0
    with urllib.request.urlopen(req, timeout=30) as resp:
        final = str(resp.geturl() or url)
        final_blocked = _check_public_url(final)
        if final_blocked:
            _audit(ctx, "download_denied", {"url": final, "reason": final_blocked})
            raise ValueError(f"download blocked after redirect: {final_blocked}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fh:
            while True:
                chunk = resp.read(DOWNLOAD_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit_bytes:
                    raise ValueError(f"download exceeds size limit ({limit_bytes // (1024 * 1024)} MB)")
                fh.write(chunk)
    _audit(ctx, "download", {"url": url, "path": str(target), "bytes": total})
    return f"downloaded {total} bytes -> {target.relative_to(sandbox_root(ctx))}"


async def zip_files(ctx: ToolContext, paths: list, out_name: str = "archive.zip") -> str:
    out = sandbox_resolve(ctx, out_name or "archive.zip")
    if out.suffix.lower() != ".zip":
        raise ValueError("out_name must end with .zip")
    members = []
    for item in paths or []:
        resolved = sandbox_resolve(ctx, str(item), must_exist=True)
        if resolved.is_file():
            members.append(resolved)
    if not members:
        raise ValueError("no files to archive (paths must be files inside the sandbox)")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for member in members:
            zf.write(member, arcname=member.name)
    _audit(ctx, "zip", {"out": str(out), "count": len(members)})
    return f"archived {len(members)} files -> {out.relative_to(sandbox_root(ctx))}"


async def unzip_file(ctx: ToolContext, path: str, dest: str = "") -> str:
    source = sandbox_resolve(ctx, path, must_exist=True)
    target_dir = sandbox_resolve(ctx, dest) if dest else source.parent / (source.stem + "_extracted")
    total = 0
    with zipfile.ZipFile(source) as zf:
        names = zf.namelist()
        if len(names) > ZIP_MAX_MEMBERS:
            raise ValueError(f"too many entries ({len(names)}, limit {ZIP_MAX_MEMBERS}) — possible zip bomb")
        for info in zf.infolist():
            member = (target_dir / info.filename).resolve()
            if target_dir.resolve() not in member.parents and member != target_dir.resolve():
                raise ValueError(f"zip entry escapes destination: {info.filename}")
            total += info.file_size
        if total > ZIP_MAX_TOTAL_BYTES:
            raise ValueError(f"uncompressed size {total} exceeds limit {ZIP_MAX_TOTAL_BYTES} — possible zip bomb")
        zf.extractall(target_dir)
    _audit(ctx, "unzip", {"source": str(source), "dest": str(target_dir), "entries": len(names)})
    return f"extracted {len(names)} entries -> {target_dir.relative_to(sandbox_root(ctx))}"


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _s(**kw) -> dict:
    return kw


SANDBOX_PATH_DESC = "Path RELATIVE to this chat's work sandbox (see list_files). Absolute paths and '..' are rejected."


def register(registry, main) -> None:
    if not bool(getattr(main.cfg, "file_tools_enabled", True)):
        return
    registry.register(Tool(
        name="list_files",
        access="safe",
        description="List files in this chat's private work sandbox (where uploaded/generated files live). Use this first to discover what exists.",
        parameters=_schema({"subdir": _s(type="string", description="Optional subdirectory (relative)")}, []),
        handler=list_files,
    ))
    registry.register(Tool(
        name="read_file",
        access="safe",
        description="Read a text file from this chat's work sandbox. " + SANDBOX_PATH_DESC + " Sensitive-looking files (*.env/*.db/config) are blocked.",
        parameters=_schema({"path": _s(type="string", description="File path (relative to sandbox)")}, ["path"]),
        handler=read_file,
    ))
    registry.register(Tool(
        name="write_file",
        access="safe",
        description="Create or overwrite a text file inside this chat's work sandbox (parent dirs auto-created). " + SANDBOX_PATH_DESC,
        parameters=_schema({
            "path": _s(type="string", description="File path (relative to sandbox)"),
            "content": _s(type="string", description="Full text content to write"),
            "append": _s(type="boolean", description="Append instead of overwrite (default false)"),
        }, ["path", "content"]),
        handler=write_file,
    ))
    registry.register(Tool(
        name="delete_file",
        access="safe",
        description="Delete a single file inside this chat's work sandbox (directories not supported).",
        parameters=_schema({"path": _s(type="string", description="File path (relative to sandbox)")}, ["path"]),
        handler=delete_file,
    ))
    registry.register(Tool(
        name="download_file",
        access="safe",
        description="Download an http(s) URL into this chat's work sandbox (internal/private network addresses are blocked; size capped).",
        parameters=_schema({
            "url": _s(type="string", description="http(s) URL"),
            "path": _s(type="string", description="Optional target path (relative); defaults to the URL filename"),
        }, ["url"]),
        handler=download_file,
    ))
    registry.register(Tool(
        name="zip_files",
        access="safe",
        description="Pack sandbox files into a .zip (send it to the user afterwards via send_message file_path).",
        parameters=_schema({
            "paths": _s(type="array", description="File paths (relative to sandbox)"),
            "out_name": _s(type="string", description="Archive name, must end with .zip"),
        }, ["paths"]),
        handler=zip_files,
    ))
    registry.register(Tool(
        name="unzip_file",
        access="safe",
        description="Extract a .zip inside the sandbox (zip-bomb and path-escape protected).",
        parameters=_schema({
            "path": _s(type="string", description="Zip path (relative to sandbox)"),
            "dest": _s(type="string", description="Optional destination directory (relative)"),
        }, ["path"]),
        handler=unzip_file,
    ))
