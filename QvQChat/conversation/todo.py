"""会话级 TODO 清单存储（AI 长任务进度管理的状态面）。

键 ``QvQChat:todo:{chat_key}`` 单 KV / 会话；条目
``{id, content(≤200), status: pending|in_progress|completed, created, updated}``
（形状权威定义见 TodoItem，存储/返回仍为 dict——KV/HTTP 形状不变）。
容量 TODO_MAX=50（FIFO 淘汰最旧已完成，保 in_progress 与 pending）。
渲染 ``render()`` 输出复选框文本，经 SystemPart("todo") 注入系统提示，
让主智能体随时知道当前任务进度（budget PRIORITY 4.2，紧随 facts）。

存储访问全部走异步接口（aget/aset/adelete）：框架同步 get/set 在事件循环内
会经 AsyncBridge 阻塞（超时返回 None），读写方法一律 async def，调用方必须 await。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

TODO_PREFIX = "QvQChat:todo:"
TODO_MAX = 50
CONTENT_MAX = 200
STATUSES = ("pending", "in_progress", "completed")
_STATUS_MARK = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}


@dataclass
class TodoItem:
    """TODO 条目形状权威（KV 中为 to_dict 形态；读取侧保持 dict 不包对象）。"""

    id: str
    content: str
    status: str = "pending"
    created: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"id": self.id, "content": self.content, "status": self.status,
                "created": self.created, "updated": self.updated}

    @classmethod
    def create(cls, content: str, status: str = "pending", now: float | None = None) -> dict | None:
        """新建条目 dict：内容清洗（trim/≤200）+ 状态合法性；不合法返回 None。"""
        text = str(content or "").strip()[:CONTENT_MAX]
        if not text or status not in STATUSES:
            return None
        ts = time.time() if now is None else now
        return cls(id="", content=text, status=status, created=ts, updated=ts).to_dict()


class TodoStore:
    def __init__(self, sdk: Any, config: Any = None):
        self.sdk = sdk
        self.config = config

    def _key(self, chat_key: str) -> str:
        return TODO_PREFIX + str(chat_key or "")

    async def _load(self, chat_key: str) -> list:
        raw = await self.sdk.storage.aget(self._key(chat_key), [])
        return [item for item in (raw if isinstance(raw, list) else []) if isinstance(item, dict)]

    async def _save(self, chat_key: str, items: list) -> None:
        await self.sdk.storage.aset(self._key(chat_key), items[:TODO_MAX])

    async def items(self, chat_key: str) -> list:
        return await self._load(chat_key)

    async def replace(self, chat_key: str, contents: list) -> list:
        """全量替换（TodoWrite 语义）：旧清单清空，按新内容建 pending 条目。"""
        now = self._now()
        stored = await self._load(chat_key)
        kept = [
            dict(item) for item in stored
            if item.get("status") == "in_progress"
        ]
        out: list = []
        for content in contents:
            item = TodoItem.create(content, now=now)
            if item is None:
                continue
            item["id"] = self._new_id(out)
            out.append(item)
        for item in kept[:5]:  # 进行中的任务保留（AI 全量重写时不易丢正在做的）
            out.append({**item, "id": self._new_id(out), "updated": now})
        await self._save(chat_key, out)
        return out

    async def update(self, chat_key: str, todo_id: str, status: str = "", content: str = "") -> dict | None:
        """更新单条：改状态或内容；status 非法/条目不存在返回 None。"""
        status = str(status or "").strip().lower()
        if status and status not in STATUSES:
            return None
        content = str(content or "").strip()[:CONTENT_MAX]
        items = await self._load(chat_key)
        for item in items:
            if str(item.get("id")) == str(todo_id):
                if status:
                    item["status"] = status
                if content:
                    item["content"] = content
                item["updated"] = self._now()
                await self._save(chat_key, items)
                return item
        return None

    async def add(self, chat_key: str, content: str, status: str = "pending") -> dict | None:
        item = TodoItem.create(content, status=status)
        if item is None:
            return None
        items = await self._load(chat_key)
        item["id"] = self._new_id(items)
        items.append(item)
        await self._save(chat_key, items)
        return item

    async def remove(self, chat_key: str, todo_id: str) -> bool:
        """删除单条（面板用）：按 id 精确移除，不影响其余条目状态。"""
        items = await self._load(chat_key)
        kept = [item for item in items if str(item.get("id")) != str(todo_id)]
        if len(kept) == len(items):
            return False
        await self._save(chat_key, kept)
        return True

    async def render(self, chat_key: str) -> str:
        """复选框文本（系统提示注入用）；空清单返回空串（不注入部件）。"""
        lines = []
        for item in await self._load(chat_key):
            mark = _STATUS_MARK.get(str(item.get("status")), "[ ]")
            lines.append(f"{mark} {item.get('content', '')}")
        return "\n".join(lines)

    async def clear(self, chat_key: str) -> None:
        await self.sdk.storage.adelete(self._key(chat_key))

    # ---------- 内部 ----------

    @staticmethod
    def _now() -> float:
        return time.time()

    @staticmethod
    def _new_id(existing: list) -> str:
        used = {str(i.get("id")) for i in existing}
        while True:
            new = uuid.uuid4().hex[:6]
            if new not in used:
                return new
