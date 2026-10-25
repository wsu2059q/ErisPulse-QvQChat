"""消息入口域（拆分自 Main.py）：触发判定 / 限频 / 聚合 / 排队 / 冷启动回填。

锁语义：``_flush_pending`` 持 per-chat 锁执行 ``_process_locked``，
与 ``Main.run_prompt`` / ``Main.run_dashboard_chat`` 的 prepare→finalize 段互斥，
防定时任务与聊天并发交错写上下文；这些路径互不嵌套（工具/子代理用独立 chat_key）。
"""
from __future__ import annotations

import asyncio
import base64
import mimetypes
import random
import time
from pathlib import Path

from .. import texts, utils
from ..agent.tools import ToolContext
from ..conversation.service import DASHBOARD_PLATFORM, make_chat_key, parse_chat_key, strip_isolation
from ..dashboard.live import bind as live_bind
from ..conversation.delivery import strip_output_tag
from ..engine.base import ChatRequest, TaskSpec
from .recovery import INFLIGHT_KEY_PREFIX, RecoveryMixin

CONFIRM_WORDS = {"确认", "確認", "确定", "確定", "是", "confirm", "yes", "y", "ok"}

# 限频滑窗字典容量上限（群聊×用户数远达不到，防极端场景只增不减）
RATE_WINDOW_CAP = 512


class InboxMixin(RecoveryMixin):
    """Main 的消息入口 mixin（组合 RecoveryMixin：实例重启恢复方法随本链挂到 Main）。
    依赖宿主提供 self.sdk / self.cfg / self.logger /
    self.sessions / self.pool / self.runner / self.delivery / self.takeover /
    self._pending / self._waiting / self._chat_locks / self._rate_window /
    self._rate_notice_shown / self.spawn / self.is_admin / self._chat_confirmer 等。"""

    @staticmethod
    def _to_model_image(url: str, max_bytes: int = 5 * 1024 * 1024) -> str:
        if not url or url.startswith(("http://", "https://", "data:")):
            return url
        raw = url[7:] if url.startswith("file://") else url
        try:
            path = Path(raw).expanduser()
            if not path.is_file() or path.stat().st_size > max_bytes:
                return ""
            mime = mimetypes.guess_type(str(path))[0] or "image/png"
            data = base64.b64encode(path.read_bytes()).decode()
            return f"data:{mime};base64,{data}"
        except Exception:
# 本地图片转 base64 失败即放弃该图（降级语义：返回空串由调用方过滤）
            return ""

    @staticmethod
    def _extract_images(event) -> list[str]:
        urls: list[str] = []
        try:
            for segment in event.get_message() or []:
                if not isinstance(segment, dict) or segment.get("type") != "image":
                    continue
                data = segment.get("data") or {}
                url = str(data.get("url") or data.get("file") or "")
                if url.startswith(("http://", "https://", "file://", "base64://")):
                    urls.append(url)
        except Exception:
            urls = []
        return urls[:3]

    def _chat_key_of(self, event) -> str:
        platform = event.get_platform() or ""
        if event.is_group_message():
            gid = str(event.get_group_id() or "")
            if getattr(self.cfg, "group_isolation", False):
                uid = str(event.get_user_id() or "")
                if uid:
                    return make_chat_key(platform, "group", f"{gid}:u{uid}")
            return make_chat_key(platform, "group", gid)
        return make_chat_key(platform, "private", str(event.get_user_id() or ""))

    def _chat_ctx(self, event, chat_key: str, origin: str = "chat") -> ToolContext:
        platform, detail_type, target_id = parse_chat_key(strip_isolation(chat_key))
        session_key = ""
        try:
            session_key = self.sdk.interaction.make_key(event)
        except Exception:
            session_key = ""
        return ToolContext(
            main=self,
            sdk=self.sdk,
            config=self.cfg,
            chat_key=chat_key,
            session_key=session_key,
            platform=platform,
            detail_type=detail_type,
            target_id=target_id,
            user_id=str(event.get_user_id() or "") if event is not None else "",
            event=event,
            origin=origin,
            confirmer=self._chat_confirmer,
        )

    def _cleanup_takeovers(self) -> None:
        now = time.time()
        for key in [k for k, v in self.takeover.items() if float(v.get("until", 0)) <= now]:
            entry = self.takeover.pop(key, None)
            lease = (entry or {}).get("lease")
            if lease is not None:
                try:
                    lease.release()
                except Exception as e:
                    self.logger.debug(f"takeover lease release failed: {e}")
