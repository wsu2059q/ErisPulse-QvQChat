from __future__ import annotations

import inspect
import time

from .. import texts, utils
from ..agent.tools import Tool, ToolContext, ToolRegistry

OBJECT_PARAMS = {"type": "object", "properties": {}, "required": []}
REPLY_PREFERENCE = ("Markdown", "Html", "Text")


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


def _s(**simple) -> dict:
    return simple


def pick_send_method(sends: list) -> str:
    available = set(sends or [])
    for name in REPLY_PREFERENCE:
        if not available or name in available:
            return name
    return "Text"


def _chain_rules(chain, rules: dict | None):
    for key, value in (rules or {}).items():
        name = str(key).lower()
        if not value:
            continue
        if name == "retry":
            chain = chain.Retry(int(value))
        elif name == "timeout":
            chain = chain.Timeout(float(value))
        elif name == "defer":
            chain = chain.Defer(float(value))
        elif name == "priority" and isinstance(value, (list, tuple)) and value:
            drop = bool(value[1]) if len(value) > 1 else False
            chain = chain.Priority(int(value[0]), drop)
    return chain


def _chain_modifies(chain, modifies: list | None):
    for item in modifies or []:
        if isinstance(item, dict) and item:
            name = next(iter(item))
            args = item[name]
            if isinstance(args, list):
                chain = getattr(chain, name)(*args)
            else:
                chain = getattr(chain, name)(args)
        elif isinstance(item, str) and item:
            chain = getattr(chain, item)()
    return chain


def _record_sent(ctx: ToolContext, platform: str, target_type: str, target_id: str) -> None:
    try:
        ctx.sent_log.append((str(platform), str(target_type), str(target_id)))
    except Exception:
        pass


async def send_message(ctx: ToolContext, platform: str, target_type: str, target_id: str,
                       text: str = "", image_url: str = "", audio_path: str = "",
                       at: str = "", reply_to: str = "", method: str = "",
                       as_forward: bool = False) -> str:
    if not text and not image_url and not audio_path:
        return texts.t("send_need_content")
    adapter = ctx.sdk.adapter.get(platform)
    if adapter is None:
        return texts.t("adapter_not_found", platform=platform)
    if target_type not in ("user", "group", "channel"):
        return texts.t("target_type_invalid")
    try:
        sends = list(ctx.sdk.adapter.list_sends(platform))
    except Exception:
        sends = []
    if method and sends and method not in sends:
        return texts.t("platform_method_unsupported", platform=platform, method=method, methods=", ".join(sends))

    threshold = int(getattr(ctx.config, "forward_threshold", 600) or 0)
    forward_attempted = False
    if text and (as_forward or (not method and threshold and len(text) >= threshold)):
        forward_attempted = True
        try:
            used = await utils.deliver_forward(
                adapter,
                target_type,
                target_id,
                utils.split_reply_sections(utils.markdown_to_text(text)),
                sends,
            )
        except Exception as e:
            used = ""
            if ctx.main is not None:
                ctx.main.logger.warning(f"send_message forward failed, fallback: {e}")
        if used:
            _record_sent(ctx, platform, target_type, target_id)
            return texts.t("sent_as_forward")

    chain = adapter.Send.To(target_type, target_id)
    if reply_to:
        chain = chain.Reply(reply_to)
    if at:
        chain = chain.At(at)

    if method:
        attempts = [method]
    else:
        attempts = [name for name in REPLY_PREFERENCE if not sends or name in sends]
        if "Text" not in attempts:
            attempts.append("Text")

    result = None
    used = ""
    last_error: Exception | None = None
    for name in attempts:
        content = utils.markdown_to_text(text) if name == "Text" else text
        try:
            if content:
                result = await getattr(chain, name)(content)
            if utils._send_failed(result):
                last_error = RuntimeError(f"send returned failed status: {result}")
                result = None
                continue
            used = name
            break
        except Exception as e:
            last_error = e
            continue
    if text and not used:
        return texts.t("tool_error", name="send_message", error=str(last_error))

    if image_url:
        result = await chain.Image(image_url)
    if audio_path:
        result = await chain.Voice(audio_path)
    if used:
        _record_sent(ctx, platform, target_type, target_id)
    body = utils.to_text(result)
    if used:
        body += "\n" + texts.t("send_method_used", method=used)
    if forward_attempted and used:
        body += "\n" + texts.t("forward_fallback")
    return body


