"""配置域 API（拆分自 dashboard/manager.py）：config / settings / personas / models / providers / tools / skills / mcp / extensions / export / import。

mixin 由 DashboardManager 组合，HTTP 路由路径不变（路由表仍在 manager.py）。
"""
from __future__ import annotations

import asyncio
import io
import json
import re
import zipfile
from dataclasses import fields as dc_fields
from pathlib import Path

from .. import texts, utils
from ..Config import QvQConfig
from ..engine.base import ChatRequest

# 去隐私：键名命中即掩码（providers api_key / mcp headers / config 敏感字段 / KV 内嵌密钥）
_SENSITIVE_KEY_RE = re.compile(r"api[_-]?key|apikey|secret|token|password|authorization", re.I)
_SENSITIVE_MARK = "«removed»"


def _sanitize_value(value):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and _SENSITIVE_KEY_RE.search(k) and v not in (None, "", [], {}):
                out[k] = _SENSITIVE_MARK
            else:
                out[k] = _sanitize_value(v)
        return out
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


def _sanitize_payload(payload: dict) -> dict:
    return _sanitize_value(payload)


class ConfigApiMixin:
    """依赖宿主提供 self.main / self.sdk。"""

    def _config_snapshot(self) -> dict:
        return {f.name: getattr(self.main.cfg, f.name, None) for f in dc_fields(QvQConfig)}

    async def models_get(self, request):
# 首次打开面板时用 models.dev 回填缺失的能力/上下文/价格；失败或超时不影响页面
        try:
            await asyncio.wait_for(self.main.pool.enrich_all_providers(), timeout=8)
        except Exception:
            pass
        providers = []
        for p in self.main.pool.list_providers():
            item = dict(p)
            key = item.get("api_key") or ""
            item["api_key_masked"] = ("*" * 8 + key[-4:]) if len(key) > 4 else ("*" * len(key) if key else "")
            item.pop("api_key", None)
            item.setdefault("enabled", True)  # provider 级开关（临时下线整家）
            providers.append(item)
        by_id = {str(p.get("id") or ""): p for p in self.main.pool.list_providers()}
        chain = []
        for entry in self.main.pool.model_chain():
            provider = by_id.get(entry["provider"]) or {}
            model = next(
                (m for m in provider.get("models") or [] if isinstance(m, dict) and str(m.get("id") or "") == entry["model"]),
                None,
            )
            if model is None:
                continue
            chain.append(
                {
                    "provider": entry["provider"],
                    "name": provider.get("name", ""),
                    "base_url": provider.get("base_url", ""),
                    "model": model,
                }
            )
        return {
            "providers": providers,
            "chain": chain,
            "models": self.main.pool.list_models(),
            "presets": self.main.pool.presets(),
            "default": getattr(self.main.cfg, "default_model", ""),
        }

    async def chain_save(self, request):
        body = await request.json()
        chain = (body or {}).get("chain")
        if not isinstance(chain, list):
            return ({"error": "chain list required"}, 400)
        return {"ok": True, "chain": self.main.pool.save_chain(chain)}

    async def providers_save(self, request):
        body = dict(await request.json() or {})
        self.main.audit("providers_save", {"id": str(body.get("id") or ""), "models": len(body.get("models") or [])})
        enriched = 0
        models = body.get("models")
        if isinstance(models, list):
            try:
                body["models"], enriched = await asyncio.wait_for(
                    self.main.pool.enrich_models(body, models), timeout=8
                )
            except Exception:
                pass
        try:
            entry = self.main.pool.save_provider(body)
            return {"ok": True, "provider": {**entry, "api_key": ""}, "enriched": enriched}
        except Exception as e:
            return ({"error": str(e)}, 400)

    async def provider_toggle(self, request):
        """临时禁用/启用整个模型池（enabled=false 下线，链路跳过；模型配置不动）。"""
        body = await request.json()
        provider_id = str((body or {}).get("id") or "")
        provider = self.main.pool.get_provider(provider_id)
        if provider is None:
            return ({"error": "provider not found"}, 404)
        enabled = bool((body or {}).get("enabled", True))
        self.main.pool.save_provider({**provider, "enabled": enabled})
        self.main.audit("provider_toggle", {"id": provider_id, "enabled": enabled})
        return {"ok": True, "id": provider_id, "enabled": enabled}

    async def models_detect(self, request):
        body = await request.json()
        model_id = str((body or {}).get("model") or "").strip()
        if not model_id:
            return ({"error": "model required"}, 400)
        provider = (body or {}).get("provider")
        if not isinstance(provider, dict):
            provider = {}
        try:
            meta = await asyncio.wait_for(self.main.pool.detect_model(provider, model_id), timeout=8)
        except Exception as e:
            return ({"error": str(e)}, 502)
        return {"ok": True, "model": model_id, "meta": meta}

    async def models_enrich(self, request):
        try:
            updated = await asyncio.wait_for(self.main.pool.enrich_all_providers(force=True), timeout=30)
        except Exception as e:
            return ({"error": str(e)}, 502)
        return {"ok": True, "updated": updated}

    async def providers_delete(self, request):
        body = await request.json()
        provider_id = str((body or {}).get("id") or "")
        snapshot = self.main.pool.get_provider(provider_id) or {}
        ok = self.main.pool.delete_provider(provider_id)
        undo = self._trash_put("provider", snapshot) if ok and snapshot else ""
        return {"ok": ok, "undo": undo}

    async def providers_remote_models(self, request):
        body = await request.json()
        data = dict(body or {})
        if not str(data.get("api_key") or "") and data.get("id"):
            provider_id = str(data.get("id"))
            for p in self.main.pool.list_providers():
                if p.get("id") == provider_id:
                    data["api_key"] = str(p.get("api_key") or "")
                    break
        try:
            models = await self.main.pool.fetch_remote_models(data)
            return {"ok": True, "models": models}
        except Exception as e:
            return ({"error": str(e)}, 502)

    async def models_test(self, request):
        body = await request.json()
        model_id = str((body or {}).get("id") or "")
        started = utils.now_ts()
        try:
            response = await self.main.pool.chat(ChatRequest(messages=[{"role": "user", "content": "ping"}], model=model_id or None))
            return {"ok": True, "reply": response.content or "", "model": response.model, "ms": int((utils.now_ts() - started) * 1000)}
        except Exception as e:
            return {"ok": False, "error": str(e), "ms": int((utils.now_ts() - started) * 1000)}

    async def personas_get(self, request):