# 顺带回收内存态（每条入站消息都会走到这里；同步无 await，回收安全）
# 1) 限频滑窗：窗口已空的键连同提示标记一并清掉
        for key in [
            k for k, w in self._rate_window.items()
            if not w or now - max(w) >= 60
        ]:
            self._rate_window.pop(key, None)
            self._rate_notice_shown.pop(key, None)
# 2) per-chat 锁：仅回收未持有且无等待者的锁
        for key in [k for k, lock in self._chat_locks.items() if not lock.locked()]:
            self._chat_locks.pop(key, None)

    def _rate_allow(self, chat_key: str, sender_id: str, event) -> bool:
        """群聊 per-user 滑动窗口限频：超限静默丢弃（每窗口至多提示一次），管理员豁免。"""
        limit = int(getattr(self.cfg, "user_rate_limit", 0) or 0)
        if limit <= 0 or not chat_key or ":group:" not in chat_key or not sender_id:
            return True
        if self.is_admin(sender_id, "chat", event.get_platform() or ""):
            return True
        now = time.time()
        key = f"rate:{chat_key}:{sender_id}"
        window = [t for t in self._rate_window.get(key, []) if now - t < 60]
        if len(window) >= limit:
            if not getattr(self, "_rate_notice_shown", {}).get(key):
                self._rate_notice_shown = getattr(self, "_rate_notice_shown", {})
                self._rate_notice_shown[key] = True
                notice_event = event
                self.spawn(self._rate_notice(notice_event))
            return False
        window.append(now)
        self._rate_window[key] = window
        if now - max(window[:-1], default=now) > 120:
            self._rate_notice_shown.pop(key, None)
# 容量上限，超出时优先淘汰已过期键，仍超则按插入序淘汰最旧键
        if len(self._rate_window) > RATE_WINDOW_CAP:
            for stale in [
                k for k, w in self._rate_window.items()
                if not w or now - max(w) >= 60
            ]:
                if len(self._rate_window) <= RATE_WINDOW_CAP:
                    break
                self._rate_window.pop(stale, None)
                self._rate_notice_shown.pop(stale, None)
            while len(self._rate_window) > RATE_WINDOW_CAP:
                stale = next(iter(self._rate_window))
                self._rate_window.pop(stale, None)
                self._rate_notice_shown.pop(stale, None)
        return True

    async def _rate_notice(self, event) -> None:
        try:
            await event.reply(texts.t("rate_limited"))
        except Exception as e:
            self.logger.debug(f"rate limit notice reply failed: {e}")

    def _should_trigger(self, event, chat_key: str, text: str) -> bool:
        if chat_key in self.takeover:
            return True
        if event.is_private_message():
            return bool(getattr(self.cfg, "reply_private", True))
        if event.is_group_message():
            if getattr(self.cfg, "reply_at", True) and event.is_at_message():
                return True
            for prefix in getattr(self.cfg, "wake_prefixes", []) or []:
                if prefix and text.startswith(prefix):
                    return True
        return False

    async def _on_message(self, event) -> None:
        try:
            if event.get("replayed"):
                return
            text = (event.get_alt_message() or "").strip()
            if event.is_command():
                return
            for prefix in getattr(self.cfg, "command_prefixes", []) or []:
                if prefix and text.startswith(prefix):
                    return
            self._cleanup_takeovers()
            chat_key = self._chat_key_of(event)
            routed = self.sessions.resolve_route(chat_key)
            if routed:
                chat_key = routed
#  扩展点 A：qvq.observe 旁听通道——命令过滤后、触发判定前广播纯数据载荷
# （含未触发回复的消息，插件借此观察全部群聊；异常吞掉不打断主流程）
            try:
                is_group = event.is_group_message()
                await self.sdk.lifecycle.emit(
                    "qvq.observe",
                    {
                        "chat_key": chat_key,
                        "platform": event.get_platform() or "",
                        "detail_type": "group" if is_group else "private",
                        "group_id": str(event.get_group_id() or "") if is_group else "",
                        "sender_id": str(event.get_user_id() or ""),
                        "sender_name": self._sender_name(event),
                        "text": text,
                        "is_group": is_group,
                        "at_bot": bool(event.is_at_message()),
                        "reply_to_bot": False,
                        "is_command_prefix": False,
                        "images": self._extract_images(event),
                        "ts": time.time(),
                    },
                )
            except Exception as e:
                self.logger.debug(f"emit qvq.observe failed: {e}")
            if not self._should_trigger(event, chat_key, text):
