"""会话级 TODO 清单存储（AI 长任务进度管理的状态面）。

键 ``QvQChat:todo:{chat_key}`` 单 KV / 会话；条目
``{id, content(≤200), status: pending|in_progress|completed, created, updated}``。
容量 TODO_MAX=50（FIFO 淘汰最旧已完成，保 in_progress 与 pending）。
渲染 ``render()`` 输出复选框文本，经 SystemPart("todo") 注入系统提示，
让主智能体随时知道当前任务进度（budget PRIORITY 4.2，紧随 facts）。
"""

from __future__ import annotations

from typing import Any

TODO_PREFIX = "QvQChat:todo:"
TODO_MAX = 50
CONTENT_MAX = 200
STATUSES = ("pending", "in_progress", "completed")
_STATUS_MARK = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}


class TodoStore:
    def __init__(self, sdk: Any, config: Any = None):
        self.sdk = sdk
        self.config = config

    def _key(self, chat_key: str) -> str:
        return TODO_PREFIX + str(chat_key or "")

    def _load(self, chat_key: str) -> list:
        raw = self.sdk.storage.get(self._key(chat_key), [])
        return [item for item in (raw if isinstance(raw, list) else []) if isinstance(item, dict)]

    def _save(self, chat_key: str, items: list) -> None:
        self.sdk.storage.set(self._key(chat_key), items[:TODO_MAX])

    def items(self, chat_key: str) -> list:
        return self._load(chat_key)

    def replace(self, chat_key: str, contents: list) -> list:
        """全量替换（TodoWrite 语义）：旧清单清空，按新内容建 pending 条目。"""
        now = self._now()
        kept = [
            dict(item) for item in self._load(chat_key)
            if item.get("status") == "in_progress"
        ]
        out: list = []
        for content in contents:
            text = str(content or "").strip()[:CONTENT_MAX]
            if not text:
                continue
            out.append({"id": self._new_id(out), "content": text,
                        "status": "pending", "created": now, "updated": now})
        for item in kept[:5]:  # 进行中的任务保留（AI 全量重写时不易丢正在做的）
            out.append({**item, "id": self._new_id(out), "updated": now})
        self._save(chat_key, out)
        return out

    def update(self, chat_key: str, todo_id: str, status: str = "", content: str = "") -> dict | None:
        """更新单条：改状态或内容；status 非法/条目不存在返回 None。"""
        status = str(status or "").strip().lower()
        if status and status not in STATUSES:
            return None
        content = str(content or "").strip()[:CONTENT_MAX]
        items = self._load(chat_key)
        for item in items:
            if str(item.get("id")) == str(todo_id):
                if status:
                    item["status"] = status
                if content:
                    item["content"] = content
                item["updated"] = self._now()
                self._save(chat_key, items)
                return item
        return None

    def add(self, chat_key: str, content: str, status: str = "pending") -> dict | None:
        text = str(content or "").strip()[:CONTENT_MAX]
        if not text or status not in STATUSES:
            return None
        items = self._load(chat_key)
        now = self._now()
        item = {"id": self._new_id(items), "content": text, "status": status,
                "created": now, "updated": now}
        items.append(item)
        self._save(chat_key, items)
        return item

    def render(self, chat_key: str) -> str:
        """复选框文本（系统提示注入用）；空清单返回空串（不注入部件）。"""
        lines = []
        for item in self._load(chat_key):
            mark = _STATUS_MARK.get(str(item.get("status")), "[ ]")
            lines.append(f"{mark} {item.get('content', '')}")
        return "\n".join(lines)

    def clear(self, chat_key: str) -> None:
        self.sdk.storage.delete(self._key(chat_key))

    # ---------- 内部 ----------

    @staticmethod
    def _now() -> float:
        import time

        return time.time()

    @staticmethod
    def _new_id(existing: list) -> str:
        import uuid

        used = {str(i.get("id")) for i in existing}
        while True:
            new = uuid.uuid4().hex[:6]
            if new not in used:
                return new
