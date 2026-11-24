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
            return "save needs a provider object: {id?, name, base_url, api_key, models:[{id, enabled, temperature?, max_tokens?, notes?, prefill_ok?(true/false/null=auto), context_length?, max_output_tokens?, vision?, reasoning?, tool_call?, cost?{input,output}}]}"
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
        return utils.to_text({
            "ok": True,
            "default_model": wanted,
            "note": "this changes the PRIMARY model for ALL chats immediately (failover follows pool order); make sure the model works with tool calls and produces non-empty content before switching",
        })
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
                          persona: str | None = None, opening: list | None = None,
                          tools: list | None = None, owner_title: str = "",
                          style: dict | None = None, examples: list | None = None,
                          nickname: str = "", prefill: str = "",
                          temperature: float | None = None,
                          max_tokens: float | None = None,
                          catchphrases: list | None = None,
                          banned_words: list | None = None,
                          avatar: str = "") -> str:
    personas = ctx.main.personas
    action = str(action or "list").lower()
    if action == "list":
        from ..conversation.service import strip_isolation

        current = str(ctx.chat_key or "")
        account = current.rsplit("@", 1)[1] if "@" in current else ""
# KV 绑定为权威源
        return utils.to_text({
            "personas": [
                {k: p.get(k) for k in ("id", "name", "builtin")}
                for p in personas.list()
            ],
            "global_default": await personas.global_default(),
            "bindings": await personas.abindings(),
            "current_chat": current,
# 当前接收账户（多账户隔离后缀）；绑定该账户全部会话用 chat_key="@<account>"
            "current_account": account,
            "account_binding_key": f"@{account}" if account else "",
            "current_group_key": strip_isolation(current) if current else "",
        })
    if action == "save":
        if not name and not system and not opening and not owner_title and not style and not examples and not nickname and not prefill and temperature is None and max_tokens is None and not catchphrases and not banned_words and not avatar:
            return "save needs at least one of name / system / opening / owner_title / style / examples / nickname / prefill / temperature / max_tokens / catchphrases / banned_words / avatar"
        payload: dict = {"id": str(persona_id or "") or None, "name": name, "system": system}
# 仅透传显式提供的扩展字段（未提供沿用存量，merge 语义防误清空）
        if opening is not None:
            payload["opening"] = opening
        if tools is not None:
            payload["tools"] = tools
        if owner_title:
            payload["owner_title"] = owner_title
        if style is not None:
            payload["style"] = style
        if examples is not None:
            payload["examples"] = examples
        if nickname:
            payload["nickname"] = nickname
        if prefill:
            payload["prefill"] = prefill
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if catchphrases is not None:
            payload["catchphrases"] = catchphrases
        if banned_words is not None:
            payload["banned_words"] = banned_words
        if avatar:
            payload["avatar"] = avatar
        saved = personas.save(payload)
        return utils.to_text({"ok": True, "persona": saved})
    if action == "delete":
        return utils.to_text({"ok": personas.delete(str(persona_id or ""))})
    if action == "bind":
        target = str(chat_key or "").strip() or ctx.chat_key
        if persona is None and not persona_id:
            return "bind needs persona (existing persona id); use unbind to clear"
# 仅写 KV 权威绑定（state.persona 镜像已废弃）
        await personas.bind(target, str(persona or persona_id))
        return utils.to_text({"ok": True, "chat_key": target, "persona": str(persona or persona_id)})
    if action == "unbind":
        target = str(chat_key or "").strip() or ctx.chat_key
        await personas.bind(target, None)
        return utils.to_text({"ok": True, "chat_key": target})
    if action == "set_global":
        await personas.set_global_default(str(persona_id or "") or None)
        return utils.to_text({"ok": True, "global_default": str(persona_id or "")})
    if action == "clear_global":
        await personas.set_global_default(None)
        return utils.to_text({"ok": True})
    return f"unknown action: {action} (list / save / delete / bind / unbind / set_global / clear_global)"


def _read_setting(ctx: ToolContext, name: str):
    """读取配置值；标记 secret 的字段脱敏（不把访问令牌等交给模型/模型日志）。"""
    from ..Config import QvQConfig

    value = getattr(ctx.config, name, None)
    field = QvQConfig.field_map().get(name)
    ui = ((field.metadata or {}).get("ui") or {}) if field is not None else {}
    if ui.get("secret") and value:
        return "***"
    return value


async def manage_config(ctx: ToolContext, action: str = "get", key: str = "", updates: dict | None = None) -> str:
    from ..Config import QvQConfig

    valid = {f.name for f in dc_fields(QvQConfig)}
    action = str(action or "get").lower()
    if action == "groups":
