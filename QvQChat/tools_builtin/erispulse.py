from __future__ import annotations

import inspect
import json
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


def _required_send_params(chain, method: str) -> list[str]:
    """探测 Send 链绑定方法的必填参数（无默认值者；self 由绑定消除，兜底再跳一次）。

    返回空列表 = 拿不到签名或没有必填参数（调用方按现状放行，保守不拦截）。
    """
    try:
        params = inspect.signature(getattr(chain, method)).parameters.values()
    except Exception:
        return []
    required: list[str] = []
    for param in params:
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD) or param.name == "self":
            continue
        if param.default is param.empty:
            required.append(param.name)
    return required


def _platform_not_found_msg(ctx: ToolContext, platform: str) -> str:
    """平台名未注册时的纠错提示：列出全部可用平台 + 模糊建议正确名称。

    模型经常凭印象填平台名（如 bilibili 填成站点名/当前会话平台），
    只报"不存在"会让它反复撞墙；给出可用清单和最相近名称后下一次调用即可修正。
    """
    try:
        available = [str(n) for n in ctx.sdk.adapter.list_registered()]
    except Exception:
        available = []
    suggest = ""
    # 简易相似度：双向前缀/包含匹配，零依赖
    if available:
        want = str(platform).lower().replace("-", "").replace("_", "")
        scored = []
        for name in available:
            key = str(name).lower().replace("-", "").replace("_", "")
            if key == want or key.startswith(want) or want.startswith(key) or (len(want) >= 4 and want in key):
                scored.insert(0, name)
        if not scored:
            for name in available:
                key = str(name).lower()
                common = sum(1 for a, b in zip(want, key) if a == b)
                if common >= max(3, len(want) // 2):
                    scored.append(name)
        if scored:
            suggest = texts.t("adapter_suggest", suggestion=scored[0])
    return texts.t(
        "adapter_not_found_suggest",
        platform=platform,
        available=", ".join(available) or "-",
        suggest=suggest,
    )


async def send_message(ctx: ToolContext, platform: str = "", target_type: str = "",
                       target_id: str = "",
                       text: str = "", image_url: str = "", audio_path: str = "",
                       file_path: str = "",
                       at: str = "", reply_to: str = "", method: str = "",
                       as_forward: bool = False) -> str:
    if not text and not image_url and not audio_path and not file_path:
        return texts.t("send_need_content")
# 工具直发路径同样清扫假媒体标记/声明：模型常在 send_message 的 text 里写
# "「[语音] 正文」"或单独一行"（语音已发）"来假装发过语音，而语音根本没发出
    if text:
        text = utils.strip_fake_media_prefix(utils.strip_fake_media_claims(text))
# 文件/语音发送：默认只允许本会话工作区内的文件（任意群友都能触发 AI——
# 放开任意路径等于把机器上的文件外泄给任何人）；file_extra_dirs 白名单目录
# （如 TTS 缓存）的产物放行发送，写入/删除仍严格限沙箱
    resolved_file = ""
    resolved_audio = ""
    if file_path:
        from . import files as file_tools

        try:
            resolved_file = str(file_tools.sandbox_resolve(ctx, file_path, must_exist=True))
        except ValueError as e:
            return f"file_path rejected: {e}"
    if audio_path:
        from . import files as file_tools

        try:
            resolved_audio = str(file_tools.sandbox_resolve(ctx, audio_path, must_exist=True,
                                                            allow_extra=True))
        except ValueError as e:
            return f"audio_path rejected: {e}"
    if text:
        text = utils.strip_stray_tags(str(text))
    # 目标缺省=当前会话：模型不确定发给谁时无需瞎猜平台/ID（系统提示 <session> 块同步此约定）
    if not platform or not target_type or not target_id:
        cur_platform = str(getattr(ctx, "platform", "") or "")
        cur_target = str(getattr(ctx, "target_id", "") or "")
        cur_type = "group" if str(getattr(ctx, "detail_type", "") or "") == "group" else "user"
        if not cur_platform or not cur_target:
            return texts.t("send_no_session_target")
        platform = platform or cur_platform
        target_type = target_type or cur_type
        target_id = target_id or cur_target
    # 平台名透传：AI 自己会 list_platforms；未命中时给可用清单+模糊建议供其自查
    adapter = ctx.sdk.adapter.get(platform)
    if adapter is None:
        return _platform_not_found_msg(ctx, platform)
    if target_type not in ("user", "group", "channel"):
        return texts.t("target_type_invalid")
    try:
        sends = list(ctx.sdk.adapter.list_sends(platform))
    except Exception:
        sends = []
    if method and sends and method not in sends:
        return texts.t("platform_method_unsupported", platform=platform, method=method, methods=", ".join(sends))

    from ..conversation.delivery import delivery_profile, dispatch_text

    # D2：转发阈值纳入平台 profile（delivery_profiles 通配命中可覆盖）
    profile = delivery_profile(ctx.config, platform)
    threshold = int(profile.get("forward_threshold", 600) or 0)
    forward_attempted = False
    if text and (as_forward or (not method and threshold and len(text) >= threshold)):
        forward_attempted = True
        # D5：先按 Markdown 标题/长块切节，仅 Text-only 平台才剥离 Markdown
        # （先剥后切会让标题切块失效：markdown_to_text 已删掉 "## " 前缀）
        sections = utils.split_reply_sections(text)
        if sends and "Markdown" not in sends and "Html" not in sends:
            sections = [utils.markdown_to_text(s) for s in sections]
        try:
            used = await utils.deliver_forward(
                adapter,
                target_type,
                target_id,
                sections,
                sends,
                account=str(getattr(ctx, "self_id", "") or ""),
            )
        except Exception as e:
            used = ""
            if ctx.main is not None:
                ctx.main.logger.warning(f"send_message forward failed, fallback: {e}")
        if used:
            _record_sent(ctx, platform, target_type, target_id)
            return texts.t("sent_as_forward")

# 多账户后端：默认绑接收事件的账户（ctx.self_id），否则适配器按默认 bot 发出
    chain = adapter.Send
    self_id = str(getattr(ctx, "self_id", "") or "")
    if self_id:
        chain = chain.Using(self_id)
    chain = chain.To(target_type, target_id)
    if reply_to:
        chain = chain.Reply(reply_to)
    if at:
        chain = chain.At(at)

    if method:
# 方法签名防护：send_message 只按单文本形态调用（getattr(chain, name)(content)）。
# 模型猜平台方法名时（如把平台变声接口当 TTS 用），多必填
# 参数的签名会 TypeError→重试耗尽→文本入待发队列（污染）。这里提前探测绑定方法
# 签名：除文本外还有必填参数的直接拦截并给出参数清单——不发送、不入待发队列，
# 引导走 call_adapter_api 补参，语音则走 TTS 工具生成文件再 audio_path 发送
        if method not in REPLY_PREFERENCE:
            required = _required_send_params(chain, method)
            if len(required) > 1:
                return texts.t("send_method_needs_params", platform=platform, method=method,
                               params=", ".join(required))
        attempts = [method]
    else:
        attempts = [name for name in REPLY_PREFERENCE if not sends or name in sends]
        if "Text" not in attempts:
            attempts.append("Text")

# D4：与回复路径收敛同一发送实现（方法降级 + 指数退避重试 + 失败入待发队列）
    used = ""
    result = None
    last_error: Exception | None = None
    undeliverable: Exception | None = None
    if text:
        queue = {
            "chat_key": str(getattr(ctx, "chat_key", "") or f"{platform}:{target_type}:{target_id}"),
            "platform": platform,
            "detail_type": target_type,
            "target_id": target_id,
        }
        logger = ctx.main.logger if ctx.main is not None else None
        used, result, last_error = await dispatch_text(
            ctx.sdk, ctx.config,
            lambda name, content: getattr(chain, name)(content),
            attempts, text, queue=queue, logger=logger,
        )
        if last_error is not None:
            from ..conversation.delivery import is_undeliverable

            undeliverable = last_error if is_undeliverable(last_error) else None
    if text and not used:
        detail = str(last_error) if last_error is not None else "send failed"
        if undeliverable is not None:
            # 不可送达（对方非好友/目标不存在/被拒）：明确告诉模型原因与下一步，而不是谎称"已入队"
            return texts.t("send_undeliverable", platform=platform, target_type=target_type,
                           target_id=target_id, error=detail[:200])
        return texts.t("tool_error", name="send_message", error=f"{detail}；已转入待发队列")

    if image_url:
        result = await chain.Image(image_url)
    if resolved_audio:
        try:
            result = await chain.Voice(resolved_audio)
        except AttributeError:
            return texts.t("platform_method_unsupported", platform=platform, method="Voice", methods=", ".join(sends) or "-")
    if resolved_file:
        try:
            result = await chain.File(resolved_file)
        except AttributeError:
            return texts.t("platform_method_unsupported", platform=platform, method="File", methods=", ".join(sends) or "-")
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
        return _platform_not_found_msg(ctx, platform)
    if target_type not in ("user", "group", "channel"):
        return texts.t("target_type_invalid")
    try:
        chain = adapter.Send
# 未显式指定账户时默认绑本会话账户（同 send_message 的默认目标约定）
        account = str(account or getattr(ctx, "self_id", "") or "")
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


def _account_kwarg_of(adapter) -> str:
    """账户参数的传参名：适配器生态与框架文档不一致，按签名探测。

    框架标准（developer-guide/adapters/core-concepts.md）是公开的 ``account_id``
    （由 ApiDSL._merge_context 注入、适配器 params.pop 掉）；但现行适配器普遍把
    ``_account_id`` 写成具名参数。写错名字的后果很隐蔽——账户不解析（静默落到
    默认账户），且 ``account_id`` 会被当成平台参数泄漏出去。
    """
    try:
        params = inspect.signature(adapter.call_api).parameters
    except (TypeError, ValueError):
        return "account_id"
    if "_account_id" in params:
        return "_account_id"
    return "account_id"  # 含显式 account_id 或仅 **params（按标准传）


def _resolve_account_name(adapter, account_id: str) -> str:
    """把稳定 user_id（数字）映射回账户配置名；映射不到原样返回。

    适配器对配置名是第一优先级精确匹配；数字 id 依赖 bot_id 回填——那是
    运行时态（连接后识别），重启后未活动的账户没有。数字在框架三层匹配
    失配时会静默回落第一个启用账户：请求受理/空间操作从错误账户发出
    （多账户场景下同意操作需绑定来源账户发出）。
    """
    acct = str(account_id or "").strip()
    if not acct:
        return acct
    try:
        accounts = adapter.accounts
        if not isinstance(accounts, dict):
            return acct
        if acct in accounts:
            return acct  # 已是配置名
# 运行时绑定表（SnowLuma 惯例：{账户名: bot_id}，事件到达即回填）
        bot_ids = getattr(adapter, "_bot_ids", None)
        if isinstance(bot_ids, dict):
            for name, bot_id in bot_ids.items():
                if str(bot_id or "") == acct:
                    return str(name)
# 逐账户查 _get_bot_id(name) / cfg.bot_id 属性
        getter = getattr(adapter, "_get_bot_id", None)
        for name, cfg in accounts.items():
            bot_id = ""
            if callable(getter):
                try:
                    bot_id = str(getter(name) or "")
                except Exception:
                    bot_id = ""
            if not bot_id:
                bot_id = str(getattr(cfg, "bot_id", "") or "")
            if bot_id == acct:
                return str(name)
    except Exception:
        pass
    return acct


async def call_adapter_api(ctx: ToolContext, platform: str, endpoint: str, params: dict | None = None,
                           account: str = "") -> str:
    adapter = ctx.sdk.adapter.get(platform)
    if adapter is None:
        return texts.t("adapter_not_found", platform=platform)
    kwargs = dict(params or {})
# 默认绑会话所在账户：空间动态/个人信息这类接口是"哪个 bot 的视角"，
# 不带账户会落到适配器默认账户（多账户下看到/操作到别人身上）
    acct = str(account or getattr(ctx, "self_id", "") or "")
    if acct:
        acct = _resolve_account_name(adapter, acct)
        kwarg = _account_kwarg_of(adapter)
        try:
            result = await adapter.call_api(endpoint, **{kwarg: acct}, **kwargs)
        except (TypeError, ValueError) as e:
# 账户名不可解析：回退默认账户，不因绑定失败丢能力
            ctx.main.logger.debug(f"adapter api account bind failed ({platform}.{acct}): {e}")
            result = await adapter.call_api(endpoint, **kwargs)
    else:
        result = await adapter.call_api(endpoint, **kwargs)
    return utils.to_text(result)


async def handle_request(ctx: ToolContext, platform: str, request_id: str,
                         action: str = "accept", account: str = "",
                         sub_type: str = "", group_id: str = "") -> str:
    adapter = ctx.sdk.adapter.get(platform)
    if adapter is None:
        return texts.t("adapter_not_found", platform=platform)
    action = str(action).lower()
    try:
# 多账户默认绑发起会话的账户：不绑会落到适配器默认账户（张冠李戴受理）。
# 数字 user_id 先映射回配置名——配置名是适配器第一优先级精确匹配，
# 数字依赖 bot_id 回填（运行时态），失配会被静默回落第一个启用账户
        account = str(account or getattr(ctx, "self_id", "") or "")
        if account:
            account = _resolve_account_name(adapter, account)
        request = adapter.Request(str(request_id))
        if account:
            request = request.Using(account)
# 请求类型路由：群邀请/加群申请必须走 set_group_add_request（带 sub_type/group_id），
# 落到 set_friend_add_request 会把 flag 当 uid → 平台报 OIDB uid/openid invalid。
# 类型信息缺省从收件箱原始请求条目还原（AI 无需感知平台差异），显式传参可覆盖
        extra = _request_route_kwargs(ctx, account, str(request_id), sub_type, group_id)
        operation = getattr(request, action, None)
        if not callable(operation):
            return texts.t("request_action_invalid", action=action)
        result = operation(**extra)
        if inspect.isawaitable(result):
            result = await result
    except Exception as e:
        return texts.t("request_failed", error=str(e))
    return utils.to_text(result)


def _request_route_kwargs(ctx: ToolContext, account: str, request_id: str,
                          sub_type: str = "", group_id: str = "") -> dict:
    """组装请求处理的平台扩展参数：群请求带 _request_type/sub_type/group_id，好友请求为空。

    sub_type/group_id 优先用 AI 显式传参，缺省从收件箱同 request_id 的条目还原。
    """
    forced_group = False
    if not sub_type or not group_id:
        try:
            main = getattr(ctx, "main", None)
            loader = getattr(main, "_inbox_load", None)
            candidates: list = []
            if callable(loader):
                for acct in (account, "default"):
                    if not acct or acct in (c.get("account") for c in candidates):
                        continue
                    candidates.extend(loader(acct))
            for entry in candidates:
                if (str(entry.get("kind") or "") == "request"
                        and str(entry.get("request_id") or "") == request_id):
                    sub_type = sub_type or str(entry.get("sub_type") or "")
                    group_id = group_id or str(entry.get("group_id") or "")
                    forced_group = forced_group or str(entry.get("detail_type") or "") == "group"
                    break
        except Exception:
            pass
    sub_type = str(sub_type or "").lower()
    if not group_id and not forced_group and sub_type not in ("invite", "add"):
        return {}  # 好友请求：无需类型参数
    extra: dict = {"_request_type": "group"}
    if sub_type:
        extra["sub_type"] = sub_type
    if group_id:
        extra["group_id"] = group_id
    return extra


async def call_module(ctx: ToolContext, module: str, service: str, args: dict | None = None) -> str:
    result = await ctx.sdk.module.call(module, service, **(args or {}))
    return utils.to_text(result)


# 单平台 sends 清单总长上限：冷门适配器可能暴露几十个方法，防 token 爆炸
SEND_SIG_LIMIT = 600


def _send_signatures(adapter, sends: list) -> list[str]:
    """给 Send 方法名补上签名（如 AIRecord(character, text)），探测失败只留名字。

    Send 是链式工厂，发送方法绑定在链实例上（getattr(adapter.Send, name) 即绑定态）。
    只渲染具名参数——*args/**kwargs 的通用转发壳渲染出来只是噪音，留裸名即可。
    总长超 SEND_SIG_LIMIT 时截断剩余方法（模型主要需要的是"哪些方法要额外参数"）。
    """
    out: list[str] = []
    total = 0
    for name in sends:
        label = str(name)
        try:
            named = [
                p.name
                for p in inspect.signature(getattr(adapter.Send, label)).parameters.values()
                if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD) and p.name != "self"
            ]
            if named:
                label = f"{label}({', '.join(named)})"
        except Exception:
            pass
        total += len(label) + 2
        if total > SEND_SIG_LIMIT:
            break
        out.append(label)
    return out