async def send_dsl(ctx: ToolContext, platform: str, target_type: str, target_id: str,
                   method: str = "Text", params: dict | None = None, account: str = "",
                   modifies: list | None = None, rules: dict | None = None) -> str:
    adapter = ctx.sdk.adapter.get(platform)
    if adapter is None:
        return texts.t("adapter_not_found", platform=platform)
    if target_type not in ("user", "group", "channel"):
        return texts.t("target_type_invalid")
    try:
        chain = adapter.Send
        if account:
            chain = chain.Using(account)
        chain = chain.To(target_type, target_id)
        chain = _chain_rules(chain, rules)
        chain = _chain_modifies(chain, modifies)
        result = await getattr(chain, method)(**(params or {}))
    except AttributeError as e:
        return texts.t("senddsl_method_missing", error=str(e))
    except Exception as e:
        return texts.t("senddsl_failed", error=str(e))
    if not utils._send_failed(result):
        _record_sent(ctx, platform, target_type, target_id)
    return utils.to_text(result)


async def list_services(ctx, module: str = "") -> str:

    try:
        catalog = ctx.sdk.module.services() or {}
    except Exception as e:
        return f"services unavailable: {e}"
    if module:
        catalog = {str(module): catalog.get(str(module), [])}
    lines: list[str] = []
    for name in sorted(catalog):
        services = catalog[name]
        if not isinstance(services, list):
            continue
        for svc in services:
            if not isinstance(svc, dict):
                continue
            params = svc.get("parameters")
            param_text = ""
            if isinstance(params, dict) and params:
                param_text = ", ".join(str(k) for k in params)
            description = str(svc.get("description") or "")
            lines.append(f"{name}.{svc.get('name')}({param_text}) - {description}")
    return "\n".join(lines) or texts.t("services_none")


async def call_adapter_api(ctx: ToolContext, platform: str, endpoint: str, params: dict | None = None) -> str:
    adapter = ctx.sdk.adapter.get(platform)
    if adapter is None:
        return texts.t("adapter_not_found", platform=platform)
    result = await adapter.call_api(endpoint, **(params or {}))
    return utils.to_text(result)


async def handle_request(ctx: ToolContext, platform: str, request_id: str,
                         action: str = "accept", account: str = "") -> str:
    adapter = ctx.sdk.adapter.get(platform)
    if adapter is None:
        return texts.t("adapter_not_found", platform=platform)
    action = str(action).lower()
    try:
        request = adapter.Request(request_id)
        operation = getattr(request, action, None)
        if not callable(operation):
            return texts.t("request_action_invalid", action=action)
        result = operation()
        if inspect.isawaitable(result):
            result = await result
    except Exception as e:
        return texts.t("request_failed", error=str(e))
    return utils.to_text(result)


async def call_module(ctx: ToolContext, module: str, service: str, args: dict | None = None) -> str:
    result = await ctx.sdk.module.call(module, service, **(args or {}))
    return utils.to_text(result)


async def list_platforms(ctx: ToolContext) -> str:
    platforms: list[dict] = []
    try:
        names = ctx.sdk.adapter.list_registered()
    except Exception:
        names = []
    for name in names:
        info: dict = {"platform": name}
        try:
            info["sends"] = ctx.sdk.adapter.list_sends(name)
        except Exception:
            info["sends"] = []
        platforms.append(info)
    return utils.to_text(platforms)


async def takeover_session(ctx: ToolContext, duration_minutes: int = 10) -> str:
    main = ctx.main
    if not main.is_admin(ctx.user_id, ctx.origin, ctx.platform):
        return texts.t("needs_admin")
    chat_key = ctx.chat_key
    if chat_key in main.takeover:
        return texts.t("takeover_already")
    lease = None
    if ctx.event is not None:
        try:
            lease = ctx.sdk.interaction.acquire(ctx.event, owner="QvQChat", ttl=duration_minutes * 60)
        except Exception:
            lease = None
        if lease is None:
            return texts.t("takeover_busy")
    main.takeover[chat_key] = {"lease": lease, "until": time.time() + duration_minutes * 60}
    return texts.t("takeover_done", chat_key=chat_key, minutes=duration_minutes)


async def release_takeover(ctx: ToolContext) -> str:
    main = ctx.main
    entry = main.takeover.pop(ctx.chat_key, None)
    if entry is None:
        return texts.t("takeover_not_active")
    lease = entry.get("lease")
    if lease is not None:
        try:
            lease.release()
        except Exception:
            pass
    return texts.t("takeover_released", chat_key=ctx.chat_key)