#  扩展点 B：未被 @/前缀命中时问询参与决策提供者（默认关闭），
# speak 则过输出预算后以 origin="plugin" 进入聚合回复，不消耗发送者限频
                manager = getattr(self, "participation", None)
                if (
                    manager is not None
                    and bool(getattr(self.cfg, "participation_enabled", False))
                    and event.is_group_message()
                    and manager.chat_allowed(chat_key)
                ):
                    decision = await manager.decide(chat_key, event, text)
                    if isinstance(decision, dict):
                        await self._interject(manager, event, chat_key, text, decision)
                return
            if event.is_group_message() and not self.sessions.member_allowed(
                chat_key, str(event.get_user_id() or ""), event.get_platform() or ""
            ):
                return
            event.done()
            if not self._rate_allow(chat_key, str(event.get_user_id() or ""), event):
                return
            images = self._extract_images(event)
            self._batch_message(event, chat_key, text, images)
        except Exception as e:
            self.logger.warning(f"on_message failed: {e}")

    async def _interject(self, manager, event, chat_key: str, text: str, decision: dict) -> None:
        """参与决策 speak 后的插话落地：成员准入按会话整体判断 → 输出预算 → 聚合入队。

        预算/准入拒绝不发消息，仅记决策观测（qvq.participation 事件 + 环形日志）。
        """
        budget_ok, budget_reason = True, ""
        if decision.get("speak"):
            sender_id = str(event.get_user_id() or "")
# 成员准入（按会话整体）：白名单非 * 时仅名单内发送者可作为插话由头
            if not self.sessions.member_allowed(chat_key, sender_id, event.get_platform() or ""):
                budget_ok, budget_reason = False, texts.t("participate_member_denied")
            else:
                budget_ok, budget_reason = manager.budget.allow(chat_key, "interject")
                if budget_ok:
                    manager.budget.record(chat_key, "interject")
                    event.done()# 插话由头不消耗发送者 _rate_allow 限额
                    self._batch_message(
                        event, chat_key, text, self._extract_images(event), origin="plugin"
                    )
        entry = {
            "kind": "interject",
            "chat_key": chat_key,
            "decision": "speak" if decision.get("speak") else "silent",
            "reason": budget_reason or str(decision.get("reason") or ""),
            "provider": str(decision.get("provider") or ""),
            "providers_queried": list(decision.get("providers_queried") or []),
            "score": decision.get("score"),
            "budget_ok": budget_ok,
            "ts": time.time(),
        }
        manager.log_decision(entry)
        try:
            await self.sdk.lifecycle.emit(
                "qvq.participation",
                {key: value for key, value in entry.items() if key != "kind"},
            )
        except Exception as e:
            self.logger.debug(f"emit qvq.participation failed: {e}")

    @staticmethod
    def _sender_name(event) -> str:
        try:
            name = event.get_user_nickname()
            if name:
                return str(name)
        except Exception:
            pass
        try:
            sender = event.get_sender()
            if isinstance(sender, dict):
                return str(sender.get("nickname") or sender.get("card") or "")
        except Exception:
            pass
        return ""

    async def _resolve_group_name(self, event, chat_key: str, group_id: str) -> str:
        if not group_id:
            return ""
        name = str(event.get("group_name") or "")
        if name:
            self.sessions.set_group_name(chat_key, name)
            return name
        cached = self.sessions.group_name_of(chat_key)
        if cached:
            return cached
        adapter = self.sdk.adapter.get(event.get_platform() or "")
        if adapter is None:
            return ""
        try:
            info = await adapter.call_api("get_group_info", group_id=group_id)
            name = str((info or {}).get("group_name") or "")
        except Exception as e:
            self.logger.debug(f"get_group_info failed: {e}")
            name = ""
        if name:
            self.sessions.set_group_name(chat_key, name)
        return name

    def _enqueue_waiting(self, chat_key: str, event, items: list) -> None:
        queue = self._waiting.setdefault(chat_key, [])
        queue.append((event, items))
        self.logger.info(f"chat busy, message queued ({chat_key}, {len(queue)} waiting)")
        self.spawn(self._announce_queued(chat_key, event, items))

    async def _announce_queued(self, chat_key: str, event, items: list) -> None:
        incoming = " ".join(str(i.get("text") or "") for i in items if i.get("text"))
        registry = getattr(self, "live_registry", None)
        current = ""
        live = registry.get(chat_key) if registry else None
        if live is not None:
            current = str(live.text or "")[-300:]
        prompt = (
            "机器人正在执行一个未完成的长任务。任务最近的输出摘要是："
            + (current or "（尚无输出）")
            + "。此时收到新消息：" + incoming[:150] + "。"
            "请以机器人自己的口吻输出一句话：简单说明当前在做什么，并告诉对方这条新消息已排入队列、"
            "任务完成后就会处理。只输出这一句话，不要调用任何工具。"
        )
        reply = ""
        try:
# A2: 排队播报迁 TaskSpec 分派（kind=announce，成本偏好 cheap），池无 dispatch 时回退 pool.chat
            request = ChatRequest(messages=[{"role": "user", "content": prompt}], max_tokens=80, temperature=0.7)
            dispatch = getattr(self.pool, "dispatch", None)
            if callable(dispatch):
                response = await dispatch(TaskSpec(kind="announce", prefer="cheap"), request)
            else:
                response = await self.pool.chat(request)
            reply = (response.content or "").strip()
        except Exception as e:
            self.logger.warning(f"queue announce failed: {e}")
        if not reply:
            return
        try:
            await event.reply(reply)
        except Exception as e:
            self.logger.warning(f"queue announce reply failed: {e}")

    def _drain_waiting(self, chat_key: str) -> None:
        queue = self._waiting.pop(chat_key, None)
        if not queue:
            return
        for event, items in queue:
            self._batch_message(event, chat_key, items)

    def _lock_for(self, chat_key: str) -> asyncio.Lock:
        lock = self._chat_locks.get(chat_key)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_key] = lock
        return lock

    def _batch_message(self, event, chat_key: str, text: str, images: list,
                       origin: str = "chat") -> None:
        entry = self._pending.setdefault(chat_key, {"items": [], "event": event, "timer": None})
# origin（chat/plugin）随聚合条目传递，进 ToolContext 记账可观测
        entry.setdefault("origin", origin)
        entry["items"].append(
            {
                "text": text,
                "images": images,
                "sender_id": str(event.get_user_id() or ""),
                "sender_name": self._sender_name(event),
            }
        )
        entry["event"] = event
        if entry["timer"] is None:
            window = float(getattr(self.cfg, "aggregate_window", 5.0) or 0)
            if window <= 0:
                entry["timer"] = self.spawn(self._flush_pending(chat_key))
            else:
                entry["timer"] = self.spawn(self._flush_later(chat_key, window))

    async def _flush_later(self, chat_key: str, window: float) -> None:
        await asyncio.sleep(window)
        await self._flush_pending(chat_key)

    async def _flush_pending(self, chat_key: str) -> None:
        entry = self._pending.pop(chat_key, None)
        if not entry:
            return
# per-chat 锁真正生效——聚合触发与定时任务/面板并发互斥，防止交错写上下文
        async with self._lock_for(chat_key):
            await self._process_locked(
                entry["event"], entry["items"], chat_key, entry.get("origin", "chat")
            )

    async def _process_locked(self, event, items: list, chat_key: str, origin: str = "chat") -> None:
        try:
            ctx = self._chat_ctx(event, chat_key, origin)
            is_group = event.is_group_message()
            sender_id = str(event.get_user_id() or "")
            sender_name = self._sender_name(event)
            group_id = str(event.get_group_id() or "") if is_group else ""
            if getattr(self.cfg, "owner_only", False) and not self.is_admin(sender_id, "chat", event.get_platform() or ""):
                await event.reply(texts.t("owner_only_msg"))
                return
            scene = ""
            if is_group:
                group_name = await self._resolve_group_name(event, chat_key, group_id)
                if group_name:
                    scene = texts.t("scene_group", name=group_name, id=group_id)
                elif group_id:
                    scene = texts.t("scene_group_noid", id=group_id)
                scene += texts.t("scene_speaker_note")
