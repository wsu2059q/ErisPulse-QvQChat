from __future__ import annotations

from typing import Any

from .. import utils

CONV_PREFIX = "QvQChat:conv:"


def make_chat_key(platform: str, detail_type: str, target_id: str) -> str:
    return f"{platform}:{detail_type}:{target_id}"


def parse_chat_key(chat_key: str) -> tuple[str, str, str]:
    parts = chat_key.split(":", 2)
    if len(parts) != 3:
        return ("", "", "")
    return (parts[0], parts[1], parts[2])


class SessionManager:
    def __init__(self, sdk: Any, config: Any):
        self.sdk = sdk
        self.config = config

    def _state(self, chat_key: str) -> dict:
        state = self.sdk.storage.get(CONV_PREFIX + chat_key, None)
        if not isinstance(state, dict):
            state = {}
        contexts = state.get("contexts")
        if not isinstance(contexts, list):
            contexts = []
        state["contexts"] = contexts
        state.setdefault("persona", None)
        state.setdefault("updated", 0.0)
        return state

    def _save(self, chat_key: str, state: dict) -> None:
        state["updated"] = utils.now_ts()
        limit = max(2, int(getattr(self.config, "context_limit", 30))) * 2
        state["contexts"] = state["contexts"][-limit:]
        self.sdk.storage.set(CONV_PREFIX + chat_key, state)

    def get_contexts(self, chat_key: str) -> list:
        return list(self._state(chat_key)["contexts"])

    def replace_contexts(self, chat_key: str, contexts: list) -> None:
        state = self._state(chat_key)
        state["contexts"] = list(contexts)
        self._save(chat_key, state)

    def seed_contexts(self, chat_key: str, seed: list) -> list:
        state = self._state(chat_key)
        if state["contexts"]:
            return list(state["contexts"])
        state["contexts"] = list(seed)
        self._save(chat_key, state)
        return list(seed)

    def recent_user_messages(self, user_id: str, exclude_chat_key: str = "", limit: int = 6) -> list[dict]:
        needle = f"({user_id}):"
        found: list[dict] = []
        for key in self.sdk.storage.keys():
            if not isinstance(key, str) or not key.startswith(CONV_PREFIX):
                continue
            chat_key = key[len(CONV_PREFIX):]
            if chat_key == exclude_chat_key or ":group:" not in chat_key:
                continue
            state = self._state(chat_key)
            contexts = state.get("contexts") or []
            matches = [
                str(c.get("content") or "")
                for c in contexts
                if isinstance(c, dict)
                and c.get("role") == "user"
                and (c.get("sender") == user_id or needle in str(c.get("content") or ""))
            ]
            if not matches:
                continue
            group_name = str(state.get("group_name") or "")
            group_id = chat_key.split(":", 2)[2] if len(chat_key.split(":", 2)) == 3 else chat_key
            label = f"{group_name}({group_id})" if group_name else group_id
            found.append(
                {
                    "label": label,
                    "messages": matches[-3:],
                    "updated": state.get("updated") or 0.0,
                }
            )
        found.sort(key=lambda item: item["updated"], reverse=True)
        out: list[dict] = []
        for item in found[:3]:
            for content in item["messages"]:
                out.append({"label": item["label"], "content": content})
        return out[:limit]

    def append(self, chat_key: str, role: str, content: str, trace: list | None = None, rounds: list | None = None) -> None:
        state = self._state(chat_key)
        entry: dict = {"role": role, "content": content}
        if trace:
            # 以下仅用于回放展示；送入模型前 sanitize_contexts 会剥掉这些字段
            entry["trace"] = list(trace)
        if rounds:
            entry["rounds"] = list(rounds)
        state["contexts"].append(entry)
        self._save(chat_key, state)

    def append_user(self, chat_key: str, content, sender_id: str = "") -> None:
        """content 可为纯文本或多模态段列表（text/image_url），历史保留图片供回放与编辑。"""
        state = self._state(chat_key)
        entry: dict = {"role": "user", "content": content}
        if sender_id:
            entry["sender"] = sender_id
        state["contexts"].append(entry)
        self._save(chat_key, state)

    def reset(self, chat_key: str) -> None:
        state = self._state(chat_key)
        state["contexts"] = []
        self._save(chat_key, state)

    def set_persona(self, chat_key: str, persona_id: str | None) -> None:
        state = self._state(chat_key)
        state["persona"] = persona_id
        self._save(chat_key, state)

    def set_flags(self, chat_key: str, pinned: bool | None = None, archived: bool | None = None) -> None:
        """置顶/归档标记；不刷新会话的 updated 时间。"""
        state = self._state(chat_key)
        if pinned is not None:
            state["pinned"] = bool(pinned)
        if archived is not None:
            state["archived"] = bool(archived)
        limit = max(2, int(getattr(self.config, "context_limit", 30))) * 2
        state["contexts"] = state["contexts"][-limit:]
        self.sdk.storage.set(CONV_PREFIX + chat_key, state)

    def set_ui(self, chat_key: str, ui: dict) -> dict:
        """会话级 UI 设置（密度/模型/强度等）；不刷新 updated。"""
        state = self._state(chat_key)
        cur = state.get("ui") if isinstance(state.get("ui"), dict) else {}
        cur.update({k: v for k, v in (ui or {}).items() if v is not None})
        state["ui"] = cur
        limit = max(2, int(getattr(self.config, "context_limit", 30))) * 2
        state["contexts"] = state["contexts"][-limit:]
        self.sdk.storage.set(CONV_PREFIX + chat_key, state)
        return cur

    def persona_of(self, chat_key: str) -> str | None:
        return self._state(chat_key)["persona"]

    def group_name_of(self, chat_key: str) -> str:
        state = self._state(chat_key)
        return str(state.get("group_name") or "")

    def set_group_name(self, chat_key: str, name: str) -> None:
        state = self._state(chat_key)
        state["group_name"] = name
        self._save(chat_key, state)

    def user_name_of(self, chat_key: str) -> str:
        state = self._state(chat_key)
        return str(state.get("user_name") or "")

    def set_user_name(self, chat_key: str, name: str) -> None:
        state = self._state(chat_key)
        state["user_name"] = name
        self._save(chat_key, state)

    def label_incoming(self, text: str, sender_id: str = "", sender_name: str = "") -> str:
        if not sender_id and not sender_name:
            return text
        who = f"{sender_name}({sender_id})" if sender_name else f"({sender_id})"
        return f"{who}: {text}"

    def trim_overflow(self, chat_key: str, keep: int) -> list:
        state = self._state(chat_key)
        contexts = state["contexts"]
        if len(contexts) <= keep:
            return []
        removed = contexts[: len(contexts) - keep]
        state["contexts"] = contexts[-keep:]
        self._save(chat_key, state)
        return removed

    def summary_of(self, chat_key: str) -> str:
        return str(self._state(chat_key).get("summary") or "")

    def append_summary(self, chat_key: str, text: str, cap: int = 1500) -> None:
        state = self._state(chat_key)
        old = str(state.get("summary") or "")
        merged = (old + "\n" + text).strip() if old else text.strip()
        if len(merged) > cap:
            merged = merged[-cap:]
        state["summary"] = merged
        self._save(chat_key, state)

    def list_sessions(self) -> list[dict]:
        sessions: list[dict] = []
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith(CONV_PREFIX):
                chat_key = key[len(CONV_PREFIX):]
                state = self._state(chat_key)
                preview = ""
                for entry in reversed(state["contexts"]):
                    content = entry.get("content") if isinstance(entry, dict) else None
                    if content:
                        preview = str(content)[:60]
                        break
                platform, detail_type, target_id = parse_chat_key(chat_key)
                sessions.append(
                    {
                        "chat_key": chat_key,
                        "platform": platform,
                        "detail_type": detail_type,
                        "target_id": target_id,
                        "name": str(state.get("group_name") or "") or str(state.get("user_name") or ""),
                        "persona": state["persona"],
                        "turns": len(state["contexts"]),
                        "updated": state["updated"],
                        "preview": preview,
                        "pinned": bool(state.get("pinned")),
                        "archived": bool(state.get("archived")),
                        "ui": state.get("ui") if isinstance(state.get("ui"), dict) else {},
                    }
                )
        sessions.sort(key=lambda s: (not s["pinned"], -s["updated"]))
        return sessions