# KV 绑定为权威源（会话 state.persona 镜像已废弃）
        return {"personas": self.main.personas.list(), "bindings": self.main.personas.bindings()}

    async def personas_save(self, request):
        body = await request.json()
        try:
            persona = self.main.personas.save(body or {})
            return {"ok": True, "persona": persona}
        except ValueError as e:
            return ({"error": str(e)}, 400)

    async def personas_delete(self, request):
        body = await request.json()
        persona_id = str((body or {}).get("id") or "")
        snapshot = self.main.personas.get(persona_id) or {}
        try:
            ok = self.main.personas.delete(persona_id)
            undo = self._trash_put("persona", snapshot) if ok and snapshot else ""
            return {"ok": ok, "undo": undo}
        except ValueError as e:
            return ({"error": str(e)}, 400)

    async def personas_bind(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        persona = (body or {}).get("persona") or None
# 覆盖/解绑前把既有绑定入回收站（撤销按钮恢复）
        undo = ""
        if chat_key:
            previous = str(self.sdk.storage.get(f"QvQChat:binding:{chat_key}", "") or "")
            if previous and (not persona or str(persona) != previous):
                undo = self._trash_put("binding", {"chat_key": chat_key, "persona": previous})
# 仅写 KV 权威绑定（state.persona 镜像已废弃，不再回写）
        self.main.personas.bind(chat_key, persona)
        return {"ok": True, "undo": undo}

    async def tools_get(self, request):
        tools = []
        for tool in self.main.registry.list():
            tools.append(
                {
                    "name": tool.name,
                    "label": texts.t(f"tool.{tool.name}.name", default=tool.name),
                    "description": texts.t(f"tool.{tool.name}.desc", default=tool.description),
                    "origin": tool.origin,
                    "origin_label": texts.t(f"origin.{tool.origin}", default=tool.origin),
                    "danger": tool.danger,
                    "access": getattr(tool, "access", "admin"),
                }
            )
        tools.sort(key=lambda t: (t["origin"], t["name"]))
        return {
            "tools": tools,
            "disabled": list(getattr(self.main.cfg, "disabled_tools", []) or []),
            "risk": texts.t("tool.risk", default="risk"),
        }

    async def tools_refresh(self, request):
        info = await self.main.eco.refresh()
        return {"ok": True, "info": info}

    async def mcp_get(self, request):
        return {"servers": self.main.mcp.list_servers(), "clients": self.main.mcp.status()}

    async def mcp_save(self, request):
        body = await request.json()
        self.main.audit("mcp_save", {"name": str((body or {}).get("name") or "")})
        try:
            saved = self.main.mcp.save_server(body or {})
        except ValueError as e:
            return ({"error": str(e)}, 400)
        info = None
        error = None
        try:
            info = await self.main.mcp.connect_one(str(saved["name"]), saved)
        except Exception as e:
            error = str(e)
        return {"ok": True, "server": saved, "info": info, "error": error}

    async def mcp_delete(self, request):
        body = await request.json()
        name = str((body or {}).get("name") or "")
        try:
            await self.main.mcp.disconnect(name)
        except Exception as e:
            self.main.logger.debug(f"mcp disconnect on delete failed: {e}")
        return {"ok": self.main.mcp.delete_server(name)}

    async def mcp_connect(self, request):
        body = await request.json()
        name = str((body or {}).get("name") or "")
        server_cfg = None
        for item in self.main.mcp.list_servers():
            if item.get("name") == name:
                server_cfg = item
                break
        if server_cfg is None:
            return ({"error": f"server not found: {name}"}, 404)
        try:
            info = await self.main.mcp.connect_one(name, server_cfg)
            return {"ok": True, "info": info}
        except Exception as e:
            return ({"error": str(e)}, 500)

    async def mcp_disconnect(self, request):
        body = await request.json()
        ok = await self.main.mcp.disconnect(str((body or {}).get("name") or ""))
        return {"ok": ok}

    async def extensions_get(self, request):
        return {
            "info": dict(self.main.eco.info),
            "extensions": self.main.eco.extensions_status(),
        }

    async def onboarding_get(self, request):
        """初始化引导数据：哪些生态模块贡献了「使用建议」+ 当前注入开关状态。"""
        eco = getattr(self.main, "eco", None)
        modules = eco.external_prompt_modules() if eco is not None and hasattr(eco, "external_prompt_modules") else []
        excluded = set(getattr(self.main.cfg, "eco_prompt_exclude", None) or [])
        return {
            "modules": [
                {**m, "injected": m["module"] not in excluded}
                for m in modules
            ],
            "excluded": sorted(excluded),
        }

    async def onboarding_set(self, request):
        """保存引导选择：{module: bool}——True 注入使用建议，False 仅保留工具。"""
        body = await request.json()
        choices = (body or {}).get("choices")
        if not isinstance(choices, dict):
            return ({"error": "choices object required"}, 400)
        current = set(getattr(self.main.cfg, "eco_prompt_exclude", None) or [])
        for module, want in choices.items():
            name = str(module)
            if bool(want):
                current.discard(name)
            else:
                current.add(name)
        self.sdk.config.setConfig("QvQChat.eco_prompt_exclude", sorted(current))
        try:
            setattr(self.main.cfg, "eco_prompt_exclude", sorted(current))
        except Exception:
            pass
        return {"ok": True, "excluded": sorted(current)}

    async def skills_get(self, request):
        return {"skills": self.main.skills.list_skills()}

    async def skills_save(self, request):
        body = await request.json()
        try:
            skill = self.main.skills.save_skill(
                str((body or {}).get("name") or ""),
                str((body or {}).get("description") or ""),
                str((body or {}).get("body") or ""),
            )
            return {"ok": True, "skill": skill}
        except (ValueError, OSError) as e:
            return ({"error": str(e)}, 400)

    async def skills_delete(self, request):
        body = await request.json()
        name = str((body or {}).get("name") or "")
        snapshot = self.main.skills.get_skill(name) or {}
        ok = self.main.skills.delete_skill(name)
        undo = self._trash_put("skill", snapshot) if ok and snapshot else ""
        return {"ok": ok, "undo": undo}

    async def skills_enabled(self, request):
        body = await request.json()
        name = str((body or {}).get("name") or "")
        self.main.skills.set_enabled(name, bool((body or {}).get("enabled")))
        return {"ok": True}

    async def skills_export(self, request):
        skills = self.main.skills.list_skills()
        return {
            "skills": [
                {"name": s["name"], "description": s.get("description", ""), "body": s.get("body", "")}
                for s in skills
            ]
        }

    async def export_data(self, request):
        """全量导出。

        format=json（默认，向后兼容：结构化段落，供 import_data 回导）
        format=zip：data.json（同 json 载荷 + 全量 KV/会话）+ 工作目录/上传/文档缓存文件。
        sanitize=1：去隐私——providers 密钥、config/mcp/storage 中敏感键名值置 «removed»。
        domains=a,b,c：内容选择（结构化段 config/models/personas/tasks/memory/skills/mcp +
        存储域 sessions/memories/profiles/knowledge/audit/usage/participation/shares/recall/
        pending/trash/docs/settings/other + 文件域 uploads/work/docs_cache），空 = 全部。
        """
        from ..conversation.memory import MEM_PREFIX
        from .api_ops import PROTECTED_KEYS, STORAGE_FILE_DOMAINS, _storage_domain_of

# query_params 缺失（旧测试桩直调）时按无参数处理
        qp = getattr(request, "query_params", None)
        qp_get = qp.get if hasattr(qp, "get") else (lambda name, default="": default)
        sanitize = str(qp_get("sanitize", "") or "") in ("1", "true", "yes")
        domains_raw = str(qp_get("domains", "") or "")
        domains = {d.strip() for d in domains_raw.split(",") if d.strip()}
        want = (lambda section: True) if not domains else (lambda section: section in domains)

        memory = {}
        storage_dump: dict = {}
        for key in self.sdk.storage.keys():
            if not isinstance(key, str) or key in PROTECTED_KEYS:
                continue
            bucket = _storage_domain_of(key)
            if not want(bucket):
                continue
            if key.startswith(MEM_PREFIX):
                entries = self.sdk.storage.get(key, [])
                if entries:
                    memory[key[len(MEM_PREFIX):]] = entries
# 全量 KV 落盘（会话/事实/画像/知识库/identity/routes/todo… 一个不漏）
            if key.startswith("QvQChat:"):
                try:
                    storage_dump[key] = self.sdk.storage.get(key, None)
                except Exception:
                    continue
        payload = {
            "version": 4,
            "exported_at": utils.now_ts(),
            "sanitize": sanitize,
            "providers": self.main.pool.list_providers() if want("models") else [],
            "chain": self.main.pool.model_chain() if want("models") else [],
            "personas": {
                pid: data
                for pid, data in (self.sdk.storage.get("QvQChat:personas", {}) or {}).items()
            } if want("personas") else {},
            "tasks": self.main.scheduler.list() if want("tasks") else [],
            "memory": memory if want("memory") else {},
            "mcp": self.main.mcp.list_servers() if want("mcp") else [],
            "skills": self.main.skills.list_skills() if want("skills") else [],
            "config": self._config_snapshot() if want("config") else {},
            "storage": storage_dump,
        }
        if domains:
            payload["domains"] = sorted(domains)
        if sanitize:
            payload = _sanitize_payload(payload)

        if str(qp_get("format", "") or "") != "zip":
            return payload
        return self._export_zip(payload, sanitize, [d for d in STORAGE_FILE_DOMAINS if want(d[0])])

    def _export_zip(self, payload: dict, sanitize: bool, file_domains=None):
        """zip 包：data.json + 工作目录/上传/文档缓存全部文件（AI 生成内容随包带走）。"""
        from .api_ops import STORAGE_FILE_DOMAINS

        buf = io.BytesIO()
        files_included = 0
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            import json

            zf.writestr("data.json", json.dumps(payload, ensure_ascii=False, default=str))
            for domain, path in (file_domains if file_domains is not None else STORAGE_FILE_DOMAINS):
                root = Path(path)
                if not root.exists():
                    continue
                for item in root.rglob("*"):
                    if not item.is_file():
                        continue
                    try:
                        arc = f"{domain}/{item.relative_to(root).as_posix()}"
                        zf.write(item, arc)
                        files_included += 1
                    except OSError:
                        continue
            zf.writestr("manifest.json", json.dumps({
                "module": "ErisPulse-QvQChat",
                "version": utils.module_version(),
                "exported_at": utils.now_ts(),
                "sanitize": sanitize,
                "files_included": files_included,
            }, ensure_ascii=False))
        from datetime import datetime as _dt

        stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
        name = f"qvqchat-export-{stamp}{'-sanitized' if sanitize else ''}.zip"
        from starlette.responses import Response

        return Response(
            buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={name}"},
        )

    async def import_data(self, request):
        body = await request.json()
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return ({"error": "data object required"}, 400)
        sections = (body or {}).get("sections")
        strategies = (body or {}).get("strategies") or {}
        applied, errors = self._apply_import(data, sections, strategies)
        if applied:
            self.main.audit("import_data", {"sections": applied})
        result = {"ok": True, "applied": applied}
        if errors:
            result["errors"] = errors
        return result

    def _mode_of(self, strategies, section: str) -> str:
        """合并策略：overwrite 覆盖 / append 追加（只补缺失）/ skip 跳过。"""
        mode = ""
        if isinstance(strategies, dict):
            mode = str(strategies.get(section) or "").strip().lower()
        return mode if mode in ("overwrite", "append", "skip") else "overwrite"

    def _apply_import(self, data: dict, sections, strategies) -> tuple[list, dict]:
        """按 sections 选择 + per-section 策略回导；返回 (applied, errors)。sections 空 = 全部。"""
        applied = []
        errors: dict = {}

        def want(section: str) -> bool:
            return not isinstance(sections, (list, set)) or section in sections

# ---- models（providers + 链）----
        if want("models"):
            mode = self._mode_of(strategies, "models")
            if mode != "skip":
                known_ids = {p.get("id") for p in self.main.pool.list_providers()}
                if isinstance(data.get("providers"), list):
                    for provider in data["providers"]:
                        if not isinstance(provider, dict):
                            continue
                        if mode == "append" and provider.get("id") in known_ids:
                            continue  # 追加：已存在的不动
                        try:
                            self.main.pool.save_provider(provider)
                        except Exception as e:
                            errors.setdefault("providers", []).append(str(e))
                    applied.append("providers")
                elif isinstance(data.get("models"), list):
                    for model in data["models"]:
                        try:
                            self.main.pool.save_provider({
                                "id": "imported",
                                "name": "Imported",
                                "base_url": model.get("base_url", ""),
                                "api_key": model.get("api_key", ""),
                                "models": [{"id": model.get("model", ""), "enabled": True}],
                            })
                        except Exception as e:
                            errors.setdefault("models", []).append(str(e))
                    applied.append("models")
                if isinstance(data.get("chain"), list) and mode == "overwrite":
                    self.main.pool.save_chain(data["chain"])
                    applied.append("chain")

# ---- personas ----
        if want("personas") and isinstance(data.get("personas"), dict):
            mode = self._mode_of(strategies, "personas")
            if mode != "skip":
                stored = self.sdk.storage.get("QvQChat:personas", {})
                if not isinstance(stored, dict):
                    stored = {}
                for pid, persona in data["personas"].items():
                    if mode == "append" and pid in stored:
                        continue  # 追加：已有人格不动
                    stored[pid] = persona
                self.sdk.storage.set("QvQChat:personas", stored)
                applied.append("personas")

# ---- tasks ----
        if want("tasks") and isinstance(data.get("tasks"), list):
            mode = self._mode_of(strategies, "tasks")
            if mode != "skip":
                existing = self.main.scheduler.list()
                if mode == "overwrite":
                    replaced = []
                    for task in data["tasks"]:
                        if isinstance(task, dict):
                            task.setdefault("managed_by", "")
                            task.setdefault("cron_ref", "")
                            replaced.append(task)
                    existing = replaced  # 覆盖：导入列表整体替换
                else:  # append：只补缺失 id
                    known = {t.get("id") for t in existing}
                    for task in data["tasks"]:
                        if isinstance(task, dict) and task.get("id") not in known:
                            task.setdefault("managed_by", "")
                            task.setdefault("cron_ref", "")
                            existing.append(task)
                if data["tasks"]:
                    self.main.scheduler._save(existing)
                applied.append("tasks")

# ---- memory ----
        if want("memory") and isinstance(data.get("memory"), dict):
            mode = self._mode_of(strategies, "memory")
            if mode != "skip":
                from ..conversation.memory import MEM_PREFIX

                for chat_key, entries in data["memory"].items():
                    if not isinstance(entries, list):
                        continue
                    if mode == "append":
                        old = self.sdk.storage.get(MEM_PREFIX + str(chat_key), [])
                        old = old if isinstance(old, list) else []
                        seen = {json.dumps(e, sort_keys=True, default=str) for e in old}
                        for entry in entries:
                            mark = json.dumps(entry, sort_keys=True, default=str)
                            if mark not in seen:
                                old.append(entry)
                                seen.add(mark)
                        self.sdk.storage.set(MEM_PREFIX + str(chat_key), old)
                    else:
                        self.sdk.storage.set(MEM_PREFIX + str(chat_key), entries)
                applied.append("memory")

# ---- mcp ----
        if want("mcp") and isinstance(data.get("mcp"), list) and data["mcp"]:
            mode = self._mode_of(strategies, "mcp")
            if mode != "skip":
                servers = [s for s in data["mcp"] if isinstance(s, dict)]
                if mode == "append":
                    existing = {s.get("name"): s for s in self.main.mcp.list_servers() if isinstance(s, dict)}
                    for server in servers:
                        if server.get("name") not in existing:
                            existing[server.get("name")] = server
                    self.main.mcp.replace_servers(list(existing.values()))
                else:
                    self.main.mcp.replace_servers(servers)
                applied.append("mcp")

# ---- skills ----
        if want("skills") and isinstance(data.get("skills"), list):
            mode = self._mode_of(strategies, "skills")
            if mode != "skip":
                known_names = {s.get("name") for s in self.main.skills.list_skills()}
                for s in data["skills"]:
                    if not (isinstance(s, dict) and s.get("name")):
                        continue
                    if mode == "append" and s.get("name") in known_names:
                        continue  # 追加：同名技能不动
                    try:
                        self.main.skills.save_skill(
                            str(s.get("name")),
                            str(s.get("description") or ""),
                            str(s.get("body") or ""),
                        )
                    except (ValueError, OSError) as e:
                        errors.setdefault("skills", []).append(f"{s.get('name')}: {e}")
                applied.append("skills")

# ---- config ----
        if want("config") and isinstance(data.get("config"), dict) and data["config"]:
            mode = self._mode_of(strategies, "config")
            if mode != "skip":
# 配置回灌走统一校验 seam（与 dashboard/AI 工具同一 coerce），坏值拒收不落盘
                applied_cfg, rejected = [], {}
                for key, value in data["config"].items():
                    ok, coerced, err = QvQConfig.coerce(str(key), value)
                    if ok:
                        self.sdk.config.setConfig(f"QvQChat.{key}", coerced)
                        applied_cfg.append(str(key))
                    else:
                        rejected[str(key)] = err
                if applied_cfg:
                    applied.append("config")
                if rejected:
                    errors["config"] = rejected

# ---- storage（全量 KV 回灌；append = 只补缺失键，覆盖已有键请用 overwrite）----
        if want("storage") and isinstance(data.get("storage"), dict) and data["storage"]:
            mode = self._mode_of(strategies, "storage")
            if mode != "skip":
                from .api_ops import PROTECTED_KEYS

                written = 0
                for key, value in data["storage"].items():
                    if not isinstance(key, str) or not key.startswith("QvQChat:") or key in PROTECTED_KEYS:
                        continue
                    if mode == "append" and self.sdk.storage.get(key, None) is not None:
                        continue  # 追加：已有键不动
                    self.sdk.storage.set(key, value)
                    written += 1
                if written:
                    applied.append("storage")
        return applied, errors

    async def import_zip(self, request):
        """zip 导入：data_b64（base64）+ sections/strategies；peek=1 只探测不落盘。"""
        import base64
        import json as _json

        body = await request.json()
        body = body or {}
        try:
            zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(str(body.get("data_b64") or ""))))
        except Exception:
            return ({"error": "invalid zip"}, 400)
        try:
            payload = _json.loads(zf.read("data.json").decode("utf-8"))
        except KeyError:
            return ({"error": "data.json missing in zip"}, 400)
        except Exception as e:
            return ({"error": f"data.json parse failed: {e}"}, 400)
        if not isinstance(payload, dict):
            return ({"error": "data.json invalid"}, 400)
        sections = body.get("sections")
        strategies = body.get("strategies") or {}
        if body.get("peek"):
            return {
                "sections": [k for k in ("models", "personas", "tasks", "memory", "mcp",
                                         "skills", "config", "storage") if isinstance(payload.get(k), (list, dict)) and payload.get(k)],
                "files": sorted({n.split("/", 1)[0] for n in zf.namelist() if "/" in n and not n.endswith("/")}),
                "version": payload.get("version"),
                "sanitize": bool(payload.get("sanitize")),
            }
        applied, errors = self._apply_import(payload, sections, strategies)
