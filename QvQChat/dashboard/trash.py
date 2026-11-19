"""删除回收站（撤销删除）：TrashStore 暂存载荷 + per-kind restore 注册表。

此前暂存/弹出散在 TrashMixin、还原逻辑是一条 8 分支的字符串 if/elif 链——
新删除类型都要改链。现在：暂存与 TTL 归 TrashStore，还原按 kind 在
build_restore_registry 注册（新类型加一行），mixin 只剩薄路由。
"""
from __future__ import annotations

import secrets
import time
from typing import Any

TRASH_PREFIX = "QvQChat:trash:"
# pop 有效性 10 分钟（撤销窗口）；列表页展示的 expires_in 按 trash_retention_days 计
TRASH_TTL = 600.0


class TrashStore:
    """删除前暂存（KV 存储）：put 返回撤销 token，pop 取出并核销（过期视作无效）。"""

    def __init__(self, sdk: Any):
        self.sdk = sdk

    def put(self, kind: str, payload) -> str:
        token = secrets.token_urlsafe(9)
        try:
            self.sdk.storage.set(TRASH_PREFIX + token, {"kind": kind, "payload": payload, "ts": time.time()})
        except Exception:
            pass
        return token

    def pop(self, token: str):
        key = TRASH_PREFIX + str(token or "")
        entry = None
        try:
            entry = self.sdk.storage.get(key, None)
            self.sdk.storage.delete(key)
        except Exception:
            entry = None
        if not isinstance(entry, dict):
            return None
        if time.time() - float(entry.get("ts") or 0) > TRASH_TTL:
            return None
        return entry

    def list(self, retention_days: int) -> list[dict]:
        """回收站浏览：kind/摘要/剩余秒（展示口径按 trash_retention_days）。"""
        now = time.time()
        out = []
        for key in self.sdk.storage.keys():
            if not (isinstance(key, str) and key.startswith(TRASH_PREFIX)):
                continue
            entry = self.sdk.storage.get(key, None)
            if not isinstance(entry, dict):
                continue
            ts = float(entry.get("ts") or 0)
            payload = entry.get("payload")
            summary = ""
            if isinstance(payload, dict):
                summary = str(payload.get("chat_key") or payload.get("name") or payload.get("title") or "")
                if payload.get("entries") is not None:
                    summary += f" ({len(payload['entries'])} entries)"
                if payload.get("items") is not None:
                    summary += f" ({len(payload['items'])} items)"
            out.append({
                "token": key[len(TRASH_PREFIX):],
                "kind": str(entry.get("kind") or ""),
                "summary": summary or "-",
                "ts": ts,
                "expires_in": max(0, int(ts + retention_days * 86400 - now)) if retention_days else -1,
            })
        out.sort(key=lambda item: -item["ts"])
        return out[:200]


def build_restore_registry(main) -> dict:
    """kind -> restore(payload)。还原实现挂在 main 的各服务上；
    新的删除类型在这里注册一行，不再往 if/elif 链里塞分支。"""
    def _restore_session(payload):
        from ..conversation.service import CONV_PREFIX

        main.sdk.storage.set(CONV_PREFIX + str(payload.get("chat_key") or ""), payload.get("state"))

    def _restore_skill(payload):
        main.skills.save_skill(str(payload.get("name") or ""), str(payload.get("description") or ""), str(payload.get("body") or ""))

    def _restore_kb(payload):
        main.knowledge.restore_entry(dict(payload))

    return {
        "session": _restore_session,
        "skill": _restore_skill,
        "persona": lambda payload: main.personas.save(dict(payload)),
        "provider": lambda payload: main.pool.save_provider(dict(payload)),
        "kb": _restore_kb,
        "binding": lambda payload: main.personas.bind(str(payload.get("chat_key") or ""), str(payload.get("persona") or "") or None),
        "kb_batch": lambda payload: [_restore_kb(kb_entry) for kb_entry in payload.get("entries") or []],
        "skill_batch": lambda payload: [
            main.skills.save_skill(str(sk.get("name") or ""), str(sk.get("description") or ""), str(sk.get("body") or ""))
            for sk in payload.get("items") or []
        ],
    }
