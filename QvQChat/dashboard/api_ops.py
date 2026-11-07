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

    async def tasks_run(self, request):
        """手动触发一次任务（不改下次计划时间）。"""
        body = await request.json()
        task_id = str((body or {}).get("id") or "")
        name = self.scheduler.run_now(task_id)
        if not name:
            return ({"error": "task not found"}, 404)
        return {"ok": True, "name": name}

    async def tasks_delete(self, request):
        body = await request.json()
        ok = self.main.scheduler.cancel(str((body or {}).get("id") or ""))
        return {"ok": ok}

    async def breakers_get(self, request):
        return {"breakers": self.main.pool.breaker_state()}

    async def breakers_reset(self, request):
        body = await request.json() or {}
        cleared = self.main.pool.breaker_reset(str(body.get("model") or ""))
        return {"ok": True, "cleared": cleared}

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
        kid = str((body or {}).get("id") or "")
        entry = self.main.knowledge.get(kid)
        ok = self.main.knowledge.delete(kid)
        undo = ""
        if ok and entry:
            undo = self._trash_put("kb", dict(entry))
        return {"ok": ok, "undo": undo if ok else ""}

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
        saved = []
        for kid in ids:
            entry = self.main.knowledge.get(str(kid))
            if self.main.knowledge.delete(str(kid)):
                removed += 1
                if entry:
                    saved.append(dict(entry))
        undo = self._trash_put("kb_batch", {"entries": saved}) if saved else ""
        return {"ok": True, "removed": removed, "undo": undo}

    async def skills_batch_delete(self, request):
        body = await request.json()
        names = body.get("names")
        if not isinstance(names, list):
            return ({"error": "names required"}, 400)
        removed = 0
        saved = []
        for name in names:
            try:
                sk = self.main.skills.get_skill(str(name))
                if sk and self.main.skills.delete_skill(str(name)):
                    removed += 1
                    saved.append({"name": sk.get("name") or str(name), "description": sk.get("description") or "", "body": sk.get("body") or ""})
            except Exception:
                continue
        undo = self._trash_put("skill_batch", {"items": saved}) if saved else ""
        return {"ok": True, "removed": removed, "undo": undo}

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

# ===== 存储管理：全库查看 / 分域清理 / 一键重置 / 瘦身 =====
# 原则：一切数据库内容交给用户——任意键可看可删；auth_token 永不出现在任何读写里（防自锁+防泄漏）

STORAGE_DOMAINS: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    # (域 id, 前缀匹配, 精确键)
    ("sessions", ("QvQChat:conv:",), ("QvQChat:conv_index", "QvQChat:routes")),
    ("memories", ("QvQChat:mem:",), ()),
    ("profiles", ("QvQChat:profile:",), ()),
    ("personas", ("QvQChat:binding:",), ("QvQChat:personas", "QvQChat:default_persona")),
    ("knowledge", ("QvQChat:kbvec:",), ("QvQChat:kb",)),
    ("audit", (), ("QvQChat:audit",)),
    ("usage", ("QvQChat:usage:",), ()),
    ("tasks", ("QvQChat:task_runs:",), ("QvQChat:tasks", "QvQChat:task_runs")),
    ("participation", ("QvQChat:participation:",), ()),
    ("shares", (), ("QvQChat:shares",)),
    ("trash", ("QvQChat:trash:",), ()),
    ("recall", ("QvQChat:user_seen:", "QvQChat:recall_last:"), ()),
    ("pending", ("QvQChat:pending_send:", "QvQChat:inflight:"), ()),
    ("models", (), ("QvQChat:models", "QvQChat:models_enriched_at", "QvQChat:modelsdev", "QvQChat:providers", "QvQChat:model_chain")),
    ("mcp", (), ("QvQChat:mcp_servers",)),
    ("docs", (), ("QvQChat:docs_meta",)),
    ("settings", (), ("QvQChat:ui_defaults",)),
]
PROTECTED_KEYS = {"QvQChat:auth_token"}
# 磁盘目录域：路径 + 清空行为（只清内容不删目录）
STORAGE_FILE_DOMAINS = [
    ("uploads", "data/QvQChat/uploads"),
    ("docs_cache", "data/QvQChat/docs"),
    ("work", "data/QvQChat/work"),
]
MAX_ENTRY_CHARS = 200_000