# 文件还原：files 域的合并策略（overwrite 覆盖 / append 只补缺失 / skip）
        file_mode = self._mode_of(strategies, "files")
        files_restored = 0
        if file_mode != "skip":
            from .api_ops import STORAGE_FILE_DOMAINS

            paths = {domain: Path(path) for domain, path in STORAGE_FILE_DOMAINS}
            for name in zf.namelist():
                if "/" not in name or name.endswith("/"):
                    continue
                domain, rel = name.split("/", 1)
                root = paths.get(domain)
                if root is None or not rel or ".." in Path(rel).parts:
                    continue  # 越界/未知域一律拒写
                target = root / rel
                if file_mode == "append" and target.exists():
                    continue
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
                    files_restored += 1
                except OSError as e:
                    errors.setdefault("files", []).append(f"{name}: {e}")
        result = {"ok": True, "applied": applied, "files_restored": files_restored}
        if errors:
            result["errors"] = errors
        return result

    async def config_get(self, request):
        from ErisPulse.Core import i18n

        fields = []
        for f in dc_fields(QvQConfig):
            meta = f.metadata or {}
            desc = meta.get("description") or {}
            if isinstance(desc, dict):
                text = str(desc.get("default") or "")
                key = desc.get("i18n")
                if key:
                    try:
                        text = i18n.t(key, default=text)
                    except Exception:
                        pass
            else:
                text = str(desc)
            ui = meta.get("ui") or {}
            value = getattr(self.main.cfg, f.name, None)
            secret = bool(ui.get("secret"))
            if secret and value not in (None, ""):
