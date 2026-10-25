


from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

RETAIN_SECONDS = 2 * 3600


@dataclass
class LiveStream:
    session: str
    status: str = "running"
    text: str = ""
    reasoning: str = ""
    steps: list = field(default_factory=list)
    segments: list = field(default_factory=list)
    reply: str | None = None
    error: str | None = None
    started: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    subscribers: set = field(default_factory=set)
    task: asyncio.Task | None = None

    def cancel(self) -> bool:

        if self.status != "running" or self.task is None or self.task.done():
            return False
        self.task.cancel()
        return True

    def snapshot(self) -> dict:
        return {
            "session": self.session,
            "status": self.status,
            "text": self.text,
            "reasoning": self.reasoning,
            "steps": self.steps,
            "segments": self.segments,
            "reply": self.reply,
            "error": self.error,
            "started": self.started,
        }

    def partial_record(self) -> tuple[str, list, list]:
        """取消/中断时从 steps 与 segments 还原 (text, trace, rounds)，保住中间步骤。"""

        trace = [
            {
                "tool": (step.get("start") or {}).get("name", "?"),
                "arguments": str((step.get("start") or {}).get("arguments", "") or ""),
                "output": str((step.get("end") or {}).get("output", "") or ""),
                "ms": int((step.get("end") or {}).get("ms") or 0),
            }
            for step in self.steps
            if step.get("start")
        ]
        rounds: list = []

        def _round() -> dict:
            if not rounds:
                rounds.append({"text": "", "tools": []})
            return rounds[-1]

        for seg in self.segments:
            if seg.get("type") == "tool":
                start = seg.get("start") or {}
                end = seg.get("end") or {}
                _round()["tools"].append(
                    {
                        "tool": start.get("name", "?"),
                        "arguments": str(start.get("arguments", "") or ""),
                        "output": str(end.get("output", "") or ""),
                        "ms": int(end.get("ms") or 0),
                    }
                )
            else:
                piece = str(seg.get("text") or "")
                if not piece:
                    continue
                if rounds and not rounds[-1]["tools"]:
                    rounds[-1]["text"] += piece
                else:
                    rounds.append({"text": piece, "tools": []})
        return self.text.strip(), trace, rounds

    def publish(self, event: str, data: dict) -> None:
        self.updated = time.time()
        for queue in list(self.subscribers):
            try:
                queue.put_nowait((event, data))
            except Exception:
                pass

    def stale(self) -> bool:
        return self.status != "running" and time.time() - self.updated > RETAIN_SECONDS


class LiveRegistry:
    def __init__(self):
        self._streams: dict[str, LiveStream] = {}

    def overview(self) -> list[dict]:
        self._cleanup()
        out = []
        for live in list(self._streams.values()):
            if live.status == "running" or not live.stale():
                out.append(
                    {
                        "session": live.session,
                        "status": live.status,
                        "started": live.started,
                        "steps": len(live.steps),
                        "text_head": (live.text or "")[:120],
                        "error": live.error or "",
                    }
                )
        out.sort(key=lambda item: item["started"], reverse=True)
        return out


    def get(self, session: str) -> LiveStream | None:
        live = self._streams.get(session)
        if live is not None and live.stale():
            self._streams.pop(session, None)
            return None
        return live

    def start(self, session: str) -> LiveStream:
        self._cleanup()
        live = LiveStream(session=session)
        self._streams[session] = live
        return live

    def _cleanup(self) -> None:
        for key in [k for k, v in self._streams.items() if v.stale()]:
            self._streams.pop(key, None)

    def busy(self, session: str) -> bool:
        live = self.get(session)
        return live is not None and live.status == "running"

    def drop(self, session: str) -> None:

        self._streams.pop(session, None)


def bind(live: LiveStream):


    async def on_delta(piece: str) -> None:
        live.text += piece
        segs = live.segments
        if not segs or segs[-1].get("type") != "text":
            segs.append({"type": "text", "text": ""})
        segs[-1]["text"] += piece
        live.publish("delta", {"t": piece, "i": len(segs) - 1})

    async def on_reset() -> None:
        live.text = ""
        live.reasoning = ""
        live.steps.clear()
        live.segments.clear()
        live.publish("reset", {"segments": []})

    async def on_reasoning(piece: str) -> None:
        if not piece:
            return
        live.reasoning += piece
        live.publish("reasoning", {"t": piece})

    async def on_tool_event(evt: dict) -> None:
        if evt.get("phase") == "start":
            live.segments.append({"type": "tool", "start": evt})
            live.steps.append({"start": evt})
        else:
            match = None
            for step in reversed(live.steps):
                if step.get("start", {}).get("step_id") == evt.get("step_id") and not step.get("end"):
                    match = step
                    break
            if match is None:
                for step in reversed(live.steps):
                    if not step.get("end"):
                        match = step
                        break
            if match is not None:
                match["end"] = evt
            seg = None
            for item in reversed(live.segments):
                if item.get("start", {}).get("step_id") == evt.get("step_id") and not item.get("end"):
                    seg = item
                    break
            if seg is None:
                for item in reversed(live.segments):
                    if item.get("type") == "tool" and not item.get("end"):
                        seg = item
                        break
            if seg is not None:
                seg["end"] = evt
        live.publish("tool", evt)

    return on_delta, on_reset, on_tool_event, on_reasoning
