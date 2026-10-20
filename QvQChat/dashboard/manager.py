from __future__ import annotations

import secrets
from dataclasses import fields as dc_fields
from pathlib import Path
from urllib.parse import quote

from .. import texts, utils
from ..Config import QvQConfig
from ..engine.base import ChatRequest

TEMPLATES = Path(__file__).parent / "templates"

ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="4" y="7" width="16" height="12" rx="2" stroke-dasharray="3 2"/>'
    '<circle cx="9" cy="13" r="1.2" fill="currentColor"/>'
    '<circle cx="15" cy="13" r="1.2" fill="currentColor"/>'
    '<path d="M12 7V4" stroke-dasharray="2 2"/>'
    '<circle cx="12" cy="3" r="1" fill="currentColor"/>'
    '<path d="M4 17l-2 2M20 17l2 2" stroke-dasharray="2 2"/>'
    "</svg>"
)

FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#3aa5dc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="4" y="7" width="16" height="12" rx="2" stroke-dasharray="3 2"/>'
    '<circle cx="9" cy="13" r="1.2" fill="#3aa5dc"/>'
    '<circle cx="15" cy="13" r="1.2" fill="#3aa5dc"/>'
    '<path d="M12 7V4" stroke-dasharray="2 2"/>'
    '<circle cx="12" cy="3" r="1" fill="#3aa5dc"/>'
    '<path d="M4 17l-2 2M20 17l2 2" stroke-dasharray="2 2"/>'
    "</svg>"
)
FAVICON_HREF = "data:image/svg+xml," + quote(FAVICON_SVG)

TOKEN_KEY = "QvQChat:auth_token"
AUDIT_STORAGE_KEY = "QvQChat:audit"
SHARES_KEY = "QvQChat:shares"
UI_DEFAULTS_KEY = "QvQChat:ui_defaults"


