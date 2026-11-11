from __future__ import annotations

import asyncio

from .. import utils
from ..agent.tools import Tool
from ..utils import sanitize_name, schema_from_signature

PREFIX = "eco_"
SCHEMA_SERVICE = "qvq_schemas"
PERSONAS_SERVICE = "qvq_personas"
SETTINGS_SERVICE = "qvq_settings"
ACCESS_SERVICE = "qvq_access"
EXTENSIONS_SERVICE = "qvq_extensions"
EXT_CALL_TIMEOUT = 15.0


def _match_service_rules(module: str, service: str, rules) -> bool:
    """「模块:服务」规则匹配：两侧均支持前缀通配；只写模块名等价于该模块全部服务。"""
    for entry in rules or []:
        text = str(entry or "").strip()
        if not text:
            continue
        if ":" in text:
            mod_pat, _, svc_pat = text.partition(":")
        else:
            mod_pat, svc_pat = text, "*"
        if utils.match_pattern(module, [mod_pat]) and utils.match_pattern(service, [svc_pat]):
            return True
    return False


class EcosystemBridge:
    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self.registry = main.registry
        self._refresh_task: asyncio.Task | None = None
        self.info: dict = {"modules": 0, "tools": 0, "updated": 0.0}
        self._schemas: dict[str, dict] = {}
        self._access: dict[str, dict[str, str]] = {}
        self._ext_skills: list[dict] = []
        self._ext_knowledge: list[dict] = []
        self._ext_prompts: list[dict] = []
        self._ext_personas: dict[str, list[str]] = {}
        self._prev_ext_personas: dict[str, list[str]] = {}

    def start(self) -> None:
        try:
            self.sdk.lifecycle.register("module.load", self._on_modules_changed)
            self.sdk.lifecycle.register("module.unload", self._on_modules_changed)
        except Exception as e:
            self.main.logger.warning(f"lifecycle register failed: {e}")

    async def _on_modules_changed(self, data) -> None:
        self.schedule_refresh()

    def schedule_refresh(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        self._refresh_task = asyncio.ensure_future(self._delayed_refresh())

    async def _delayed_refresh(self) -> None:
        await asyncio.sleep(1.0)
        try:
            info = await self.refresh()
            self.main.logger.info(f"ecosystem bridge refreshed: {info}")
        except Exception as e:
            self.main.logger.warning(f"ecosystem bridge refresh failed: {e}")

    async def refresh(self) -> dict:
        try:
            catalog = self.sdk.module.services() or {}
        except Exception as e:
            self.main.logger.warning(f"services() unavailable: {e}")
            catalog = {}
        if not isinstance(catalog, dict):
            catalog = {}
        include = set(getattr(self.main.cfg, "eco_include", []) or [])
        exclude = set(getattr(self.main.cfg, "eco_exclude", []) or ["QvQChat"])
        self.registry.unregister_prefix(PREFIX)
        self._schemas = {}
        self._access = {}
        self._ext_skills = []
        self._ext_knowledge = []
        self._ext_prompts = []
        self.main.plugin_settings_catalog = {}
        self._prev_ext_personas = self._ext_personas
        self._ext_personas = {}
        used: set[str] = set()
        tool_count = 0
        module_count = 0
        for module_name, services in catalog.items():
            if module_name in exclude:
                continue
            if include and module_name not in include:
                continue
            if not isinstance(services, list):
                continue
            module_count += 1
            await self._collect_schemas(module_name)
            await self._collect_access(module_name)
            await self._collect_extensions(module_name)
            await self._collect_settings(module_name)
            for service in services:
                tool = self._build_tool(module_name, service, used)
                if tool is None:
                    continue
                self.registry.register(tool)
                used.add(tool.name)
                tool_count += 1
            await self._collect_personas(module_name)
        for ids in self._prev_ext_personas.values():
            self._remove_personas(ids)
        self._prev_ext_personas = {}
        self.info = {"modules": module_count, "tools": tool_count, "updated": utils.now_ts()}
# 防抖热刷新（module.load/unload）后自动重发现参与决策提供者
        participation = getattr(self.main, "participation", None)
        if participation is not None:
            try:
                await participation.discover()
            except Exception as e:
                self.main.logger.debug(f"participation discover failed: {e}")
        return dict(self.info)

    async def _call_optional(self, module: str, service: str):
        try:
            return await self.sdk.module.call(module, service, timeout=EXT_CALL_TIMEOUT)
        except Exception:
            return None

    async def _collect_schemas(self, module: str) -> None:
        schemas = await self._call_optional(module, SCHEMA_SERVICE)
        if isinstance(schemas, dict):
            self._schemas[module] = {
                str(name): schema
                for name, schema in schemas.items()
                if isinstance(schema, dict)
            }

    async def _collect_access(self, module: str) -> None:
        """qvq_access 约定服务：模块自声明哪些服务对所有人开放（"safe"）或仅管理员（"admin"）。"""
        data = await self._call_optional(module, ACCESS_SERVICE)
        if not isinstance(data, dict):
            return
        declared = {}
        for name, value in data.items():
            level = str(value or "").strip().lower()
            if level in ("safe", "admin"):
                declared[str(name)] = level
        if declared:
            self._access[module] = declared

    async def _collect_extensions(self, module: str) -> None:
        """qvq_extensions：模块用**一个服务**提交全部贡献（技能 / 知识库条目 / 工具说明）。

        返回 dict：
        - prompts: [str 或 {text, priority?}] 使用建议，注入系统提示由 AI 自行判断
        - skills: [{name, description, body, enabled?}]
        - knowledge: [{title, content, source?, triggers?, priority?, cooldown_min?}]
        条目只读、随模块卸载自动消失；同名内置技能优先，不被覆盖。
        """
        data = await self._call_optional(module, EXTENSIONS_SERVICE)
        if not isinstance(data, dict):
            return
        prompts = data.get("prompts")
        if isinstance(prompts, list):
            for index, item in enumerate(prompts):
                if isinstance(item, str):
                    text, priority = item.strip(), 0
                elif isinstance(item, dict):
                    text = str(item.get("text") or "").strip()
                    priority = item.get("priority", 0)
                else:
                    continue
                if text:
                    self._ext_prompts.append({
                        "text": text,
                        "priority": priority,
                        "module": module,
                        "index": index,
                    })
        skills = data.get("skills")
        if isinstance(skills, list):
            for index, item in enumerate(skills):
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                body = str(item.get("body") or "").strip()
                if not name or not body:
                    continue
                self._ext_skills.append({
                    "name": name,
                    "description": str(item.get("description") or "").strip(),
                    "body": body,
                    "enabled": bool(item.get("enabled", True)),
                    "module": module,
                    "index": index,
                })
        knowledge = data.get("knowledge")
        if isinstance(knowledge, list):
            for index, item in enumerate(knowledge):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                content = str(item.get("content") or "").strip()
                if not title or not content:
                    continue
                self._ext_knowledge.append({
                    "title": title,
                    "content": content,
                    "source": str(item.get("source") or module).strip(),
                    "triggers": item.get("triggers") or [],
                    "priority": item.get("priority", 0),
                    "cooldown_min": item.get("cooldown_min"),
                    "module": module,
                    "index": index,
                })

    def external_prompts(self) -> list[str]:
        """模块贡献的使用建议（按 priority 降序；注入系统提示，由 AI 自行判断）。

        初始化引导面：用户可按模块排除注入（QvQChat.eco_prompt_exclude，
        首启引导面板写这里）——模块服务照常桥接成工具，只是"使用建议"
        不再进系统提示（AI 仍可从工具列表发现能力）。
        """
        excluded = set(self.main_eco_prompt_exclude())
        ordered = sorted(
            (p for p in self._ext_prompts if p["module"] not in excluded),
            key=lambda item: (-float(item.get("priority", 0) or 0), item["module"], item["index"]),
        )
        return [item["text"] for item in ordered]

    def external_prompt_modules(self) -> list[dict]:
        """引导面数据：有注入建议的模块清单（模块名/条数/首条摘要）。"""
        by_module: dict[str, list] = {}
        for item in self._ext_prompts:
            by_module.setdefault(item["module"], []).append(item)
        return [
            {
                "module": module,
                "count": len(items),
                "preview": str(items[0].get("text") or "")[:80],
            }
            for module, items in sorted(by_module.items())
        ]

    def main_eco_prompt_exclude(self) -> list:
        try:
            value = getattr(self.main.cfg, "eco_prompt_exclude", None)
            return value if isinstance(value, list) else []
        except Exception:
            return []

    def external_skills(self) -> list[dict]:
        """模块贡献的技能（只读，source=module:<模块名>）。"""
        return [dict(item, source=f"module:{item['module']}") for item in self._ext_skills]

    def external_knowledge(self) -> list[dict]:
        """模块贡献的知识库条目（只读，owner=全局；id 形如 ext:<模块>:<序号>）。"""
        result = []
        for item in self._ext_knowledge:
            result.append({
                "id": f"ext:{item['module']}:{item['index']}",
                "title": item["title"],
                "content": item["content"],
                "source": item["source"],
                "triggers": list(item.get("triggers") or []),
                "priority": item.get("priority", 0),
                "cooldown_min": item.get("cooldown_min"),
                "owner": "",
                "external": True,
                "module": item["module"],
            })
        return result

    async def _collect_settings(self, module: str) -> None:
# qvq_settings 只作归属标记（返回 {"title": ...}）：登记"谁出现在设置页插件分区"，
# 字段 schema 与值一律走框架 ConfigClass / sdk.config（异常静默跳过，白名单陷阱同 qvq_schemas）
        raw = await self._call_optional(module, SETTINGS_SERVICE)
        if raw is None:
            return
        title = raw.get("title") if isinstance(raw, dict) else raw
        title = str(title).strip() if title is not None else ""
        self.main.plugin_settings_catalog[module] = title or module

    def _remove_personas(self, ids: list[str]) -> None:
        for pid in ids:
            try:
                self.main.personas.delete(pid)
            except Exception:
                pass

    async def _collect_personas(self, module: str) -> None:
        self._remove_personas(self._prev_ext_personas.pop(module, []))
        data = await self._call_optional(module, PERSONAS_SERVICE)
        if not isinstance(data, list):
            self._ext_personas[module] = []
            return
        ids: list[str] = []
        for index, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            base_id = str(item.get("id") or f"p{index}")
            pid = f"ext.{module}.{base_id}"
# 外部人格全量字段白名单透传（未提供项由 persona.save merge 语义兜底）
            payload = {
                "id": pid,
                "name": str(item.get("name") or base_id),
                "system": str(item.get("system") or ""),
                "opening": item.get("opening"),
                "tools": item.get("tools"),
            }
            for key in ("owner_title", "nickname", "avatar"):
                if item.get(key):
                    payload[key] = item.get(key)
            for key in ("style", "examples", "banned_words", "catchphrases"):
                if item.get(key) is not None:
                    payload[key] = item.get(key)
            try:
                self.main.personas.save(payload)
            except Exception:
                continue
            ids.append(pid)
        self._ext_personas[module] = ids

    def _build_tool(self, module_name: str, service, used: set[str]) -> Tool | None:
        if not isinstance(service, dict):
            return None
        service_name = service.get("name")
        if not service_name:
            return None
        schema = (self._schemas.get(module_name) or {}).get(str(service_name))
        if not (isinstance(schema, dict) and schema.get("type") == "object"):
            try:
                schema = schema_from_signature(service.get("signature") or "()")
            except Exception:
                schema = {"type": "object", "properties": {}, "required": []}
        description = service.get("description") or f"{module_name}.{service_name}"
        base = f"{PREFIX}{sanitize_name(module_name)}_{sanitize_name(service_name)}"
        tool_name = base
        index = 2
        while tool_name in used or self.registry.get(tool_name) is not None:
            tool_name = f"{base}_{index}"
            index += 1

        async def handler(ctx, **kwargs):
            result = await self.sdk.module.call(module_name, service_name, **kwargs)
            return utils.to_text(result)

        return Tool(
            name=tool_name,
            description=f"[{module_name}] {description}",
            parameters=schema,
            handler=handler,
            origin="eco",
            access=self.service_access(module_name, service_name, service),
            meta={"module": module_name, "service": service_name},
        )

    def service_access(self, module: str, service: str, service_meta: dict | None = None) -> str:
        """服务访问级别：运营方覆盖 > 模块自声明 > 条目自带 > 默认档（eco_default_access，默认 safe）。

        声明来源（优先级从高到低）：
        1. 运营方配置 eco_admin / eco_safe（「模块:服务」，两侧支持通配）——最终否决权
        2. qvq_access 约定服务返回的 {"服务名": "safe"|"admin"}
        3. 服务条目自带 access 字段（未来框架透传 metadata 时自动生效）
        4. 默认档走 eco_default_access 配置（默认 safe）

        默认 safe 的理由：默认 admin 会把 TTS/表情包这类表达型生态
        工具对普通成员整体藏起来——模型看不到工具就发不出语音/表情，只能瞎猜
        方法名或把工具名当正文发出去；模块真有危险服务应由其自声明 admin 或
        运营方经 eco_admin 否决，而不是靠默认档兜底误伤。
        """
        cfg = self.main.cfg
        if _match_service_rules(module, service, getattr(cfg, "eco_admin", []) or []):
            return "admin"
        if _match_service_rules(module, service, getattr(cfg, "eco_safe", []) or []):
            return "safe"
        declared = (self._access.get(module) or {}).get(service)
        if declared:
            return declared
        if isinstance(service_meta, dict):
            inline = str(service_meta.get("access") or "").strip().lower()
            if inline in ("safe", "admin"):
                return inline
        return str(getattr(cfg, "eco_default_access", "safe") or "safe").strip().lower()

    def is_safe_service(self, module: str, service: str) -> bool:
        """兼容旧调用名：判定服务是否对所有人开放。"""
        return self.service_access(module, service) == "safe"

    def safe_tool_hint(self, limit: int = 12) -> str:
        """给系统提示的生态能力清单：仅列出非管理员也能用的 eco 工具（一行一个）。"""
        lines: list[str] = []
        for tool in self.registry.list(origin="eco"):
            if getattr(tool, "access", "admin") != "safe":
                continue
            desc = str(getattr(tool, "description", "") or "").split("\n")[0]
            lines.append(f"- {tool.name}: {desc}")
            if len(lines) >= limit:
                break
        return "\n".join(lines)

    def extensions_status(self) -> list[dict]:
        names = set(self._ext_personas) | set(self._schemas)
        names |= {s["module"] for s in self._ext_skills}
        names |= {k["module"] for k in self._ext_knowledge}
        names |= {p["module"] for p in self._ext_prompts}
        result = []
        for module in sorted(names):
            result.append(
                {
                    "module": module,
                    "personas": len(self._ext_personas.get(module, [])),
                    "schemas": len(self._schemas.get(module, {})),
                    "skills": len([s for s in self._ext_skills if s["module"] == module]),
                    "knowledge": len([k for k in self._ext_knowledge if k["module"] == module]),
                    "prompts": len([p for p in self._ext_prompts if p["module"] == module]),
                }
            )
        return result