async def list_platforms(ctx: ToolContext) -> str:
    platforms: list[dict] = []
    try:
        names = ctx.sdk.adapter.list_registered()
    except Exception:
        names = []
    for name in names:
        info: dict = {"platform": name}
        try:
            sends = list(ctx.sdk.adapter.list_sends(name))
        except Exception:
            sends = []
        info["sends"] = _send_signatures(ctx.sdk.adapter.get(name), sends)
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


async def get_current_event(ctx: ToolContext) -> str:
    """读取当前触发消息的完整原始内容：全文、各段（含引用目标 id、图片、@）、发送者等。

    自动注入只带摘要时（如引用原文拉取失败），用它能看到全部细节。
    网页端/定时任务没有实时事件，返回提示文本。
    """
    event = getattr(ctx, "event", None)
    if event is None:
        return texts.t("event_unavailable")
# 非消息事件（通知/请求）：没有消息段可读，直接给摘要 + 平台原始载荷
    ev_type = ""
    try:
        ev_type = str(event.get_type() or "")
    except Exception:
        ev_type = ""
    if ev_type and ev_type != "message":
        summary = ""
        try:
            summary = ctx.main._event_summary(event, ev_type)
        except Exception:
            summary = ""
        raw = ""
        try:
            platform = str(event.get_platform() or "")
            raw_obj = event.get(f"{platform}_raw") if hasattr(event, "get") else None
            raw = json.dumps(raw_obj, ensure_ascii=False, default=str)[:1500] if raw_obj else ""
        except Exception:
            raw = ""
        return utils.to_text({"event_type": ev_type, "summary": summary, "raw": raw})
    payload: dict = {
        "platform": str(event.get_platform() or ""),
        "message_id": str(event.get("message_id") or "") if hasattr(event, "get") else "",
        "text": str(event.get_alt_message() or ""),
        "sender_id": str(event.get_user_id() or ""),
        "sender_name": str(event.get_user_nickname() or ""),
    }
    try:
        if event.is_group_message():
            payload["group_id"] = str(event.get_group_id() or "")
    except Exception:
        pass
    segments = []
    try:
        for seg in event.get_message() or []:
            if not isinstance(seg, dict):
                continue
            stype = str(seg.get("type") or "")
            data = seg.get("data") or {}
            entry: dict = {"type": stype}
            if stype == "reply":
                entry["quoted_message_id"] = str(data.get("id") or data.get("message_id") or "")
                if data.get("text"):
                    entry["quoted_text"] = str(data.get("text"))[:200]
            elif stype == "at":
                entry["at"] = str(data.get("qq") or "")
            elif stype == "image":
                entry["url"] = str(data.get("url") or data.get("file") or "")[:200]
            elif data.get("text"):
                entry["text"] = str(data.get("text"))[:200]
            segments.append(entry)
    except Exception:
        pass
    payload["segments"] = segments
    return utils.to_text(payload)


