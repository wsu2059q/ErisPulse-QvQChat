"""运维观测域 API（拆分自 dashboard/manager.py）：tasks / usage / audit / kb / breakers / costs / running。

participation 观测：GET /api/qvq/participation → main.participation_status()
（提供者目录 + 输出预算现状 + 最近决策环形日志）。
mixin 由 DashboardManager 组合，路由表仍在 manager.py。
"""
from __future__ import annotations

from .. import texts, utils

AUDIT_STORAGE_KEY = "QvQChat:audit"


class OpsApiMixin:
    """依赖宿主提供 self.main / self.sdk / self._query / self._live。"""

    async def usage_get(self, request):
        return {
            "days": self.main._usage_history(14),
            "limit": int(getattr(self.main.cfg, "daily_token_limit", 0) or 0),
        }

    async def tasks_get(self, request):
        tasks = []
        for task in self.main.scheduler.list():
            item = dict(task)
            item["next_formatted"] = utils.format_ts(float(task.get("next_run", 0)))
            if task.get("last_run"):
                item["last_formatted"] = utils.format_ts(float(task.get("last_run") or 0))
            tasks.append(item)
        runs = [
            {**run, "at_formatted": utils.format_ts(float(run.get("at") or 0))}
            for run in reversed(self.main.scheduler.runs())
        ]
        return {"tasks": tasks, "runs": runs}

    async def tasks_delete(self, request):
        body = await request.json()
        ok = self.main.scheduler.cancel(str((body or {}).get("id") or ""))
        return {"ok": ok}

    async def breakers_get(self, request):
        return {"breakers": self.main.pool.breaker_state()}

    async def costs_get(self, request):
# 每百万 token 单价 × 用量明细（in/out），换算每日与按模型成本
        prices = self.main.pool.model_costs()
        daily: list[dict] = []
        by_model: dict[str, float] = {}
        total = 0.0
        for day in self.main._usage_history(14):
            day_cost = 0.0
            for model_id, usage in (day.get("by_model") or {}).items():
                price = prices.get(str(model_id))
                if not price or not isinstance(usage, dict):
                    continue
                cost = (int(usage.get("in", 0) or 0) / 1e6) * price["input"] + (
                    int(usage.get("out", 0) or 0) / 1e6
                ) * price["output"]
                day_cost += cost
                by_model[str(model_id)] = by_model.get(str(model_id), 0.0) + cost
            daily.append({"date": day.get("date"), "cost": round(day_cost, 4)})
            total += day_cost
        return {
            "daily": daily,
            "by_model": {k: round(v, 4) for k, v in sorted(by_model.items(), key=lambda kv: -kv[1])},
            "total": round(total, 4),
        }

    async def running_get(self, request):
        return {"running": self._live.overview()}

    async def kb_get(self, request):
        query = self._query(request, "q") or ""
        kb = self.main.knowledge
        stats = kb.stats()
        if query:
            hits = kb.search(query, top_k=8)
            items = [kb.get(h["id"]) for h in hits]
            items = [i for i in items if i]
        else:
            items = kb.list()
        return {"entries": items, "stats": stats}

    async def kb_add(self, request):
        body = await request.json()
        title = str((body or {}).get("title") or "").strip()
        content = str((body or {}).get("content") or "")
        if not title or not content.strip():
            return ({"error": texts.t("kb_need_title_content")}, 400)
# Lorebook 透传：triggers（世界书触发关键词）/ priority / cooldown_min
        cooldown = (body or {}).get("cooldown_min")
        entry = self.main.knowledge.add(
            title,
            content,
            source=str((body or {}).get("source") or ""),
            triggers=(body or {}).get("triggers"),
            priority=int((body or {}).get("priority") or 0),
            cooldown_min=int(cooldown) if cooldown is not None else None,
        )
        return {"ok": True, "entry": entry}

    async def kb_delete(self, request):
        body = await request.json()
        ok = self.main.knowledge.delete(str((body or {}).get("id") or ""))
        return {"ok": ok}

    async def kb_export(self, request):
        return {"entries": self.main.knowledge.export()}

    async def kb_import(self, request):
        body = await request.json()
        added = self.main.knowledge.import_entries((body or {}).get("entries") or [])
        return {"ok": True, "added": added}

    async def audit_get(self, request):
        entries = self.main.sdk.storage.get(AUDIT_STORAGE_KEY, [])
        if not isinstance(entries, list):
            entries = []
        limit = 200
        try:
            limit = max(1, min(int(self._query(request, "limit") or 200), 500))
        except Exception:
            limit = 200
        return {"entries": list(reversed(entries[-limit:]))}

# ===== 参与决策（participation）观测 =====
# 提供者目录（qvq_decision 约定服务）+ 输出预算现状 + 最近决策环形日志。

    async def participation_get(self, request):
        status = getattr(self.main, "participation_status", None)
        if status is None:
            return {"enabled": False, "providers": [], "budget": {}, "decisions": []}
        try:
            return await status()
        except Exception as e:
            self.main.logger.debug(f"participation_status failed: {e}")
            return {"enabled": False, "providers": [], "budget": {}, "decisions": [], "error": str(e)}
