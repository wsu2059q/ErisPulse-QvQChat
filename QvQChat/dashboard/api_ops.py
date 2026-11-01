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
 
        prices = {str(k).lower(): v for k, v in self.main.pool.model_costs().items()}
        daily: list[dict] = []
        by_model: dict[str, float] = {}
        total = 0.0
        for day in self.main._usage_history(14):
            day_cost = 0.0
            for model_id, usage in (day.get("by_model") or {}).items():
                price = prices.get(str(model_id).lower())
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
 
 
        cooldown = (body or {}).get("cooldown_min")
        entry = self.main.knowledge.add(
            title,
            content,
            source=str((body or {}).get("source") or ""),
            triggers=(body or {}).get("triggers"),
            priority=int((body or {}).get("priority") or 0),
            cooldown_min=int(cooldown) if cooldown is not None else None,
            owner=str((body or {}).get("scope") or ""),
        )
        return {"ok": True, "entry": entry}

    async def kb_update(self, request):
        body = await request.json()
        kb_id = str((body or {}).get("id") or "")
        if not kb_id:
            return ({"error": "id required"}, 400)
        updates: dict = {}
        if (body or {}).get("title") is not None:
            updates["title"] = str((body or {}).get("title") or "")
        if (body or {}).get("content") is not None:
            updates["content"] = str((body or {}).get("content") or "")
        if (body or {}).get("source") is not None:
            updates["source"] = str((body or {}).get("source") or "")
        if (body or {}).get("triggers") is not None:
            raw = (body or {}).get("triggers")
            if isinstance(raw, str):
                raw = [t.strip() for t in raw.split(",") if t.strip()]
            updates["triggers"] = raw
        if (body or {}).get("scope") is not None:
            updates["owner"] = str((body or {}).get("scope") or "")
        entry = self.main.knowledge.update(kb_id, **updates)
        if entry is None:
            return ({"error": texts.t("kb_not_found", kb_id=kb_id)}, 404)
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
 
        try:
            offset = max(0, int(self._query(request, "offset") or 0))
        except Exception:
            offset = 0
        newest_first = list(reversed(entries))
        total = len(newest_first)
        page = newest_first[offset : offset + limit]
        return {"entries": page, "total": total, "offset": offset, "limit": limit}

 
 

    async def participation_get(self, request):
        status = getattr(self.main, "participation_status", None)
        if status is None:
            return {"enabled": False, "providers": [], "budget": {}, "decisions": []}
        try:
            return await status()
        except Exception as e:
            self.main.logger.debug(f"participation_status failed: {e}")
            return {"enabled": False, "providers": [], "budget": {}, "decisions": [], "error": str(e)}
