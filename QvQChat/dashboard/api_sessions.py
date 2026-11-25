"""会话域 API（拆分自 dashboard/manager.py）：sessions / messages / share / routes / memory / UI 默认值。

mixin 由 DashboardManager 组合，HTTP 路由路径不变（路由表仍在 manager.py）。
"""
from __future__ import annotations

from pathlib import Path

from ..engine.base import ChatRequest

from .. import texts, utils
from ..chat.events import EVENT_INBOX_KEY
from ..conversation import handover
from ..conversation.policy import get_policy, set_policy
from ..conversation.service import parse_chat_key, strip_account, strip_isolation
from ..tools_builtin import agent as agent_tools
from .api_common import ApiError, api_handler, read_json, sget

TEMPLATES = Path(__file__).parent / "templates"
SHARES_KEY = "QvQChat:shares"
UI_DEFAULTS_KEY = "QvQChat:ui_defaults"


def _sub_decoration(chat_key: str) -> dict:
    """``sub:`` 会话键装饰：kind（sub=子智能体 / handover=让渡）+ sub_of（父会话键）。

    键格式：``sub:<parent>:<hex8>``、``sub:<parent>:demote:<hex8>``、
    ``sub:handover:<parent>:<hex8>``。parent 本身含冒号，只能按已知后缀尽力解析；
    解析不出父键时只给 kind。
    """
    key = str(chat_key or "")
    if not key.startswith("sub:"):
        return {}
    rest = key[4:]
    kind = "sub"
    if rest.startswith("handover:"):
        kind, rest = "handover", rest[len("handover:"):]
    if ":demote:" in rest:
        parent = rest.rsplit(":demote:", 1)[0]
    else:
        head, _, tail = rest.rpartition(":")
        if len(tail) != 8:
            return {"kind": kind}
        parent = head
    return {"kind": kind, "sub_of": parent}


class SessionsApiMixin:
    """依赖宿主提供 self.main / self.sdk / self._query / self._live。"""

    async def sessions_get(self, request):
        sessions = await self.main.sessions.list_sessions()
        total = len(sessions)
# 窗口参数：大会话量（几百群）时全量展开每会话的成员/路由/策略解析是面板卡顿
# 的主因——列表行按页展开，账户聚合/身份建议仍用全量计算（纯内存，便宜）
        try:
            limit_n = max(1, min(int(self._query(request, "limit") or 0), 200))
        except ValueError:
            limit_n = 0
        try:
            start_i = int(self._query(request, "start") or 0)
        except ValueError:
            start_i = 0
        archived_only = str(self._query(request, "archived") or "").strip() == "1"
        rows = [s for s in sessions if s.get("archived")] if archived_only else sessions
        # 搜索过滤（对话页侧栏搜索框）：名字/chat_key 不区分大小写包含匹配；
        # 名字不中时全局搜消息正文（contexts 内容，最近 300 条/会话）——命中行带
        # snippet（首个命中消息前后截断摘要），DeepSeek 式"找那句在哪说的"。
        # 名字尚未异步解析落定时退回 chat_key 匹配，任一命中即保留。
        query = str(self._query(request, "q") or "").strip().lower()
        if query:
            text_of = self.main.sessions._text_of
            scanned: dict[str, str] = {}

            async def _body_scan(chat_key: str) -> str:
                # 内容扫描结果进程内缓存（同 key 二次输入防抖免重扫；列表请求高频不进此路径）
                if chat_key not in scanned:
                    try:
                        contexts = await self.main.sessions.get_contexts(chat_key) or []
                    except Exception:
                        contexts = []
                    scanned[chat_key] = "\n".join(
                        text_of(c.get("content")) for c in contexts[-300:] if isinstance(c, dict)
                    )
                return scanned[chat_key]

            async def _hit(s: dict) -> bool:
                name = str(s.get("name") or "").lower()
                key = str(s.get("chat_key") or "").lower()
                if query in name or query in key:
                    return True
                body = await _body_scan(str(s.get("chat_key") or ""))
                return query in body.lower()

            rows = [s for s in rows if await _hit(s)]
            for s in rows:
                if query in str(s.get("name") or "").lower() or query in str(s.get("chat_key") or "").lower():
                    continue  # 名字/key 命中：不扫正文，snippet 留空
                body = await _body_scan(str(s.get("chat_key") or ""))
                idx = body.lower().find(query)
                if idx >= 0:
                    head = max(0, idx - 40)
                    snippet = body[head:idx + len(query) + 60].replace("\n", " ").strip()
                    s["snippet"] = ("…" + snippet + "…") if head > 0 or idx + len(query) + 60 < len(body) else snippet
        total = len(rows)
        if limit_n:
            start_i = max(0, min(start_i, total))
            window = rows[start_i : start_i + limit_n]
        else:
            start_i = 0
            window = rows
        for session in window:
            if str(session.get("platform") or "") == "dashboard" and not session.get("name"):
                session["name"] = texts.t("dashboard_session_name")
            session["members"] = await self.main.sessions.members_of(session.get("chat_key") or "")
            session["sources"] = await self.main.sessions.routes_into(session.get("chat_key") or "")
# 人工接管态随行下发（头部横幅 + composer 直发分支）
            session["manual"] = bool(await self.main.sessions.get_flag(session.get("chat_key") or "", "manual"))
# 会话治理策略随行下发：面板开关直接渲染 muted/low_token/priority 当前值
            session["policy"] = await get_policy(self.sdk, session.get("chat_key") or "")
