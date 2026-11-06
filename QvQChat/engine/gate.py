"""全局并发闸门：多人高负载平台下限制同时在飞的模型请求数。

- limit <= 0：不限流，acquire 直接放行（默认行为，零开销）
- limit > 0：超出上限时按 (priority, 先来后到) 排队——直接提问（低数值）先于
  插话/压缩/标题等后台任务拿到空位；饱和状态可被上游用来跳过可选工作
  （如参与决策问询），避免后台流量淹没真实用户。
"""
from __future__ import annotations

import asyncio
import heapq


class PriorityGate:

    def __init__(self, limit: int = 0):
        self.limit = max(0, int(limit))
        self._active = 0
        self._waiters: list[tuple[tuple[int, int], asyncio.Future]] = []
        self._seq = 0

    def set_limit(self, limit: int) -> None:
        self.limit = max(0, int(limit))
        self._wake()

    @property
    def active(self) -> int:
        return self._active

    @property
    def waiting(self) -> int:
        return len(self._waiters)

    @property
    def saturated(self) -> bool:
        """满载判定：没有空闲槽位。上游可据此跳过插话等可选路径。"""
        return self.limit > 0 and self._active >= self.limit

    async def acquire(self, priority: int = 5) -> None:
        if self.limit <= 0:
            self._active += 1
            return
# 有空位且无人排队：直接进（优先级只在争抢时起作用，不满载零开销）
        if self._active < self.limit and not self._waiters:
            self._active += 1
            return
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        heapq.heappush(self._waiters, ((int(priority), self._seq), fut))
        self._seq += 1
        try:
            await fut
        except asyncio.CancelledError:
# 被取消：若已拿到槽位（future 已被 set）要归还；还在队列里则移除
            if fut.done() and not fut.cancelled():
                self.release()
            else:
                self._waiters = [(k, f) for k, f in self._waiters if f is not fut]
                heapq.heapify(self._waiters)
            raise

    def release(self) -> None:
        self._active = max(0, self._active - 1)
        self._wake()

    def _wake(self) -> None:
        while self._waiters and (self.limit <= 0 or self._active < self.limit):
            _, fut = heapq.heappop(self._waiters)
            self._active += 1
            if not fut.done():
                fut.set_result(None)
