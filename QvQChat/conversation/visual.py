from __future__ import annotations

import json

from .. import texts


def _short(text, limit: int = 80) -> str:
# 参数/输出里常见字面量 \n、\t（JSON 转义的代码片段）：先还原成空格再压缩，
# 避免合并转发卡里出现满屏空行和 \n 字面量
    text = str(text or "").replace("\\r", " ").replace("\\n", " ").replace("\\t", " ")
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def _loads(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def visual_args(args: str) -> str:
    data = _loads(str(args or ""))
    if isinstance(data, dict):
        pairs = []
        for key, value in data.items():
            v = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            pairs.append(f"{key}={_short(v, 40)}")
        return _short("、".join(pairs) or "无参数", 140)
    if data is None:
        return _short(args, 100)
    return _short(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False), 100)


def visual_output(output: str) -> str:
    text = str(output or "").strip()
    if not text:
        return ""
    data = _loads(text)
    if isinstance(data, dict):
        pairs = []
        for key, value in list(data.items())[:3]:
            v = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            pairs.append(f"{key}={_short(v, 40)}")
        more = "" if len(data) <= 3 else f"（共 {len(data)} 项）"
        return _short("、".join(pairs), 180) + more
    if isinstance(data, list):
        return _short(f"共 {len(data)} 项：{json.dumps(data[:2], ensure_ascii=False)}", 180)
    return _short(text, 180)


def visual_call(entry: dict) -> str:
    name = str(entry.get("tool") or "")
    label = texts.t(f"tool.{name}.name", default=name)
    ms = entry.get("ms")
    args = str(entry.get("arguments") or "")
    line = label + ("：" + visual_args(args) if args else "")
    if ms is not None:
        line += f"（{ms}ms）"
    out = visual_output(entry.get("output"))
    if out:
        line += "\n" + texts.t("forward_result", output=out)
    return line


def build_sections(rounds: list | None, reply: str, tool_trace: list | None) -> list:
    """合并卡节点序列：AI 每段发言一条节点，连续工具调用合并为一条节点。"""
    sections: list[str] = []
    text_count = 0
    tool_group: list[dict] = []

    def flush_tools():
        if tool_group:
            body = "\n".join(visual_call(e) for e in tool_group)
            sections.append(texts.t("forward_process_title") + "\n" + body)
            tool_group.clear()

    for round_data in rounds or []:
        if not isinstance(round_data, dict):
            continue
        for entry in round_data.get("tools") or []:
            if isinstance(entry, dict):
                tool_group.append(entry)
        text = str(round_data.get("text") or "").strip()
        if text:
            flush_tools()
            sections.append(text)
            text_count += 1
    flush_tools()

    if not sections:
        for entry in tool_trace or []:
            if isinstance(entry, dict):
                tool_group.append(entry)
        flush_tools()
    if not sections:
        sections = [reply]
    if len(sections) > 40:
        sections = sections[:39] + ["…"]
    return sections, text_count
