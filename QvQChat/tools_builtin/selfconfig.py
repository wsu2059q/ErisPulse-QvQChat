from __future__ import annotations

from dataclasses import fields as dc_fields

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry
from ..engine.base import EngineError


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _s(**simple) -> dict:
    return simple


def _mask_key(key: str) -> str:
    if not key:
        return ""
    return "***" + key[-4:] if len(key) > 4 else "***"


async def manage_models(ctx: ToolContext, action: str = "list", provider: dict | None = None,
                        provider_id: str = "", model_id: str = "") -> str:
    pool = ctx.main.pool
    action = str(action or "list").lower()
    if action == "list":
        providers = []
        for p in pool.list_providers():
            item = dict(p)
            item["api_key"] = _mask_key(str(item.get("api_key") or ""))
            item["enabled_models"] = [
                m.get("id") for m in item.get("models") or []
                if isinstance(m, dict) and m.get("enabled", True)
            ]
            providers.append(item)
        return utils.to_text({
            "providers": providers,
            "default_model": getattr(ctx.config, "default_model", ""),
        })
    if action == "presets":
        return utils.to_text(pool.presets())
    if action == "save":
        if not isinstance(provider, dict):
            return "save needs a provider object: {id?, name, base_url, api_key, models:[{id, enabled, temperature?, max_tokens?}]}"
        try:
            entry = pool.save_provider(provider)
        except EngineError as e:
            return str(e)
        return utils.to_text({"ok": True, "provider": {**entry, "api_key": _mask_key(str(entry.get("api_key") or ""))}})
    if action == "delete":
        return utils.to_text({"ok": pool.delete_provider(str(provider_id or ""))})
    if action == "fetch_models":
        data = dict(provider) if isinstance(provider, dict) else {}
        if not str(data.get("api_key") or "") and provider_id:
            existing = pool.get_provider(str(provider_id))
            if existing is not None:
                data.setdefault("base_url", existing.get("base_url", ""))
                data["api_key"] = existing.get("api_key", "")
        try:
            return utils.to_text(await pool.fetch_remote_models(data))
        except EngineError as e:
            return str(e)
    if action == "set_default":
        wanted = str(model_id or "")
        if wanted and not any(m["id"] == wanted for m in pool.list_models()):
            known = ", ".join(m["id"] for m in pool.list_models())
            return f"unknown model: {wanted} (available: {known or 'none'})"
        ctx.sdk.config.setConfig("QvQChat.default_model", wanted)
        return utils.to_text({"ok": True, "default_model": wanted})
    return f"unknown action: {action} (list / presets / save / delete / fetch_models / set_default)"


async def manage_mcp(ctx: ToolContext, action: str = "list", name: str = "", transport: str = "stdio",
                     command: str = "", args: list | None = None, env: dict | None = None,
                     url: str = "", headers: dict | None = None, timeout: int = 0) -> str:
    mcp = ctx.main.mcp
    action = str(action or "list").lower()
    if action == "list":
        return utils.to_text({"servers": mcp.list_servers(), "clients": mcp.status()})
    if action == "status":
        return utils.to_text(mcp.status())
    if action == "save":
        entry: dict = {"name": str(name or "").strip(), "transport": str(transport or "stdio").lower()}
        if entry["transport"] == "http":
            entry["url"] = str(url or "")
            if isinstance(headers, dict) and headers:
                entry["headers"] = {str(k): str(v) for k, v in headers.items()}
        else:
            entry["command"] = str(command or "")
            if args:
                entry["args"] = [str(a) for a in args]
            if isinstance(env, dict) and env:
                entry["env"] = {str(k): str(v) for k, v in env.items()}
        if timeout:
            entry["timeout"] = timeout
        try:
            saved = mcp.save_server(entry)
        except ValueError as e:
            return str(e)
        info = None
        error = None
        try:
            info = await mcp.connect_one(str(saved["name"]), saved)
        except Exception as e:
            error = str(e)
        return utils.to_text({"ok": True, "server": saved, "connected": info, "error": error})
    if action == "remove":
        try:
            await mcp.disconnect(str(name or ""))
        except Exception:
            pass
        return utils.to_text({"ok": mcp.delete_server(str(name or ""))})
    if action == "connect":
        server_cfg = next((s for s in mcp.list_servers() if s.get("name") == name), None)
        if server_cfg is None:
            return f"server not found: {name}"
        try:
            info = await mcp.connect_one(str(name), server_cfg)
        except Exception as e:
            return f"connect failed: {e}"
        return utils.to_text({"ok": True, "info": info})
    if action == "disconnect":
        return utils.to_text({"ok": await mcp.disconnect(str(name or ""))})
    return f"unknown action: {action} (list / status / save / remove / connect / disconnect)"


