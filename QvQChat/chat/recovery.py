"""实例重启恢复域：悬空回复重跑 / 待发队列启动重放 / 定时任务中断标记对账。

挂在 RecoveryMixin 上，经 InboxMixin 组合进 Main 的 mixin 链（不改 Main.py 本体）。
标记协议：
- ``QvQChat:inflight:{chat_key}``：_process_locked 进入 runner 前落盘、finally 清除；
  重启后残留即视为"生成被打断"，按 recovery_enabled/recovery_min_age 决定是否重跑。
- ``QvQChat:pending_send:{chat_key}``：delivery 已有的待发队列，启动时逐会话重放一条。
- ``QvQChat:task_runs:{task_id}``：scheduler._fire 执行前落 running、结束落 done/failed；
  启动时发现 running 残留改为 interrupted（保守：不自动重跑长任务）。
"""
from __future__ import annotations

import asyncio
import time

from ..conversation.delivery import PENDING_KEY_PREFIX
from ..conversation.service import parse_chat_key, strip_isolation
from ..scheduler import TASK_RUN_STATE_PREFIX

# 悬空回复标记前缀（chat/inbox.py _process_locked 写入/删除）
INFLIGHT_KEY_PREFIX = "QvQChat:inflight:"

# 启动恢复延迟：避开模块加载期（适配器/连接未就绪）
RECOVERY_BOOT_DELAY = 15.0
# 待发队列逐会话重放间隔
RECOVERY_REPLAY_GAP = 2.0


class RecoveryMixin:
    """Main 的实例重启恢复 mixin。依赖宿主提供 self.sdk / self.cfg / self.logger /
    self.sessions / self.delivery / self.run_prompt（与 InboxMixin 同宿主）。"""

    async def recover_inflight_routine(self, boot_delay: float | None = None,
                                       replay_gap: float | None = None) -> None:
        """启动恢复例程：延迟避开加载期 → 任务中断对账 → 待发队列重放 → 悬空回复重跑。

        boot_delay/replay_gap 可注入（测试用 0 跳过真实等待）；scheduler.start 默认无参调用。
        """
        delay = RECOVERY_BOOT_DELAY if boot_delay is None else max(0.0, float(boot_delay))
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            self._mark_interrupted_task_runs()
            await self._replay_pending_on_boot(gap=replay_gap)
            await self._recover_inflight_marks()
        except Exception as e:
            self.logger.warning(f"recovery routine failed: {e}")

    def _mark_interrupted_task_runs(self) -> None:
        """定时任务执行标记对账：running 残留（重启打断）改 interrupted，仅 debug 观测。"""
        try:
            keys = list(self.sdk.storage.keys())
        except Exception:
            return
        for key in keys:
            if not isinstance(key, str) or not key.startswith(TASK_RUN_STATE_PREFIX):
                continue
            task_id = key[len(TASK_RUN_STATE_PREFIX):]
            try:
                state = self.sdk.storage.get(key, None)
            except Exception:
                continue
            if not isinstance(state, dict) or str(state.get("status") or "") != "running":
                continue
            state["status"] = "interrupted"
            state["interrupted_at"] = time.time()
            try:
                self.sdk.storage.set(key, state)
                self.logger.debug(f"task run {task_id} marked interrupted (restart during run)")
            except Exception as e:
                self.logger.debug(f"task run {task_id} interrupt mark failed: {e}")

    async def _replay_pending_on_boot(self, gap: float | None = None) -> None:
        """待发队列启动重放：replay_on_boot 开启时逐会话串行各重放一条，失败跳过。"""
        if not bool(getattr(self.cfg, "replay_on_boot", True)):
            return
        wait = RECOVERY_REPLAY_GAP if gap is None else max(0.0, float(gap))
        try:
            keys = list(self.sdk.storage.keys())
        except Exception:
            return
        first = True
        for key in keys:
            if not isinstance(key, str) or not key.startswith(PENDING_KEY_PREFIX):
                continue
            chat_key = key[len(PENDING_KEY_PREFIX):]
            if not chat_key:
                continue
            try:
                data = self.sdk.storage.get(key, [])
            except Exception:
                continue
            if not isinstance(data, list) or not data:
                continue
            if not first and wait > 0:
                await asyncio.sleep(wait)
            first = False
            try:
                if await self.delivery.replay_pending(chat_key):
                    self.logger.info(f"boot replayed pending send for {chat_key}")
            except Exception as e:
                self.logger.debug(f"boot pending replay failed for {chat_key}: {e}")

    async def _recover_inflight_marks(self) -> None:
        """悬空回复恢复：扫描 inflight 残留标记 → 先删标记 → 满足条件则经 run_prompt 重跑。

        重启后内存 live 已丢，残留一律视为被打断。防 user 重复：prepare 已把该轮 user 消息
        持久化为 contexts 末条，重跑前先 pop_last_user_if 弹出（run_prompt 内 prepare
        persist=False，重跑以 user_msg 形式单独携带该文本，不重复出现在上下文）。
        """
        enabled = bool(getattr(self.cfg, "recovery_enabled", True))
        min_age = float(getattr(self.cfg, "recovery_min_age", 90) or 0)
        now = time.time()
        try:
            keys = list(self.sdk.storage.keys())
        except Exception:
            return
        for key in keys:
            if not isinstance(key, str) or not key.startswith(INFLIGHT_KEY_PREFIX):
                continue
            chat_key = key[len(INFLIGHT_KEY_PREFIX):]
            try:
                marker = self.sdk.storage.get(key, None)
            except Exception:
                marker = None
            try:
                self.sdk.storage.delete(key)
            except Exception:
                pass
            if not isinstance(marker, dict) or not chat_key:
                continue
            text = str(marker.get("text") or "")
            ts = float(marker.get("ts") or 0)
            origin = str(marker.get("origin") or "chat")
            if not text:
                continue
            if not enabled:
                self.logger.info(f"inflight mark cleared, recovery disabled: {chat_key}")
                continue
            if now - ts < min_age:
                self.logger.info(f"inflight mark too fresh, skip recovery: {chat_key}")
                continue
            if not parse_chat_key(strip_isolation(chat_key))[0]:
                continue
            popped = False
            try:
                popped = self.sessions.pop_last_user_if(chat_key, text)
            except Exception as e:
                self.logger.debug(f"pop_last_user_if failed for {chat_key}: {e}")
            try:
                await self.run_prompt(chat_key, text, origin="recovery", send=True)
                self.logger.info(
                    f"recovered inflight reply for {chat_key} (origin={origin}, popped_user={popped})"
                )
            except Exception as e:
                self.logger.warning(f"inflight recovery failed for {chat_key}: {e}")
