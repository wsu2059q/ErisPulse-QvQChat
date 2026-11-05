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
# Lorebook 透传：triggers（世界书触发关键词）/ priority / cooldown_min
# 可见域透传：scope 空=全局（运维默认）；chat:<key> / <platform> 为私有域
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
# 倒序分页：offset 跳过最新 N 条，返回该页 + 总数（前端“加载更多”用）
        try:
            offset = max(0, int(self._query(request, "offset") or 0))
        except Exception:
            offset = 0
        newest_first = list(reversed(entries))
        total = len(newest_first)
        page = newest_first[offset : offset + limit]
        return {"entries": page, "total": total, "offset": offset, "limit": limit}

    async def audit_delete(self, request):
        """批删/清空审计。indexes 为前端「最新在前」序号；clear=true 清空全部。"""
        body = await request.json()
        entries = self.main.sdk.storage.get(AUDIT_STORAGE_KEY, [])
        if not isinstance(entries, list):
            entries = []
        if body.get("clear"):
            removed = len(entries)
            self.main.sdk.storage.set(AUDIT_STORAGE_KEY, [])
            return {"ok": True, "removed": removed, "cleared": True}
        indexes = body.get("indexes")
        if not isinstance(indexes, list) or not indexes:
            return ({"error": "indexes required"}, 400)
        total = len(entries)
        drop = set()
        for raw in indexes:
            try:
                newest_idx = int(raw)
            except (TypeError, ValueError):
                continue
            if 0 <= newest_idx < total:
                drop.add(total - 1 - newest_idx)  # 转回存储序（最旧在前）
        if not drop:
            return {"ok": True, "removed": 0}
        kept = [e for i, e in enumerate(entries) if i not in drop]
        self.main.sdk.storage.set(AUDIT_STORAGE_KEY, kept)
        return {"ok": True, "removed": total - len(kept)}

    async def kb_batch_delete(self, request):
        body = await request.json()
        ids = body.get("ids")
        if not isinstance(ids, list):
            return ({"error": "ids required"}, 400)
        removed = 0
        for kid in ids:
            if self.main.knowledge.delete(str(kid)):
                removed += 1
        return {"ok": True, "removed": removed}

    async def skills_batch_delete(self, request):
        body = await request.json()
        names = body.get("names")
        if not isinstance(names, list):
            return ({"error": "names required"}, 400)
        removed = 0
        for name in names:
            try:
                if self.main.skills.delete_skill(str(name)):
                    removed += 1
            except Exception:
                continue
        return {"ok": True, "removed": removed}

    async def sessions_batch_delete(self, request):
        body = await request.json()
        chat_keys = body.get("chat_keys")
        if not isinstance(chat_keys, list):
            return ({"error": "chat_keys required"}, 400)
        removed = 0
        for key in chat_keys:
            key = str(key or "")
            if not key:
                continue
            try:
                if self.main.conversations.delete(key):
                    removed += 1
            except Exception:
                continue
        return {"ok": True, "removed": removed}

    # ===== AI 整理：cheap 模型分析条目 → JSON 建议 → 应用 =====

    def _organize_ask(self):
        from ..engine.base import ChatRequest, TaskSpec

        async def _ask(system, user):
            request = ChatRequest(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                tools=None, temperature=0.2, max_tokens=3000,
            )
            response = await self.main.pool.dispatch(TaskSpec(kind="compact", prefer="cheap"), request)
            return response.content or ""

        return _ask

    @staticmethod
    def _extract_json_array(text):
        import json
        import re

        match = re.search(r"\[[\s\S]*\]", text or "")
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, list) else None
        except Exception:
            return None

    async def kb_organize(self, request):
        """AI 整理知识库：合并重复/补触发词/改标题，直接应用并返回报告。"""
        entries = self.main.knowledge.list()
        if not entries:
            return {"ok": True, "report": "empty", "actions": 0}
        listing = []
        newline = chr(10)
        for i, e in enumerate(entries[:60]):
            trig = ",".join(e.get("triggers") or [])
            listing.append(
                f"[{i}] id={e.get('id')} title={e.get('title')} triggers={trig}" + newline + str(e.get("content") or "")[:300]
            )
        system = (
            "You are a knowledge-base curator. Given numbered entries, output ONLY a JSON array of actions: "
            '[{"op":"merge","ids":["a","b"],"title":"...","content":"...","triggers":["..."]}, '
            '{"op":"update","id":"a","title":"...","triggers":["..."]}, '
            '{"op":"delete","id":"a","reason":"..."}]. '
            "Merge only true duplicates/overlaps; keep merged content concise; never invent facts. "
            "If everything is already tidy, output []."
        )
        user = newline.join(listing)
        try:
            raw = await self._organize_ask()(system, user)
        except Exception as e:
            return ({"error": str(e)}, 502)
        actions = self._extract_json_array(raw)
        if not actions:
            return {"ok": True, "report": "noop", "actions": 0}
        applied = 0
        deleted = merged = updated = 0
        for act in actions[:30]:
            if not isinstance(act, dict):
                continue
            op = str(act.get("op") or "")
            try:
                if op == "delete":
                    if self.main.knowledge.delete(str(act.get("id") or "")):
                        applied += 1
                        deleted += 1
                elif op == "update":
                    entry = self.main.knowledge.update(
                        str(act.get("id") or ""),
                        title=str(act.get("title") or "") or None,
                        triggers=act.get("triggers"),
                    )
                    if entry:
                        applied += 1
                        updated += 1
                elif op == "merge":
                    ids = [str(x) for x in (act.get("ids") or []) if x]
                    if len(ids) >= 2 and str(act.get("content") or "").strip():
                        first = self.main.knowledge.update(
                            ids[0],
                            title=str(act.get("title") or "") or None,
                            content=str(act.get("content")),
                            triggers=[str(t) for t in (act.get("triggers") or [])] or None,
                        )
                        if first:
                            applied += 1
                            merged += 1
                            for extra in ids[1:]:
                                self.main.knowledge.delete(extra)
            except Exception:
                continue
        return {"ok": True, "report": f"删除 {deleted}，合并 {merged}，更新 {updated}", "actions": applied}

    async def skills_organize(self, request):
        """AI 整理技能：合并近似技能/修描述/删陈旧，仅动 dashboard 来源的技能。"""
        skills = [s for s in self.main.skills.list_skills() if s.get("source") == "dashboard"]
        if not skills:
            return {"ok": True, "report": "empty", "actions": 0}
        listing = []
        newline = chr(10)
        for i, sk in enumerate(skills[:50]):
            listing.append(
                f"[{i}] name={sk.get('name')} desc={sk.get('description')}" + newline + str(sk.get("body") or "")[:240]
            )
        system = (
            "You are a skill-library curator. Given numbered skills, output ONLY a JSON array: "
            '{"op":"delete","name":"...","reason":"obsolete"}, '
            '{"op":"merge","names":["a","b"],"name":"kept-name","description":"...","body":"numbered steps"}, '
            '{"op":"update","name":"a","description":"better one-liner"} wrapped in a JSON array. '
            "Only merge skills that clearly overlap; keep bodies actionable and short. If tidy, output []."
        )
        user = newline.join(listing)
        try:
            raw = await self._organize_ask()(system, user)
        except Exception as e:
            return ({"error": str(e)}, 502)
        actions = self._extract_json_array(raw)
        if not actions:
            return {"ok": True, "report": "noop", "actions": 0}
        applied = 0
        for act in actions[:30]:
            if not isinstance(act, dict):
                continue
            op = str(act.get("op") or "")
            try:
                if op == "delete":
                    if self.main.skills.delete_skill(str(act.get("name") or "")):
                        applied += 1
                elif op == "merge":
                    names = [str(x) for x in (act.get("names") or []) if x]
                    if len(names) >= 2 and str(act.get("body") or "").strip():
                        keep = str(act.get("name") or names[0])
                        self.main.skills.save_skill(keep, str(act.get("description") or ""), str(act.get("body")))
                        applied += 1
                        for extra in names:
                            if extra != keep:
                                self.main.skills.delete_skill(extra)
                elif op == "update":
                    sk = self.main.skills.get_skill(str(act.get("name") or ""))
                    if sk and sk.get("source") == "dashboard":
                        self.main.skills.save_skill(
                            sk["name"],
                            str(act.get("description") or sk.get("description") or ""),
                            sk.get("body") or "",
                        )
                        applied += 1
            except Exception:
                continue
        return {"ok": True, "report": f"{applied} 项调整", "actions": applied}

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