# 子会话装饰：面板侧栏给 sub: 键挂 子智能体/让渡 徽标与父会话链接
            deco = _sub_decoration(session.get("chat_key") or "")
            if deco:
                session.update(deco)
        try:
            self.main.spawn(self.main.conversations.resolve_session_names(window))
        except Exception as e:
            self.main.logger.debug(f"resolve session names failed: {e}")
        live_keys = set()
        try:
            for s in window:
                if self._live.busy(s["chat_key"]):
                    live_keys.add(s["chat_key"])
                    s["live"] = True
        except Exception as e:
            self.main.logger.debug(f"live session mark failed: {e}")
        return {
            "sessions": window,
            "total": total,
            "start": start_i,
            "limit": limit_n,
            "live_sessions": sorted(live_keys),
            "ui_defaults": await self._ui_defaults(),
            "identity_map": await self.main.sessions.identity_map(),
            "identity_suggestions": await self._identity_suggestions(sessions),
            "accounts": await self._accounts_overview(sessions),
        }

    @api_handler
    async def handover_get(self, request):
        """让渡状态（面板横幅）：active/setup/turns/max_turns/model/listen/started。"""
        chat_key = str(self._query(request, "chat_key") or "")
        state = await handover.get_state(self.sdk, chat_key)
        if not isinstance(state, dict):
            return {"active": False}
        out = dict(state)
        out.pop("role_prompt", None)  # 角色系统提示含场景细节，不外泄
        return out

    @api_handler
    async def handover_stop(self, request):
        """结束让渡：走 Main.handover_stop（注记 + 剧情摘要同一套收场管线）。"""
        body = await read_json(request)
        chat_key = sget(body, "chat_key")
        if not chat_key:
            raise ApiError("chat_key required")
# 先查状态再调服务：无让渡不触发收场管线（注记/摘要）
        if await handover.get_state(self.sdk, chat_key) is None:
            raise ApiError("no active handover for this session", 404)
        ok = await self.main.handover_stop(chat_key=chat_key)
        if not ok:
            raise ApiError("no active handover for this session", 404)
        await self.main.audit("handover_stop", {"chat_key": utils.truncate(chat_key, 120)})
        return {"ok": True}

    @api_handler
    async def subjobs_get(self, request):
        """后台子智能体任务列表：运行中（进程内）+ 终态（探针，新在前）。"""
        rows = await agent_tools.list_subjobs(self.main, limit=100)
        return {"jobs": rows, "total": len(rows)}

    @api_handler
    async def subjobs_cancel(self, request):
        """取消后台子智能体：任务 cancel，收场说明经 qvq.subagent_done 插回父会话。"""
        body = await read_json(request)
        sub_key = sget(body, "sub_key")
        if not sub_key:
            raise ApiError("sub_key required")
        ok = agent_tools.cancel_subjob(self.main, sub_key)
        if not ok:
            raise ApiError("subjob not running (finished or process restarted)", 404)
        await self.main.audit("subjob_cancel", {"sub_key": utils.truncate(sub_key, 120)})
        return {"ok": True}

    async def identity_set(self, request):
        """身份迁移：source 会话键的事件此后按 target 会话处理（历史/人格/记忆跟随）。

        mode=alias 仅映射 / merge 合并（上下文/事实/记忆并入）/ overwrite 覆盖（先备份进回收站）。
        """
        body = await request.json()
        source = str((body or {}).get("source") or "").strip()
        target = str((body or {}).get("target") or "").strip()
        mode = str((body or {}).get("mode") or "alias").strip().lower()
        if not source or not target or source == target:
            return ({"error": "source/target required and must differ"}, 400)
        summary = await self.main.sessions.migrate_identity(source, target, mode)
        if not summary.get("ok"):
            return ({"error": summary.get("error") or "migrate failed"}, 400)
        return summary

    async def identity_remove(self, request):
        body = await request.json()
        source = str((body or {}).get("source") or "")
        return {"ok": await self.main.sessions.remove_identity(source)}

    async def _inbox_entries(self, kind: str = "", account: str = "") -> list:
        """聚合全部账户的事件收件箱（storage 为准），新的在前。"""
        entries: list = []
        try:
            keys = [str(k) for k in (await self.sdk.storage.aget_all_keys() or []) if str(k).startswith(EVENT_INBOX_KEY)]
        except Exception:
            keys = [EVENT_INBOX_KEY + account] if account else []
        for key in keys:
            stored = await self.sdk.storage.aget(key)
            if not isinstance(stored, list):
                continue
            owner = key[len(EVENT_INBOX_KEY):]
            if account and owner != account:
                continue
            for entry in stored:
                if not isinstance(entry, dict):
                    continue
                if kind and str(entry.get("kind") or "") != kind:
                    continue
                item = dict(entry)
                item["account"] = owner
                entries.append(item)
        entries.sort(key=lambda e: float(e.get("ts") or 0), reverse=True)
        return entries

    async def inbox_get(self, request):
        """事件收件箱面板：通知/请求列表（聚合多账户），支持类型过滤与分页。"""
        kind = str(self._query(request, "kind") or "").strip().lower()
        account = str(self._query(request, "account") or "").strip()
        try:
            limit = max(1, min(int(self._query(request, "limit") or 100), 500))
        except ValueError:
            limit = 100
        try:
            offset = max(0, int(self._query(request, "offset") or 0))
        except ValueError:
            offset = 0
        entries = await self._inbox_entries(kind, account)
        unread = sum(1 for e in entries if not e.get("read"))