# 发言者认知：明确"当前说话的人"，防止把历史对话者误认成当前发言者
                scene += texts.t("scene_group_attribution", name=sender_name or sender_id, id=sender_id)
                if getattr(self.cfg, "group_isolation", False):
                    scene += texts.t("scene_isolation_note")
            else:
                if sender_name:
                    scene = texts.t("scene_private", name=sender_name, id=sender_id)
            combined_text = "\n".join(str(i.get("text") or "") for i in items if i.get("text"))
            try:
                await self.sdk.lifecycle.emit(
                    "qvq.message",
                    {
                        "chat_key": chat_key,
                        "platform": event.get_platform() or "",
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "text": combined_text,
                        "is_group": is_group,
                        "merged": len(items) > 1,
                    },
                )
            except Exception as e:
                self.logger.debug(f"emit qvq.message failed: {e}")
            labeled_parts = []
            all_images: list = []
            for item in items:
                item_text = str(item.get("text") or "")
                if item_text:
                    labeled_parts.append(
                        self.sessions.label_incoming(
                            item_text,
                            sender_id=item["sender_id"] if is_group else "",
                            sender_name=item["sender_name"] if is_group else "",
                        )
                    )
                for image in item.get("images") or []:
                    if len(all_images) < 3:
                        all_images.append(image)
            labeled = "\n".join(labeled_parts)
            images = [
                converted
                for raw in all_images
                for converted in [self._to_model_image(raw)]
                if converted
            ]
            limit = int(getattr(self.cfg, "daily_token_limit", 0) or 0)
            if limit:
                used_today = int(self._usage_today().get("tokens", 0) or 0)
                if used_today >= limit and not self.is_admin(sender_id, "chat", event.get_platform() or ""):
                    await event.reply(texts.t("daily_limit_reached", used=used_today, limit=limit))
                    return
            interrupted_note = ""
            live = None
            registry = getattr(self, "live_registry", None)
            if registry is not None:
                old_live = registry.get(chat_key)
                if old_live and old_live.status == "running" and old_live.text.strip():
# queue：当前任务后台继续，新消息排到任务完成后处理；interrupt：取消旧任务
                    if str(getattr(self.cfg, "interrupt_mode", "queue")) == "queue":
                        self._enqueue_waiting(chat_key, event, items)
                        return
                    old_live.cancel()
                    interrupted_note = texts.t(
                        "interrupted_note",
                        content=utils.truncate(old_live.text.strip(), 500),
                    )
                live = registry.start(chat_key)
                live.task = asyncio.current_task()
                on_delta, on_reset, on_tool_event, on_reasoning = live_bind(live)
            else:
                on_delta = on_reset = on_tool_event = on_reasoning = None
            prepared = await self.sessions.prepare(
                chat_key,
                labeled,
                images=images,
                scene=scene,
                seed_provider=lambda: self._seed_history(event),
                cross_user_id=("" if is_group else sender_id),
                sender_id=sender_id,
                profile_user=(f"{event.get_platform()}:{sender_id}" if sender_id else ""),
            )
            system = prepared["system"]
            contexts = prepared["contexts"]
            user_msg = prepared["user_msg"]
            persona = prepared["persona"]
# 首次接触且未发过开场白 → await 先发开场白再进 runner（时序保证）
            await self._maybe_send_opening(event, chat_key, prepared, persona)
            if interrupted_note:
                contexts.append({"role": "user", "content": interrupted_note})
            async def on_tool_round(calls):
                if getattr(self.cfg, "tool_notice_mode", "brief") != "all":
                    return
                labels = [
                    f"{call['name']}({call['arguments']})" if call["arguments"] else call["name"]
                    for call in calls[:3]
                ]
                suffix = " …" if len(calls) > 3 else ""
                await event.reply(texts.t("processing_notice", tools="、".join(labels) + suffix))

            async def on_intermediate(speech):
# 边做边说：reply_narrate 开启时独立生效，不再依赖 tool_notice_mode=all
                if getattr(self.cfg, "tool_notice_mode", "brief") != "all" and not getattr(
                    self.cfg, "reply_narrate", False
                ):
                    return
                text = utils.truncate(str(speech).strip(), 1200)
                if text:
                    await event.reply(text)

