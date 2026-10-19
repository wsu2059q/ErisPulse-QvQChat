from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

TEXT_LIMIT = 4000
OUTPUT_LIMIT = 8000


_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_DELAY_RE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_WEEKDAY_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def now_ts() -> float:
    return time.time()


def new_id() -> str:
    return uuid.uuid4().hex[:8]


def truncate(text: str, limit: int = TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…(truncated, {len(text)} chars total)"


def decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def to_text(result: Any, limit: int = TEXT_LIMIT) -> str:
    if result is None:
        return "ok"
    if isinstance(result, str):
        return truncate(result, limit)
    try:
        return truncate(json.dumps(result, ensure_ascii=False, default=str), limit)
    except (TypeError, ValueError):
        return truncate(str(result), limit)


def sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name)).strip("_")
    if cleaned:
        return cleaned
    return "n" + hashlib.md5(str(name).encode("utf-8")).hexdigest()[:6]


def split_top_level(text: str, sep: str = ",") -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote = ""
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def _json_type(default: Any, annotation: str | None) -> str:
    if annotation:
        name = annotation.strip()
        if name.endswith("| None"):
            name = name[: -len("| None")].strip()
        elif name.startswith("None |"):
            name = name[len("None |"):].strip()
        if name.startswith("int"):
            return "integer"
        if name.startswith("float"):
            return "number"
        if name.startswith("bool"):
            return "boolean"
        if name.startswith("str"):
            return "string"
        if name.startswith(("list", "tuple", "set")):
            return "array"
        if name.startswith("dict"):
            return "object"
    if isinstance(default, bool):
        return "boolean"
    if isinstance(default, int):
        return "integer"
    if isinstance(default, float):
        return "number"
    if isinstance(default, (list, tuple)):
        return "array"
    if isinstance(default, dict):
        return "object"
    return "string"


def schema_from_signature(signature: str) -> dict:
    sig = signature.strip()
    if sig.startswith("(") and sig.endswith(")"):
        sig = sig[1:-1]
    properties: dict[str, Any] = {}
    required: list[str] = []
    for raw in split_top_level(sig):
        chunks = split_top_level(raw, "=")
        if len(chunks) >= 2:
            left = "=".join(chunks[:-1]).strip()
            has_default = True
            default_raw = chunks[-1].strip()
        else:
            left = raw.strip()
            has_default = False
            default_raw = ""
        type_chunks = split_top_level(left, ":")
        if len(type_chunks) >= 2:
            name_raw = type_chunks[0].strip()
            annotation = ":".join(type_chunks[1:]).strip()
        else:
            name_raw = left
            annotation = None
        if not name_raw or name_raw.startswith(("*", "/")):
            continue
        default: Any = None
        if has_default:
            try:
                default = ast.literal_eval(default_raw)
            except (ValueError, SyntaxError):
                default = default_raw
        name = sanitize_name(name_raw)
        prop: dict[str, Any] = {"type": _json_type(default, annotation)}
        if has_default:
            prop["default"] = default
        else:
            required.append(name)
        properties[name] = prop
    return {"type": "object", "properties": properties, "required": required}


def _cron_field_match(field: str, value: int, low: int, high: int) -> bool:
    for part in field.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            part, step_raw = part.split("/", 1)
            try:
                step = max(1, int(step_raw))
            except ValueError:
                continue
        part = part.strip()
        if part in ("*", "?", ""):
            start, end = low, high
        elif "-" in part:
            try:
                a, b = part.split("-", 1)
                start, end = int(a), int(b)
            except ValueError:
                continue
        else:
            try:
                start = int(part)
            except ValueError:
                continue
            end = start
        for candidate in range(start, end + 1, step):
            if candidate == value:
                return True
    return False