async def manage_personas(ctx: ToolContext, action: str = "list", persona_id: str = "",
                          name: str = "", system: str = "", chat_key: str = "",
                          persona: str | None = None) -> str:
    personas = ctx.main.personas
    action = str(action or "list").lower()
    if action == "list":
        bound = {}
        for session in ctx.main.sessions.list_sessions():
            pid = session.get("persona")
            if pid:
                bound[session["chat_key"]] = pid
        return utils.to_text({
            "personas": [
                {k: p.get(k) for k in ("id", "name", "builtin")}
                for p in personas.list()
            ],
            "global_default": personas.global_default(),
            "bindings": bound,
            "current_chat": ctx.chat_key,
        })
    if action == "save":
        if not name and not system:
            return "save needs name and/or system"
        saved = personas.save({
            "id": str(persona_id or "") or None,
            "name": name,
            "system": system,
        })
        return utils.to_text({"ok": True, "persona": saved})
    if action == "delete":
        return utils.to_text({"ok": personas.delete(str(persona_id or ""))})
    if action == "bind":
        target = str(chat_key or "").strip() or ctx.chat_key
        if persona is None and not persona_id:
            return "bind needs persona (existing persona id); use unbind to clear"
        personas.bind(target, str(persona or persona_id))
        ctx.main.sessions.set_persona(target, str(persona or persona_id))
        return utils.to_text({"ok": True, "chat_key": target, "persona": str(persona or persona_id)})
    if action == "unbind":
        target = str(chat_key or "").strip() or ctx.chat_key
        personas.bind(target, None)
        ctx.main.sessions.set_persona(target, None)
        return utils.to_text({"ok": True, "chat_key": target})
    if action == "set_global":
        personas.set_global_default(str(persona_id or "") or None)
        return utils.to_text({"ok": True, "global_default": str(persona_id or "")})
    if action == "clear_global":
        personas.set_global_default(None)
        return utils.to_text({"ok": True})
    return f"unknown action: {action} (list / save / delete / bind / unbind / set_global / clear_global)"


async def manage_config(ctx: ToolContext, action: str = "get", key: str = "", updates: dict | None = None) -> str:
    from ..Config import QvQConfig

    valid = {f.name for f in dc_fields(QvQConfig)}
    action = str(action or "get").lower()
    if action == "get":
        if key:
            if key not in valid:
                return f"unknown config key: {key}"
            return utils.to_text({key: getattr(ctx.config, key, None)})
        return utils.to_text({name: getattr(ctx.config, name, None) for name in sorted(valid)})
    if action == "set":
        if not isinstance(updates, dict) or not updates:
            return "set needs an updates object of {config_key: value}"
        applied, rejected = [], []
        for config_key, value in updates.items():
            if config_key in valid:
                ctx.sdk.config.setConfig(f"QvQChat.{config_key}", value)
                applied.append(config_key)
            else:
                rejected.append(config_key)
        return utils.to_text({"ok": True, "applied": applied, "rejected": rejected})
    return f"unknown action: {action} (get / set)"


def register(registry: ToolRegistry, main) -> None:
    if not bool(getattr(main.cfg, "self_config", True)):
        return
    registry.register(Tool(
        name="manage_models",
        access="admin",
        description="Self-configure the model pool: list providers & models, presets, save a provider (empty api_key keeps the stored one), delete, fetch the remote model list, set the default model. Admin only.",
        parameters=_schema(
            {
                "action": _s(type="string", description="list / presets / save / delete / fetch_models / set_default"),
                "provider": _s(type="object", description="Provider object for save / fetch_models: {id?, name, base_url, api_key, models:[{id, enabled, temperature?, max_tokens?}]}"),
                "provider_id": _s(type="string", description="Provider id for delete, or to reuse stored credentials in fetch_models"),
                "model_id": _s(type="string", description="Model pool id (provider:model) for set_default; empty clears to pool order"),
            },
            [],
        ),
        handler=manage_models,
        danger=True,
    ))
    registry.register(Tool(
        name="manage_mcp",
        access="admin",
        description="Self-configure MCP servers: list/status servers and their live tool sets, save (adds or updates and connects immediately), remove, connect, disconnect. Admin only.",
        parameters=_schema(
            {
                "action": _s(type="string", description="list / status / save / remove / connect / disconnect"),
                "name": _s(type="string", description="Server name"),
                "transport": _s(type="string", description="stdio (default) or http"),
                "command": _s(type="string", description="stdio: executable command"),
                "args": _s(type="array", description="stdio: command arguments"),
                "env": _s(type="object", description="stdio: environment variables"),
                "url": _s(type="string", description="http: server URL"),
                "headers": _s(type="object", description="http: request headers"),
                "timeout": _s(type="integer", description="Optional per-request timeout in seconds"),
            },
            [],
        ),
        handler=manage_mcp,
        danger=True,
    ))
    registry.register(Tool(
        name="manage_personas",
        description="Self-manage personas: list, create or update, delete, bind a persona to the current or any chat, unbind, and set/clear the global default persona. Admin only.",
        parameters=_schema(
            {
                "action": _s(type="string", description="list / save / delete / bind / unbind / set_global / clear_global"),
                "persona_id": _s(type="string", description="Persona id for delete/set_global; optional id for save"),
                "name": _s(type="string", description="save: persona name"),
                "system": _s(type="string", description="save: system prompt"),
                "persona": _s(type="string", description="bind: existing persona id to bind"),
                "chat_key": _s(type="string", description="bind/unbind target chat; omit for the current chat"),
            },
            [],
        ),
        handler=manage_personas,
        danger=True,
    ))
    registry.register(Tool(
        name="manage_config",
        access="admin",
        description="Read or change this module's own settings: get all fields or one key, set key-value updates (valid QvQChat config keys only). Covers triggers, aggregate window, forward behaviour, notice modes, etc. Admin only.",
        parameters=_schema(
            {
                "action": _s(type="string", description="get or set"),
                "key": _s(type="string", description="get: a single config key; omit for all"),
                "updates": _s(type="object", description="set: {config_key: value} pairs"),
            },
            [],
        ),
        handler=manage_config,
        danger=True,
    ))
