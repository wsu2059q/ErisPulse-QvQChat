"""参与决策管理器（扩展点 B）：qvq_decision 约定服务的发现 / 并发问询 / 聚合。

与插件侧（如 QvQStalker）的契约：
- 发现：``sdk.module.services()`` 目录中声明 ``qvq_decision`` 的生态模块，
  探测调用 ``qvq_decision(ctx={"probe": True})`` 返回 dict 即视为提供者；
  探测失败（含 services 白名单拒绝的 ServiceNotProvidedError）静默视为无。
  生态桥 refresh() 尾部自动重发现（module.load/unload 防抖热刷新后生效）。
- 问询：并发问询全部提供者，单提供者 ``participation_provider_timeout`` 秒
（默认 2s）超时/异常视为 silent。
- 聚合：``participation_strategy``（first_speak 默认 / max_score 需
  score>=participation_score_threshold / unanimous）。

另维护两份自身观测状态（供决策 ctx 与 Dashboard）：
- 旁听窗口：订阅 ``qvq.observe``（核心在命令过滤后广播的纯数据载荷），
  每会话保留最近 10 条，作为 ctx.recent_messages；
- 最近回复：订阅 ``qvq.replied``，映射 ctx.replied_recently。
"""
from __future__ import annotations

import asyncio
import time
from collections import deque

from .. import texts, utils
from ..conversation.service import strip_isolation
from .budget import SpeechBudget

DECISION_SERVICE = "qvq_decision"
OBSERVE_EVENT = "qvq.observe"
REPLIED_EVENT = "qvq.replied"
PARTICIPATION_EVENT = "qvq.participation"

WINDOW_SIZE = 10# ctx.recent_messages 旁听条数
REPLIED_WINDOW = 600.0# replied_recently 判定窗口（秒）
PROBE_TIMEOUT = 3.0# 提供者探测超时
DECISION_LOG_SIZE = 100# 最近决策环形日志容量


class ParticipationManager:
    """依赖宿主 main 提供 sdk / cfg / logger（均 getattr 防御，支持 FakeMain）。"""

    def __init__(self, main):
        self.main = main
        self.sdk = getattr(main, "sdk", None)
        self.logger = getattr(main, "logger", None)
        self.providers: dict[str, dict] = {}
        self.budget = SpeechBudget(self.sdk, lambda: getattr(main, "cfg", None))
        self.decisions: deque = deque(maxlen=DECISION_LOG_SIZE)
        self._window: dict[str, deque] = {}
        self._last_reply: dict[str, float] = {}
        self._subscribed = False

# ==================== 生命周期 ====================

    def start(self) -> None:
        """订阅旁听/回复事件（Main.on_load 调用；重复调用幂等）。"""
        if self._subscribed:
            return
        for event, handler in ((OBSERVE_EVENT, self._on_observe), (REPLIED_EVENT, self._on_replied)):
            try:
                self.sdk.lifecycle.register(event, handler)
            except Exception as e:
                self._log("debug", f"lifecycle register {event} failed: {e}")
        self._subscribed = True

    def _log(self, level: str, message: str) -> None:
        logger = self.logger
        if logger is None:
            return
        try:
            getattr(logger, level, logger.debug)(message)
        except Exception:
            pass

# ==================== 提供者发现 ====================

    async def discover(self) -> dict:
        """扫描服务目录并探测提供者；返回 ``{module: info}``。失败静默（视为无提供者）。"""
        try:
            catalog = self.sdk.module.services() or {}
        except Exception as e:
            self._log("debug", f"services() unavailable: {e}")
            catalog = {}
        if not isinstance(catalog, dict):
            catalog = {}
        found: dict[str, dict] = {}
        for module_name in sorted(catalog):
            if module_name == "QvQChat":
                continue
            services = catalog.get(module_name)
            if not isinstance(services, list):
                continue
            entry = next(
                (s for s in services if isinstance(s, dict) and s.get("name") == DECISION_SERVICE),
                None,
            )
            if entry is None:
                continue
            info = await self._probe(module_name, str(entry.get("description") or ""))
            if info is not None:
                found[module_name] = info
        added = sorted(set(found) - set(self.providers))
        removed = sorted(set(self.providers) - set(found))
        self.providers = found
        if added or removed:
            self._log("info", texts.t(
                "participate_providers_updated",
                added=", ".join(added) or "-", removed=", ".join(removed) or "-",
            ))
        return dict(found)

    async def _probe(self, module_name: str, description: str) -> dict | None:
        """探测约定服务：传 {"probe": True}，返回 dict 即视为提供者。

        注意 services 白名单陷阱：目标模块未在 get_meta().services 声明该服务时
        sdk.module.call 抛 ServiceNotProvidedError——静默视为无提供者。
        """
        try:
            raw = await asyncio.wait_for(
                self.sdk.module.call(module_name, DECISION_SERVICE, ctx={"probe": True}),
                timeout=PROBE_TIMEOUT,
            )
        except Exception as e:
            self._log("debug", f"probe {module_name}.{DECISION_SERVICE} failed: {e}")
            return None
        if not isinstance(raw, dict):
            return None
        return {"module": module_name, "description": description}

    def providers_status(self) -> list[dict]:
        return [dict(info) for _, info in sorted(self.providers.items())]