def cron_next(expr: str, from_ts: float) -> float:
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError("cron expression needs 5 fields: minute hour day month weekday")
    minute_f, hour_f, dom_f, month_f, dow_f = fields
    day = datetime.fromtimestamp(from_ts).replace(hour=0, minute=0, second=0, microsecond=0)
    dom_restricted = dom_f not in ("*", "?")
    dow_restricted = dow_f not in ("*", "?")
    for _ in range(366 * 4 + 1):
        if (
            _cron_field_match(month_f, day.month, 1, 12)
            and _day_matches(dom_f, dow_f, dom_restricted, dow_restricted, day)
        ):
            for hour in range(24):
                if not _cron_field_match(hour_f, hour, 0, 23):
                    continue
                for minute in range(60):
                    if not _cron_field_match(minute_f, minute, 0, 59):
                        continue
                    ts = day.replace(hour=hour, minute=minute).timestamp()
                    if ts > from_ts:
                        return ts
        day = day + timedelta(days=1)
    raise ValueError("cron expression has no trigger within the next 4 years")


def _day_matches(dom_f: str, dow_f: str, dom_restricted: bool, dow_restricted: bool, day) -> bool:
    dom_ok = _cron_field_match(dom_f, day.day, 1, 31)
    dow_ok = _cron_field_match(dow_f, (day.weekday() + 1) % 7, 0, 6)
    if dom_restricted and dow_restricted:
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def parse_schedule(text: str) -> dict:
    raw = text.strip()
    if not raw:
        raise ValueError("schedule is empty")
    low = raw.lower()
    if low.startswith("in:") or low.startswith("in "):
        body = raw[3:].strip()
        match = _DELAY_RE.match(body)
        if not match:
            raise ValueError("in format: in:30m / in:2h / in:1d")
        amount, unit = int(match.group(1)), match.group(2).lower()
        return {"type": "once", "delay": amount * _UNIT_SECONDS[unit]}
    if low.startswith("at:") or low.startswith("at "):
        body = raw[3:].strip()
        try:
            moment = datetime.strptime(body, "%Y-%m-%d %H:%M")
        except ValueError as e:
            raise ValueError("at format: at:2026-10-17 09:00") from e
        return {"type": "once", "at": moment.timestamp()}
    if low.startswith("every:") or low.startswith("every "):
        body = raw[6:].strip()
        match = _DELAY_RE.match(body)
        if not match:
            raise ValueError("every format: every:30m / every:2h / every:1d")
        amount, unit = int(match.group(1)), match.group(2).lower()
        seconds = amount * _UNIT_SECONDS[unit]
        if seconds < 60:
            raise ValueError("interval must be at least 60 seconds")
        return {"type": "interval", "seconds": seconds}
    if low.startswith("cron:") or low.startswith("cron "):
        expr = raw[5:].strip()
        fields = expr.split()
        if len(fields) != 5:
            raise ValueError("cron format: cron:minute hour day month weekday")
        return {"type": "cron", "expr": " ".join(fields)}
    fields = raw.split()
    if len(fields) == 5:
        return {"type": "cron", "expr": raw}
    raise ValueError(
        "supported schedules: cron:m h dom mon dow / at:YYYY-MM-DD HH:MM / in:30m / every:2h"
    )


def schedule_next(schedule: dict, from_ts: float) -> float:
    kind = schedule.get("type")
    if kind == "once":
        if "at" in schedule:
            return float(schedule["at"])
        return from_ts + float(schedule.get("delay", 0))
    if kind == "interval":
        return from_ts + float(schedule.get("seconds", 60))
    if kind == "cron":
        return cron_next(schedule["expr"], from_ts)
    raise ValueError(f"unknown schedule type: {kind}")


def format_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")


def time_line() -> str:
    moment = datetime.now()
    return f"Current time: {moment.strftime('%Y-%m-%d %H:%M:%S')} ({_WEEKDAY_EN[moment.weekday()]})"


