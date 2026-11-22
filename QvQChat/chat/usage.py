"""用量记账（拆分自 Main.py）：按日 token/调用数/会话/模型维度落 storage，滚动清理。"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from .. import texts, utils

# 上次清理日标记（跨天首条记账才执行一次全扫）
USAGE_LAST_PRUNE_KEY = "QvQChat:usage:last_prune"


class UsageMixin:
    """Main 的用量记账 mixin。依赖宿主提供 self.sdk / self.cfg / self.logger。"""

    def _usage_today(self) -> dict:
        data = self.sdk.storage.get(f"QvQChat:usage:{time.strftime('%Y-%m-%d')}", {})
        return data if isinstance(data, dict) else {}

    def record_usage(self, chat_key: str, usage: dict, model: str = "", origin: str = "") -> None:
        try:
            today = time.strftime("%Y-%m-%d")
            key = f"QvQChat:usage:{today}"
            tokens = int(usage.get("total_tokens", 0) or 0)
            user_id = str(usage.get("user_id") or "")
            origin = str(origin or "chat")

            def _merge(data: dict) -> dict:
                if not isinstance(data, dict):
                    data = {}
                data["tokens"] = int(data.get("tokens", 0) or 0) + tokens
                data["calls"] = int(data.get("calls", 0) or 0) + 1
                by_chat = data.get("by_chat")
                if not isinstance(by_chat, dict):
                    by_chat = {}
                by_chat[chat_key] = int(by_chat.get(chat_key, 0) or 0) + tokens
                data["by_chat"] = by_chat
# 用户维度（user_daily_budget 配额门槛读这里）：ctx.user_id 由调用方带出
                if user_id:
                    by_user = data.get("by_user")
                    if not isinstance(by_user, dict):
                        by_user = {}
                    by_user[user_id] = int(by_user.get(user_id, 0) or 0) + tokens
                    data["by_user"] = by_user
# 来源维度（对话/面板/定时任务/主动发言/子智能体）：用量页构成条与筛选
                by_origin = data.get("by_origin")
                if not isinstance(by_origin, dict):
                    by_origin = {}
                o_entry = by_origin.get(origin)
                o_entry = {"tokens": 0, "calls": 0} if not isinstance(o_entry, dict) else o_entry
                o_entry["tokens"] = int(o_entry.get("tokens", 0) or 0) + tokens
                o_entry["calls"] = int(o_entry.get("calls", 0) or 0) + 1
                by_origin[origin] = o_entry
                data["by_origin"] = by_origin
                if model:
                    by_model = data.get("by_model")
                    if not isinstance(by_model, dict):
                        by_model = {}
                    entry = by_model.get(model)
                    entry = {"tokens": 0, "in": 0, "out": 0} if not isinstance(entry, dict) else entry
                    entry["tokens"] = int(entry.get("tokens", 0) or 0) + tokens
                    entry["in"] = int(entry.get("in", 0) or 0) + int(usage.get("prompt_tokens", 0) or 0)
                    entry["out"] = int(entry.get("out", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)
                    by_model[model] = entry
                    data["by_model"] = by_model
                return data

# 键级 RMW（并发回合同时记账不再互相覆盖少记）
            data = utils.storage_update(self.sdk, key, _merge, {})
            self._append_flow(today, chat_key, origin, model, usage)
            self._prune_usage(today)
            self._usage_warn_check(chat_key, int(data.get("tokens", 0) or 0), today)
        except Exception as e:
# 记账路径不允许完全静默
            self.logger.debug(f"record_usage failed: {e}")

    def _append_flow(self, today: str, chat_key: str, origin: str, model: str, usage: dict) -> None:
        """逐条调用流水（用量页明细数据源；每日截断防膨胀）。"""
        flow_key = f"QvQChat:usageflow:{today}"

        def _append(flow) -> list:
            if not isinstance(flow, list):
                flow = []
            flow.append(
                {
                    "ts": utils.now_ts(),
                    "chat_key": chat_key,
                    "origin": origin,
                    "model": model,
                    "in": int(usage.get("prompt_tokens", 0) or 0),
                    "out": int(usage.get("completion_tokens", 0) or 0),
                }
            )
            cap = int(getattr(self.cfg, "usage_flow_limit", 500) or 0)
            if cap > 0 and len(flow) > cap:
                flow = flow[-cap:]
                flow[0]["truncated"] = True
            return flow

        try:
            utils.storage_update(self.sdk, flow_key, _append, [])
        except Exception as e:
            self.logger.debug(f"usage flow append failed: {e}")

    def _usage_warn_check(self, chat_key: str, tokens_today: int, today: str) -> None:
        """R5 用量超限预警：跨 usage_warn_at%/100% 各发一次提示（每阈值每天一次）。"""
        limit = int(getattr(self.cfg, "daily_token_limit", 0) or 0)
        warn_at = int(getattr(self.cfg, "usage_warn_at", 80) or 0)
        if limit <= 0 or warn_at <= 0:
            return
        pct = tokens_today * 100 // limit
        marker_key = f"QvQChat:usage:warned:{today}"
        crossed: list = []

        def _mark(warned) -> dict:
            if not isinstance(warned, dict):
                warned = {}
            if pct >= 100 and not warned.get("100"):
                warned["100"] = True
                crossed.append(("100", texts.t("usage_warn_100", limit=limit)))
            elif pct >= warn_at and not warned.get(str(warn_at)):
                warned[str(warn_at)] = True
                crossed.append((str(warn_at), texts.t("usage_warn_80", at=warn_at, pct=pct, limit=limit)))
            return warned

        try:
# 键级 RMW（并发回合跨阈值只提示一次，不重复发）
            utils.storage_update(self.sdk, marker_key, _mark, {})
        except Exception as e:
# 存储故障时不发提示（发了也记不住阈值，会重复打扰）；留调试日志
            self.logger.debug(f"usage warn marker failed: {e}")
            return
        if not crossed:
            return
        logger = self.logger
        for _, message in crossed:
            logger.info(f"usage warn: {message}")
        main = getattr(self, "main", None)
        sender = getattr(main, "speak", None) if main is not None else None
        if callable(sender):
            try:
                import asyncio as _asyncio

                _asyncio.get_event_loop().create_task(sender(chat_key, reason="usage warn", prompt=message))
            except Exception:
                pass

    def _prune_usage(self, today: str) -> None:
        days = int(getattr(self.cfg, "usage_retention_days", 14) or 0)
        if days <= 0:
            return
# 同一天只扫一次（避免每条消息记账后都全库 keys() 扫描）
        if self.sdk.storage.get(USAGE_LAST_PRUNE_KEY, "") == today:
            return
        try:
            cutoff = datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days)
        except ValueError:
            return
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith("QvQChat:usage:"):
                date_part = key.rsplit(":", 1)[-1]
                try:
                    if datetime.strptime(date_part, "%Y-%m-%d") < cutoff:
                        self.sdk.storage.delete(key)
                except ValueError:
                    continue
        self.sdk.storage.set(USAGE_LAST_PRUNE_KEY, today)

    def _usage_history(self, days: int = 14) -> list[dict]:
        history = []
        for offset in range(days - 1, -1, -1):
            date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
            data = self.sdk.storage.get(f"QvQChat:usage:{date}", {})
            history.append(
                {
                    "date": date,
                    "tokens": int((data or {}).get("tokens", 0) or 0) if isinstance(data, dict) else 0,
                    "calls": int((data or {}).get("calls", 0) or 0) if isinstance(data, dict) else 0,
                    "by_chat": (data or {}).get("by_chat", {}),
                    "by_model": (data or {}).get("by_model", {}),
                    "by_user": (data or {}).get("by_user", {}),
                    "by_origin": (data or {}).get("by_origin", {}),
                }
            )
        return history

    def _usage_flow(self, days: int = 7) -> list[dict]:
        """最近 N 天逐条流水（新→旧）。"""
        flow: list[dict] = []
        for offset in range(days):
            date = (datetime.now() - timedelta(days=offset)).strftime("%Y-%m-%d")
            rows = self.sdk.storage.get(f"QvQChat:usageflow:{date}", [])
            if isinstance(rows, list):
                flow.extend(rows)
        return flow