# 配置组目录：AI 的自发现入口——新增配置项/新能力组无需手动同步任何工具描述，
# AI 调一次 groups 就能看到当前全部字段（按组整理 + 一句话说明）
        groups: dict[str, dict] = {}
        for f in dc_fields(QvQConfig):
            meta = f.metadata or {}
            desc = meta.get("description") or {}
            text = str(desc.get("default") or "") if isinstance(desc, dict) else str(desc)
            ui = meta.get("ui") or {}
            g = str(ui.get("group") or "other")
            entry = groups.setdefault(g, {})
            title = text.split("：")[0].split(":")[0].split("，")[0].split(",")[0]
            entry[f.name] = (title or f.name)[:40] + ("（敏感）" if ui.get("secret") else "")
        order = {gid: i for i, gid in enumerate(g["id"] for g in QvQConfig.groups())}
        ordered = {gid: groups[gid] for gid in sorted(groups, key=lambda x: order.get(x, 99))}
        return utils.to_text({"groups": ordered, "hint": "set 用 manage_config(action=set, updates={key: value})；类型校验失败会带原因拒收"}, limit=20000)
    if action == "get":
        if key:
            if key not in valid:
                return f"unknown config key: {key}"
            return utils.to_text({key: _read_setting(ctx, key)})
# 全量读取会超过工具输出默认 4000 字符上限：放宽到 20000，否则 JSON 被截断成不可解析
        return utils.to_text(
            {name: _read_setting(ctx, name) for name in sorted(valid)},
            limit=20000,
        )
    if action == "set":
        if not isinstance(updates, dict) or not updates:
            return "set needs an updates object of {config_key: value}"
# 与 Dashboard config_set 走同一 QvQConfig.coerce 校验：类型抝合失败/未知键
# 拒收并带原因，杜绝把 "" 写进数字字段、字符串写进 list 字段
        applied, rejected = [], {}
        for config_key, value in updates.items():
            ok, coerced, err = QvQConfig.coerce(str(config_key), value)
            if ok:
                ctx.sdk.config.setConfig(f"QvQChat.{config_key}", coerced)
                applied.append(str(config_key))
            else:
                rejected[str(config_key)] = err
        return utils.to_text({"ok": not rejected, "applied": applied, "rejected": rejected})
    return f"unknown action: {action} (get / set / groups)"


def _plugin_config_class(sdk, module: str):
    """
    {!--< internal-use >!--}
    插件 ConfigClass 解析：模块注册名 → 模块类（与 Dashboard 插件设置端点同源）。
    """
    classes = getattr(getattr(sdk, "module", None), "_module_classes", None) or {}
    cls = classes.get(str(module))
    return getattr(cls, "ConfigClass", None) if cls is not None else None


def _plugin_field_meta(config_class) -> dict:
    """
    {!--< internal-use >!--}
    ConfigClass → {field: {type, description, secret}}（描述经框架 i18n 解析）。
    """
    from ErisPulse.runtime.config_schema import resolve_config_schema

    schema = resolve_config_schema(config_class) or {}
    fields = {}
    for name, meta in (schema.get("fields") or {}).items():
        fields[str(name)] = {
            "type": str((meta or {}).get("type") or "string"),
            "description": str((meta or {}).get("description") or ""),
            "secret": bool((meta or {}).get("secret")),
        }
    return fields


