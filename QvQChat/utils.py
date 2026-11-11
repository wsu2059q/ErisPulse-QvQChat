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
_WEEKDAY_ZH = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# 输出投递控制标签：[[转发]] 强制合并转发 / [[直发]] 强制普通消息直发。
# 可出现在任意一段 AI 发言开头（首个命中对整轮生效，见 AgentRunner.delivery_hint）
OUTPUT_TAG_RE = re.compile(r"^\[\[(转发|直发)\]\]\s*")
# 自主跳过标签：模型判断"这条不值得回"（无人问津的接话/纯表情刷屏）时输出，
# 全链静默——不发送、不写占位进上下文；与空回复静默共用 inbox 层的 skip 分支
SKIP_TAG_RE = re.compile(r"^\[\[(?:不回复|skip)\]\]$", re.IGNORECASE)
# 模型经常把标签写进正文中间、漏写成单括号，甚至塞进 send_message 内容里——
# 统一清扫：双括号任意位置 + 单括号行首（独占一行或同行带正文，如 "[直发] xxx"）
# 标签与正文同行的形态：单/双括号规则都不命中时会原样发出
STRAY_TAG_RE = re.compile(r"^\s*\[\[?(转发|直发)\]\]?\s*", re.MULTILINE)
STRAY_TAG_INLINE_RE = re.compile(r"\[\[(转发|直发)\]\]")


def is_skip_reply(reply: str) -> bool:
    """整条回复是否为自主跳过标记（[[不回复]]/[[skip]]，允许首尾空白）。"""
    return bool(SKIP_TAG_RE.match(str(reply or "").strip()))


def strip_output_tag(reply: str) -> tuple[str, bool | None]:
    """剥离开头的 [[转发]]/[[直发]] 标签。

    返回 (剩余文本, force)：force=True 转发 / False 直发 / None 无标签（走自动规则）。
    """
    tag = OUTPUT_TAG_RE.match(reply)
    if not tag:
        return reply, None
    return reply[tag.end():].strip(), tag.group(1) == "转发"


def strip_stray_tags(text: str) -> str:
    """清扫正文中残留的投递标签（双括号任意位置、单括号独占一行）。

    只处理标记语义明确的形态，不碰普通方括号文本。
    """
    text = STRAY_TAG_INLINE_RE.sub("", str(text or ""))
    text = STRAY_TAG_RE.sub("", text)
    return text.strip()


# 假媒体标记：模型不调工具，自己写「[语音] 文字」「[表情包]」假装发过媒体。
# 剥掉标记保留正文（用户至少能看到内容）；真媒体走对应工具发送是唯一正道。
# 全媒介封闭词表（语音/表情包/图片/视频/文件系）——三类正则共用一份词表保证口径一致。
# 红线：只处理"括号包裹的标记"形态，且标记内容必须恰为词表词——带正文的普通句子
# （如"发你个表情包"、"表情包见附件"）没有标记结构，绝不误删
MEDIA_TAG = r"(?:语音|声音|voice|audio|表情包|贴图|表情|sticker|图片|照片|相片|image|pic|视频|video|文件|file)"
FAKE_MEDIA_PREFIX_RE = re.compile(
    rf"^\s*[\[［（(【]\s*{MEDIA_TAG}\s*[\]］）)】]\s*[:：]?\s*", re.IGNORECASE
)


def strip_fake_media_prefix(reply: str) -> str:
    """剥掉开头的假媒体标记（[语音]/[表情包]/（图片）等），只处理行首形态。"""
    text = str(reply or "")
    prev = None
    while prev != text:
        prev = text
        text = FAKE_MEDIA_PREFIX_RE.sub("", text, count=1)
    return text.strip()


# 假媒体声明行：模型没真发语音/图片，却塞一行「（语音已发）」「（合成语音中）」宣告
# 已发/将发（用户根本收不到媒体）。必须用封闭词表锚定整行，不能泛化匹配——行内带
# 正文的（"（语音已发）喵？！"）是用户正文的一部分，误删等于吞消息。只匹配
# "整行仅为声明"的形态（动词集合与媒介词表相互独立，动词保持最小封闭集）
FAKE_CLAIM_RE = re.compile(
    rf"^[（(【\[]?\s*{MEDIA_TAG}?\s*"
    r"(合成语音后发送|语音合成后发送|合成语音中|语音合成中|稍后语音发送|录好后再发|"
    r"已发出去|已发送|已发|发送成功|发出去啦|发出去咯|发好了|sent)"
    r"\s*[！!。~～]?\s*[）)】\]]?$",
    re.IGNORECASE,
)
# 裸标签行：整行只有「[语音]」「[表情包]」「（图片）」「【video】」这类标记、
# 后面没有任何正文（分段器把"标记+正文"切成独立气泡时，标记就成了孤行）。
# 与 strip_fake_media_prefix 的分工：prefix 剥"行首标记+同内容"，这里只删
# "整行仅有标记"的孤行
FAKE_LABEL_RE = re.compile(
    rf"^[\[［（(【]\s*{MEDIA_TAG}\s*[\]］）)】]\s*[:：]?[。.!！~～]?\s*$",
    re.IGNORECASE,
)


def strip_fake_media_claims(reply: str) -> str:
    """剥掉整行仅为假媒体声明/裸标记的行（（语音已发）/语音合成中！/[表情包] 等），保留其它内容。

    只删"整行就是声明/标记"的行——行内带正文的（"（语音已发）喵"）保留，防止误删用户正文；
    循环剥到稳定（声明行删除后剩下的仍是声明行时一并清掉）。
    """
    text = str(reply or "")
    prev = None
    while prev != text:
        prev = text
        text = "\n".join(
            line for line in text.splitlines()
            if not FAKE_CLAIM_RE.match(line.strip()) and not FAKE_LABEL_RE.match(line.strip())
        )
    return text.strip()


