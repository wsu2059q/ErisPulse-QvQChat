from __future__ import annotations

import asyncio
import base64 as _base64
import hashlib as _hashlib
import re as _re
from pathlib import Path
from typing import Any
from urllib.parse import unquote as _unquote

from .. import texts, utils
from .compactor import Compactor, context_tokens, estimate_tokens

CONV_PREFIX = "QvQChat:conv:"
ROUTES_KEY = "QvQChat:routes"
UPLOAD_DIR = Path("data/QvQChat/uploads")

DASHBOARD_PLATFORM = "dashboard"


def make_chat_key(platform: str, detail_type: str, target_id: str) -> str:
    return f"{platform}:{detail_type}:{target_id}"


def parse_chat_key(chat_key: str) -> tuple[str, str, str]:
    parts = chat_key.split(":", 2)
    if len(parts) != 3:
        return ("", "", "")
    return (parts[0], parts[1], parts[2])


_ISOLATION_RE = _re.compile(r"^([^:]+):group:([^:]+):u[^:]+$")


def strip_isolation(chat_key: str) -> str:
    """仅对形如 platform:group:<群>:u<成员> 的隔离 key 剥离成员后缀"""
    m = _ISOLATION_RE.match(chat_key or "")
    return f"{m.group(1)}:group:{m.group(2)}" if m else (chat_key or "")