async def manage_plugin_config(ctx: ToolContext, action: str = "list", module: str = "",
                               key: str = "", values: dict | None = None) -> str:
    """
    读写其他插件模块的声明式配置（仅限声明了 qvq_settings 的模块）。

    :param ctx: [ToolContext] 工具上下文
    :param action: [str] list / get / set (默认: "list")
    :param module: [str] 目标模块注册名 (默认: "")
    :param key: [str] get 时读取的单个配置键 (默认: "")
    :param values: [dict] set 时 {config_key: value} 键值对 (默认: None)
    :return: [str] 操作结果 JSON
    """
    main = ctx.main
    action = str(action or "list").lower()
    catalog = dict(getattr(main, "plugin_settings_catalog", {}) or {})
    if action == "list":
        rows = []
        for name in sorted(catalog):
            config_class = _plugin_config_class(ctx.sdk, name)
            rows.append({
                "module": name,
                "title": str(catalog.get(name) or name),
                "fields": _plugin_field_meta(config_class) if config_class is not None else {},
            })
        return utils.to_text({"plugins": rows}, limit=20000)
    module = str(module or "").strip()
    if not module:
        return "module is required (see action=list)"
    if module not in catalog:
        return f"unknown plugin module: {module} (only modules exposing qvq_settings are manageable; see action=list)"
    config_class = _plugin_config_class(ctx.sdk, module)
    if config_class is None:
        return f"module {module} has no declarative ConfigClass; nothing to manage"
    try:
        from ErisPulse.runtime.config_schema import dict_to_dataclass, validate_config
    except Exception as e:
        return f"framework config schema unavailable: {type(e).__name__}: {e}"
    current = ctx.sdk.config.getConfig(module)
    current = dict(current) if isinstance(current, dict) else {}
    fields = _plugin_field_meta(config_class)
    if action == "get":
        if key:
            name = str(key)
            value = current.get(name)
            if (fields.get(name) or {}).get("secret") and value:
                value = "***"
            return utils.to_text({module: {name: value}})
        masked = {
            str(name): ("***" if (fields.get(str(name)) or {}).get("secret") and value else value)
            for name, value in current.items()
        }
        return utils.to_text({module: masked}, limit=20000)
    if action == "set":
        if not isinstance(values, dict) or not values:
            return "set needs a values object of {config_key: value}"
        unknown = [str(k) for k in values if str(k) not in fields]
        if unknown:
            return utils.to_text({"ok": False, "rejected": {k: "unknown config key" for k in unknown}})
# 与 Dashboard 保存端点同管线：整节合并出实例校验（类型/必填/枚举/区间），
# 错误原样返回不写任何值；通过后逐键写入（config.set 事件自动通知目标模块）
        merged = {**current, **values}
        try:
            instance = dict_to_dataclass(config_class, merged)
            errors = validate_config(instance)
        except Exception as e:
            return f"validation failed: {type(e).__name__}: {e}"
        if errors:
            return utils.to_text({"ok": False, "errors": errors})
        applied = []
        for name in values:
            ctx.sdk.config.setConfig(f"{module}.{name}", values[name])
            applied.append(str(name))
        try:
            await ctx.sdk.lifecycle.emit(
                "qvq.plugin_config",
                {"module": module, "values": {str(k): merged.get(k) for k in values}},
            )
        except Exception:
            pass
        return utils.to_text({"ok": True, "module": module, "applied": applied})
    return f"unknown action: {action} (list / get / set)"


async def manage_identity(ctx: ToolContext, action: str = "list", source: str = "",
                          target: str = "", mode: str = "alias") -> str:
    """身份迁移自管理：换平台/换号后把旧会话身份映射到新身份，历史/人格/记忆跟随。"""
    sessions = ctx.main.sessions
    action = str(action or "list").strip().lower()
    if action == "list":
        return utils.to_text({
            "identity_map": sessions.identity_map(),
            "hint": "source → target: 新消息按 target 会话处理；映射可 remove 回退",
        })
    if action == "migrate":
        summary = sessions.migrate_identity(str(source or ""), str(target or ""), str(mode or "alias"))
        if not summary.get("ok"):
            return utils.to_text({"ok": False, "error": summary.get("error")})
        return utils.to_text(summary)
    if action == "remove":
        return utils.to_text({"ok": sessions.remove_identity(str(source or ""))})
    return f"unknown action: {action} (list / migrate / remove)"


def _as_bool(value) -> bool:
    """工具入参布尔归一：模型常把布尔写成 "true"/"false" 字符串，
    直接 bool("false") 是 True——字符串按词面判，其余走真值。"""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


async def session_settings(ctx: ToolContext, action: str = "get", chat_key: str = "",
                           settings: dict | None = None) -> str:
    """会话级覆盖自管理：触发规则/模型/思考强度/密度/隐私 + 会话策略
    （静音/低token/优先级/日限额）与当日用量读回（只作用于单个会话）。"""
    main = ctx.main
    key = str(chat_key or "").strip() or str(ctx.chat_key or "")
    action = str(action or "get").strip().lower()
    if action == "get":
        from ..conversation.policy import budget_effective, get_policy

        policy = get_policy(ctx.sdk, key)
        usage = await main._usage_today() if hasattr(main, "_usage_today") else {}
        if not isinstance(usage, dict):
            usage = {}
        by_chat = usage.get("by_chat")
        session_tokens = int((by_chat or {}).get(key, 0) or 0) if isinstance(by_chat, dict) else 0
        return utils.to_text({
            "chat_key": key,
            "trigger_mode": main.sessions.trigger_mode_of(key),
            "listen_off": bool(main.sessions.get_flag(key, "listen_off")),
            "ui": (main.sessions._state(key).get("ui") or {}),
            "muted": policy.get("muted"),
            "low_token": policy.get("low_token"),
            "priority": policy.get("priority"),
            "session_budget": policy.get("session_budget"),
            "low_token_active": budget_effective(ctx.sdk, ctx.config, key),
            "usage_today": {
                "session_tokens": session_tokens,
                "session_budget": policy.get("session_budget"),
                "global_tokens": int(usage.get("tokens", 0) or 0),
                "daily_token_limit": int(getattr(ctx.config, "daily_token_limit", 0) or 0),
            },
        })
    if action == "set":
        if not isinstance(settings, dict) or not settings:
            return "set needs a settings object"
        applied = []