# secret 值掩码回显：真实值不进浏览器
                value = "******"
            fields.append(
                {
                    "key": f.name,
                    "value": value,
                    "description": text,
                    "group": str(ui.get("group") or "other"),
                    "order": ui.get("order", 99),
                    "widget": str(ui.get("widget") or "text"),
                    "options": ui.get("options"),
                    "type": QvQConfig.type_of(f.name),
                    "min": ui.get("min"),
                    "max": ui.get("max"),
                    "step": ui.get("step"),
                    "placeholder": ui.get("placeholder"),
                    "secret": secret,
                    "dangerous": bool(ui.get("dangerous")),
                    "items": ui.get("items"),
                }
            )
        return {"fields": fields, "groups": QvQConfig.groups()}

    async def config_set(self, request):
        body = await request.json()
        if not isinstance(body, dict):
            return ({"error": "body must be an object"}, 400)
        applied = []
        errors: dict[str, str] = {}
        for key, value in body.items():
            ok, coerced, err = QvQConfig.coerce(str(key), value)
            if ok:
                self.sdk.config.setConfig(f"QvQChat.{key}", coerced)
                applied.append(str(key))
            else:
                errors[str(key)] = err
        if errors:
            return ({"ok": False, "applied": applied, "errors": errors}, 400)
        if applied:
            self.main.audit("config_set", {"keys": applied})
        return {"ok": True, "applied": applied}

    # ===== 插件设置（框架声明式配置流：qvq_settings 仅作归属标记） =====

    def _plugin_catalog(self) -> dict:
        catalog = getattr(self.main, "plugin_settings_catalog", None)
        return catalog if isinstance(catalog, dict) else {}

    def _plugin_config_class(self, module: str):
        """模块注册名 → ConfigClass（与 Dashboard 同源：sdk.module._module_classes）。"""
        module_class = (getattr(self.sdk.module, "_module_classes", None) or {}).get(module)
        if module_class is None:
            return None
        return getattr(module_class, "ConfigClass", None)

    async def plugin_settings_get(self, request):
        from ErisPulse.runtime.config_schema import resolve_config_schema

        modules = []
        for name, title in sorted(self._plugin_catalog().items()):
            config_class = self._plugin_config_class(name)
            if config_class is None:
                continue  # 无 ConfigClass 无法走框架 schema 流，不出现在设置页
            try:
                schema = resolve_config_schema(config_class)
            except Exception as e:
                self.main.logger.debug(f"plugin config schema resolve failed ({name}): {e}")
                continue
            try:
                values = self.sdk.config.getConfig(name)
            except Exception:
                values = None
            modules.append(
                {
                    "module": name,
                    "title": title or name,
                    "config_key": name,  # 配置键 = 模块注册名（与框架 BaseModule 一致）
                    "schema": schema,
                    "values": dict(values) if isinstance(values, dict) else {},
                }
            )
        return {"modules": modules}

    async def plugin_settings_save(self, request):
        from ErisPulse.runtime.config_schema import dict_to_dataclass, validate_config

        body = await request.json()
        if not isinstance(body, dict):
            return ({"error": "body must be an object"}, 400)
        module = str(body.get("module") or "")
        values = body.get("values")
        if module not in self._plugin_catalog():
            return ({"error": f"unknown module: {module}"}, 400)
        if not isinstance(values, dict):
            return ({"error": "values must be an object"}, 400)
        config_class = self._plugin_config_class(module)
        if config_class is None:
            return ({"error": f"module has no config schema: {module}"}, 400)
        try:
            current = self.sdk.config.getConfig(module)
        except Exception:
            current = None
        merged = {**(current if isinstance(current, dict) else {}), **values}
        try:
            config_instance = dict_to_dataclass(config_class, merged)
        except Exception as e:
            return ({"ok": False, "applied": [], "errors": {"": str(e)}}, 400)
        errors_list = validate_config(config_instance)
        if errors_list:
# 校验错误按提交键归位（前端字段级红字；嵌套字段消息带 "outer.inner:" 前缀同样按子键命中），
# 归不进任何提交键的单条挂到 ""（全局）
            errors: dict[str, str] = {}
            for msg in errors_list:
                target = ""
                for key in sorted((str(k) for k in values), key=len, reverse=True):
                    if msg.startswith(f"{key}:") or key in msg:
                        target = key
                        break
                errors[target] = f"{errors[target]}; {msg}" if target in errors else msg
            return ({"ok": False, "applied": [], "errors": errors}, 400)
# 逐键 setConfig（写 coerce 规范化后的全量生效值）：触发框架 config.set 热更新（模块 on_config_update 由框架自动跟进）
        from dataclasses import asdict

        applied_values = asdict(config_instance)
        for key, value in applied_values.items():
            self.sdk.config.setConfig(f"{module}.{key}", value)
        try:
            await self.sdk.lifecycle.emit("qvq.plugin_config", {"module": module, "values": applied_values})
        except Exception as e:
            self.main.logger.debug(f"plugin_config emit failed: {e}")
        return {"ok": True, "applied": [str(k) for k in values]}