# ==================== 决策 ====================

    async def decide(self, chat_key: str, event, text: str) -> dict | None:
        """并发问询全部提供者并聚合；无提供者返回 None。

        返回 ``{speak, reason, provider, score, providers_queried, strategy, results}``。
        """
        if not self.providers:
            return None
        cfg = getattr(self.main, "cfg", None)
        try:
            timeout = float(getattr(cfg, "participation_provider_timeout", 2.0) or 2.0)
        except (TypeError, ValueError):
            timeout = 2.0
        ctx = self._build_ctx(chat_key, event, text)
        names = sorted(self.providers)
        outcomes = await asyncio.gather(
            *(self._query(name, ctx, timeout) for name in names)
        )
        return self._aggregate([o for o in outcomes if isinstance(o, dict)], names, cfg)

    async def _query(self, module: str, ctx: dict, timeout: float) -> dict:
        try:
            raw = await asyncio.wait_for(
                self.sdk.module.call(module, DECISION_SERVICE, ctx=ctx),
                timeout=max(timeout, 0.05),
            )
        except asyncio.TimeoutError:
            return self._norm(module, None, texts.t("participate_provider_timeout", provider=module))
        except Exception as e:
            return self._norm(
                module, None,
                texts.t("participate_provider_error", provider=module, error=utils.truncate(str(e), 120)),
            )
        return self._norm(module, raw, "")

    @staticmethod
    def _norm(module: str, raw, error: str) -> dict:
        """归一化提供者返回：``{decision: speak|silent, reason, score}``。"""
        if not isinstance(raw, dict):
            if not error:
                error = texts.t("participate_provider_error", provider=module, error="invalid result")
            return {"provider": module, "decision": "silent", "reason": error, "score": 0.0}
        decision = str(raw.get("decision") or "").strip().lower()
        if decision not in ("speak", "silent"):
            decision = "silent"
        try:
            score = float(raw.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        return {
            "provider": module,
            "decision": decision,
            "reason": str(raw.get("reason") or ""),
            "score": max(0.0, min(score, 1.0)),
        }

    def _aggregate(self, results: list[dict], names: list[str], cfg) -> dict:
        strategy = str(getattr(cfg, "participation_strategy", "first_speak") or "first_speak")
        try:
            threshold = float(getattr(cfg, "participation_score_threshold", 0.6) or 0.0)
        except (TypeError, ValueError):
            threshold = 0.6
        base = {
            "speak": False,
            "reason": "",
            "provider": "",
            "score": 0.0,
            "providers_queried": list(names),
            "strategy": strategy,
            "results": results,
        }
        if not results:
            return base
        speaks = [r for r in results if r.get("decision") == "speak"]

        if strategy == "max_score":
            if not speaks:
                first = results[0]
                return {**base, "reason": first.get("reason", ""), "provider": first.get("provider", ""),
                        "score": first.get("score", 0.0)}
            best = max(speaks, key=lambda r: float(r.get("score") or 0.0))
            if float(best.get("score") or 0.0) >= threshold:
                return {**base, "speak": True, "reason": best.get("reason", ""), "provider": best.get("provider", ""),
                        "score": best.get("score", 0.0)}
            return {**base, "reason": texts.t("participate_score_below", score=best.get("score", 0.0), threshold=threshold),
                    "provider": best.get("provider", ""), "score": best.get("score", 0.0)}

        if strategy == "unanimous":
            if speaks and len(speaks) == len(results):
                best = max(results, key=lambda r: float(r.get("score") or 0.0))
                return {**base, "speak": True, "reason": best.get("reason", ""), "provider": best.get("provider", ""),
                        "score": best.get("score", 0.0)}
            first_silent = next((r for r in results if r.get("decision") != "speak"), results[0])
            return {**base, "reason": first_silent.get("reason", ""), "provider": first_silent.get("provider", ""),
                    "score": first_silent.get("score", 0.0)}

# first_speak（默认）：按稳定顺序首个 speak 胜出
        for r in results:
            if r.get("decision") == "speak":
                return {**base, "speak": True, "reason": r.get("reason", ""), "provider": r.get("provider", ""),
                        "score": r.get("score", 0.0)}
        first = results[0]
        return {**base, "reason": first.get("reason", ""), "provider": first.get("provider", ""),
                "score": first.get("score", 0.0)}

    def _build_ctx(self, chat_key: str, event, text: str) -> dict:
        """决策 ctx 载荷（热度等插件自维护，heat_hint 恒 None）。"""
        try:
            is_group = bool(event.is_group_message())
        except Exception:
            is_group = ":group:" in str(chat_key or "")
        try:
            platform = str(event.get_platform() or "")
            sender_id = str(event.get_user_id() or "")
            group_id = str(event.get_group_id() or "") if is_group else ""
        except Exception:
            platform, sender_id, group_id = "", "", ""
        recent = [dict(m) for m in (self._window.get(chat_key) or ())]
        last_reply = float(self._last_reply.get(chat_key, 0.0) or 0.0)
        now = time.time()
        return {
            "chat_key": str(chat_key or ""),
            "platform": platform,
            "detail_type": "group" if is_group else "private",
            "group_id": group_id,
            "is_group": is_group,
            "text": str(text or ""),
            "sender_id": sender_id,
            "sender_name": self._sender_name(event),
# 确定性触发（@/前缀）永远短路插件决策，到达这里的 at_bot 恒 False
            "at_bot": False,
            "recent_messages": recent,
            "heat_hint": None,
            "replied_recently": bool(last_reply and now - last_reply < REPLIED_WINDOW),
            "ts": now,
        }

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

# ==================== 群白名单 ====================

    def chat_allowed(self, chat_key: str) -> bool:
        """participation_groups / participation_groups_exclude 群过滤（空名单=全部群）。"""
        cfg = getattr(self.main, "cfg", None)
        base = strip_isolation(str(chat_key or ""))
        gid = base.split(":group:", 1)[1] if ":group:" in base else ""
        exclude = [str(p) for p in (getattr(cfg, "participation_groups_exclude", []) or []) if str(p)]
        include = [str(p) for p in (getattr(cfg, "participation_groups", []) or []) if str(p)]

        def _hit(pattern: str) -> bool:
            return utils.match_pattern(base, [pattern]) or (bool(gid) and utils.match_pattern(gid, [pattern]))

        if any(_hit(p) for p in exclude):
            return False
        if not include:
            return True
        return any(_hit(p) for p in include)

# ==================== 观测 ====================

    def log_decision(self, entry: dict) -> None:
        """最近决策环形日志（内存 deque，容量 100，Dashboard 展示）。"""
        try:
            self.decisions.append(dict(entry))
        except Exception as e:
            self._log("debug", f"decision log append failed: {e}")

    def status(self) -> dict:
        cfg = getattr(self.main, "cfg", None)
        return {
            "enabled": bool(getattr(cfg, "participation_enabled", False)),
            "strategy": str(getattr(cfg, "participation_strategy", "first_speak") or "first_speak"),
            "providers": self.providers_status(),
            "budget": self.budget.status(),
            "decisions": list(self.decisions),
        }

    async def _on_observe(self, data) -> None:
        """qvq.observe 旁听入窗（先于同消息的 decide 发生；恒返回 None 不改写载荷）。"""
        try:
            if not isinstance(data, dict):
                return
            chat_key = str(data.get("chat_key") or "")
            if not chat_key:
                return
            window = self._window.get(chat_key)
            if window is None:
                window = deque(maxlen=WINDOW_SIZE)
                self._window[chat_key] = window
            window.append({
                "sender_id": str(data.get("sender_id") or ""),
                "sender_name": str(data.get("sender_name") or ""),
                "text": str(data.get("text") or ""),
                "ts": _as_float(data.get("ts"), time.time()),
            })
            if len(self._window) > 512:
                for key in list(self._window)[: len(self._window) - 256]:
                    self._window.pop(key, None)
        except Exception as e:
            self._log("debug", f"observe window append failed: {e}")
        return None

    async def _on_replied(self, data) -> None:
        """qvq.replied 回执时间（replied_recently 判定依据）；恒返回 None。"""
        try:
            if not isinstance(data, dict):
                return
            chat_key = str(data.get("chat_key") or "")
            if chat_key:
                self._last_reply[chat_key] = time.time()
                if len(self._last_reply) > 512:
                    oldest = sorted(self._last_reply.items(), key=lambda kv: kv[1])
                    for key, _ in oldest[: len(self._last_reply) - 256]:
                        self._last_reply.pop(key, None)
        except Exception as e:
            self._log("debug", f"replied mark failed: {e}")
        return None


def _as_float(value, default: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out > 0 else default