# 读取即标已读（单源：与 AI list_events 同一 read 字段；仅标记本次返回的页）
        for entry in entries[offset : offset + limit]:
            if entry.get("read"):
                continue
            entry["read"] = True
            try:
                inbox_account = str(entry.get("account") or "default")
                for item in await self.main._inbox_load(inbox_account):
                    if str(item.get("id") or "") == str(entry.get("id") or ""):
                        item["read"] = True
                await self.main._inbox_save(inbox_account)
                self._inbox_cache_drop(inbox_account)
            except Exception:
                pass
        return {"events": entries[offset : offset + limit], "total": len(entries), "unread": unread,
                "offset": offset, "limit": limit}

    async def inbox_handle(self, request):
        """面板直接处置请求事件（同意/拒绝）：转调 handle_request 的路由逻辑
        （类型还原 + 账户绑定），处置后标记条目已读。"""
        body = await request.json()
        entry_id = str((body or {}).get("id") or "")
        action = str((body or {}).get("action") or "accept").lower()
        if action not in ("accept", "reject"):
            return ({"error": "action must be accept/reject"}, 400)
        entry = None
        for candidate in await self._inbox_entries("request", ""):
            if str(candidate.get("id") or "") == entry_id:
                entry = candidate
                break
        if entry is None:
            return ({"error": "request entry not found"}, 404)
        from ..tools_builtin.erispulse import _request_route_kwargs, _resolve_account_name
        from ..agent.tools import ToolContext

        platform = str(entry.get("platform") or "")
        request_id = str(entry.get("request_id") or "")
        account = _resolve_account_name(
            self.sdk.adapter.get(platform) if platform else None,
            str(entry.get("account") or ""),
        ) if platform else ""
        ctx = ToolContext(main=self.main, sdk=self.sdk, config=self.main.cfg,
                          chat_key=str(entry.get("chat_key") or ""), platform=platform,
                          user_id=str(entry.get("user_id") or ""), origin="dashboard")
        extra = await _request_route_kwargs(ctx, account, request_id,
                                      str(entry.get("sub_type") or ""),
                                      str(entry.get("group_id") or ""))
        adapter = self.sdk.adapter.get(platform) if platform else None
        if adapter is None:
            return {"ok": False, "error": f"adapter {platform} not found"}
        try:
            request_dsl = adapter.Request(request_id)
            if account:
                request_dsl = request_dsl.Using(account)
            operation = getattr(request_dsl, action, None)
            if not callable(operation):
                return {"ok": False, "error": f"invalid action {action}"}
            result = operation(**extra)
            import inspect as _inspect

            if _inspect.isawaitable(result):
                result = await result
        except Exception as e:
            return {"ok": False, "error": str(e)}
# 已读标记：面板与 AI 视角一致
        try:
            inbox_account = str(entry.get("account") or "default")
            for item in await self.main._inbox_load(inbox_account):
                if str(item.get("id") or "") == entry_id:
                    item["read"] = True
            await self.main._inbox_save(inbox_account)
            self._inbox_cache_drop(inbox_account)
        except Exception:
            pass
        await self.main.audit("inbox_handle", {"id": entry_id, "action": action,
                                               "platform": platform, "request_id": request_id})
        return {"ok": True, "result": result}

    def _inbox_cache_drop(self, account: str) -> None:
        # AI 侧读的是 main.rt.event_inbox 里的同一个 list 对象：面板删改后必须
        # 失效缓存，否则下次 AI 读取/保存会把删除的条目原样写回
        self.main.rt.event_inbox.pop(account, None)

    async def inbox_delete(self, request):
        body = await request.json()
        account = str((body or {}).get("account") or "")
        entry_id = str((body or {}).get("id") or "")
        if not account or not entry_id:
            return ({"error": "account/id required"}, 400)
        key = EVENT_INBOX_KEY + account
        stored = await self.sdk.storage.aget(key)
        if not isinstance(stored, list):
            return {"ok": False}
        kept = [e for e in stored if not (isinstance(e, dict) and str(e.get("id") or "") == entry_id)]
        if len(kept) == len(stored):
            return {"ok": False}
        await self.sdk.storage.aset(key, kept)
        self._inbox_cache_drop(account)
        return {"ok": True}

    async def inbox_clear(self, request):
        body = await request.json()
        account = str((body or {}).get("account") or "")
        if account:
            await self.sdk.storage.aset(EVENT_INBOX_KEY + account, [])
            self._inbox_cache_drop(account)
            return {"ok": True}
        try:
            keys = [str(k) for k in (await self.sdk.storage.aget_all_keys() or []) if str(k).startswith(EVENT_INBOX_KEY)]
        except Exception:
            keys = []
        for key in keys:
            await self.sdk.storage.aset(key, [])
            self._inbox_cache_drop(key[len(EVENT_INBOX_KEY):])
        return {"ok": True, "cleared": len(keys)}

    async def _accounts_overview(self, sessions: list) -> dict:
        """多账户概览：各平台在线 bot + 每个已隔离账户（chat_key 的 @account 后缀）的会话数。

        单账户平台不产生后缀，不进 accounts；sub: 前缀的子会话键跳过。
        """
        counts: dict[str, dict] = {}
        for s in sessions:
            key = str(s.get("chat_key") or "")
            if "@" not in key or key.startswith("sub:"):
                continue
            base, _, acct = key.rpartition("@")
            if not acct or base.startswith("sub:"):
                continue
            platform = base.split(":", 1)[0] or "?"
            entry = counts.setdefault(acct, {"account": acct, "platforms": set(), "sessions": 0})
            entry["platforms"].add(platform)
            entry["sessions"] += 1
        adapters: list[dict] = []
        try:
            names = list(self.sdk.adapter.list_registered() or [])
        except Exception:
            names = []
        display_names: dict = {}
        summary: dict = {}
        try:
            summary = self.sdk.adapter.get_status_summary() or {}
        except Exception:
            summary = {}
        adapters_summary = summary.get("adapters") or {}
        for name in names:
            info = adapters_summary.get(str(name)) or {}
            bots_raw = info.get("bots") or {}
            bots = []
            for bot_id, meta in bots_raw.items():
                meta = meta if isinstance(meta, dict) else {}
                bots.append({
                    "id": str(bot_id),
                    "status": str(meta.get("status") or ""),
                    "last_active": meta.get("last_active"),
                    "nickname": str((meta.get("info") or {}).get("nickname") or ""),
                })
            adapters.append({
                "platform": str(name),
                "status": str(info.get("status") or ""),
                "enabled": bool(info.get("enabled", True)),
                "bots": bots,
                "persona": "",
            })