def _kv_size(value) -> int:
    """KV 值的持久化体积估算（JSON 序列化长度，失败退 repr）。"""
    import json as _json

    try:
        return len(_json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return len(repr(value))


def _storage_domain_of(key: str) -> str:
    for domain, prefixes, exacts in STORAGE_DOMAINS:
        if key in exacts:
            return domain
        for prefix in prefixes:
            if key.startswith(prefix):
                return domain
    return "other"


class StorageApiMixin:
    """依赖宿主提供 self.main / self.sdk / self._query。"""

    def _kv_keys(self) -> list[str]:
        out = []
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith("QvQChat:") and key not in PROTECTED_KEYS:
                out.append(key)
        return out

    def _domain_keys(self, domain: str) -> list[str]:
        if domain in ("uploads", "docs_cache"):
            return []
        return [k for k in self._kv_keys() if _storage_domain_of(k) == domain]

    def _dir_stats(self, path: str) -> dict:
        from pathlib import Path

        root = Path(path)
        files = bytes_total = 0
        if root.exists():
            for item in root.rglob("*"):
                try:
                    if item.is_file():
                        files += 1
                        bytes_total += item.stat().st_size
                except OSError:
                    continue
        return {"files": files, "bytes": bytes_total}

    async def storage_get(self, request):
        stats: dict[str, dict] = {}
        for key in self._kv_keys():
            domain = _storage_domain_of(key)
            entry = stats.setdefault(domain, {"keys": 0, "bytes": 0})
            entry["keys"] += 1
            try:
                entry["bytes"] += _kv_size(self.sdk.storage.get(key, None))
            except Exception:
                continue
        files = []
        for domain, path in STORAGE_FILE_DOMAINS:
            info = self._dir_stats(path)
            info.update({"id": domain, "path": path})
            files.append(info)
        total = sum(v["bytes"] for v in stats.values()) + sum(f["bytes"] for f in files)
        return {
            "domains": [
                {"id": domain, "keys": stats[domain]["keys"], "bytes": stats[domain]["bytes"]}
                for domain in sorted(stats, key=lambda d: -stats[d]["bytes"])
            ],
            "files": files,
            "total_bytes": total,
        }

    async def storage_keys(self, request):
        domain = self._query(request, "domain") or ""
        if not domain or domain in ("uploads", "docs_cache"):
            return ({"error": "bad domain"}, 400)
        keys = []
        for key in self._domain_keys(domain):
            try:
                size = _kv_size(self.sdk.storage.get(key, None))
            except Exception:
                size = 0
            keys.append({"key": key, "bytes": size})
        keys.sort(key=lambda item: (-item["bytes"], item["key"]))
        return {"domain": domain, "keys": keys[:600], "total": len(keys)}

    async def storage_entry(self, request):
        import json as _json

        key = self._query(request, "key") or ""
        if not key or not key.startswith("QvQChat:") or key in PROTECTED_KEYS:
            return ({"error": "bad key"}, 400)
        value = self.sdk.storage.get(key, None)
        try:
            text = _json.dumps(value, ensure_ascii=False, indent=1, default=str)
        except Exception:
            text = repr(value)
        truncated = len(text) > MAX_ENTRY_CHARS
        return {"key": key, "value": text[:MAX_ENTRY_CHARS], "truncated": truncated, "bytes": len(text)}

    async def storage_delete(self, request):
        body = await request.json()
        wanted = [str(k) for k in ((body or {}).get("keys") or []) if isinstance(k, str)]
        wanted = [k for k in wanted if k.startswith("QvQChat:") and k not in PROTECTED_KEYS]
        removed = freed = 0
        for key in wanted:
            try:
                freed += _kv_size(self.sdk.storage.get(key, None))
                self.sdk.storage.delete(key)
                removed += 1
            except Exception:
                continue
        return {"ok": True, "removed": removed, "freed": freed}

    async def storage_cleanup(self, request):
        """分域清理 / 一键重置。reset=true 时清全部域（keep 列表除外）；否则清 domains 列表。"""
        body = await request.json() or {}
        keep = {str(k) for k in (body.get("keep") or [])}
        if body.get("reset"):
            domains = [d for d, _, _ in STORAGE_DOMAINS if d not in keep] + [
                d for d, _ in STORAGE_FILE_DOMAINS if d not in keep
            ]
        else:
            domains = [str(d) for d in (body.get("domains") or [])]
        removed = freed = 0
        for domain in domains:
            if domain in ("uploads", "docs_cache"):
                removed += self._clear_dir(dict(STORAGE_FILE_DOMAINS)[domain])
                continue
            for key in self._domain_keys(domain):
                try:
                    freed += _kv_size(self.sdk.storage.get(key, None))
                    self.sdk.storage.delete(key)
                    removed += 1
                except Exception:
                    continue
        return {"ok": True, "domains": domains, "removed": removed, "freed": freed}

    def _clear_dir(self, path: str) -> int:
        from pathlib import Path

        root = Path(path)
        if not root.exists():
            return 0
        count = 0
        for item in root.iterdir():
            try:
                if item.is_dir():
                    import shutil

                    shutil.rmtree(item)
                else:
                    item.unlink()
                count += 1
            except OSError:
                continue
        return count

    async def storage_slim(self, request):
        """瘦身：历史消息里 rounds 与 trace 双写的旧数据去重（新写入已不双写）。"""
        from ..conversation.service import CONV_PREFIX

        freed = changed = 0
        for key in self._kv_keys():
            if not key.startswith(CONV_PREFIX):
                continue
            state = self.sdk.storage.get(key, None)
            if not isinstance(state, dict) or not isinstance(state.get("contexts"), list):
                continue
            dirty = False
            for entry in state["contexts"]:
                if isinstance(entry, dict) and entry.get("rounds") and entry.get("trace"):
                    freed += _kv_size(entry["trace"])
                    del entry["trace"]
                    dirty = True
            if dirty:
                self.sdk.storage.set(key, state)
                changed += 1
        return {"ok": True, "sessions": changed, "freed": freed}