class DashboardManager:
    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self._token_announced = False
        from .live import LiveRegistry

        self._live = getattr(main, "live_registry", None) or LiveRegistry()

    def register(self) -> None:
        router = self.sdk.router
        routes = [
            ("GET", "/api/qvq/auth", self.auth),
            ("GET", "/api/qvq/status", self.status),
            ("GET", "/api/qvq/models", self.models_get),
            ("POST", "/api/qvq/providers/save", self.providers_save),
            ("POST", "/api/qvq/providers/delete", self.providers_delete),
            ("POST", "/api/qvq/providers/remote-models", self.providers_remote_models),
            ("GET", "/api/qvq/skills", self.skills_get),
            ("POST", "/api/qvq/skills/save", self.skills_save),
            ("POST", "/api/qvq/skills/delete", self.skills_delete),
            ("POST", "/api/qvq/skills/enabled", self.skills_enabled),
            ("GET", "/api/qvq/skills/export", self.skills_export),
            ("POST", "/api/qvq/models/test", self.models_test),
            ("GET", "/api/qvq/personas", self.personas_get),
            ("POST", "/api/qvq/personas/save", self.personas_save),
            ("POST", "/api/qvq/personas/delete", self.personas_delete),
            ("POST", "/api/qvq/personas/bind", self.personas_bind),
            ("GET", "/api/qvq/tools", self.tools_get),
            ("POST", "/api/qvq/tools/refresh", self.tools_refresh),
            ("GET", "/api/qvq/mcp", self.mcp_get),
            ("POST", "/api/qvq/mcp/save", self.mcp_save),
            ("POST", "/api/qvq/mcp/delete", self.mcp_delete),
            ("POST", "/api/qvq/mcp/connect", self.mcp_connect),
            ("POST", "/api/qvq/mcp/disconnect", self.mcp_disconnect),
            ("GET", "/api/qvq/extensions", self.extensions_get),
            ("GET", "/api/qvq/usage", self.usage_get),
            ("GET", "/api/qvq/export", self.export_data),
            ("POST", "/api/qvq/import", self.import_data),
            ("GET", "/api/qvq/tasks", self.tasks_get),
            ("POST", "/api/qvq/tasks/delete", self.tasks_delete),
            ("GET", "/api/qvq/breakers", self.breakers_get),
            ("GET", "/api/qvq/costs", self.costs_get),
            ("GET", "/api/qvq/running", self.running_get),
            ("GET", "/api/qvq/kb", self.kb_get),
            ("POST", "/api/qvq/kb/add", self.kb_add),
            ("POST", "/api/qvq/kb/delete", self.kb_delete),
            ("GET", "/api/qvq/memory", self.memory_get),
            ("POST", "/api/qvq/memory/delete", self.memory_delete),
            ("GET", "/api/qvq/sessions", self.sessions_get),
            ("GET", "/api/qvq/session/messages", self.session_messages),
            ("POST", "/api/qvq/session/messages/delete", self.session_message_delete),
            ("POST", "/api/qvq/session/context/edit", self.session_context_edit),
            ("POST", "/api/qvq/session/flags", self.session_flags),
            ("POST", "/api/qvq/session/settings", self.session_settings),
            ("POST", "/api/qvq/sessions/delete", self.sessions_delete),
            ("POST", "/api/qvq/sessions/delete-archived", self.sessions_delete_archived),
            ("POST", "/api/qvq/session/compact", self.session_compact),
            ("POST", "/api/qvq/sessions/create", self.sessions_create),
            ("GET", "/api/qvq/settings/defaults", self.settings_defaults_get),
            ("POST", "/api/qvq/settings/defaults", self.settings_defaults_set),
            ("POST", "/api/qvq/session/share", self.session_share),
            ("POST", "/api/qvq/session/share/revoke", self.session_share_revoke),
            ("POST", "/api/qvq/sessions/reset", self.sessions_reset),
            ("GET", "/api/qvq/audit", self.audit_get),
            ("GET", "/api/qvq/config", self.config_get),
            ("POST", "/api/qvq/config", self.config_set),
            ("POST", "/api/qvq/chat", self.chat_post),
            ("POST", "/api/qvq/chat/stream", self.chat_stream),
            ("GET", "/api/qvq/chat/live", self.chat_live),
            ("POST", "/api/qvq/chat/cancel", self.chat_cancel),
            ("GET", "/api/qvq/chat/live/subscribe", self.chat_live_subscribe),
        ]
        for method, path, handler in routes:
            router.register_http_route("QvQChat", path, self._guard(handler), methods=[method])
        public_routes = [
            ("GET", "/api/qvq/share/messages", self.share_messages),
            ("GET", "/share", self.share_page),
        ]
        for method, path, handler in public_routes:
            router.register_http_route("QvQChat", path, handler, methods=[method])
        router.register_http_route("QvQChat", "/view", self.view_page, methods=["GET"])
        self._register_view()

    def unregister(self) -> None:
        try:
            self.sdk.Dashboard.unregister_view("QvQChat")
        except Exception:
            pass

    def _register_view(self) -> None:
        self.sdk.Dashboard.register_view(
            id="QvQChat",
            title="QvQChat 智能体",
            title_en="QvQChat Agent",
            icon_svg=ICON_SVG,
            iframe_url="/QvQChat/view",
            group="qvq",
        )


    def _own_token(self) -> str:
        configured = str(getattr(self.main.cfg, "view_token", "") or "")
        if configured:
            return configured
        stored = self.sdk.storage.get(TOKEN_KEY, "")
        if stored:
            return str(stored)
        token = secrets.token_urlsafe(24)
        self.sdk.storage.set(TOKEN_KEY, token)
        return token

    def _announce_token(self) -> None:
        if self._token_announced:
            return
        self._token_announced = True
        if getattr(self.main.cfg, "view_token", ""):
            return
        self.main.logger.warning(
            f"QvQChat standalone access token: {self._own_token()}  (view at /QvQChat/view)"
        )

    @staticmethod
    def _query(request, name: str) -> str | None:

        try:
            raw = getattr(request, "raw", request)
            qp = raw.query_params
        except Exception:
            qp = getattr(request, "query_params", None)
        if qp is None:
            return None
        try:
            value = qp.get(name)
        except Exception:
            return None
        if isinstance(value, str) and value.startswith(name + "="):
            value = value[len(name) + 1:]
        return value or None

    @staticmethod
    def _extract_token(request) -> str | None:
        raw = getattr(request, "raw", request)
        try:
            auth = raw.headers.get("Authorization", "")
        except Exception:
            auth = ""
        if isinstance(auth, str) and auth.startswith("Bearer "):
            return auth[7:]
        try:
            query = raw.query_params
            return query.get("token") if query is not None else None
        except Exception:
            return None

    def _dashboard_module(self):
        try:
            if "Dashboard" in self.sdk.module:
                return self.sdk.module.Dashboard
        except Exception:
            return None
        return None

    def _authorized(self, request) -> bool:
        provided = self._extract_token(request)
        if not provided:
            return False
        provided = str(provided)
        dashboard = self._dashboard_module()
        if dashboard is not None:
            try:
                raw = getattr(request, "raw", request)
                if hasattr(dashboard, "verify_request") and dashboard.verify_request(raw):
                    return True
                if hasattr(dashboard, "verify_token") and dashboard.verify_token(provided):
                    return True
            except Exception:
                pass
        return secrets.compare_digest(provided, self._own_token())

    def _guard(self, handler):
        async def wrapped(request):
            self._announce_token()
            if not self._authorized(request):
                return ({"error": "Unauthorized"}, 401)
            return await handler(request)

        return wrapped


    def _view_html(self) -> str:
        html = (TEMPLATES / "view.html").read_text(encoding="utf-8")
        css_dir = TEMPLATES / "css"
        css = "".join(
            (css_dir / f"{name}.css").read_text(encoding="utf-8")
            for name in ("base", "admin", "chat", "views")
        )
        chat_dir = TEMPLATES / "chat"
        order = ("core", "ui", "nav", "sessions", "messages", "stream", "views", "init")
        js = "".join(
            (chat_dir / f"{name}.js").read_text(encoding="utf-8")
            for name in order
        )
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>QvQChat</title>"
            f"<link rel='icon' type='image/svg+xml' href='{FAVICON_HREF}'>"
            f"<style>html,body{{margin:0;padding:0;height:100%}}{css}</style></head>"
            f"<body>{html}<script>{js}</script></body></html>"
        )

    async def view_page(self, request):
        from starlette.responses import HTMLResponse

        return HTMLResponse(self._view_html(), headers={"Cache-Control": "no-store"})


    async def status(self, request):
        data = await self.main.get_status()
        data["takeovers"] = len(self.main.takeover)
        data["dashboard_auth"] = self._dashboard_module() is not None
        today = self.main._usage_today()
        data["usage_today"] = {
            "tokens": int(today.get("tokens", 0) or 0),
            "calls": int(today.get("calls", 0) or 0),
            "limit": int(getattr(self.main.cfg, "daily_token_limit", 0) or 0),
        }
        return data

    async def usage_get(self, request):
        return {
            "days": self.main._usage_history(14),
            "limit": int(getattr(self.main.cfg, "daily_token_limit", 0) or 0),
        }

    async def export_data(self, request):
        from ..conversation.memory import MEM_PREFIX

        memory = {}
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith(MEM_PREFIX):
                entries = self.sdk.storage.get(key, [])
                if entries:
                    memory[key[len(MEM_PREFIX):]] = entries
        return {
            "version": 2,
            "exported_at": utils.now_ts(),
            "providers": self.main.pool.list_providers(),
            "personas": {
                pid: data
                for pid, data in (self.sdk.storage.get("QvQChat:personas", {}) or {}).items()
            },
            "tasks": self.main.scheduler.list(),
            "memory": memory,
            "mcp": self.main.mcp.list_servers(),
            "skills": self.main.skills.list_skills(),
        }

    async def import_data(self, request):
        body = await request.json()
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return ({"error": "data object required"}, 400)
        applied = []
        if isinstance(data.get("providers"), list):
            for provider in data["providers"]:
                try:
                    self.main.pool.save_provider(provider)
                except Exception:
                    pass
            applied.append("providers")
        elif isinstance(data.get("models"), list):
            for model in data["models"]:
                try:
                    self.main.pool.save_provider({
                        "id": "imported",
                        "name": "Imported",
                        "base_url": model.get("base_url", ""),
                        "api_key": model.get("api_key", ""),
                        "models": [{"id": model.get("model", ""), "enabled": True}],
                    })
                except Exception:
                    pass
            applied.append("models")
        if isinstance(data.get("personas"), dict):
            stored = self.sdk.storage.get("QvQChat:personas", {})
            if not isinstance(stored, dict):
                stored = {}
            stored.update(data["personas"])
            self.sdk.storage.set("QvQChat:personas", stored)
            applied.append("personas")
        if isinstance(data.get("tasks"), list):
            existing = self.main.scheduler.list()
            known = {t.get("id") for t in existing}
            for task in data["tasks"]:
                if isinstance(task, dict) and task.get("id") not in known:
                    task.setdefault("managed_by", "")
                    task.setdefault("cron_ref", "")
                    existing.append(task)
            if data["tasks"]:
                self.main.scheduler._save(existing)
            applied.append("tasks")
        if isinstance(data.get("memory"), dict):
            from ..conversation.memory import MEM_PREFIX

            for chat_key, entries in data["memory"].items():
                if isinstance(entries, list):
                    self.sdk.storage.set(MEM_PREFIX + str(chat_key), entries)
            applied.append("memory")
        if isinstance(data.get("mcp"), list):
            self.main.mcp.replace_servers([s for s in data["mcp"] if isinstance(s, dict)])
            applied.append("mcp")
        if isinstance(data.get("skills"), list):
            for s in data["skills"]:
                if isinstance(s, dict) and s.get("name"):
                    try:
                        self.main.skills.save_skill(
                            str(s.get("name")),
                            str(s.get("description") or ""),
                            str(s.get("body") or ""),
                        )
                    except (ValueError, OSError):
                        pass
            applied.append("skills")
        return {"ok": True, "applied": applied}

    async def auth(self, request):
        return {"ok": True}

    async def models_get(self, request):
        providers = []
        for p in self.main.pool.list_providers():
            item = dict(p)
            key = item.get("api_key") or ""
            item["api_key_masked"] = ("*" * 8 + key[-4:]) if len(key) > 4 else ("*" * len(key) if key else "")
            item.pop("api_key", None)
            providers.append(item)
        return {
            "providers": providers,
            "models": self.main.pool.list_models(),
            "presets": self.main.pool.presets(),
            "default": getattr(self.main.cfg, "default_model", ""),
        }

    async def providers_save(self, request):
        body = await request.json()
        try:
            entry = self.main.pool.save_provider(body or {})
            return {"ok": True, "provider": {**entry, "api_key": ""}}
        except Exception as e:
            return ({"error": str(e)}, 400)

    async def providers_delete(self, request):
        body = await request.json()
        ok = self.main.pool.delete_provider(str((body or {}).get("id") or ""))
        return {"ok": ok}

    async def providers_remote_models(self, request):
        body = await request.json()
        data = dict(body or {})
        if not str(data.get("api_key") or "") and data.get("id"):
            provider_id = str(data.get("id"))
            for p in self.main.pool.list_providers():
                if p.get("id") == provider_id:
                    data["api_key"] = str(p.get("api_key") or "")
                    break
        try:
            models = await self.main.pool.fetch_remote_models(data)
            return {"ok": True, "models": models}
        except Exception as e:
            return ({"error": str(e)}, 502)

    async def models_test(self, request):
        body = await request.json()
        model_id = str((body or {}).get("id") or "")
        started = utils.now_ts()
        try:
            response = await self.main.pool.chat(ChatRequest(messages=[{"role": "user", "content": "ping"}], model=model_id or None))
            return {"ok": True, "reply": response.content or "", "model": response.model, "ms": int((utils.now_ts() - started) * 1000)}
        except Exception as e:
            return {"ok": False, "error": str(e), "ms": int((utils.now_ts() - started) * 1000)}

    async def skills_get(self, request):
        return {"skills": self.main.skills.list_skills()}

    async def skills_save(self, request):
        body = await request.json()
        try:
            skill = self.main.skills.save_skill(
                str((body or {}).get("name") or ""),
                str((body or {}).get("description") or ""),
                str((body or {}).get("body") or ""),
            )
            return {"ok": True, "skill": skill}
        except (ValueError, OSError) as e:
            return ({"error": str(e)}, 400)

    async def skills_delete(self, request):
        body = await request.json()
        ok = self.main.skills.delete_skill(str((body or {}).get("name") or ""))
        return {"ok": ok}

    async def skills_enabled(self, request):
        body = await request.json()
        name = str((body or {}).get("name") or "")
        self.main.skills.set_enabled(name, bool((body or {}).get("enabled")))
        return {"ok": True}

    async def skills_export(self, request):
        skills = self.main.skills.list_skills()
        return {
            "skills": [
                {"name": s["name"], "description": s.get("description", ""), "body": s.get("body", "")}
                for s in skills
            ]
        }

    async def personas_get(self, request):
        bindings = {}
        for session in self.main.sessions.list_sessions():
            if session.get("persona"):
                bindings[session["chat_key"]] = session["persona"]
        return {"personas": self.main.personas.list(), "bindings": bindings}

    async def personas_save(self, request):
        body = await request.json()
        try:
            persona = self.main.personas.save(body or {})
            return {"ok": True, "persona": persona}
        except ValueError as e:
            return ({"error": str(e)}, 400)

    async def personas_delete(self, request):
        body = await request.json()
        try:
            ok = self.main.personas.delete(str((body or {}).get("id") or ""))
            return {"ok": ok}
        except ValueError as e:
            return ({"error": str(e)}, 400)

    async def personas_bind(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        persona = (body or {}).get("persona") or None
        self.main.personas.bind(chat_key, persona)
        self.main.sessions.set_persona(chat_key, persona)
        return {"ok": True}

    async def tools_get(self, request):
        tools = []
        for tool in self.main.registry.list():
            tools.append(
                {
                    "name": tool.name,
                    "label": texts.t(f"tool.{tool.name}.name", default=tool.name),
                    "description": texts.t(f"tool.{tool.name}.desc", default=tool.description),
                    "origin": tool.origin,
                    "origin_label": texts.t(f"origin.{tool.origin}", default=tool.origin),
                    "danger": tool.danger,
                    "access": getattr(tool, "access", "admin"),
                }
            )
        tools.sort(key=lambda t: (t["origin"], t["name"]))
        return {
            "tools": tools,
            "disabled": list(getattr(self.main.cfg, "disabled_tools", []) or []),
            "risk": texts.t("tool.risk", default="risk"),
        }

    async def tools_refresh(self, request):
        info = await self.main.eco.refresh()
        return {"ok": True, "info": info}

    async def mcp_get(self, request):
        return {"servers": self.main.mcp.list_servers(), "clients": self.main.mcp.status()}

    async def mcp_save(self, request):
        body = await request.json()
        try:
            saved = self.main.mcp.save_server(body or {})
        except ValueError as e:
            return ({"error": str(e)}, 400)
        info = None
        error = None
        try:
            info = await self.main.mcp.connect_one(str(saved["name"]), saved)
        except Exception as e:
            error = str(e)
        return {"ok": True, "server": saved, "info": info, "error": error}

    async def mcp_delete(self, request):
        body = await request.json()
        name = str((body or {}).get("name") or "")
        try:
            await self.main.mcp.disconnect(name)
        except Exception:
            pass
        return {"ok": self.main.mcp.delete_server(name)}

    async def mcp_connect(self, request):
        body = await request.json()
        name = str((body or {}).get("name") or "")
        server_cfg = None
        for item in self.main.mcp.list_servers():
            if item.get("name") == name:
                server_cfg = item
                break
        if server_cfg is None:
            return ({"error": f"server not found: {name}"}, 404)
        try:
            info = await self.main.mcp.connect_one(name, server_cfg)
            return {"ok": True, "info": info}
        except Exception as e:
            return ({"error": str(e)}, 500)

    async def mcp_disconnect(self, request):
        body = await request.json()
        ok = await self.main.mcp.disconnect(str((body or {}).get("name") or ""))
        return {"ok": ok}

    async def extensions_get(self, request):
        return {
            "info": dict(self.main.eco.info),
            "extensions": self.main.eco.extensions_status(),
        }

    async def tasks_get(self, request):
        tasks = []
        for task in self.main.scheduler.list():
            item = dict(task)
            item["next_formatted"] = utils.format_ts(float(task.get("next_run", 0)))
            if task.get("last_run"):
                item["last_formatted"] = utils.format_ts(float(task.get("last_run") or 0))
            tasks.append(item)
        runs = [
            {**run, "at_formatted": utils.format_ts(float(run.get("at") or 0))}
            for run in reversed(self.main.scheduler.runs())
        ]
        return {"tasks": tasks, "runs": runs}

    async def breakers_get(self, request):
        return {"breakers": self.main.pool.breaker_state()}

    async def costs_get(self, request):
        # 每百万 token 单价 × 用量明细（in/out），换算每日与按模型成本
        prices = self.main.pool.model_costs()
        daily: list[dict] = []
        by_model: dict[str, float] = {}
        total = 0.0
        for day in self.main._usage_history(14):
            day_cost = 0.0
            for model_id, usage in (day.get("by_model") or {}).items():
                price = prices.get(str(model_id))
                if not price or not isinstance(usage, dict):
                    continue
                cost = (int(usage.get("in", 0) or 0) / 1e6) * price["input"] + (
                    int(usage.get("out", 0) or 0) / 1e6
                ) * price["output"]
                day_cost += cost
                by_model[str(model_id)] = by_model.get(str(model_id), 0.0) + cost
            daily.append({"date": day.get("date"), "cost": round(day_cost, 4)})
            total += day_cost
        return {
            "daily": daily,
            "by_model": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])},
            "total": round(total, 4),
        }

    async def running_get(self, request):
        return {"running": self._live.overview()}

    async def kb_get(self, request):
        query = self._query(request, "q") or ""
        kb = self.main.knowledge
        stats = kb.stats()
        if query:
            hits = kb.search(query, top_k=8)
            items = [kb.get(h["id"]) for h in hits]
            items = [i for i in items if i]
        else:
            items = kb.list()
        return {"entries": items, "stats": stats}

    async def kb_add(self, request):
        body = await request.json()
        title = str((body or {}).get("title") or "").strip()
        content = str((body or {}).get("content") or "")
        if not title or not content.strip():
            return ({"error": texts.t("kb_need_title_content")}, 400)
        entry = self.main.knowledge.add(title, content, source=str((body or {}).get("source") or ""))
        return {"ok": True, "entry": entry}

    async def kb_delete(self, request):
        body = await request.json()
        ok = self.main.knowledge.delete(str((body or {}).get("id") or ""))
        return {"ok": ok}

    async def tasks_delete(self, request):
        body = await request.json()
        ok = self.main.scheduler.cancel(str((body or {}).get("id") or ""))
        return {"ok": ok}

    async def memory_get(self, request):
        chat_key = self._query(request, "chat_key")
        if not chat_key:
            return {"scopes": self.main.memory.list_scopes(), "entries": []}
        return {"scopes": [], "entries": self.main.memory.entries(chat_key)}

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

    async def sessions_get(self, request):
        sessions = self.main.sessions.list_sessions()
        for session in sessions:
            if str(session.get("platform") or "") == "dashboard" and not session.get("name"):
                session["name"] = texts.t("dashboard_session_name")
        try:
            self.main.spawn(self.main.conversations.resolve_session_names(sessions))
        except Exception:
            pass
        live_keys = set()
        try:
            for s in sessions:
                if self._live.busy(s["chat_key"]):
                    live_keys.add(s["chat_key"])
                    s["live"] = True
        except Exception:
            pass
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
        allowed = ("density", "model", "effort")
        saved = self.main.sessions.set_ui(chat_key, {k: str(ui[k]) for k in allowed if ui.get(k) is not None})
        return {"ok": True, "ui": saved}

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

    async def audit_get(self, request):
        entries = self.main.sdk.storage.get(AUDIT_STORAGE_KEY, [])
        if not isinstance(entries, list):
            entries = []
        limit = 200
        try:
            limit = max(1, min(int(self._query(request, "limit") or 200), 500))
        except Exception:
            limit = 200
        return {"entries": list(reversed(entries[-limit:]))}

    async def config_get(self, request):
        from ErisPulse.Core import i18n

        fields = []
        for f in dc_fields(QvQConfig):
            meta = f.metadata or {}
            desc = meta.get("description") or {}
            if isinstance(desc, dict):
                text = str(desc.get("default") or "")
                key = desc.get("i18n")
                if key:
                    try:
                        text = i18n.t(key, default=text)
                    except Exception:
                        pass
            else:
                text = str(desc)
            ui = meta.get("ui") or {}
            fields.append(
                {
                    "key": f.name,
                    "value": getattr(self.main.cfg, f.name, None),
                    "description": text,
                    "group": str(ui.get("group") or "other"),
                    "order": ui.get("order", 99),
                    "widget": str(ui.get("widget") or "text"),
                    "options": ui.get("options"),
                }
            )
        return {"fields": fields}

    async def config_set(self, request):
        body = await request.json()
        if not isinstance(body, dict):
            return ({"error": "body must be an object"}, 400)
        valid = {f.name for f in dc_fields(QvQConfig)}
        applied = []
        for key, value in body.items():
            if key in valid:
                self.sdk.config.setConfig(f"QvQChat.{key}", value)
                applied.append(key)
        return {"ok": True, "applied": applied}

    UPLOAD_DIR = Path("data/QvQChat/uploads")

    def _save_upload(self, name: str, data: str) -> str | None:
        return self.main.conversations.save_upload(name, data)

    def _parse_chat_body(self, body: dict):

        body = body or {}
        text = str(body.get("text") or "").strip()
        images: list[str] = []
        file_blocks: list[str] = []
        for att in body.get("attachments") or []:
            if not isinstance(att, dict):
                continue
            name = str(att.get("name") or "file")
            mime = str(att.get("mime") or "").lower()
            data = str(att.get("data") or "")
            if not data:
                continue
            if mime.startswith("image/"):
                if len(images) < 3 and len(data) <= 7_000_000:
                    images.append(data if data.startswith("data:") else f"data:{mime};base64,{data}")
                saved = self._save_upload(name, data)
                if saved:
                    size = Path(saved).stat().st_size
                    file_blocks.append(texts.t("attachment_saved", name=name, path=saved, size=size))
            elif len(data) <= 20000 and not data.startswith("data:"):
                file_blocks.append(f"[attachment {name}]\n{data[:20000]}")
            else:
                saved = self._save_upload(name, data)
                if saved:
                    size = Path(saved).stat().st_size
                    file_blocks.append(
                        texts.t("attachment_saved", name=name, path=saved, size=size)
                    )
                else:
                    file_blocks.append(f"[attachment {name}]（保存失败，内容不可用）")
        if file_blocks:
            text = (text + "\n\n" + "\n\n".join(file_blocks)).strip()
        if not text and not images:
            return ({"error": "empty text"}, 400)
        session = str(body.get("session") or "dashboard:private:web")
        skills = [str(s) for s in (body.get("skills") or []) if str(s)]
        mcp_tools = [str(t) for t in (body.get("mcp_tools") or []) if str(t)]
        persona_id = str(body.get("persona") or "")
        model = str(body.get("model") or "")
        temperature = body.get("temperature")
        try:
            temperature = float(temperature) if temperature is not None else None
        except (TypeError, ValueError):
            temperature = None
        return text, images, session, skills, mcp_tools, persona_id, model, temperature

    async def chat_post(self, request):
        body = await request.json()
        parsed = self._parse_chat_body(body)
        if len(parsed) == 2 and isinstance(parsed[0], dict):
            return parsed
        text, images, session, skills, mcp_tools, persona_id, model, temperature = parsed
        try:
            reply = await self.main.run_dashboard_chat(
                session,
                text,
                images=images,
                skill_names=skills,
                mcp_tools=mcp_tools,
                persona_id=persona_id,
                model=model,
                temperature=temperature,
            )
        except Exception as e:
            return ({"error": str(e)}, 500)
        return {"reply": reply, "session": session}

    async def chat_stream(self, request):
        import asyncio as _asyncio
        import json as _json

        from starlette.responses import StreamingResponse

        from . import live as live_mod

        body = await request.json()
        parsed = self._parse_chat_body(body)
        if len(parsed) == 2 and isinstance(parsed[0], dict):
            return parsed
        text, images, session, skills, mcp_tools, persona_id, model, temperature = parsed
        if self._live.busy(session):
            return ({"error": "session busy"}, 409)

        run_live = self._live.start(session)
        on_delta, on_reset, on_tool_event = live_mod.bind(run_live)

        async def run():
            try:
                reply = await self.main.run_dashboard_chat(
                    session,
                    text,
                    images=images,
                    skill_names=skills,
                    mcp_tools=mcp_tools,
                    persona_id=persona_id,
                    model=model,
                    temperature=temperature,
                    on_delta=on_delta,
                    on_reset=on_reset,
                    on_tool_event=on_tool_event,
                )
                run_live.reply = reply
                run_live.status = "done"
                run_live.publish("done", {"reply": reply, "session": session})
            except _asyncio.CancelledError:
                partial = run_live.text.strip()
                if partial:
                    try:
                        self.main.sessions.append(session, "assistant", partial)
                    except Exception:
                        pass
                run_live.reply = partial or None
                run_live.status = "done"
                run_live.publish("done", {"reply": partial, "session": session})
                raise
            except Exception as e:
                run_live.status = "error"
                run_live.error = str(e)
                run_live.publish("error", {"error": str(e)})
            finally:
                run_live.publish("end", {"status": run_live.status})

        async def gen():
            queue: _asyncio.Queue = _asyncio.Queue()
            run_live.subscribers.add(queue)
            task = _asyncio.create_task(run())
            run_live.task = task
            try:
                yield f"event: meta\ndata: {_json.dumps({'session': session}, ensure_ascii=False)}\n\n"
                while True:
                    try:
                        event, data = await _asyncio.wait_for(queue.get(), timeout=15.0)
                    except _asyncio.TimeoutError:
                        yield ": ping\n\n"
                        continue
                    if event == "end":
                        break
                    yield f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"
            finally:
                run_live.subscribers.discard(queue)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def chat_cancel(self, request):
        body = await request.json()
        session = str((body or {}).get("session") or "")
        live = self._live.get(session) if session else None
        if live is None:
            return ({"error": "no live stream"}, 404)
        cancelled = live.cancel()
        return {"ok": cancelled}

    async def chat_live(self, request):
        session = self._query(request, "session")
        live = self._live.get(session) if session else None
        if live is None:
            return {"status": "idle"}
        return live.snapshot()

    async def chat_live_subscribe(self, request):
        import asyncio as _asyncio
        import json as _json

        from starlette.responses import StreamingResponse

        session = self._query(request, "session")
        live = self._live.get(session) if session else None
        if live is None:
            return ({"error": "no live stream"}, 404)

        async def gen():
            queue: _asyncio.Queue = _asyncio.Queue()
            live.subscribers.add(queue)
            try:
                yield "event: snapshot\ndata: " + _json.dumps(live.snapshot(), ensure_ascii=False) + "\n\n"
                while True:
                    try:
                        event, data = await _asyncio.wait_for(queue.get(), timeout=15.0)
                    except _asyncio.TimeoutError:
                        yield ": ping\n\n"
                        continue
                    if event == "end":
                        yield "event: end\ndata: " + _json.dumps({"status": live.status}, ensure_ascii=False) + "\n\n"
                        break
                    yield f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"
            finally:
                live.subscribers.discard(queue)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
