"""会话域 API（拆分自 dashboard/manager.py）：sessions / messages / share / routes / memory / UI 默认值。

mixin 由 DashboardManager 组合，HTTP 路由路径不变（路由表仍在 manager.py）。
"""
from __future__ import annotations

from pathlib import Path

from .. import texts, utils

TEMPLATES = Path(__file__).parent / "templates"
SHARES_KEY = "QvQChat:shares"
UI_DEFAULTS_KEY = "QvQChat:ui_defaults"


class SessionsApiMixin:
    """依赖宿主提供 self.main / self.sdk / self._query / self._live。"""

    async def sessions_get(self, request):
        sessions = self.main.sessions.list_sessions()
        for session in sessions:
            if str(session.get("platform") or "") == "dashboard" and not session.get("name"):
                session["name"] = texts.t("dashboard_session_name")
            session["members"] = self.main.sessions.members_of(session.get("chat_key") or "")
            session["sources"] = self.main.sessions.routes_into(session.get("chat_key") or "")
        try:
            self.main.spawn(self.main.conversations.resolve_session_names(sessions))
        except Exception as e:
            self.main.logger.debug(f"resolve session names failed: {e}")
        live_keys = set()
        try:
            for s in sessions:
                if self._live.busy(s["chat_key"]):
                    live_keys.add(s["chat_key"])
                    s["live"] = True
        except Exception as e:
            self.main.logger.debug(f"live session mark failed: {e}")
        return {"sessions": sessions, "live_sessions": sorted(live_keys), "ui_defaults": self._ui_defaults()}

    async def session_messages(self, request):
        chat_key = self._query(request, "chat_key")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        contexts = self.main.sessions.get_contexts(chat_key)
        total = len(contexts)
