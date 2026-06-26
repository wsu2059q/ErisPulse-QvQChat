"""
Dashboard 管理器

注册 Dashboard 视窗和 API 路由，提供 Web 管理界面。
"""

import copy
from typing import Any, Dict

from ErisPulse import sdk

from . import html as html_mod
from . import icons, scripts, styles


class DashboardManager:
    """Dashboard 管理器"""

    ROUTES = [
        ("/api/status", "GET", "_api_status"),
        ("/api/config", "GET", "_api_get_config"),
        ("/api/config", "POST", "_api_save_config"),
        ("/api/models", "GET", "_api_get_models"),
        ("/api/models", "POST", "_api_save_model"),
        ("/api/models/delete", "POST", "_api_delete_model"),
        ("/api/behaviors", "GET", "_api_get_behaviors"),
        ("/api/behaviors", "POST", "_api_save_behavior"),
        ("/api/behaviors/delete", "POST", "_api_delete_behavior"),
        ("/api/test-model", "POST", "_api_test_model"),
        ("/api/agents", "GET", "_api_get_agents"),
        ("/api/agents", "POST", "_api_save_agent"),
        ("/api/agents/delete", "POST", "_api_delete_agent"),
        ("/api/knowledge", "GET", "_api_get_knowledge"),
        ("/api/knowledge", "POST", "_api_save_knowledge"),
        ("/api/knowledge/delete", "POST", "_api_delete_knowledge"),
        ("/api/tools", "GET", "_api_get_tools"),
        ("/api/tools", "POST", "_api_save_tool"),
        ("/api/tools/delete", "POST", "_api_delete_tool"),
        ("/api/groups", "GET", "_api_get_groups"),
        ("/api/groups", "POST", "_api_save_group"),
    ]

    def __init__(self, core):
        self.core = core
        self.sdk = core.sdk
        self.logger = core.logger.get_child("Dashboard")

    @property
    def config(self):
        return self.core.config

    @property
    def model_pool(self):
        return self.core.model_pool

    @property
    def behavior_manager(self):
        return self.core.behavior_manager

    @property
    def ai_engine(self):
        return self.core.ai_engine

    @property
    def multi_agent(self):
        return self.core.multi_agent

    @property
    def knowledge_base(self):
        return self.core.knowledge_base

    @property
    def mcp_manager(self):
        return self.core.mcp_manager

    # ==================== 注册/注销 ====================

    def register(self) -> None:
        self._register_routes()
        self._register_view()

    def unregister(self) -> None:
        self._unregister_routes()
        try:
            if hasattr(self.sdk, "Dashboard") and self.sdk.Dashboard:
                self.sdk.Dashboard.unregister_view("QvQChat")
        except Exception as e:
            self.logger.warning(f"注销 Dashboard 视窗失败: {e}")

    def _register_routes(self) -> None:
        r = self.sdk.router
        registered = set()
        for path, method, handler_name in self.ROUTES:
            key = (path, method)
            if key in registered:
                continue
            registered.add(key)
            try:
                r.register_http_route(
                    "QvQChat",
                    path,
                    handler=getattr(self, handler_name),
                    methods=[method],
                )
            except Exception as e:
                self.logger.warning(f"注册路由 {method} {path} 失败: {e}")

    def _unregister_routes(self) -> None:
        r = self.sdk.router
        seen = set()
        for path, _, _ in self.ROUTES:
            if path in seen:
                continue
            seen.add(path)
            try:
                r.unregister_http_route("QvQChat", path)
            except Exception:
                pass

    def _register_view(self) -> None:
        try:
            if not (hasattr(self.sdk, "Dashboard") and self.sdk.Dashboard):
                self.logger.info("Dashboard 模块未安装，跳过视窗注册")
                return

            # 组装 HTML
            html = html_mod.HTML
            html = html.replace("__ICON_OVERVIEW__", icons.OVERVIEW)
            html = html.replace("__ICON_SETTINGS__", icons.SETTINGS)
            html = html.replace("__ICON_MODELS__", icons.CPU)
            html = html.replace("__ICON_BEHAVIORS__", icons.SETTINGS)
            html = html.replace("__ICON_AGENTS__", icons.USERS)
            html = html.replace("__ICON_BOOK__", icons.BOOK)
            html = html.replace("__ICON_TOOL__", icons.TOOL)
            html = html.replace("__ICON_GROUP__", icons.GROUP)
            html = html.replace("__ICON_PLUS__", icons.PLUS)
            html = html.replace("__ICON_SAVE__", icons.SAVE)
            html = html.replace("__ICON_CLOSE__", icons.CLOSE)

            # 组装 JS
            js = scripts.SCRIPTS
            js = js.replace("__ICON_EDIT__", icons.EDIT)
            js = js.replace("__ICON_TRASH__", icons.TRASH)
            js = js.replace("__ICON_SAVE__", icons.SAVE)
            js = js.replace("__ICON_REFRESH__", icons.REFRESH)

            self.sdk.Dashboard.register_view(
                id="QvQChat",
                title="QvQChat",
                title_en="QvQChat",
                icon_svg=icons.CHAT,
                html_content=html,
                js_content=js,
                css_content=styles.STYLES,
                loader="loadQvQChatView",
                group="group_qvc",
                group_title="QvQChat",
                group_title_en="QvQChat",
            )
            self.logger.info("Dashboard 视窗注册成功")
        except Exception as e:
            self.logger.warning(f"注册 Dashboard 视窗失败: {e}")

    # ==================== API 处理器 ====================

    async def _parse_body(self, request) -> Dict[str, Any]:
        try:
            return await request.json()
        except Exception:
            return {}

    def _mask_api_keys(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        safe = copy.deepcopy(cfg)
        if isinstance(safe, dict) and "api_key" in safe:
            key = safe["api_key"]
            if key and len(str(key)) > 6:
                safe["api_key"] = str(key)[:6] + "***"
            elif key:
                safe["api_key"] = "***"
        return safe

    async def _api_status(self, request) -> Dict[str, Any]:
        behavior_status = self.ai_engine.get_behavior_status()

        # 功能开关状态
        features = {
            "stalker_mode": self.config.get("stalker_mode.enabled", True),
            "continue_conversation": self.config.get(
                "continue_conversation.enabled", True
            ),
            "knowledge_base": self.config.get("knowledge_base.enabled", True),
            "mcp": self.config.get("mcp.enabled", True),
            "multi_agent": self.config.get("multi_agent.enabled", True),
            "voice": self.config.get("voice.enabled", False),
        }

        return {
            "stats": {
                "models": self.model_pool.get_stats(),
                "behaviors": self.behavior_manager.get_stats(),
                "agents": {"total": len(self.multi_agent.list_agents())},
                "knowledge": self.knowledge_base.get_stats(),
                "tools": self.mcp_manager.get_stats(),
            },
            "ai_status": behavior_status,
            "features": features,
            "active_groups": len(self.config.list_all_groups()),
        }

    async def _api_get_config(self, request) -> Dict[str, Any]:
        return {"config": self.config.config}

    async def _api_save_config(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        # JS 发送 { config: {...} } 格式
        if "config" in body and isinstance(body["config"], dict):
            self.config.config.update(body["config"])
            sdk.env.setConfig("QvQChat", self.config.config)
        else:
            # 兼容扁平格式
            for key, value in body.items():
                self.config.set(key, value)
        self.logger.info("基础配置已通过 Dashboard 更新")
        return {"ok": True}

    # ----- 模型管理 -----

    async def _api_get_models(self, request) -> Dict[str, Any]:
        models = [self._mask_api_keys(m) for m in self.model_pool.list_models()]
        return {"models": models}

    async def _api_save_model(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        model_id = body.get("id", "")
        if "api_key" in body and "***" in str(body.get("api_key", "")):
            existing = self.model_pool.get_model(model_id)
            if existing:
                body["api_key"] = existing.get("api_key", "")
        if model_id:
            result = self.model_pool.update_model(model_id, body)
        else:
            body.pop("id", None)
            result = self.model_pool.create_model(body)
        if result:
            self.core.ai_engine.reload_clients()
        return {
            "ok": result is not None,
            "model": self._mask_api_keys(result) if result else None,
        }

    async def _api_delete_model(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        ok = self.model_pool.delete_model(body.get("id", ""))
        if ok:
            self.core.ai_engine.reload_clients()
        return {"ok": ok}

    # ----- 行为管理 -----

    async def _api_get_behaviors(self, request) -> Dict[str, Any]:
        behaviors = []
        for b in self.behavior_manager.list_behaviors():
            b_copy = copy.deepcopy(b)
            # 附加模型名称信息
            model_names = []
            for mid in b.get("models", []):
                m = self.model_pool.get_model(mid)
                if m:
                    model_names.append({"id": mid, "name": m.get("name", mid)})
                else:
                    model_names.append({"id": mid, "name": mid + " (已删除)"})
            b_copy["model_info"] = model_names
            behaviors.append(b_copy)
        return {"behaviors": behaviors}

    async def _api_save_behavior(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        behavior_id = body.get("id", "")
        if behavior_id:
            result = self.behavior_manager.update_behavior(behavior_id, body)
        else:
            body.pop("id", None)
            result = self.behavior_manager.create_behavior(body)
        if result:
            self.core.ai_engine.reload_behavior(result["id"])
        return {"ok": result is not None, "behavior": result}

    async def _api_delete_behavior(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        ok = self.behavior_manager.delete_behavior(body.get("id", ""))
        return {"ok": ok}

    async def _api_test_model(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        model_id = body.get("id", "")
        try:
            ok = await self.ai_engine.test_model(model_id)
            return {"ok": ok}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ----- 多智能体 -----

    async def _api_get_agents(self, request) -> Dict[str, Any]:
        return {"agents": self.multi_agent.list_agents()}

    async def _api_save_agent(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        agent_id = body.get("id", "")
        if agent_id:
            result = self.multi_agent.update_agent(agent_id, body)
        else:
            result = self.multi_agent.create_agent(body)
        return {"ok": result is not None, "agent": result}

    async def _api_delete_agent(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        return {"ok": self.multi_agent.delete_agent(body.get("id", ""))}

    # ----- 知识库 -----

    async def _api_get_knowledge(self, request) -> Dict[str, Any]:
        return {"entries": self.knowledge_base.list_entries()}

    async def _api_save_knowledge(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        entry_id = body.get("id", "")
        if entry_id:
            result = self.knowledge_base.update_entry(entry_id, body)
        else:
            body.pop("id", None)
            result = self.knowledge_base.create_entry(body)
        return {"ok": result is not None, "entry": result}

    async def _api_delete_knowledge(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        return {"ok": self.knowledge_base.delete_entry(body.get("id", ""))}

    # ----- MCP 工具 -----

    async def _api_get_tools(self, request) -> Dict[str, Any]:
        return {"tools": self.mcp_manager.list_tools()}

    async def _api_save_tool(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        tool_id = body.get("id", "")
        if tool_id:
            result = self.mcp_manager.update_tool(tool_id, body)
        else:
            body.pop("id", None)
            result = self.mcp_manager.create_tool(body)
        return {"ok": result is not None, "tool": result}

    async def _api_delete_tool(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        return {"ok": self.mcp_manager.delete_tool(body.get("id", ""))}

    # ----- 群组 -----

    async def _api_get_groups(self, request) -> Dict[str, Any]:
        groups = []
        for gid in self.config.list_all_groups():
            groups.append({"id": gid, "config": self.config.get_group_config(gid)})
        return {"groups": groups, "agents": self.multi_agent.list_agents()}

    async def _api_save_group(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        # JS 发送 { id: group_id, config: {...} }
        group_id = body.get("group_id") or body.get("id", "")
        if not group_id:
            return {"ok": False, "error": "缺少 group_id"}
        config_data = body.get("config", body)
        existing = self.config.get_group_config(group_id)
        existing.update(config_data)
        self.config.set_group_config(group_id, existing)
        return {"ok": True}
