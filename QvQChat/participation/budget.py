"""输出预算（扩展点 D）：参与决策插话与插件主动发言共用的护栏，插件不可绕过。

四层护栏中的"输出层"：member_allowed（输入）→ _rate_allow（输入）→ SpeechBudget
（输出，本模块）→ daily_token_limit（成本）。

规则：
- 每群每小时 ``participation_hourly_limit`` 条（默认 8，0 不限）
- 同群两次发言最小间隔 ``participation_cooldown_seconds`` 秒（默认 300，0 不限）
- kind="proactive"（speak 服务主动开口）额外受全局每日
  ``participation_proactive_daily_limit`` 条上限（默认 3，0 不限）；kind="interject"
（插话）不计入全局日限

持久化：``QvQChat:participation:{chat_key}`` 时间戳环形列表（按时间窗修剪 + 长度
上限），``QvQChat:participation:global`` 当日计数（跨日自动重置）。并发安全：内存锁
（storage get/set 为同步 API）。
"""
from __future__ import annotations

import threading
import time
from datetime import datetime

from .. import texts

KIND_INTERJECT = "interject"
KIND_PROACTIVE = "proactive"

CHAT_KEY_PREFIX = "QvQChat:participation:"
GLOBAL_KEY = "QvQChat:participation:global"

HOUR_SECONDS = 3600.0
# 环形列表长度上限（防极端配置下无限增长；正常远小于该值）
RING_CAP = 512


def _f(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class SpeechBudget:
    """会话输出预算：``allow(chat_key, kind) -> (bool, reason)`` + ``record``。

    :param sdk: 框架 sdk（storage 持久化；不可用时静默降级为内存态）
    :param config: 配置对象或返回配置对象的 callable（支持热更新；可为 None 走默认值）
    """

    def __init__(self, sdk, config=None):
        self.sdk = sdk
        self._config = config
        self._lock = threading.Lock()
        self._memory: dict[str, object] = {}
        self._touched: set[str] = set()

# ==================== 配置读取 ====================

    def _cfg(self):
        if callable(self._config):
            try:
                return self._config()
            except Exception:
                return None
        return self._config

    def _hourly(self) -> int:
        cfg = self._cfg()
        try:
            return int(getattr(cfg, "participation_hourly_limit", 8) or 0)
        except (TypeError, ValueError):
            return 0

    def _cooldown(self) -> float:
        cfg = self._cfg()
        return max(_f(getattr(cfg, "participation_cooldown_seconds", 300), 300.0), 0.0)

    def _daily(self) -> int:
        cfg = self._cfg()
        try:
            return int(getattr(cfg, "participation_proactive_daily_limit", 3) or 0)
        except (TypeError, ValueError):
            return 0

# ==================== 判定与记账 ====================

    def allow(self, chat_key: str, kind: str, now: float | None = None) -> tuple[bool, str]:
        """预算是否放行一次发言；拒绝时第二个返回值为人类可读原因（texts）。"""
        chat_key = str(chat_key or "")
        if not chat_key:
            return False, "empty chat_key"
        now = time.time() if now is None else float(now)
        hourly = self._hourly()
        cooldown = self._cooldown()
        daily = self._daily()
        with self._lock:
            self._touched.add(chat_key)
            stamps = self._chat_stamps(chat_key, now, cooldown)
            if cooldown > 0 and stamps:
                last = max(stamps)
                if now - last < cooldown:
                    remain = int(cooldown - (now - last)) + 1
                    return False, texts.t("participate_budget_cooldown", seconds=remain)
            if hourly > 0 and len([t for t in stamps if now - t < HOUR_SECONDS]) >= hourly:
                return False, texts.t("participate_budget_hourly", limit=hourly)
            if kind == KIND_PROACTIVE and daily > 0:
                used, _ = self._daily_state(now)
                if used >= daily:
                    return False, texts.t("participate_budget_daily", limit=daily)
        return True, ""

    def record(self, chat_key: str, kind: str, now: float | None = None) -> None:
        """记账一次已放行的发言（时间戳入环形列表；proactive 另计全局日限）。"""
        chat_key = str(chat_key or "")
        if not chat_key:
            return
        now = time.time() if now is None else float(now)
        cooldown = self._cooldown()
        with self._lock:
            self._touched.add(chat_key)
            key = CHAT_KEY_PREFIX + chat_key
            stamps = [t for t in self._load(key, []) if isinstance(t, (int, float))]
            window = max(HOUR_SECONDS, cooldown)
            stamps = [t for t in stamps if now - t < window]
            stamps.append(now)
            self._save(key, stamps[-RING_CAP:])
            if kind == KIND_PROACTIVE:
                used, date = self._daily_state(now)
                self._save(GLOBAL_KEY, {"date": date, "count": used + 1})

# ==================== 现状观测 ====================

    def status(self, now: float | None = None) -> dict:
        """预算现状（Dashboard participation_status 消费）。"""
        now = time.time() if now is None else float(now)
        with self._lock:
            chats: dict[str, dict] = {}
            for chat_key in sorted(self._touched):
                stamps = [
                    t for t in self._load(CHAT_KEY_PREFIX + chat_key, [])
                    if isinstance(t, (int, float))
                ]
                chats[chat_key] = {
                    "hour": len([t for t in stamps if now - t < HOUR_SECONDS]),
                    "last": max(stamps) if stamps else 0.0,
                }
            used, date = self._daily_state(now)
        return {
            "limits": {
                "hourly_limit": self._hourly(),
                "cooldown_seconds": self._cooldown(),
                "proactive_daily_limit": self._daily(),
            },
            "chats": chats,
            "proactive_today": used,
            "proactive_date": date,
        }

# ==================== 持久化（锁内调用） ====================

    def _chat_stamps(self, chat_key: str, now: float, cooldown: float) -> list[float]:
        key = CHAT_KEY_PREFIX + chat_key
        stamps = [t for t in self._load(key, []) if isinstance(t, (int, float))]
        window = max(HOUR_SECONDS, cooldown)
        stamps = [t for t in stamps if now - t < window]
        self._save(key, stamps[-RING_CAP:])
        return stamps

    def _daily_state(self, now: float) -> tuple[int, str]:
        """当日 proactive 计数（跨日自动重置）。"""
        date = datetime.fromtimestamp(now).strftime("%Y-%m-%d")
        data = self._load(GLOBAL_KEY, {})
        if not isinstance(data, dict) or data.get("date") != date:
            return 0, date
        try:
            return int(data.get("count") or 0), date
        except (TypeError, ValueError):
            return 0, date

    def _load(self, key: str, default):
        try:
            storage = getattr(self.sdk, "storage", None)
            if storage is not None:
                return storage.get(key, default)
        except Exception:
            pass
        return self._memory.get(key, default)

    def _save(self, key: str, value) -> None:
        try:
            storage = getattr(self.sdk, "storage", None)
            if storage is not None:
                storage.set(key, value)
                return
        except Exception:
            pass
        self._memory[key] = value