def collapse_spaces(text: str) -> str:
    """规范化文本：剥首尾空白 + 连续空白（含换行/制表/全角空格）压成单空格。

    同回合重复发言判定用（阶段发言 vs 阶段发言、阶段发言 vs 最终回复）：
    只比内容不比排版，换行差异不算新发言。
    """
    return re.sub(r"\s+", " ", str(text or "")).strip()


# 元叙述开头：模型把"回复策略/分析过程"写进正文首段（随后才是正式回复）
META_SECTION_RE = re.compile(
    r"^\s*(回复策略|回复思路|回复方案|分析[：:或]|思考[：:过]|策略[：:]|"
    r"让我(看看|想想|分析)|我(应该|打算|准备|需要)(先|再)?|本喵(先|再)?(看|想|分析))[^\n]{0,40}[：:、]"
)

def strip_meta_section(reply: str) -> str:
    """段级元文本剥离：首段是思考/策略/分析过程而后面还有正文时剥掉首段。

    典型形态：首段「回复策略：……保持简短口语化……就这么回。」
    空行后才是正式回复——分段器把分析段切第一条发出去了。只剥首段、要求
    后面还有内容（防止整条唯一段落被误删）；保守词表锚定，不做泛化判断。
    """
    text = str(reply or "").strip()
    if not text or "\n\n" not in text:
        return text
    parts = text.split("\n\n", 1)
    if META_SECTION_RE.match(parts[0]) and parts[1].strip():
        return parts[1].strip()
    return text


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


def match_pattern(name: str, rules, star_all: bool = True) -> bool:
    """前缀通配匹配（收编，替代 Main/_match_tool_rules、tools/_allowed/_disabled_match 等重复实现）。

    规则以 ``*`` 结尾按前缀匹配（``eco_*`` 命中所有 eco_ 开头项），否则全等；
    ``star_all=True``（默认）时单独的 ``*`` 匹配一切。delivery.py 的平台通配
（`a == "*" or platform == a or a.endswith("*")`）语义与此一致，后续可迁此实现。
    """
    for rule in rules or []:
        rule = str(rule)
        if rule.endswith("*"):
            if rule == "*" and not star_all:
                continue
            if name.startswith(rule[:-1]):
                return True
        elif rule == name:
            return True
    return False


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
    return f"当前时间：{moment.strftime('%Y-%m-%d %H:%M:%S')}（{_WEEKDAY_ZH[moment.weekday()]}）"


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


def build_forward_nodes(sections: list[str], nickname: str = "", user_id: str = "") -> list[dict]:
    cleaned = [str(s).strip() for s in sections if s and str(s).strip()]
    nodes: list[dict] = []
    for section in cleaned:
        nodes.append(
            {
                "type": "node",
                "data": {
                    "user_id": str(user_id),
                    "nickname": str(nickname),
# NapCat/LLOneBot 的转发预览与详情读取的键对不同（uin/nick vs user_id/nickname）：
# 四键同值冗余，读哪对都能拿到昵称（多余键各实现忽略，无副作用）
                    "uin": str(user_id),
                    "nick": str(nickname),
                    "content": [{"type": "text", "data": {"text": section}}],
                },
            }
        )
    return nodes


def _send_failed(result) -> bool:

    return isinstance(result, dict) and str(result.get("status") or "") == "failed"


async def deliver_forward(adapter, target_type: str, target_id: str, sections: list, sends,
                          nickname: str = "", user_id: str = "", account: str = "") -> str:


    cleaned = [str(s).strip() for s in sections if s and str(s).strip()]
    if not cleaned or adapter is None or "MergeForward" not in set(sends or ()):
        return ""
    nodes = build_forward_nodes(cleaned, nickname=nickname, user_id=user_id)
    try:
# 多账户后端：不绑账户会用适配器默认 bot 发出（错乱根源），有 account 必绑
        chain = adapter.Send
        if account:
            chain = chain.Using(account)
        chain = chain.To(target_type, target_id)
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


def image_data_url(url: str, max_bytes: int = 6 * 1024 * 1024) -> str:
    """本地图片路径 → base64 data URL；http(s)/data: 原样返回。

    云厂商拉不到部署机本地路径，`{"image_url": {"url": "/app/data/..."}}` 会被
    静默丢图——"视觉模型说没收到图、工具反复 view_image"死循环的根因。
    读取失败/超限原样返回（由调用方向模型如实描述）。"""
    text = str(url or "").strip()
    if not text or text.startswith(("http://", "https://", "data:")):
        return text
    path = text[7:] if text.startswith("file://") else text
    try:
        from pathlib import Path as _Path

        file = _Path(path)
        if not file.is_file() or file.stat().st_size > max_bytes:
            return text
        import base64 as _base64

        suffix = file.suffix.lower().lstrip(".") or "png"
        if suffix == "jpg":
            suffix = "jpeg"
        return f"data:image/{suffix};base64," + _base64.b64encode(file.read_bytes()).decode()
    except Exception:
        return text


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

def module_version() -> str:
    """本模块版本号（状态卡显示用）。"""
    from importlib.metadata import version as _v

    try:
        return _v("ErisPulse-QvQChat")
    except Exception:
        from .version import __version__

        return __version__