async def list_takeovers(ctx: ToolContext) -> str:
    main = ctx.main
    now = time.time()
    active = [
        key
        for key, entry in main.takeover.items()
        if entry.get("until", 0) > now
    ]
    return utils.to_text({"active": active})


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="send_message",
        access="safe",
        description="Send a message to any user/group on any platform. The send method is chosen by platform capability automatically (Markdown > Html > Text, with plain-text fallback); pass method to force one. Use list_platforms to discover supported methods.",
        parameters=_schema(
            {
                "platform": _s(type="string", description="Platform name, e.g. onebot11"),
                "target_type": _s(type="string", description="Target type: user / group / channel"),
                "target_id": _s(type="string", description="Target id"),
                "text": _s(type="string", description="Text content (markdown allowed; downgraded to plain text automatically when the platform only supports Text)"),
                "image_url": _s(type="string", description="Image URL or local path"),
                "audio_path": _s(type="string", description="Local audio file path"),
                "at": _s(type="string", description="User id to mention"),
                "reply_to": _s(type="string", description="Message id to quote"),
                "method": _s(type="string", description="Force a specific send method (e.g. Markdown, EmojiFace); empty for auto"),
                "as_forward": _s(type="boolean", description="Send as a merged-forward card (onebot11 only); long text converts automatically anyway"),
            },
            ["platform", "target_type", "target_id"],
        ),
        handler=send_message,
    ))
    registry.register(Tool(
        name="send_dsl",
        access="safe",
        description="Full SendDSL power: build a complete send chain — Using(account), rules (retry/timeout/defer/priority), modifiers (Reply/At/AtAll/...), then any send method the platform supports. Inspect list_platforms for available methods.",
        parameters=_schema(
            {
                "platform": _s(type="string", description="Platform name"),
                "target_type": _s(type="string", description="user / group / channel"),
                "target_id": _s(type="string", description="Target id"),
                "method": _s(type="string", description="Send method name, e.g. Text / Markdown / Image"),
                "params": _s(type="object", description="Keyword arguments for the send method"),
                "account": _s(type="string", description="Bot account to send with (Using)"),
                "modifies": _s(type="array", description="Modifier chain before the send, e.g. [{'Reply': 'msg_id'}, {'At': 'uid'}, 'AtAll']"),
                "rules": _s(type="object", description="Send rules, e.g. {'retry': 2, 'timeout': 10, 'defer': 5, 'priority': [3, false]}"),
            },
            ["platform", "target_type", "target_id"],
        ),
        handler=send_dsl,
    ))
    registry.register(Tool(
        name="list_services",
        access="safe",
        description="List ErisPulse module services as module.service(params) - description lines. "
                    "Use it to discover capabilities, then invoke them via call_module "
                    "(covers modules whose services are not bridged as eco_* tools).",
        parameters=_schema({"module": _s(type="string", description="Optional module name filter")}, []),
        handler=list_services,
    ))
    registry.register(Tool(
        name="call_adapter_api",
        access="admin",
        description="Call a platform adapter's native API directly (management endpoints not covered by Send DSL).",
        parameters=_schema(
            {
                "platform": _s(type="string", description="Platform name"),
                "endpoint": _s(type="string", description="API endpoint name"),
                "params": _s(type="object", description="API parameters"),
            },
            ["platform", "endpoint"],
        ),
        handler=call_adapter_api,
    ))
    registry.register(Tool(
        name="handle_request",
        access="admin",
        description="Handle a friend/group request event via Request DSL: accept or reject it by request id.",
        parameters=_schema(
            {
                "platform": _s(type="string", description="Platform name"),
                "request_id": _s(type="string", description="Request event id"),
                "action": _s(type="string", description="accept or reject"),
                "account": _s(type="string", description="Bot account, optional"),
            },
            ["platform", "request_id"],
        ),
        handler=handle_request,
    ))
    registry.register(Tool(
        name="call_module",
        access="admin",
        description="Call another ErisPulse module's service (also works for modules not in the ecosystem bridge).",
        parameters=_schema(
            {
                "module": _s(type="string", description="Module name"),
                "service": _s(type="string", description="Service method name"),
                "args": _s(type="object", description="Arguments dict"),
            },
            ["module", "service"],
        ),
        handler=call_module,
    ))
    registry.register(Tool(
        name="list_platforms",
        access="safe",
        description="List online platform adapters and their supported send methods.",
        parameters=OBJECT_PARAMS,
        handler=list_platforms,
    ))
    registry.register(Tool(
        name="takeover_session",
        access="admin",
        description="Take over the current session: every incoming message is handled by the agent first and claimed. Dangerous, admin only.",
        parameters=_schema(
            {"duration_minutes": _s(type="integer", description="Duration in minutes", default=10)},
            [],
        ),
        handler=takeover_session,
        danger=True,
    ))
    registry.register(Tool(
        name="release_takeover",
        access="admin",
        description="Release the takeover of the current session.",
        parameters=OBJECT_PARAMS,
        handler=release_takeover,
    ))
    registry.register(Tool(
        name="list_takeovers",
        access="safe",
        description="List sessions currently taken over.",
        parameters=OBJECT_PARAMS,
        handler=list_takeovers,
    ))