# 与 dashboard session_settings 同链路：set_ui（density/model/effort/trigger_mode）
        ui_patch = {k: str(settings[k]) for k in ("density", "model", "effort", "trigger_mode")
                    if settings.get(k) is not None}
        if ui_patch:
            main.sessions.set_ui(key, ui_patch)
            applied.extend(sorted(ui_patch))
        if "listen_off" in settings:
            main.sessions.set_flags(key, {"listen_off": _as_bool(settings["listen_off"])})
            applied.append("listen_off")
# 会话策略与 chatcfg（policy.set_policy）同源：静音/低token/优先级/会话日限额
        from ..conversation.policy import set_policy

        policy_patch: dict = {}
        for name in ("muted", "low_token"):
            if name in settings:
                policy_patch[name] = _as_bool(settings[name])
        if "priority" in settings:
            policy_patch["priority"] = str(settings["priority"])
        if "session_budget" in settings:
            policy_patch["session_budget"] = settings["session_budget"]
        if policy_patch:
            set_policy(ctx.sdk, key, **policy_patch)
            applied.extend(sorted(policy_patch))
        return utils.to_text({"ok": True, "applied": applied, "chat_key": key})
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
                "provider": _s(type="object", description="Provider object for save / fetch_models: {id?, name, base_url, api_key, models:[{id, enabled, temperature?, max_tokens?, notes?, prefill_ok?(true/false/null=auto), context_length?, max_output_tokens?, vision?, reasoning?, tool_call?, cost?{input,output}}]}"),
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
        description=(
            "Self-manage personas: list, create or update (full field coverage: name/system/opening/tools/"
            "owner_title/style/examples/nickname/avatar/prefill/catchphrases/banned_words/temperature/"
            "max_tokens), delete, bind a persona to the current or any chat, unbind, and set/clear the "
            "global default persona. Admin only. "
            "Binding tiers (most specific first, first match wins): exact chat_key → group (platform:group:ID) → "
            "@account (e.g. \"@<bot account id>\", all chats served by that bot account) → platform (e.g. \"<platform>:*\") "
            "→ global default. So to give ONE bot account a persona, bind with chat_key=\"@<account id>\"; "
            "to apply platform-wide use \"<platform>:*\". Use list first to see existing ids and bindings. "
            "Fields not provided on save keep their stored values (merge semantics)."
        ),
        parameters=_schema(
            {
                "action": _s(type="string", description="list / save / delete / bind / unbind / set_global / clear_global"),
                "persona_id": _s(type="string", description="Persona id for delete/set_global; optional id for save"),
                "name": _s(type="string", description="save: persona name"),
                "system": _s(type="string", description="save: system prompt"),
                "opening": _s(type="array", description="save: opening message candidates (sent once on first contact)"),
                "tools": _s(type="array", description="save: tool name whitelist for this persona (empty clears)"),
                "owner_title": _s(type="string", description="save: how the persona addresses the owner (e.g. 主人/老板)"),
                "style": _s(type="object", description="save: style dict {emoji_density, verbosity, formality}"),
                "examples": _s(type="array", description="save: few-shot examples [{user, assistant}]"),
                "nickname": _s(type="string", description="save: display name on merged-forward cards"),
                "avatar": _s(type="string", description="save: avatar image URL for forward cards"),
                "prefill": _s(type="string", description="save: prefilled opener - replies always start from this colloquial phrase (empty string clears it)"),
                "catchphrases": _s(type="array", description="save: catchphrases (signature lines, one per entry)"),
                "banned_words": _s(type="array", description="save: banned words this persona must never say"),
                "temperature": _s(type="number", description="save: model temperature override for this persona (omit/null to follow the model pool)"),
                "max_tokens": _s(type="number", description="save: max output tokens override for this persona (omit/null to follow the model pool)"),
                "persona": _s(type="string", description="bind: existing persona id to bind"),
                "chat_key": _s(type="string", description=(
                    "bind/unbind target; omit for the current chat. Tiered forms: "
                    "exact chat_key (one chat), platform:group:ID (one group across accounts), "
                    "@account_id (all chats of one bot account), platform:* (whole platform)"
                )),
            },
            [],
        ),
        handler=manage_personas,
        danger=True,
    ))
    registry.register(Tool(
        name="manage_config",
        access="admin",
        description="Read or change this module's own settings: get all fields or one key, set key-value updates (valid QvQChat config keys only; values are type-checked and invalid ones are rejected with a reason). Covers triggers, aggregate window, forward behaviour, notice modes, etc. Admin only.",
        parameters=_schema(
            {
                "action": _s(type="string", description="get / set / groups (grouped field catalog with one-line descriptions; call groups first to discover what is configurable)"),
                "key": _s(type="string", description="get: a single config key; omit for all"),
                "updates": _s(type="object", description="set: {config_key: value} pairs"),
            },
            [],
        ),
        handler=manage_config,
        danger=True,
    ))
    registry.register(Tool(
        name="manage_plugin_config",
        access="admin",
        description=(
            "Read or change OTHER plugin modules' settings through the framework's declarative config "
            "API. Only modules that expose qvq_settings are manageable (same pipeline as the Dashboard "
            "plugin settings page: schema from ConfigClass, type/range validation, per-key hot update, "
            "qvq.plugin_config event). list = manageable catalog with field schemas; get = current "
            "values (secrets masked); set = {module, values} key-value updates. Use this when the user "
            "asks to tweak a companion plugin's behaviour instead of guessing file paths. Admin only."
        ),
        parameters=_schema(
            {
                "action": _s(type="string", description="list / get / set"),
                "module": _s(type="string", description="get/set: target module registration name (from list)"),
                "key": _s(type="string", description="get: single config key; omit for all"),
                "values": _s(type="object", description="set: {config_key: value} pairs, validated against the module's schema (unknown keys rejected)"),
            },
            [],
        ),
        handler=manage_plugin_config,
        danger=True,
    ))
    registry.register(Tool(
        name="manage_identity",
        access="admin",
        description=(
            "Identity migration self-management: after a platform switch or account change, map an old "
            "chat identity onto a new one so history/persona/memory follow. Platform equivalence: if the old "
            "and new platform names belong to the same protocol family (one may be a fork of the other), "
            "migration is a safe like-for-like swap when the user id matches; adapters may self-declare "
            "their family relations. For OTHER platform pairs, judge yourself: matching user ids across "
            "different protocol families MAY be the same person but verify with the user before "
            "migrating. Modes: alias (map only, histories untouched) / "
            "merge (merge old history/facts/memory into target, deduped by time) / overwrite (replace "
            "target history with source, target backed up to recycle bin first). Admin only."
        ),
        parameters=_schema(
            {
                "action": _s(type="string", description="list / migrate / remove"),
                "source": _s(type="string", description="Old chat key (platform:detail_type:id), e.g. <platform>:private:12345"),
                "target": _s(type="string", description="migrate: new chat key to take over"),
                "mode": _s(type="string", description="migrate: alias / merge / overwrite (default alias)"),
            },
            [],
        ),
        handler=manage_identity,
        danger=True,
    ))
    registry.register(Tool(
        name="session_settings",
        access="admin",
        description=(
            "Per-session overrides (single chat only, unlike manage_config which is global): read or set, "
            "for ONE chat — trigger_mode (all/at_only/lurk/off), listen_off privacy flag, model, effort "
            "level, density, muted (true silences ALL responses in that chat), low_token (lean prompt + "
            "tightened history), priority (high/normal/low concurrency slot), session_budget (daily token "
            "cap for that chat, 0 = unlimited). get also returns today's usage (this session vs budget, "
            "global vs daily_token_limit) and low_token_active (whether low-token mode is currently in "
            "effect, including auto-on-limit). Falls back to the current chat when chat_key is omitted."
        ),
        parameters=_schema(
            {
                "action": _s(type="string", description="get / set"),
                "chat_key": _s(type="string", description="Target chat key; omit for the current chat"),
                "settings": _s(type="object", description="set: {trigger_mode?, listen_off?, model?, effort?, density?, muted?, low_token?, priority? (high/normal/low), session_budget? (daily tokens, 0=unlimited)}"),
            },
            [],
        ),
        handler=session_settings,
        danger=True,
    ))
