from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import quote

from .. import texts, utils# noqa: F401 — utils 供后续扩展；texts 为 chat 附件注入使用
from .api_config import ConfigApiMixin
from .api_ops import OpsApiMixin
from .api_sessions import SessionsApiMixin
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
    '<rect x="4" y="7" width="16" height="12" rx="2"/>'
    '<circle cx="9" cy="13" r="1.2" fill="#3aa5dc"/>'
    '<circle cx="15" cy="13" r="1.2" fill="#3aa5dc"/>'
    '<path d="M12 7V4"/>'
    '<circle cx="12" cy="3" r="1" fill="#3aa5dc"/>'
    '<path d="M4 17l-2 2M20 17l2 2"/>'
    "</svg>"
)
FAVICON_HREF = "data:image/svg+xml," + quote(FAVICON_SVG)

TOKEN_KEY = "QvQChat:auth_token"


class DashboardManager(SessionsApiMixin, ConfigApiMixin, OpsApiMixin):
    """Dashboard 管理器（拆分后）。

    会话/配置/运维三个 API 域分别在 api_sessions.py / api_config.py / api_ops.py（mixin），
    本文件保留：路由注册表、鉴权、视图与 OpenAI 兼容 / 聊天流式端点。
    HTTP 路径零变化。
    """

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
            ("POST", "/api/qvq/chain/save", self.chain_save),
            ("POST", "/api/qvq/models/detect", self.models_detect),
            ("POST", "/api/qvq/models/enrich", self.models_enrich),
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
            ("GET", "/api/qvq/participation", self.participation_get),
            ("GET", "/api/qvq/kb", self.kb_get),
            ("POST", "/api/qvq/kb/add", self.kb_add),
            ("POST", "/api/qvq/kb/delete", self.kb_delete),
            ("GET", "/api/qvq/kb/export", self.kb_export),
            ("POST", "/api/qvq/kb/import", self.kb_import),
            ("POST", "/api/qvq/session/routes", self.session_routes),
            ("GET", "/api/qvq/memory", self.memory_get),
            ("POST", "/api/qvq/memory/delete", self.memory_delete),
            ("POST", "/api/qvq/profile/clear", self.profile_clear),
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
            ("GET", "/api/qvq/plugin_settings", self.plugin_settings_get),
            ("POST", "/api/qvq/plugin_settings/save", self.plugin_settings_save),
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
            ("GET", "/v1/models", self.v1_models),
            ("POST", "/v1/chat/completions", self.v1_chat_completions),
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

    async def auth(self, request):
        return {"ok": True}

# ===== OpenAI 兼容端点：Bearer=view_token，映射 run_dashboard_chat =====

    def _v1_authorized(self, request) -> bool:
        raw = getattr(request, "raw", request)
        try:
            auth = raw.headers.get("Authorization", "")
        except Exception:
            auth = ""
        token = self._own_token()
        return bool(token) and auth == f"Bearer {token}"

    @staticmethod
    def _v1_message_text(content) -> str:
        if isinstance(content, list):
            return "\n".join(
                str(p.get("text") or "") for p in content if isinstance(p, dict) and p.get("type") == "text"
            )
        return str(content or "")

    async def v1_models(self, request):
        if not self._v1_authorized(request):
            return ({"error": {"message": "Invalid API key", "type": "auth_error"}}, 401)
        data = [
            {"id": m["id"], "object": "model", "owned_by": "QvQChat"}
            for m in self.main.pool.list_models()
        ]
        return {"object": "list", "data": data}

    async def v1_chat_completions(self, request):
        import asyncio as _asyncio
        import json as _json

        if not self._v1_authorized(request):
            return ({"error": {"message": "Invalid API key", "type": "auth_error"}}, 401)
        body = await request.json()
        messages = (body or {}).get("messages") or []
        user_text = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                user_text = self._v1_message_text(msg.get("content"))
                break
        if not user_text.strip():
            return ({"error": {"message": "messages must contain a user message", "type": "invalid_request_error"}}, 400)
        api_user = str((body or {}).get("user") or "").strip()
        session = "dashboard:private:api" + (f"_{utils.sanitize_name(api_user)}" if api_user else "")
        model = str((body or {}).get("model") or "")
        comp_id = "chatcmpl-" + utils.new_id()
        created = int(utils.now_ts())

        def base_chunk():
            return {
                "id": comp_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
            }

        if (body or {}).get("stream"):
            queue: _asyncio.Queue = _asyncio.Queue()

            def on_delta(piece: str) -> None:
                if piece:
                    queue.put_nowait(piece)

            async def runner():
                try:
                    await self.main.run_dashboard_chat(session, user_text, model=model, on_delta=on_delta)
                    queue.put_nowait(None)
                except Exception as e:
                    queue.put_nowait(e)

            async def gen():
                _asyncio.get_running_loop().create_task(runner())
                started = False
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        yield "data: " + _json.dumps({"error": {"message": str(item)}}, ensure_ascii=False) + "\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    delta = {"role": "assistant", "content": item} if not started else {"content": item}
                    started = True
                    piece = base_chunk()
                    piece["choices"][0]["delta"] = delta
                    yield "data: " + _json.dumps(piece, ensure_ascii=False) + "\n\n"
                if not started:
                    piece = base_chunk()
                    piece["choices"][0]["delta"] = {"role": "assistant", "content": ""}
                    yield "data: " + _json.dumps(piece, ensure_ascii=False) + "\n\n"
                last = base_chunk()
                last["choices"][0]["delta"] = {}
                last["choices"][0]["finish_reason"] = "stop"
                yield "data: " + _json.dumps(last, ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"

            from starlette.responses import StreamingResponse

            return StreamingResponse(gen(), media_type="text/event-stream")

        try:
            reply = await self.main.run_dashboard_chat(session, user_text, model=model)
        except Exception as e:
            return ({"error": {"message": str(e), "type": "internal_error"}}, 500)
        return {
            "id": comp_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

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
        if self._live.busy(session):
            return ({"error": "session busy"}, 409)
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
        on_delta, on_reset, on_tool_event, on_reasoning = live_mod.bind(run_live)

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
                    on_reasoning=on_reasoning,
                )
                run_live.reply = reply
                run_live.status = "done"
                run_live.publish("done", {"reply": reply, "session": session})
            except _asyncio.CancelledError:
                partial, trace, rounds = run_live.partial_record()
                if partial:
                    try:
                        self.main.sessions.append(session, "assistant", partial, trace=trace, rounds=rounds)
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
