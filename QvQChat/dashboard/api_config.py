"""配置域 API（拆分自 dashboard/manager.py）：config / settings / personas / models / providers / tools / skills / mcp / extensions / export / import。

mixin 由 DashboardManager 组合，HTTP 路由路径不变（路由表仍在 manager.py）。
"""
from __future__ import annotations

from dataclasses import fields as dc_fields

from .. import texts, utils
from ..Config import QvQConfig
from ..engine.base import ChatRequest


class ConfigApiMixin:
    """依赖宿主提供 self.main / self.sdk。"""

    def _config_snapshot(self) -> dict:
        return {f.name: getattr(self.main.cfg, f.name, None) for f in dc_fields(QvQConfig)}

    async def models_get(self, request):
        providers = []
        for p in self.main.pool.list_providers():
            item = dict(p)
            key = item.get("api_key") or ""
            item["api_key_masked"] = ("*" * 8 + key[-4:]) if len(key) > 4 else ("*" * len(key) if key else "")
            item.pop("api_key", None)
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
        body = await request.json()
        try:
            entry = self.main.pool.save_provider(body or {})
            return {"ok": True, "provider": {**entry, "api_key": ""}}
        except Exception as e:
            return ({"error": str(e)}, 400)

    async def providers_delete(self, request):
        body = await request.json()
        ok = self.main.pool.delete_provider(str((body or {}).get("id") or ""))
        return {"ok": ok}

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
        try:
            ok = self.main.personas.delete(str((body or {}).get("id") or ""))
            return {"ok": ok}
        except ValueError as e:
            return ({"error": str(e)}, 400)

    async def personas_bind(self, request):
        body = await request.json()
        chat_key = str((body or {}).get("chat_key") or "")
        persona = (body or {}).get("persona") or None
# 仅写 KV 权威绑定（state.persona 镜像已废弃，不再回写）
        self.main.personas.bind(chat_key, persona)
        return {"ok": True}

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
        ok = self.main.skills.delete_skill(str((body or {}).get("name") or ""))
        return {"ok": ok}

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
        from ..conversation.memory import MEM_PREFIX

        memory = {}
        for key in self.sdk.storage.keys():
            if isinstance(key, str) and key.startswith(MEM_PREFIX):
                entries = self.sdk.storage.get(key, [])
                if entries:
                    memory[key[len(MEM_PREFIX):]] = entries
        return {
            "version": 3,
            "exported_at": utils.now_ts(),
            "providers": self.main.pool.list_providers(),
            "chain": self.main.pool.model_chain(),
            "personas": {
                pid: data
                for pid, data in (self.sdk.storage.get("QvQChat:personas", {}) or {}).items()
            },
            "tasks": self.main.scheduler.list(),
            "memory": memory,
            "mcp": self.main.mcp.list_servers(),
            "skills": self.main.skills.list_skills(),
            "config": self._config_snapshot(),
        }

    async def import_data(self, request):
        body = await request.json()
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return ({"error": "data object required"}, 400)
        applied = []
        errors: dict = {}
        if isinstance(data.get("providers"), list):
            for provider in data["providers"]:
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
        if isinstance(data.get("chain"), list):
            self.main.pool.save_chain(data["chain"])
            applied.append("chain")
        if isinstance(data.get("personas"), dict):
            stored = self.sdk.storage.get("QvQChat:personas", {})
            if not isinstance(stored, dict):
                stored = {}
            stored.update(data["personas"])
            self.sdk.storage.set("QvQChat:personas", stored)
            applied.append("personas")
        if isinstance(data.get("tasks"), list):
            existing = self.main.scheduler.list()
            known = {t.get("id") for t in existing}
            for task in data["tasks"]:
                if isinstance(task, dict) and task.get("id") not in known:
                    task.setdefault("managed_by", "")
                    task.setdefault("cron_ref", "")
                    existing.append(task)
            if data["tasks"]:
                self.main.scheduler._save(existing)
            applied.append("tasks")
        if isinstance(data.get("memory"), dict):
            from ..conversation.memory import MEM_PREFIX

            for chat_key, entries in data["memory"].items():
                if isinstance(entries, list):
                    self.sdk.storage.set(MEM_PREFIX + str(chat_key), entries)
            applied.append("memory")
        if isinstance(data.get("mcp"), list):
            self.main.mcp.replace_servers([s for s in data["mcp"] if isinstance(s, dict)])
            applied.append("mcp")
        if isinstance(data.get("skills"), list):
            for s in data["skills"]:
                if isinstance(s, dict) and s.get("name"):
                    try:
                        self.main.skills.save_skill(
                            str(s.get("name")),
                            str(s.get("description") or ""),
                            str(s.get("body") or ""),
                        )
                    except (ValueError, OSError) as e:
                        errors.setdefault("skills", []).append(f"{s.get('name')}: {e}")
            applied.append("skills")
        if isinstance(data.get("config"), dict):
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
        result = {"ok": True, "applied": applied}
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