# 配置中存在但未注册的适配器（禁用态）也透出，便于在面板开启
        for platform_name, info in adapters_summary.items():
            if str(platform_name) in names or not isinstance(info, dict):
                continue
            adapters.append({
                "platform": str(platform_name),
                "status": str(info.get("status") or ""),
                "enabled": bool(info.get("enabled", False)),
                "bots": [],
                "persona": "",
            })
# user_id → 账户名（配置键）：会话键统一用稳定的 user_id 后缀，UI 显示可读账户名
        adapter_accounts: dict[str, list[str]] = {}  # 适配器名 → 配置账户名列表
        try:
            for name in names:
                adapter = self.sdk.adapter.get(str(name))
                accounts_cfg = getattr(adapter, "accounts", None) if adapter is not None else None
                if isinstance(accounts_cfg, dict):
                    adapter_accounts[str(name)] = [str(k) for k in accounts_cfg if str(k)]
                    for acct_name, cfg in accounts_cfg.items():
                        bot_id = getattr(cfg, "bot_id", None)
                        if bot_id:
                            display_names[str(bot_id)] = str(acct_name)
        except Exception:
            adapter_accounts = {}
# 每账户当前人格：绑定表的 @account / 平台:* 层级键（编排页账户卡显示+快捷绑定用）
        persona_by_key: dict[str, str] = {}
        try:
            for bind_key, persona_id in (await self.main.personas.abindings() or {}).items():
                persona_by_key[str(bind_key)] = str(persona_id)
        except Exception:
            persona_by_key = {}
# 适配器卡的平台级绑定（platform:*）——适配器卡上的快捷下拉
        for a in adapters:
            a["persona"] = persona_by_key.get(a["platform"] + ":*", "")
# 会话键后缀（bot_id 或账户名变体）归并到配置账户名：同一账户不再裂成多条；
# 适配器配置里的账户即使 0 会话也透出（新登录账户还没有会话，也要能绑定人格）
        merged: dict[str, dict] = {}
        for entry in counts.values():
            acct = entry["account"]
            canonical = display_names.get(acct, acct)
            slot = merged.setdefault(
                canonical,
                {"account": canonical, "platforms": set(), "sessions": 0, "aliases": set()},
            )
            slot["platforms"] |= entry["platforms"]
            slot["sessions"] += entry["sessions"]
            slot["aliases"].add(acct)
        for platform, accts in adapter_accounts.items():
            for acct in accts:
                if acct in merged:
                    merged[acct]["platforms"].add(platform)
                    continue
                merged[acct] = {
                    "account": acct,
                    "platforms": {platform},
                    "sessions": 0,
                    "aliases": {acct},
                }
        accounts = []
        for slot in sorted(merged.values(), key=lambda x: (-x["sessions"], x["account"])):
            acct = slot["account"]
            platforms = sorted(slot["platforms"])