def markdown_to_text(text: str) -> str:
    if not text:
        return text
    s = text
    s = re.sub(r"```[a-zA-Z0-9_-]*\n(.*?)```", lambda m: m.group(1), s, flags=re.S)
    s = re.sub(r"```(.*?)```", lambda m: m.group(1), s, flags=re.S)
    s = re.sub(r"`([^`\n]+)`", r"\1", s)
    s = re.sub(r"^[ \t]*\|?[ \t]*:?-{2,}[-| :]*$", "", s, flags=re.M)
    s = re.sub(r"^[ \t]*\|[ \t]*", "", s, flags=re.M)
    s = re.sub(r"\|[ \t]*$", "", s, flags=re.M)
    s = re.sub(r"^[ \t]*#{1,6}[ \t]*", "", s, flags=re.M)
    s = re.sub(r"\*\*\*([^*]+)\*\*\*", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*\n]+)\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"~~([^~]+)~~", r"\1", s)
    s = re.sub(r"!?\[([^\]]*)\]\(([^)\s]+)\)", r"\1(\2)", s)
    s = re.sub(r"^[ \t]*>[ \t]?", "", s, flags=re.M)
    s = re.sub(r"^[ \t]*([-*_][ \t]*){3,}$", "", s, flags=re.M)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def split_reply_sections(text: str, max_nodes: int = 12, min_nodes: int = 2) -> list[str]:
    body = text.strip()
    if not body:
        return []
    blocks = re.split(r"\n(?=#{1,6} )", body)
    sections: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) > 600:
            for chunk in re.split(r"\n{2,}", block):
                piece = chunk.strip()
                if piece:
                    sections.append(piece)
        else:
            sections.append(block)
    if not sections:
        sections = [body]
    if len(sections) < min_nodes:
        only = sections[0]
        parts = [p.strip() for p in re.split(r"\n{2,}", only) if p.strip()]
        if len(parts) >= min_nodes:
            sections = parts
    if len(sections) < min_nodes:
        only = sections[0]
        step = max(200, (len(only) + min_nodes - 1) // min_nodes)
        sections = [only[i : i + step].strip() for i in range(0, len(only), step)]
        sections = [s for s in sections if s]
    if len(sections) > max_nodes:
        merged_tail = "\n\n".join(sections[max_nodes - 1:])
        sections = sections[: max_nodes - 1] + [merged_tail]
    return sections


def build_forward_nodes(sections: list[str], nickname: str = "QvQChat", user_id: str = "10000") -> list[dict]:
    cleaned = [str(s).strip() for s in sections if s and str(s).strip()]
    total = len(cleaned)
    nodes: list[dict] = []
    for index, section in enumerate(cleaned, 1):
        lines = section.splitlines()
        head = lines[0][:80] if lines else ""
        rest = "\n".join(lines[1:]).strip()
        display = f"【{index}/{total}】{head}" + (f"\n{rest}" if rest else "")
        nodes.append(
            {
                "type": "node",
                "data": {
                    "user_id": str(user_id),
                    "nickname": str(nickname),
                    "content": [{"type": "text", "data": {"text": display}}],
                },
            }
        )
    return nodes


def _send_failed(result) -> bool:

    return isinstance(result, dict) and str(result.get("status") or "") == "failed"


async def deliver_forward(adapter, target_type: str, target_id: str, sections: list, sends) -> str:


    cleaned = [str(s).strip() for s in sections if s and str(s).strip()]
    if not cleaned or adapter is None or "MergeForward" not in set(sends or ()):
        return ""
    nodes = build_forward_nodes(cleaned)
    try:
        chain = adapter.Send.To(target_type, target_id)
        result = await chain.MergeForward(nodes)
        if not _send_failed(result):
            return "forward"
    except Exception:
        pass
    return ""


def bigrams(text: str) -> set[str]:
    cleaned = re.sub(r"[\s\W_]+", "", str(text).lower())
    if len(cleaned) < 2:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + 2] for i in range(len(cleaned) - 1)}


def overlap_score(query: str, content: str) -> float:
    q = bigrams(query)
    if not q:
        return 0.0
    c = bigrams(content)
    if not c:
        return 0.0
    return len(q & c) / len(q)


async def run_process(
    args: str | list[str],
    cwd: str | None = None,
    timeout: float = 30.0,
    shell: bool = False,
) -> dict:
    try:
        if shell:
            proc = await asyncio.create_subprocess_shell(
                str(args),
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
    except (OSError, ValueError) as e:
        return {"code": -1, "output": f"failed to spawn process: {e}"}
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        code = proc.returncode
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return {"code": -1, "output": f"process timed out after {timeout}s and was terminated"}
    output = decode_bytes(out) if out else ""
    return {"code": code if code is not None else -1, "output": truncate(output, OUTPUT_LIMIT)}