async def list_events(ctx: ToolContext, kind: str = "", limit: int = 20) -> str:
    """查看本账户的事件收件箱：平台通知与请求（含平台私有拓展的原始字段）。

    事件到达不一定会触发回复——收件箱是模型主动回看事件流的入口，读取即标记已读。
    """
    main = ctx.main
    account = str(getattr(ctx, "self_id", "") or "") or "default"
    entries = main._inbox_load(account)
    want = str(kind or "").strip().lower()
    picked: list = []
    for entry in reversed(entries):  # 新的在前
        if want and str(entry.get("kind") or "") != want:
            continue
        picked.append(entry)
        if len(picked) >= max(1, min(int(limit or 20), 100)):
            break
    for entry in picked:
        entry["read"] = True
    if picked:
        main._inbox_save(account)
    return utils.to_text({"events": picked, "total": len(entries)})


async def recall_message(ctx: ToolContext) -> str:
    """撤回本会话机器人最近一条消息：模型发错内容后的自纠通道。

    模型想撤回时会发明语法（线上事故：把 `[recall] <id>` 当正文发出来）——
    真通道在这儿，描述里明确告知，杜绝发明语法。"""
    delivery = getattr(ctx.main, "delivery", None)
    recall = getattr(delivery, "recall_last", None)
    if not callable(recall):
        return utils.to_text({"ok": False, "error": "recall unavailable on this deployment"})
    ok = await recall(str(ctx.chat_key or ""))
    if ok:
        return utils.to_text({"ok": True, "recalled": "last message"})
    return utils.to_text({
        "ok": False,
        "error": "recall failed: nothing recallable (no message sent in this chat within the last ~2 minutes, or platform lacks delete_msg)",
    })