# 生效人格：账户名与全部历史后缀变体的 @键 依次试，其次该账户任一平台的 platform:* 键
            persona = ""
            for alias in [acct, *sorted(slot["aliases"])]:
                persona = persona_by_key.get("@" + alias, "")
                if persona:
                    break
            if not persona:
                for platform in platforms:
                    persona = persona_by_key.get(f"{platform}:*", "")
                    if persona:
                        break
            accounts.append({
                "account": acct,
                "platforms": platforms,
                "sessions": slot["sessions"],
                "persona": persona,
            })
        return {
            "adapters": adapters,
            "accounts": accounts,
            "display_names": display_names,
        }

    async def _identity_suggestions(self, sessions: list) -> list:
        """疑似同源会话对：同 target_id 跨平台的会话（换平台场景），供迁移面板一键预填。

        只做发现不做自动迁移——方向（谁是源谁是目标）与模式由用户确认
        （面板有交换方向按钮）。键保留完整形态（含 @账户 后缀），预填才能
        选中下拉选项。已在 identity_map 中的不再建议。
        """
        from ..conversation.service import strip_isolation

        try:
            mapped = set((await self.main.sessions.identity_map()).keys())
        except Exception:
            mapped = set()
        seen: dict[str, dict] = {}
        found: list = []
        for s in sessions:
            key = strip_isolation(str(s.get("chat_key") or ""))
            base = key.rsplit("@", 1)[0] if "@" in key.rsplit(":", 2)[-1] else key
            parts = base.split(":", 2)
            if len(parts) < 3:
                continue
            platform, dtype, tid = parts[0], parts[1], parts[2]
            if dtype not in ("private", "group") or not tid:
                continue
            slot = f"{dtype}:{tid}"
            first = seen.get(slot)
            if first and first["platform"] != platform and first["key"] != key \
                    and first["key"] not in mapped and key not in mapped:
                found.append({"source": first["key"], "target": key, "detail": slot})
            elif not first:
                seen[slot] = {"platform": platform, "key": key}
        return found[:8]

    async def identity_merge_account(self, request):
        """账户级批量归并：把 @from 账户名下的全部会话迁到 @to（历史/人格/记忆合并）。

        存量数据归并工具——如适配器上报的账户从数字 id 漂移成配置名（或反向）后，
        同一机器人的会话散在两个 @后缀下，一键归并到稳定形态。
        """
        body = await request.json() or {}
        platform = str(body.get("platform") or "").strip()
        from_acct = str(body.get("from") or "").strip()
        to_acct = str(body.get("to") or "").strip()
        mode = str(body.get("mode") or "merge").strip().lower()
        if not platform or not from_acct or not to_acct or from_acct == to_acct:
            return ({"error": "platform/from/to required and from != to"}, 400)
        if mode not in ("merge", "overwrite"):
            return ({"error": "mode must be merge or overwrite"}, 400)
        migrated, failed = 0, []
        for session in await self.main.sessions.list_sessions():
            key = str(session.get("chat_key") or "")
            if not key.startswith(f"{platform}:") or not key.endswith(f"@{from_acct}"):
                continue
            target = key[: -len(f"@{from_acct}")] + f"@{to_acct}"
            summary = await self.main.sessions.migrate_identity(key, target, mode)
            if summary.get("ok"):
                migrated += 1
            else:
                failed.append({"chat_key": key, "error": summary.get("error")})
        return {"ok": not failed, "migrated": migrated, "failed": failed}

    async def prompt_preview(self, request):
        """提示词调试器：dry-run 整条组装链，返回部件明细与全文（不落库、无副作用）。"""
        chat_key = self._query(request, "chat_key")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        try:
            prepared = await self.main.sessions.prepare(
                chat_key,
                "(调试预览：此处将替换为用户本次消息)",
                persist=False,
                debug=True,
            )
        except Exception as e:
            self.main.logger.debug(f"prompt preview failed: {e}")
            return ({"error": str(e)}, 500)
        return {
            "chat_key": chat_key,
            "model": prepared.get("model") or "",
            "persona": (prepared.get("persona") or {}).get("name") or "",
            "system_chars": len(prepared.get("system") or ""),
            "history_turns": len(prepared.get("contexts") or []),
            "debug": prepared.get("debug") or {},
            "system": prepared.get("system") or "",
        }

    async def session_messages(self, request):
        chat_key = self._query(request, "chat_key")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        contexts = await self.main.sessions.get_contexts(chat_key)
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
        return {"chat_key": chat_key, "summary": await self.main.sessions.summary_of(chat_key) if start_i == 0 else "",
                "messages": window, "total": total, "start": start_i}

    async def session_message_delete(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        index = int((body or {}).get("index", -1))
        if await self.main.conversations.delete_message(chat_key, index):
            return {"ok": True}
        return ({"error": "index out of range"}, 400)

    async def session_context_edit(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        index = int((body or {}).get("index", -1))
        content = str((body or {}).get("content") or "")
        attachments = (body or {}).get("attachments")
        if await self.main.conversations.edit_message(chat_key, index, content, attachments):
            return {"ok": True}
        return ({"error": "index out of range"}, 400)

    async def session_rewind(self, request):
        """编辑并重发：丢弃该条及其之后的消息，返回原文（前端拿到后走正常发送管线）。"""
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        try:
            index = int((body or {}).get("index", -1))
        except (TypeError, ValueError):
            return ({"error": "bad index"}, 400)
        if self._live.busy(chat_key):
            return ({"error": "session busy"}, 409)
        ok, text = await self.main.conversations.rewind_to(chat_key, index)
        if not ok:
            return ({"error": "index out of range"}, 400)
        return {"ok": True, "text": text}

    async def sessions_delete(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        # 撤销删除：删除前把完整会话状态放进回收站
        from ..conversation.service import CONV_PREFIX

        state = await self.sdk.storage.aget(CONV_PREFIX + chat_key, None)
        undo = ""
        if isinstance(state, dict):
            undo = await self._trash_put("session", {"chat_key": chat_key, "state": state})
        ok = await self.main.conversations.delete(chat_key)
        return {"ok": ok, "undo": undo if ok else ""}

    async def sessions_create(self, request):
        body = await request.json()
        chat_key = await self.main.conversations.create(
            platform=str((body or {}).get("platform") or "dashboard"),
            detail_type=str((body or {}).get("detail_type") or "private"),
            target_id=str((body or {}).get("target_id") or ""),
        )
        return {"ok": True, "chat_key": chat_key}

    async def sessions_delete_archived(self, request):
        return {"ok": True, "removed": await self.main.conversations.delete_archived()}

    async def session_compact(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        report = await self.main.conversations.compact_now(chat_key)
        return {"ok": True, "report": report}


    # ---------- 会话 TODO 清单（与 AI 工具同库 TodoStore） ----------

    def _todo_store(self):
        return self.main.conversations.todos

    async def todo_list(self, request):
        chat_key = str(self._query(request, "chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        todos = await self._todo_store().items(chat_key)
        return {"todos": todos}

    async def todo_save(self, request):
        """整表替换（与 AI 的 todo_write 同语义）；空列表 = 清空。"""
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        items = (body or {}).get("items")
        if not chat_key or not isinstance(items, list):
            return ({"error": "chat_key and items required"}, 400)
        todos = await self._todo_store().replace(chat_key, [str(i) for i in items])
        return {"ok": True, "todos": todos}

    async def todo_update(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        todo_id = str((body or {}).get("id") or "")
        status = str((body or {}).get("status") or "")
        if not chat_key or not todo_id:
            return ({"error": "chat_key and id required"}, 400)
        todo = await self._todo_store().update(chat_key, todo_id, status=status)
        if todo is None:
            return ({"error": "todo not found"}, 404)
        return {"ok": True, "todo": todo}

    async def todo_delete(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        todo_id = str((body or {}).get("id") or "")
        if not chat_key or not todo_id:
            return ({"error": "chat_key and id required"}, 400)
        if not await self._todo_store().remove(chat_key, todo_id):
            return ({"error": "todo not found"}, 404)
        return {"ok": True}

    async def todo_add(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        content = str((body or {}).get("content") or "")
        if not chat_key or not content.strip():
            return ({"error": "chat_key and content required"}, 400)
        todo = await self._todo_store().add(chat_key, content)
        if todo is None:
            return ({"error": "todo rejected"}, 400)
        return {"ok": True, "todo": todo}

    async def sessions_reset(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        await self.main.sessions.reset(chat_key)
        return {"ok": True}

    async def session_flags(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        pinned = (body or {}).get("pinned")
        archived = (body or {}).get("archived")
        await self.main.sessions.set_flags(
            chat_key,
            pinned=None if pinned is None else bool(pinned),
            archived=None if archived is None else bool(archived),
        )
        return {"ok": True}

    async def takeover_say(self, request):
        """人工接管发言：以 bot 身份把文本直发平台会话，并写入上下文。

        与普通面板发送的区别：不进 AI 管线（AI 不响应、不开回合），
        但以 assistant 身份落库——AI 下一轮知道"自己"说过这句话。
        会话级开关（session_settings.manual）开启后前端发送走这里。
        """
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        text = str((body or {}).get("text") or "").strip()
        if not chat_key or not text:
            return ({"error": "chat_key/text required"}, 400)
        platform, detail_type, target_id = parse_chat_key(strip_account(strip_isolation(chat_key)))
        if not platform or platform == "dashboard":
            return ({"error": "not a platform session"}, 400)
        try:
            await self.main.delivery.send_segments(
                platform, detail_type, target_id, [(0.0, text)], chat_key=chat_key,
            )
        except Exception as e:
            return ({"error": f"{type(e).__name__}: {e}"}, 502)
        await self.main.sessions.append(chat_key, "assistant", text)
        await self.main.audit("takeover_say", {"chat_key": chat_key, "chars": len(text)})
        return {"ok": True}

    async def session_settings(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        ui = (body or {}).get("settings")
        if not isinstance(ui, dict):
            return ({"error": "settings object required"}, 400)
        saved = await self.main.sessions.set_ui(chat_key, {k: str(ui[k]) for k in ("density", "model", "effort", "trigger_mode") if ui.get(k) is not None})
        members = ui.get("members")
        if isinstance(members, list):
            saved["members"] = await self.main.sessions.set_members(chat_key, members)
# 隐私开关：关闭监听后本群消息不进入旁听/插话/回执事件
        if "listen_off" in ui:
            await self.main.sessions.set_flags(chat_key, {"listen_off": bool(ui["listen_off"])})
            saved["listen_off"] = bool(ui["listen_off"])
# 人工接管：面板发送以 bot 身份直发平台并写入上下文（AI 不响应该条，见 takeover_say）
        if "manual" in ui:
            await self.main.sessions.set_flags(chat_key, {"manual": bool(ui["manual"])})
            saved["manual"] = bool(ui["manual"])
        await self.main.audit("session_settings", {"chat_key": chat_key, "keys": sorted(ui.keys())})
        return {"ok": True, "ui": saved}

    async def session_policy(self, request):
        """会话治理策略（muted/low_token/priority/session_budget）：只传要改的键，返回更新后的完整策略。

        与 /qvq mute|policy|lowtoken 同一存储（conversation/policy），双入口单事实源。
        """
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        updates = {k: body[k] for k in ("muted", "low_token", "priority", "session_budget", "full_access") if k in body}
        policy = await set_policy(self.sdk, chat_key, **updates)
        if "full_access" in updates:
            await self.main.audit("session_full_access", {"chat_key": chat_key, "value": bool(policy.get("full_access"))})
# 面板改策略与聊天命令同源，审计留痕（detail 记录本次变更的键值）
        await self.main.audit("session_policy", {"chat_key": chat_key, **updates})
        return {"ok": True, "policy": policy}

    async def session_rename(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        name = str((body or {}).get("name") or "").strip()[:60]
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        await self.main.sessions.set_name(chat_key, name)
        return {"ok": True, "name": name}

    async def session_regenerate(self, request):
        """F2 重新生成：弹出末轮交换并返回 user 文本，前端再走正常发送管线。"""
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        if not chat_key:
            return ({"error": "chat_key required"}, 400)
        if self._live.busy(chat_key):
            return ({"error": "session busy"}, 409)
        text = str(await self.main.sessions.pop_last_exchange(chat_key) or "")
        if not text:
            return ({"error": "nothing to regenerate"}, 409)
        return {"ok": True, "text": text}

    async def session_routes(self, request):
        body = await request.json()
        target = str((body or {}).get("target") or "").strip()
        if not target:
            return ({"error": "target required"}, 400)
        sources = (body or {}).get("sources")
        if isinstance(sources, list):
            routes = {k: v for k, v in (await self.main.sessions.routes()).items() if v != target}
            for src in sources:
                src = str(src).strip()
                if src and src != target:
                    routes[src] = target
            await self.main.sessions.save_routes(routes)
            return {"ok": True, "sources": sorted(k for k, v in routes.items() if v == target)}
        return {"sources": await self.main.sessions.routes_into(target)}

    async def _ui_defaults(self) -> dict:
        d = await self.sdk.storage.aget(UI_DEFAULTS_KEY, {})
        if not isinstance(d, dict):
            d = {}
# 全局触发规则随 defaults 下发：会话设置弹窗据此隐藏"更松"的档位（会话只能收紧）
        d = dict(d)
        d.setdefault("trigger_mode", str(getattr(self.main.cfg, "trigger_mode", "all") or "all"))
        return d

    async def settings_defaults_get(self, request):
        return {"ui_defaults": await self._ui_defaults()}

    async def settings_defaults_set(self, request):
        body = await request.json()
        ui = (body or {}).get("settings")
        if not isinstance(ui, dict):
            return ({"error": "settings object required"}, 400)
        cur = await self._ui_defaults()
        allowed = ("density", "model", "effort")
        cur.update({k: str(ui[k]) for k in allowed if ui.get(k) is not None})
        await self.sdk.storage.aset(UI_DEFAULTS_KEY, cur)
        return {"ok": True, "ui_defaults": cur}

    async def _session_profile(self, chat_key: str) -> tuple[str, dict]:
        """会话最近发言者（platform:uid）与其画像；无发言者/画像返回 ("", 空结构)。"""
        try:
            contexts = await self.main.sessions.get_contexts(chat_key)
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
        return (user_key, await profile.get(user_key))

    async def profile_edit(self, request):
        """画像纠错：整段替换 traits/preferences/facts 之一（前端逐条编辑后保存）。"""
        body = await request.json()
        user_key = str((body or {}).get("user_key") or "")
        section = str((body or {}).get("section") or "")
        items = (body or {}).get("items")
        if not user_key or section not in ("traits", "preferences", "facts") or not isinstance(items, list):
            return ({"error": "user_key/section/items required"}, 400)
        profile = getattr(self.main.conversations, "profile", None)
        if profile is None:
            return ({"error": "profile store unavailable"}, 500)
        data = await profile.get(user_key)
        texts = [profile._clean_item(x) for x in items]
        texts = [x for x in texts if x]
        data[section] = [{"text": x, "ts": utils.now_ts()} for x in texts]
        await profile._save(user_key, data)
        await self.main.audit("profile_edit", {"user_key": user_key, "section": section, "count": len(texts)})
        return {"ok": True, "profile": data}

    async def memory_get(self, request):
        chat_key = self._query(request, "chat_key")
        if not chat_key:
# 无会话上下文：附最近活跃会话的画像（记忆页"用户画像"卡数据源）
            profile_user, profile = "", {"traits": [], "preferences": [], "facts": [], "updated": 0.0}
            sessions = await self.main.sessions.list_sessions()
            if sessions:
                profile_user, profile = await self._session_profile(str(sessions[0].get("chat_key") or ""))
            return {"scopes": await self.main.memory.list_scopes(), "entries": [], "profile_user": profile_user, "profile": profile}
        profile_user, profile = await self._session_profile(chat_key)
        return {"scopes": [], "entries": await self.main.memory.entries(chat_key), "profile_user": profile_user, "profile": profile}

    async def profile_clear(self, request):
        body = await request.json()
        user_key = str((body or {}).get("user_key") or "").strip()
        if not user_key:
            return ({"error": "user_key required"}, 400)
        profile = getattr(self.main.conversations, "profile", None)
        if profile is None:
            return ({"error": "profile store unavailable"}, 500)
        return {"ok": True, "user_key": user_key, "removed": await profile.clear(user_key)}

    async def memory_delete(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        query = str((body or {}).get("query") or "")
        content = (body or {}).get("content")
        if content is not None:
            removed = 1 if await self.main.memory.remove(chat_key, str(content)) else 0
        elif query:
            removed = await self.main.memory.forget(chat_key, query)
        else:
            removed = await self.main.memory.clear(chat_key)
        await self.main.audit("memory_delete", {"chat_key": chat_key})
        return {"ok": True, "removed": removed}

# ===== 会话分享 =====

    async def _shares(self) -> dict:
        shares = await self.sdk.storage.aget(SHARES_KEY, {})
        return shares if isinstance(shares, dict) else {}

    async def _share_token(self, token: str) -> dict | None:
        share = (await self._shares()).get(token)
        if not isinstance(share, dict) or not share.get("enabled", True):
            return None
        expires = float(share.get("expires", 0) or 0)
        if expires and utils.now_ts() > expires:
            return None
        return share

    async def _share_contexts(self, share: dict) -> list:

        contexts = await self.main.sessions.get_contexts(str(share.get("chat_key") or ""))
        budget = int(share.get("max_tokens", 4000) or 4000) * 2
        picked: list = []
        used = 0
        for message in reversed(contexts):
            if not isinstance(message, dict):
                continue
            size = len(utils.content_text(message.get("content")))
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
# 续聊配额：rounds=0 只读分享（默认）；>0 允许访问者继续对话的轮数
        try:
            rounds = min(200, max(0, int((body or {}).get("rounds", 0))))
        except (TypeError, ValueError):
            rounds = 0
        try:
            chat_tokens = min(500_000, max(500, int((body or {}).get("chat_tokens", 20000))))
        except (TypeError, ValueError):
            chat_tokens = 20000
        token = _secrets.token_urlsafe(18)
        created: dict = {}

        def _add(shares) -> dict:
            if not isinstance(shares, dict):
                shares = {}
            shares[token] = {
                "chat_key": chat_key,
                "created": utils.now_ts(),
                "expires": utils.now_ts() + hours * 3600,
                "max_tokens": max_tokens,
                "rounds": rounds,
                "chat_tokens": chat_tokens,
                "rounds_used": 0,
                "tokens_used": 0,
                "cont": [],
                "enabled": True,
            }
            created["rec"] = shares[token]
            return shares

# 键级 RMW（并发创建/撤销分享不再互相覆盖）；异步上下文用 aupdate（同步版经桥接会阻塞丢数据）
        await utils.storage_aupdate(self.sdk, SHARES_KEY, _add, {})
        rec = created["rec"]
        return {"ok": True, "token": token, "url": f"/QvQChat/share?token={token}", "expires": rec["expires"], "max_tokens": max_tokens}

    async def session_share_revoke(self, request):
        body = await request.json()
        token = str((body or {}).get("token") or "")
        found: list = []

        def _drop(shares) -> dict:
            if not isinstance(shares, dict):
                shares = {}
            if token in shares:
                shares.pop(token)
                found.append(True)
            return shares

        await utils.storage_aupdate(self.sdk, SHARES_KEY, _drop, {})
        if found:
            return {"ok": True}
        return ({"error": "not found"}, 404)

    async def share_messages(self, request):
        token = self._query(request, "token")
        share = await self._share_token(token) if token else None
        if share is None:
            return ({"error": "invalid or expired share"}, 403)
        try:
            return await self._share_payload(share)
        except Exception as e:
            # 返回 JSON 而非框架的 HTML 500：分享页才能显示具体原因，不至于只剩"加载失败"
            self.main.logger.warning(f"share_messages failed: {e}")
            return ({"error": f"{type(e).__name__}: {e}"}, 500)

    async def _share_payload(self, share: dict) -> dict:
        contexts = await self._share_contexts(share)
        chat_key = str(share.get("chat_key") or "")
        summary = await self.main.sessions.summary_of(chat_key)
        rounds = int(share.get("rounds") or 0)
        return {
            "chat_key": share.get("chat_key"),
            "summary": summary,
            "bot_name": await self._share_bot_name(chat_key),
            "messages": contexts,
            "expires": share.get("expires"),
            "rounds": rounds,
            "rounds_left": max(0, rounds - int(share.get("rounds_used") or 0)),
            "tokens_left": max(0, int(share.get("chat_tokens") or 0) - int(share.get("tokens_used") or 0)),
            "continuation": share.get("cont") if isinstance(share.get("cont"), list) else [],
        }

    async def _share_bot_name(self, chat_key: str) -> str:
        """分享页 AI 侧显示名：分享时会话绑定的人格名；未绑定回退 "AI"。"""
        try:
            state = await self.sdk.storage.aget("QvQChat:conv:" + chat_key, None)
            persona_id = str(state.get("persona") or "") if isinstance(state, dict) else ""
            if persona_id:
                personas = await self.sdk.storage.aget("QvQChat:personas", {}) or {}
                persona = personas.get(persona_id)
                if isinstance(persona, dict):
                    return str(persona.get("name") or persona_id)
                return persona_id
        except Exception:
            pass
        return "AI"

    async def share_chat(self, request):
        """分享续聊：访问者凭 token 继续对话；纯文本、无工具、非管理员权限。"""
        body = await request.json()
        token = str((body or {}).get("token") or "")
        text = str((body or {}).get("text") or "").strip()
        share = await self._share_token(token) if token else None
        if share is None:
            return ({"error": "invalid or expired share"}, 403)
        if not text:
            return ({"error": "empty text"}, 400)
        rounds = int(share.get("rounds") or 0)
        used = int(share.get("rounds_used") or 0)
        if rounds <= 0 or used >= rounds:
            return ({"error": "rounds exhausted"}, 429)
        budget = int(share.get("chat_tokens") or 0)
        spent = int(share.get("tokens_used") or 0)
        if budget > 0 and spent >= budget:
            return ({"error": "token budget exhausted"}, 429)
# 上下文 = 分享可见消息 + 既有续聊记录 + 本轮提问；纯 pool.chat，不带任何工具
        messages: list = [{"role": "system", "content": texts.t("share_chat_system")}]
        for message in await self._share_contexts(share):
            role = str(message.get("role") or "user")
            if role not in ("user", "assistant"):
                continue
            messages.append({"role": role, "content": self._share_plain_text(message.get("content"))})
        for message in share.get("cont") or []:
            if isinstance(message, dict) and message.get("role") in ("user", "assistant"):
                messages.append({"role": str(message["role"]), "content": str(message.get("content") or "")})
        messages.append({"role": "user", "content": text})
        try:
            response = await self.main.pool.chat(
                ChatRequest(messages=messages, max_tokens=1000, temperature=0.7)
            )
        except Exception as e:
            return ({"error": str(e)}, 502)
        reply = (response.content or "").strip() or texts.t("no_reply_content")
        cost = int(response.usage.get("total_tokens", 0) or 0)

        def _apply(shares) -> dict:
            if not isinstance(shares, dict):
                shares = {}
            record = shares.get(token)
            if not isinstance(record, dict):
                record = dict(share)
            cont = record.get("cont") if isinstance(record.get("cont"), list) else []
            record["cont"] = (cont + [{"role": "user", "content": text}, {"role": "assistant", "content": reply}])[-40:]
            record["rounds_used"] = int(record.get("rounds_used") or 0) + 1
            record["tokens_used"] = int(record.get("tokens_used") or 0) + cost
            shares[token] = record
            return shares

# 键级 RMW：多个访问者同时续聊，配额计数与续聊记录不再互相覆盖
        await utils.storage_aupdate(self.sdk, SHARES_KEY, _apply, {})
        return {
            "ok": True,
            "reply": reply,
            "rounds_left": max(0, rounds - share["rounds_used"]),
            "tokens_left": max(0, budget - share["tokens_used"]),
        }

    @staticmethod
    def _share_plain_text(content) -> str:
        text = utils.content_text(content)
        return text.strip() if isinstance(content, list) else text

    async def share_page(self, request):
        from starlette.responses import HTMLResponse

        token = request.query_params.get("token") if request.query_params else ""
        html = (TEMPLATES / "share.html").read_text(encoding="utf-8")
        from starlette.responses import HTMLResponse as _H

        return _H(html.replace("__TOKEN__", token), headers={"Cache-Control": "no-store"})
