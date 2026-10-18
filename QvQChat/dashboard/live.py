"""对话流注册表：流式执行归属于后端，前端断开后可重连续看。

每个 dashboard 会话同一时间至多一个活跃流；流结束后记录保留一段时间，
供用户切走再回来时看到结果；再次发起新消息时覆盖旧记录。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

RETAIN_SECONDS = 2 * 3600


@dataclass
class LiveStream:
    session: str
    status: str = "running"  # running | done | error
    text: str = ""           # 累积的 assistant 输出（reset 会清空）
    steps: list = field(default_factory=list)  # [{start, end}]
    segments: list = field(default_factory=list)  # 有序：{type:text|tool, ...} 供串行渲染
    reply: str | None = None
    error: str | None = None
    started: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    subscribers: set = field(default_factory=set)
    task: asyncio.Task | None = None

    def cancel(self) -> bool:
        """链式取消：取消运行任务即贯穿中止 LLM 流、工具与子智能体。"""
        if self.status != "running" or self.task is None or self.task.done():
            return False
        self.task.cancel()
        return True

    def snapshot(self) -> dict:
        return {
            "session": self.session,
            "status": self.status,
            "text": self.text,
            "steps": self.steps,
            "segments": self.segments,
            "reply": self.reply,
            "error": self.error,
            "started": self.started,
        }

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


# ── 回调适配：把 runner 的 on_delta/on_reset/on_tool_event 写入 LiveStream ──

def bind(live: LiveStream):
    """返回 (on_delta, on_reset, on_tool_event)，由 run_dashboard_chat 透传给 runner。"""

    async def on_delta(piece: str) -> None:
        live.text += piece
        segs = live.segments
        if not segs or segs[-1].get("type") != "text":
            segs.append({"type": "text", "text": ""})
        segs[-1]["text"] += piece
        live.publish("delta", {"t": piece, "i": len(segs) - 1})

    async def on_reset() -> None:
        live.text = ""
        live.steps.clear()
        live.publish("reset", {})

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

    return on_delta, on_reset, on_tool_event