# 窗口参数：start/limit 按需加载；start 缺省且给 limit 时取尾部一页
        start_raw = self._query(request, "start")
        limit_raw = self._query(request, "limit")
        start_i, limit_n = 0, 0
        try:
            limit_n = max(1, int(limit_raw)) if limit_raw else 0
        except ValueError:
            limit_n = 0
        try:
            start_i = int(start_raw) if start_raw is not None else None
        except ValueError:
            start_i = None
        if limit_n:
            if start_i is None:
                start_i = max(0, total - limit_n)
            start_i = max(0, min(start_i, total))
            window = contexts[start_i : start_i + limit_n]
        else:
            start_i = 0
            window = contexts
        for message in window:
            if isinstance(message, dict) and isinstance(message.get("content"), list):
                images = [p for p in message["content"] if isinstance(p, dict) and p.get("type") == "image_url"]
                if images:
                    message["atts"] = [
                        {"isImage": True, "name": "image", "data": (p.get("image_url") or {}).get("url", "")}
                        for p in images
                    ]
        return {"chat_key": chat_key, "summary": self.main.sessions.summary_of(chat_key) if start_i == 0 else "",
                "messages": window, "total": total, "start": start_i}

    async def session_message_delete(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        index = int((body or {}).get("index", -1))
        if self.main.conversations.delete_message(chat_key, index):
            return {"ok": True}
        return ({"error": "index out of range"}, 400)

    async def session_context_edit(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        index = int((body or {}).get("index", -1))
        content = str((body or {}).get("content") or "")
        attachments = (body or {}).get("attachments")
        if self.main.conversations.edit_message(chat_key, index, content, attachments):
            return {"ok": True}
        return ({"error": "index out of range"}, 400)

    async def sessions_delete(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        return {"ok": self.main.conversations.delete(chat_key)}

    async def sessions_create(self, request):
        body = await request.json()
        chat_key = self.main.conversations.create(
            platform=str((body or {}).get("platform") or "dashboard"),
            detail_type=str((body or {}).get("detail_type") or "private"),
            target_id=str((body or {}).get("target_id") or ""),
        )
        return {"ok": True, "chat_key": chat_key}

    async def sessions_delete_archived(self, request):
        return {"ok": True, "removed": self.main.conversations.delete_archived()}

    async def session_compact(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        report = await self.main.conversations.compact_now(chat_key)
        return {"ok": True, "report": report}

    async def sessions_reset(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        self.main.sessions.reset(chat_key)
        return {"ok": True}

    async def session_flags(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        pinned = (body or {}).get("pinned")
        archived = (body or {}).get("archived")
        self.main.sessions.set_flags(
            chat_key,
            pinned=None if pinned is None else bool(pinned),
            archived=None if archived is None else bool(archived),
        )
        return {"ok": True}

    async def session_settings(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        ui = (body or {}).get("settings")
        if not isinstance(ui, dict):
            return ({"error": "settings object required"}, 400)
        saved = self.main.sessions.set_ui(chat_key, {k: str(ui[k]) for k in ("density", "model", "effort") if ui.get(k) is not None})
        members = ui.get("members")
        if isinstance(members, list):
            saved["members"] = self.main.sessions.set_members(chat_key, members)
        return {"ok": True, "ui": saved}

    async def session_routes(self, request):
        body = await request.json()
        target = str((body or {}).get("target") or "").strip()
        if not target:
            return ({"error": "target required"}, 400)
        sources = (body or {}).get("sources")
        if isinstance(sources, list):
            routes = {k: v for k, v in self.main.sessions.routes().items() if v != target}
            for src in sources:
                src = str(src).strip()
                if src and src != target:
                    routes[src] = target
            self.main.sessions.save_routes(routes)
            return {"ok": True, "sources": sorted(k for k, v in routes.items() if v == target)}
        return {"sources": self.main.sessions.routes_into(target)}

    def _ui_defaults(self) -> dict:
        d = self.sdk.storage.get(UI_DEFAULTS_KEY, {})
        return d if isinstance(d, dict) else {}

    async def settings_defaults_get(self, request):
        return {"ui_defaults": self._ui_defaults()}

    async def settings_defaults_set(self, request):
        body = await request.json()
        ui = (body or {}).get("settings")
        if not isinstance(ui, dict):
            return ({"error": "settings object required"}, 400)
        cur = self._ui_defaults()
        allowed = ("density", "model", "effort")
        cur.update({k: str(ui[k]) for k in allowed if ui.get(k) is not None})
        self.sdk.storage.set(UI_DEFAULTS_KEY, cur)
        return {"ok": True, "ui_defaults": cur}

    def _session_profile(self, chat_key: str) -> tuple[str, dict]:
        """会话最近发言者（platform:uid）与其画像；无发言者/画像返回 ("", 空结构)。"""
        try:
            contexts = self.main.sessions.get_contexts(chat_key)
        except Exception:
            return ("", {"traits": [], "preferences": [], "facts": [], "updated": 0.0})
        sender = ""
        for message in reversed(contexts):
            if isinstance(message, dict) and message.get("role") == "user" and str(message.get("sender") or "").strip():
                sender = str(message["sender"]).strip()
                break
        if not sender:
            return ("", {"traits": [], "preferences": [], "facts": [], "updated": 0.0})
        platform = str(chat_key.split(":", 1)[0] or "")
        user_key = f"{platform}:{sender}" if platform else sender
        profile = getattr(self.main.conversations, "profile", None)
        if profile is None:
            return ("", {"traits": [], "preferences": [], "facts": [], "updated": 0.0})
        return (user_key, profile.get(user_key))

    async def memory_get(self, request):
        chat_key = self._query(request, "chat_key")
        if not chat_key:
# 无会话上下文：附最近活跃会话的画像（记忆页"用户画像"卡数据源）
            profile_user, profile = "", {"traits": [], "preferences": [], "facts": [], "updated": 0.0}
            sessions = self.main.sessions.list_sessions()
            if sessions:
                profile_user, profile = self._session_profile(str(sessions[0].get("chat_key") or ""))
            return {"scopes": self.main.memory.list_scopes(), "entries": [], "profile_user": profile_user, "profile": profile}
        profile_user, profile = self._session_profile(chat_key)
        return {"scopes": [], "entries": self.main.memory.entries(chat_key), "profile_user": profile_user, "profile": profile}

    async def profile_clear(self, request):
        body = await request.json()
        user_key = str((body or {}).get("user_key") or "").strip()
        if not user_key:
            return ({"error": "user_key required"}, 400)
        profile = getattr(self.main.conversations, "profile", None)
        if profile is None:
            return ({"error": "profile store unavailable"}, 500)
        return {"ok": True, "user_key": user_key, "removed": profile.clear(user_key)}

    async def memory_delete(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        query = str((body or {}).get("query") or "")
        content = (body or {}).get("content")
        if content is not None:
            removed = 1 if self.main.memory.remove(chat_key, str(content)) else 0
        elif query:
            removed = self.main.memory.forget(chat_key, query)
        else:
            removed = self.main.memory.clear(chat_key)
        return {"ok": True, "removed": removed}

# ===== 会话分享 =====

    def _shares(self) -> dict:
        shares = self.sdk.storage.get(SHARES_KEY, {})
        return shares if isinstance(shares, dict) else {}

    def _share_token(self, token: str) -> dict | None:
        share = self._shares().get(token)
        if not isinstance(share, dict) or not share.get("enabled", True):
            return None
        expires = float(share.get("expires", 0) or 0)
        if expires and utils.now_ts() > expires:
            return None
        return share

    def _share_contexts(self, share: dict) -> list:

        contexts = self.main.sessions.get_contexts(str(share.get("chat_key") or ""))
        budget = int(share.get("max_tokens", 4000) or 4000) * 2
        picked: list = []
        used = 0
        for message in reversed(contexts):
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, list):
                content = " ".join(str(p.get("text") or "") for p in content if isinstance(p, dict) and p.get("type") == "text")
            size = len(str(content or ""))
            if picked and used + size > budget:
                break
            picked.append(message)
            used += size
        return list(reversed(picked))

    async def session_share(self, request):
        import secrets as _secrets

        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        try:
            hours = min(24 * 30, max(1, int((body or {}).get("expires_hours", 24))))
        except (TypeError, ValueError):
            hours = 24
        try:
            max_tokens = min(200_000, max(200, int((body or {}).get("max_tokens", 4000))))
        except (TypeError, ValueError):
            max_tokens = 4000
        token = _secrets.token_urlsafe(18)
        shares = self._shares()
        shares[token] = {
            "chat_key": chat_key,
            "created": utils.now_ts(),
            "expires": utils.now_ts() + hours * 3600,
            "max_tokens": max_tokens,
            "enabled": True,
        }
        self.sdk.storage.set(SHARES_KEY, shares)
        return {"ok": True, "token": token, "url": f"/QvQChat/share?token={token}", "expires": shares[token]["expires"], "max_tokens": max_tokens}

    async def session_share_revoke(self, request):
        body = await request.json()
        token = str((body or {}).get("token") or "")
        shares = self._shares()
        if token in shares:
            shares.pop(token)
            self.sdk.storage.set(SHARES_KEY, shares)
            return {"ok": True}
        return ({"error": "not found"}, 404)

    async def share_messages(self, request):
        token = self._query(request, "token")
        share = self._share_token(token) if token else None
        if share is None:
            return ({"error": "invalid or expired share"}, 403)
        contexts = self._share_contexts(share)
        summary = self.main.sessions.summary_of(str(share.get("chat_key") or ""))
        return {
            "chat_key": share.get("chat_key"),
            "summary": summary,
            "messages": contexts,
            "expires": share.get("expires"),
        }

    async def share_page(self, request):
        from starlette.responses import HTMLResponse

        token = request.query_params.get("token") if request.query_params else ""
        html = (TEMPLATES / "share.html").read_text(encoding="utf-8")
        return HTMLResponse(html.replace("__TOKEN__", token))