class ConversationService:


    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self.config = main.cfg
        self.compactor = Compactor(main)


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

    def _save_no_touch(self, chat_key: str, state: dict) -> None:
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

    def append(self, chat_key: str, role: str, content, trace: list | None = None, rounds: list | None = None) -> None:
        state = self._state(chat_key)
        entry: dict = {"role": role, "content": content}
        if trace:
            entry["trace"] = list(trace)
        if rounds:
            entry["rounds"] = list(rounds)
        state["contexts"].append(entry)
        self._save(chat_key, state)

    def append_user(self, chat_key: str, content, sender_id: str = "") -> None:

        state = self._state(chat_key)
        entry: dict = {"role": "user", "content": content}
        if sender_id:
            entry["sender"] = sender_id
        state["contexts"].append(entry)
        state["turns"] = int(state.get("turns") or 0) + 1
        self._save(chat_key, state)

    def reset(self, chat_key: str) -> None:
        state = self._state(chat_key)
        state["contexts"] = []
        state["summary"] = ""
        state["turns"] = 0
        state["compacted_at_turn"] = 0
        self._save(chat_key, state)

    def edit_message(self, chat_key: str, index: int, content: str, attachments: list | None = None) -> bool:
        contexts = self.get_contexts(chat_key)
        if not (0 <= index < len(contexts)):
            return False
        entry = contexts[index]
        if isinstance(attachments, list):
            entry["content"] = self.rebuild_user_content(content, attachments)
        elif isinstance(entry.get("content"), list):
            kept = [p for p in entry["content"] if isinstance(p, dict) and p.get("type") != "text"]
            merged = ([{"type": "text", "text": content}] + kept) if content else kept
            entry["content"] = merged or content
        else:
            entry["content"] = content
        self.replace_contexts(chat_key, contexts)
        return True

    def delete_message(self, chat_key: str, index: int) -> bool:
        contexts = self.get_contexts(chat_key)
        if not (0 <= index < len(contexts)):
            return False
        contexts.pop(index)
        self.replace_contexts(chat_key, contexts)
        return True

    def trim_overflow(self, chat_key: str, keep: int) -> list:
        state = self._state(chat_key)
        contexts = state["contexts"]
        if len(contexts) <= keep:
            return []
        removed = contexts[: len(contexts) - keep]
        state["contexts"] = contexts[-keep:]
        self._save(chat_key, state)
        return removed


    def set_persona(self, chat_key: str, persona_id: str | None) -> None:
        state = self._state(chat_key)
        state["persona"] = persona_id
        self._save_no_touch(chat_key, state)

    def persona_of(self, chat_key: str) -> str | None:
        return self._state(chat_key)["persona"]

    def set_flags(self, chat_key: str, pinned: bool | None = None, archived: bool | None = None) -> None:

        state = self._state(chat_key)
        if pinned is not None:
            state["pinned"] = bool(pinned)
        if archived is not None:
            state["archived"] = bool(archived)
        self._save_no_touch(chat_key, state)

    # ===== 会话成员白名单与跨会话路由 =====

    def routes(self) -> dict:
        data = self.sdk.storage.get(ROUTES_KEY, {})
        return {k: str(v) for k, v in data.items() if isinstance(k, str) and v} if isinstance(data, dict) else {}

    def save_routes(self, routes: dict) -> None:
        self.sdk.storage.set(ROUTES_KEY, {str(k): str(v) for k, v in (routes or {}).items() if v})

    def resolve_route(self, chat_key: str) -> str:
        """消息来源 key → 目标会话 key；群隔离 key 先精确匹配再回落到群 base key"""
        routes = self.routes()
        if not routes:
            return ""
        if chat_key in routes:
            return routes[chat_key]
        base = strip_isolation(chat_key)
        if base != chat_key:
            return routes.get(base, "")
        return ""

    def routes_into(self, target: str) -> list[str]:
        return sorted(k for k, v in self.routes().items() if v == target)

    def members_of(self, chat_key: str) -> list[str]:
        members = self._state(chat_key).get("members")
        return members if isinstance(members, list) and members else ["*"]

    def set_members(self, chat_key: str, members: list) -> list[str]:
        cleaned: list[str] = []
        for item in members if isinstance(members, list) else []:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        state = self._state(chat_key)
        state["members"] = cleaned or ["*"]
        self._save_no_touch(chat_key, state)
        return state["members"]

    def member_allowed(self, chat_key: str, user_id: str, platform: str = "") -> bool:
        members = self.members_of(chat_key)
        if "*" in members:
            return True
        uid = str(user_id or "")
        if not uid:
            return False
        return uid in members or f"{platform}:{uid}" in members

    def set_ui(self, chat_key: str, ui: dict) -> dict:

        state = self._state(chat_key)
        cur = state.get("ui") if isinstance(state.get("ui"), dict) else {}
        cur.update({k: v for k, v in (ui or {}).items() if v is not None})
        state["ui"] = cur
        self._save_no_touch(chat_key, state)
        return cur

    def group_name_of(self, chat_key: str) -> str:
        return str(self._state(chat_key).get("group_name") or "")

    def set_group_name(self, chat_key: str, name: str) -> None:
        state = self._state(chat_key)
        state["group_name"] = name
        self._save(chat_key, state)

    def user_name_of(self, chat_key: str) -> str:
        return str(self._state(chat_key).get("user_name") or "")

    def set_user_name(self, chat_key: str, name: str) -> None:
        state = self._state(chat_key)
        state["user_name"] = name
        self._save(chat_key, state)

    def label_incoming(self, text: str, sender_id: str = "", sender_name: str = "") -> str:
        if not sender_id and not sender_name:
            return text
        who = f"{sender_name}({sender_id})" if sender_name else f"({sender_id})"
        return f"{who}: {text}"

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


    def _turn_count(self, chat_key: str) -> int:
        return int(self._state(chat_key).get("turns") or 0)

    def turns_since_compact(self, chat_key: str) -> int:
        state = self._state(chat_key)
        return int(state.get("turns") or 0) - int(state.get("compacted_at_turn") or 0)

    def mark_compacted(self, chat_key: str) -> None:
        state = self._state(chat_key)
        state["compacted_at_turn"] = int(state.get("turns") or 0)
        self._save_no_touch(chat_key, state)

    async def compact_if_needed(self, chat_key: str) -> dict:
        return await self.compactor.compact(chat_key, force=False, reason="auto")

    async def compact_now(self, chat_key: str) -> dict:
        return await self.compactor.compact(chat_key, force=True, reason="manual")


    def create(self, platform: str = DASHBOARD_PLATFORM, detail_type: str = "private", target_id: str = "") -> str:

        if target_id:
            chat_key = make_chat_key(platform, detail_type, target_id)
            self._state(chat_key)
            return chat_key
        prefix = make_chat_key(platform, detail_type, "")
        existing = {
            key[len(CONV_PREFIX):]
            for key in self.sdk.storage.keys()
            if isinstance(key, str) and key.startswith(CONV_PREFIX)
        }
        chat_key = prefix + "web"
        if chat_key in existing and (self._state(chat_key).get("contexts") or self._state(chat_key).get("summary")):
            n = 2
            while (prefix + f"web{n}") in existing:
                n += 1
            chat_key = prefix + f"web{n}"
        state = self._state(chat_key)
        self._save(chat_key, state)
        return chat_key

    def delete(self, chat_key: str) -> bool:

        existed = self.sdk.storage.get(CONV_PREFIX + chat_key, None) is not None
        registry = getattr(self.main, "live_registry", None)
        if registry is not None:
            live = registry.get(chat_key)
            if live is not None and live.status == "running":
                live.cancel()
            registry.drop(chat_key)
        self.sdk.storage.delete(CONV_PREFIX + chat_key)
        self.main.memory.clear(chat_key)
        personas = getattr(self.main, "personas", None)
        if personas is not None:
            personas.bind(chat_key, None)
        return existed

    def delete_archived(self) -> int:
        removed = 0
        for session in self.list_sessions():
            if session.get("archived"):
                if self.delete(session["chat_key"]):
                    removed += 1
        return removed

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
                        preview = utils.truncate(self._text_of(content), 60)
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


    async def prepare(
        self,
        chat_key: str,
        text: str,
        *,
        images: list | None = None,
        scene: str = "",
        persona_id: str = "",
        active_skills: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        seed_provider: Any = None,
        cross_user_id: str = "",
        persist: bool = True,
    ) -> dict:


        await self.compact_if_needed(chat_key)
        contexts = self.get_contexts(chat_key)
        # 发送级轮窗口：只携带最近 N 轮，历史本身不动
        max_turns = int(getattr(self.config, "max_context_turns", 0) or 0)
        if max_turns > 0:
            from .compactor import split_turns, merge_turns

            turns = split_turns(contexts)
            if len(turns) > max_turns:
                contexts = merge_turns(turns[-max_turns:])
        if not contexts and seed_provider is not None:
            seeded = seed_provider()
            if asyncio.iscoroutine(seeded):
                seeded = await seeded
            seeded = list(seeded) if seeded else []
            if not seeded and cross_user_id:
                cross = self.recent_user_messages(cross_user_id, exclude_chat_key=chat_key)
                if cross:
                    lines: list[str] = []
                    for item in cross:
                        lines.append(f"[来自 {item['label']}]")
                        lines.append(item["content"])
                    seeded = [{"role": "user", "content": texts.t("cross_session_header") + "\n" + "\n".join(lines)}]
            if seeded:
                contexts = self.seed_contexts(chat_key, seeded)
        personas = getattr(self.main, "personas", None)
        persona = personas.get(persona_id) if (persona_id and personas) else personas.resolve(chat_key)
        system = self.build_system(persona, scene=scene, chat_key=chat_key, active_skills=active_skills, mcp_tools=mcp_tools, kb_query=self._text_of(text))
        memory = getattr(self.main, "memory", None)
        if memory is not None:
            recalled = memory.recall(chat_key, query=self._text_of(text), limit=int(getattr(self.config, "memory_recall", 6)))
            if recalled:
                lines = "\n".join(f"- {entry.get('content', '')}" for entry in recalled)
                system += "\n\nRelated memories:\n" + lines
        user_msg: dict = {"role": "user", "content": text}
        if images:
            pool = getattr(self.main, "pool", None)
            caps = {}
            try:
                caps = pool.primary_capabilities() if pool else {}
            except Exception:
                caps = {}
            if caps.get("vision") is False:
                described = await pool.describe_images(images) if pool else []
                lines = [f"[image {i + 1}] {d}" for i, d in enumerate(described) if d]
                if lines:
                    merged = (text + "\n\n" if text else "") + texts.t("vision_delegate_note") + "\n" + "\n".join(lines)
                    user_msg["content"] = merged
                    images = None
            if images:
                parts: list = [{"type": "text", "text": text}] if text else []
                parts += [{"type": "image_url", "image_url": {"url": url}} for url in images[:3]]
                user_msg["content"] = parts
        if persist:
            self.append_user(chat_key, user_msg["content"], sender_id=self._persist_sender(chat_key, cross_user_id))
        return {"system": system, "contexts": contexts, "user_msg": user_msg, "persona": persona}

    @staticmethod
    def _persist_sender(chat_key: str, cross_user_id: str) -> str:
        platform, detail_type, _ = parse_chat_key(chat_key)
        if platform == DASHBOARD_PLATFORM:
            return "dashboard"
        return cross_user_id if detail_type != "group" else ""

    def finalize(
        self,
        chat_key: str,
        reply: str,
        *,
        trace: list | None = None,
        rounds: list | None = None,
        usage: dict | None = None,
        model: str = "",
        title_from: str = "",
    ) -> str:

        self.append(chat_key, "assistant", reply, trace=trace, rounds=rounds)
        if usage:
            self.main.record_usage(chat_key, usage, model)
        overflow = self.trim_overflow(chat_key, keep=max(2, int(getattr(self.config, "context_limit", 30))))
        if overflow:
            self.main.spawn(self._summarize_overflow(chat_key, overflow))
        if title_from and not self.group_name_of(chat_key):
            self.main.spawn(self.title_task(chat_key, title_from, reply))
        return reply

    async def _summarize_overflow(self, chat_key: str, removed: list) -> None:
        summary = await self.compactor.summarize_entries(removed)
        if summary:
            self.append_summary(chat_key, summary)


    def build_system(
        self,
        persona: dict,
        scene: str = "",
        chat_key: str = "",
        active_skills: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        kb_query: str = "",
    ) -> str:
        from ..Main import CAPABILITY_PROMPT

        system = persona["system"] + "\n" + utils.time_line()
        if scene:
            system += "\n" + scene
        if chat_key:
            summary = self.summary_of(chat_key)
            if summary:
                system += "\nEarlier conversation summary (older than recent messages):\n" + summary
        system += "\n" + CAPABILITY_PROMPT
        system += "\n" + texts.t("system_brevity")
        skills = getattr(self.main, "skills", None)
        if skills:
            if active_skills:
                for name in active_skills:
                    skill = skills.get_skill(str(name))
                    if not skill:
                        continue
                    system += (
                        "\n\n<active-skill name=\"" + str(name) + "\">\n"
                        + utils.truncate(str(skill.get("body") or ""), 8000)
                        + "\n</active-skill>"
                    )
            enabled = [s for s in skills.list_skills() if s.get("enabled")]
            if enabled:
                lines = "\n".join(f"- {s['name']}: {s.get('description') or ''}" for s in enabled)
                system += "\n\n<skills>\n" + texts.t("skills_system_note") + "\n" + lines + "\n</skills>"
        if mcp_tools:
            tools_hint = [str(t) for t in mcp_tools if str(t)]
            if tools_hint:
                system += "\n\n" + texts.t("dashboard_mcp_hint", tools=", ".join(tools_hint))
        if getattr(self.config, "kb_auto_inject", True) and kb_query:
            kb = getattr(self.main, "knowledge", None)
            hits = kb.search(kb_query, top_k=int(getattr(self.config, "kb_top_k", 2) or 0)) if kb else []
            if hits:
                blocks = "\n\n".join(
                    f"<kb-doc title=\"{h['title']}\">\n{h['snippet']}\n</kb-doc>" for h in hits
                )
                system += "\n\n" + texts.t("kb_system_note") + "\n" + blocks
        for line in getattr(self.config, "extra_prompts", []) or []:
            line = str(line).strip()
            if line:
                system += "\n" + line
        return system


    async def resolve_session_names(self, sessions: list[dict]) -> None:

        for session in sessions[:20]:
            chat_key = str(session.get("chat_key") or "")
            if session.get("name") or not chat_key:
                continue
            platform = str(session.get("platform") or "")
            detail_type = str(session.get("detail_type") or "")
            target_id = str(session.get("target_id") or "")
            if platform == DASHBOARD_PLATFORM or not platform or not target_id:
                continue
            try:
                adapter = self.sdk.adapter.get(platform)
            except Exception:
                adapter = None
            if adapter is None:
                continue
            name = ""
            try:
                if detail_type == "group":
                    info = await asyncio.wait_for(
                        adapter.call_api("get_group_info", group_id=target_id), 6
                    )
                    name = str((info or {}).get("group_name") or "") if isinstance(info, dict) else ""
                    if name:
                        self.set_group_name(chat_key, name)
                else:
                    for endpoint in ("get_stranger_info", "get_user_info"):
                        try:
                            info = await asyncio.wait_for(
                                adapter.call_api(endpoint, user_id=target_id), 6
                            )
                        except Exception:
                            continue
                        if isinstance(info, dict):
                            name = str(info.get("nickname") or info.get("card") or "")
                            if name:
                                break
                    if name:
                        self.set_user_name(chat_key, name)
            except Exception:
                continue

    async def title_task(self, chat_key: str, user_text: str, reply: str) -> None:

        pool = getattr(self.main, "pool", None)
        if pool is None:
            return
        try:
            resp = await pool.chat(
                ChatRequest(
                    messages=[
                        {"role": "system", "content": texts.t("title_system")},
                        {
                            "role": "user",
                            "content": utils.truncate(user_text, 200) + "\n---\n" + utils.truncate(reply, 300),
                        },
                    ],
                    max_tokens=48,
                    temperature=0.3,
                )
            )
            title = (resp.content or "").strip().strip("\"“”‘’。.!!??")
            title = title.splitlines()[0][:40] if title else ""
            if title:
                self.set_group_name(chat_key, title)
        except Exception as e:
            self.main.logger.warning(f"title generation failed: {e}")


    def save_upload(self, name: str, data: str) -> str | None:

        payload: bytes | None = None
        m = _re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data, _re.DOTALL)
        if m and m.group(2):
            try:
                payload = _base64.b64decode(m.group(3))
            except Exception:
                return None
        elif m:
            payload = _unquote(m.group(3)).encode("utf-8", "replace")
        else:
            payload = data.encode("utf-8", "replace")
        if payload is None:
            return None
        digest = _hashlib.sha256(payload).hexdigest()[:16]
        safe = _re.sub(r"[^\w.\-]+", "_", name, flags=_re.UNICODE).strip("_") or "file"
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            for existing in UPLOAD_DIR.iterdir():
                if existing.is_file() and existing.name.startswith(digest + "_"):
                    return str(existing)
            target = UPLOAD_DIR / f"{digest}_{safe}"
            target.write_bytes(payload)
        except OSError:
            return None
        return str(target)

    def rebuild_user_content(self, text: str, attachments: list):

        parts: list = []
        notes: list[str] = []
        if text:
            parts.append({"type": "text", "text": text})
        for att in attachments or []:
            if not isinstance(att, dict):
                continue
            name = str(att.get("name") or "file")
            mime = str(att.get("mime") or "").lower()
            data = str(att.get("data") or "")
            if not data:
                continue
            if mime.startswith("image/") and len(parts) < 4 and len(data) <= 7_000_000:
                url = data if data.startswith("data:") else f"data:{mime};base64,{data}"
                parts.append({"type": "image_url", "image_url": {"url": url}})
                continue
            saved = self.save_upload(name, data)
            if saved:
                size = Path(saved).stat().st_size
                notes.append(texts.t("attachment_saved", name=name, path=saved, size=size))
            else:
                notes.append(f"[attachment {name}]（保存失败，内容不可用）")
        if notes:
            tail = "\n\n".join(notes)
            if parts and parts[0].get("type") == "text":
                parts[0]["text"] = (parts[0]["text"] + "\n\n" + tail).strip()
            else:
                parts.insert(0, {"type": "text", "text": tail})
        if not parts:
            return text or ""
        if len(parts) == 1 and parts[0].get("type") == "text":
            return parts[0]["text"]
        return parts


    @staticmethod
    def _text_of(content) -> str:
        if isinstance(content, list):
            return " ".join(
                str(p.get("text") or "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        return str(content or "")