def register(registry: ToolRegistry, main) -> None:
    registry.register(Tool(
        name="recall_message",
        access="safe",
        dedupe_success=True,
        description="Recall (delete) the bot's own most recent message in the CURRENT chat — the self-correction channel after sending something wrong. Takes no parameters. Only works within ~2 minutes of that message and on platforms supporting delete_msg; failures are reported honestly. NEVER write your own recall syntax (like [recall] <id>) into reply text — that is not a real protocol; call this tool instead.",
        parameters=_schema({}, []),
        handler=recall_message,
    ))
    registry.register(Tool(
        name="send_message",
        access="safe",
        dedupe_success=True,
        description="Send a message to a user/group on ANY platform (cross-platform outreach). The send method is chosen by platform capability automatically (Markdown > Html > Text, with plain-text fallback); pass method to force one. DEFAULT TARGET = the CURRENT session: omit platform/target_type/target_id entirely to reply here. Fill them ONLY for a different destination — the platform name MUST be the exact 'platform' value returned by list_platforms, never guessed from the user's wording (a user mentioning a website name still needs the registered platform name). If the user asks to reach someone elsewhere but the exact platform/id is unclear, ASK the user instead of guessing. Forced methods are signature-checked before sending: a method needing extra parameters is rejected up-front with its required list (nothing is sent or queued) — check list_platforms for signatures.",
        parameters=_schema(
            {
                "platform": _s(type="string", description="Exact platform name as returned by list_platforms; see list_platforms for valid values. OMIT to use the current session's platform. Not the website name the user mentioned — verify with list_platforms when unsure."),
                "target_type": _s(type="string", description="user / group / channel. OMIT to use the current session's type."),
                "target_id": _s(type="string", description="Target id. OMIT to use the current session's id."),
                "text": _s(type="string", description="Text content (markdown allowed; downgraded to plain text automatically when the platform only supports Text)"),
                "image_url": _s(type="string", description="Image URL or local path"),
                "audio_path": _s(type="string", description="Path to an EXISTING audio file (output of a speech-synthesis tool) to deliver as a voice message. The file must live in this chat's sandbox workspace or a file_extra_dirs whitelist directory."),
                "file_path": _s(type="string", description="Send a local file as a document. MUST be a path inside this chat's work sandbox (list_files to browse; write_file/download_file/zip_files to produce one). Paths outside the sandbox are rejected."),
                "at": _s(type="string", description="User id to mention"),
                "reply_to": _s(type="string", description="Message id to quote"),
                "method": _s(type="string", description="Force a specific send method (e.g. Markdown, EmojiFace); empty for auto. Single-text methods only — methods needing extra parameters are rejected before sending, with the required params listed in the result"),
                "as_forward": _s(type="boolean", description="Send as a merged-forward card (only on platforms that support MergeForward; see list_platforms); long text converts automatically anyway"),
            },
            [],
        ),
        handler=send_message,
    ))
    registry.register(Tool(
        name="send_dsl",
        access="safe",
        dedupe_success=True,
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
        description=(
            "Call a platform adapter's native API directly — this is how platform-specific abilities are reached "
            "(e.g. social feeds, media search, account-scoped actions). Endpoint names and params are whatever "
            "the installed adapter exposes — discover them from the adapter's docs or its self-declared usage "
            "hints (installed adapters may inject their own capability notes); the call is bound to this "
            "session's bot account by default."
        ),
        parameters=_schema(
            {
                "platform": _s(type="string", description="Platform name"),
                "endpoint": _s(type="string", description="API endpoint name"),
                "params": _s(type="object", description="API parameters"),
                "account": _s(type="string", description="Bot account to act as (default: this session's account)"),
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
        name="list_events",
        access="safe",
        description="List platform events (notices & requests) waiting in this bot account's event inbox - pokes, recalls, member changes, friend/group requests AND platform-specific extended event types, with their raw payload fields preserved. Events land here even when they did not trigger a chat reply. Reading marks entries as read. Multi-account: each bot account has its OWN inbox (events for account B are not visible from account A's session); to handle a request that arrived on another account, pass that account id to handle_request.",
        parameters=_schema(
            {
                "kind": _s(type="string", description="Optional filter: notice / request. Empty for all."),
                "limit": _s(type="integer", description="Max entries to return (default 20, newest first)"),
            },
            [],
        ),
        handler=list_events,
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
        description="List online platform adapters and their supported send methods (with signatures, e.g. SendMethod(param1, param2), so you can see which methods need extra parameters and cannot be used via send_message).",
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
    registry.register(Tool(
        name="get_current_event",
        access="safe",
        description=(
            "Read the FULL raw content of the message that triggered this turn: complete text, "
            "all segments (reply/quote target message id, images with urls, @mentions), sender, "
            "group id. Use it when the auto-injected context seems truncated or a quoted message's "
            "content is missing. Returns a notice if there is no live event (dashboard/tasks)."
        ),
        parameters=OBJECT_PARAMS,
        handler=get_current_event,
    ))