# 悬空回复标记：生成开始落盘（记录将送入模型的 labeled 文本），实例崩溃重启后
# 据此重跑该轮；完成/异常/取消均在 finally 清除，保证正常路径无残留
            self.sdk.storage.set(
                INFLIGHT_KEY_PREFIX + chat_key,
                {"text": labeled, "origin": origin, "ts": time.time()},
            )
            try:
                try:
                    result = await self.runner.run(
                        system=system,
                        messages=contexts + [user_msg],
                        ctx=ctx,
                        persona_tools=persona.get("tools"),
                        on_tool_round=on_tool_round,
                        on_intermediate=on_intermediate,
                        on_delta=on_delta,
                        on_reset=on_reset,
                        on_tool_event=on_tool_event,
                        on_reasoning=on_reasoning,
                    )
                except asyncio.CancelledError:
                    if live is not None:
                        partial, partial_trace, partial_rounds = live.partial_record()
                        if partial:
                            self.sessions.append(chat_key, "assistant", partial, trace=partial_trace, rounds=partial_rounds)
                        live.reply = partial or None
                        live.status = "done"
                        live.publish("done", {"reply": partial, "session": chat_key})
                        live.publish("end", {"status": live.status})
                    raise
                finally:
                    if live is not None:
                        if live.status == "running":
                            live.status = "done"
                        live.publish("end", {"status": live.status})
                if live is not None:
                    live.reply = result.text.strip()
                    live.status = "done"
                    live.publish("done", {"reply": live.reply, "session": chat_key})
                reply, force_forward = strip_output_tag(result.text.strip())
                reply = reply or texts.t("no_reply_content")
                self.sessions.finalize(chat_key, reply, trace=result.tool_trace, rounds=getattr(result, "rounds", None), usage=result.usage, model=getattr(result, "model", ""))
                try:
                    await self.sdk.lifecycle.emit(
                        "qvq.replied",
                        {"chat_key": chat_key, "reply": reply, "tools": len(result.tool_trace)},
                    )
                except Exception as e:
                    self.logger.debug(f"emit qvq.replied failed: {e}")
                await self.delivery.deliver_reply(event, reply, result.tool_trace, force=force_forward, rounds=getattr(result, "rounds", None))
                self._drain_waiting(chat_key)
            finally:
                self.sdk.storage.delete(INFLIGHT_KEY_PREFIX + chat_key)
        except Exception as e:
            self.logger.warning(f"process failed: {e}")
            try:
                await event.reply(texts.t("run_failed", error=utils.truncate(str(e), 200)))
            except Exception as inner:
                self.logger.debug(f"run_failed notice reply failed: {inner}")

    async def _maybe_send_opening(self, event, chat_key: str, prepared: dict, persona: dict) -> None:
        """首次接触开场白：prepare 标记 first_contact 且未发过 → 随机一条 await 直发。

        防重靠会话 state 的 opening_sent 标记；Dashboard 平台不触发；
        seed 回填发生时默认不触发（opening_on_seed=True 才发）；
        发送成功后停 0.8s 再返回，让主回复与开场白保持拟人间隔。
        """
        try:
            if not prepared.get("first_contact"):
                return
            if not getattr(self.cfg, "opening_enabled", True):
                return
            if prepared.get("seeded") and not getattr(self.cfg, "opening_on_seed", False):
                return
            if str(event.get_platform() or "") == DASHBOARD_PLATFORM:
                return
            if self.sessions.get_flag(chat_key, "opening_sent"):
                return
            opening = [str(o).strip() for o in (persona.get("opening") or []) if str(o or "").strip()]
            if not opening:
                return
            text = utils.truncate(
                str(random.choice(opening)),
                max(1, int(getattr(self.cfg, "opening_max_len", 200) or 200)),
            )
            await event.reply(text)
            self.sessions.set_flags(chat_key, {"opening_sent": True})
            await asyncio.sleep(0.8)
        except Exception as e:
            self.logger.debug(f"opening send failed: {e}")

    async def _seed_history(self, event) -> list:
        """冷启动回填：优先取带 sender 的收件箱记录并逐条标注发言者，避免历史对话者被误认成当前发言者。"""
        limit = int(getattr(self.cfg, "history_seed", 20) or 0)
        if limit <= 0:
            return []
        try:
            rows = self._transcript_rows(event, limit)
        except Exception as e:
            self.logger.debug(f"transcript rows fetch failed: {e}")
            rows = []
        if not rows:
# 降级：框架收件箱不可用时走 event.history（无 sender，统一标注为未记录）
            try:
                history = await event.history(limit)
            except Exception:
                return []
            rows = [
                {"role": str(e.get("role") or ""), "text": str(e.get("text") or ""), "sender": ""}
                for e in (history or [])
                if isinstance(e, dict)
            ]
        return await self._label_seed_rows(event, rows)

    def _transcript_rows(self, event, limit: int) -> list:
        """按框架收件箱会话键（群聊=群级）过滤近期记录，保留 sender 字段。"""
        transcript = getattr(self.sdk, "transcript", None)
        recent = getattr(transcript, "recent", None)
        if not callable(recent):
            return []
        platform = str(event.get_platform() or "")
        try:
            is_group = event.is_group_message()
        except Exception:
            is_group = False
        target = str(event.get_group_id() or "") if is_group else str(event.get_user_id() or "")
        if not platform or not target:
            return []
        base_key = f"{platform}:{'group' if is_group else 'private'}:{target}"
        try:
            rows = recent(7 * 24 * 3600, limit=max(500, limit * 25))
        except Exception:
            return []
        picked = [r for r in (rows or []) if isinstance(r, dict) and r.get("session_key") == base_key]
        return picked[-limit:] if len(picked) > limit else picked

    async def _label_seed_rows(self, event, rows: list) -> list:
        bot_note = texts.t("seed_bot_note")
        unknown_note = texts.t("seed_unknown_speaker")
        try:
            is_group = event.is_group_message()
        except Exception:
            is_group = False
        senders: list[str] = []
        for row in rows:
            sid = str(row.get("sender") or "")
            if row.get("role") == "user" and sid and sid not in senders:
                senders.append(sid)
        names: dict[str, str] = {}
        if is_group and senders:
            names = await self._group_nicknames(
                str(event.get_platform() or ""), str(event.get_group_id() or ""), senders[:8]
            )
        seeded: list = []
        for row in rows:
            text = str(row.get("text") or "")
            if not text:
                continue
            if row.get("role") == "bot":
                seeded.append({"role": "assistant", "content": f"[{bot_note}] {text}"})
            elif row.get("role") == "user":
                sid = str(row.get("sender") or "")
                if sid:
                    name = str(names.get(sid) or "")
                    label = f"{name}({sid})" if name else f"({sid})"
                    seeded.append({"role": "user", "content": f"{label}: {text}"})
                else:
                    seeded.append({"role": "user", "content": f"[{unknown_note}] {text}"})
            else:
                seeded.append({"role": "assistant", "content": text})
        if seeded:
            seeded[0]["content"] = texts.t("seed_history_header") + "\n" + seeded[0]["content"]
        return seeded

    async def _group_nicknames(self, platform: str, group_id: str, uids: list) -> dict:
        """uid→群昵称批量反查，storage 缓存 7 天；失败返回空（标注退化为 (uid):）。"""
        if not platform or not group_id or not uids:
            return {}
        cache_key = f"QvQChat:nick:{platform}:{group_id}"
        cache = self.sdk.storage.get(cache_key, {})
        cache = cache if isinstance(cache, dict) else {}
        now = time.time()
        names: dict[str, str] = {}
        missing: list[str] = []
        for uid in uids:
            hit = cache.get(uid)
            if isinstance(hit, dict) and hit.get("name") and now - float(hit.get("ts") or 0) < 7 * 24 * 3600:
                names[uid] = str(hit["name"])
            else:
                missing.append(uid)
        adapter = self.sdk.adapter.get(platform) if missing else None
        if adapter is not None:

            async def fetch(uid: str) -> tuple[str, str]:
                try:
                    info = await asyncio.wait_for(
                        adapter.call_api("get_group_member_info", group_id=group_id, user_id=uid), 5
                    )
                    return uid, str((info or {}).get("card") or (info or {}).get("nickname") or "")
                except Exception:
                    return uid, ""

            for uid, name in await asyncio.gather(*[fetch(uid) for uid in missing]):
                if name:
                    names[uid] = name
                    cache[uid] = {"name": name, "ts": now}
            self.sdk.storage.set(cache_key, cache)
        return names

    async def _chat_confirmer(self, ctx: ToolContext, text: str, timeout: int) -> bool:
        event = ctx.event
        if event is None:
            return False
        try:
            await event.reply(text)
            reply = await event.wait_reply(timeout=timeout)
            if reply is None:
                return False
            answer = (reply.get_alt_message() or "").strip().lower()
            return answer in CONFIRM_WORDS
        except Exception as e:
            self.logger.warning(f"confirm failed: {e}")
            return False
