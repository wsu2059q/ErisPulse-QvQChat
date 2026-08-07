"""
Dashboard 管理器

注册 Dashboard 视窗和 API 路由，提供 Web 管理界面。
"""

import copy
import io
import os
from typing import Any, Dict

from ErisPulse import i18n, sdk

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
        ("/api/agents/test", "POST", "_api_test_agent"),
        ("/api/agents/clone", "POST", "_api_clone_agent"),
        ("/api/agents/bind", "POST", "_api_bind_agent"),
        ("/api/knowledge", "GET", "_api_get_knowledge"),
        ("/api/knowledge", "POST", "_api_save_knowledge"),
        ("/api/knowledge/delete", "POST", "_api_delete_knowledge"),
        ("/api/tools", "GET", "_api_get_tools"),
        ("/api/tools", "POST", "_api_save_tool"),
        ("/api/tools/delete", "POST", "_api_delete_tool"),
        ("/api/mcp-servers", "GET", "_api_get_mcp_servers"),
        ("/api/mcp-servers", "POST", "_api_save_mcp_server"),
        ("/api/mcp-servers/delete", "POST", "_api_delete_mcp_server"),
        ("/api/mcp-servers/connect", "POST", "_api_connect_mcp_server"),
        ("/api/stickers", "GET", "_api_get_stickers"),
        ("/api/stickers", "POST", "_api_save_sticker"),
        ("/api/stickers/delete", "POST", "_api_delete_sticker"),
        ("/api/stickers/upload", "POST", "_api_upload_sticker"),
        ("/stickers/img/{sticker_id}", "GET", "_api_sticker_image"),
        ("/api/stickers/autofill", "POST", "_api_sticker_autofill"),
        ("/api/stickers/upload-batch", "POST", "_api_upload_stickers_batch"),
        ("/api/export", "POST", "_api_export"),
        ("/api/import", "POST", "_api_import"),
        ("/api/groups", "GET", "_api_get_groups"),
        ("/api/groups", "POST", "_api_save_group"),
        ("/api/templates", "GET", "_api_get_templates"),
        ("/api/reset", "POST", "_api_reset_all"),
        ("/api/memories", "GET", "_api_get_memories"),
        ("/api/memories/delete", "POST", "_api_delete_memory"),
        ("/api/memories/clear-all", "POST", "_api_clear_all_memories"),
        ("/api/memories/group", "GET", "_api_get_group_memories"),
        ("/api/memories/detail", "GET", "_api_get_memory_detail"),
        ("/api/memories/edit", "POST", "_api_edit_memory"),
        ("/api/sessions", "GET", "_api_get_sessions"),
        ("/api/sessions/history", "GET", "_api_get_session_history"),
        ("/api/sessions/edit", "POST", "_api_edit_session_message"),
        ("/api/sessions/delete", "POST", "_api_delete_session_message"),
        ("/api/sessions/clear", "POST", "_api_clear_session"),
        ("/api/sessions/add", "POST", "_api_add_session_message"),
        ("/api/human-state", "GET", "_api_get_human_state"),
        ("/api/pipeline", "GET", "_api_get_pipeline"),
        ("/api/pipeline", "POST", "_api_save_pipeline"),
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
    def pipeline(self):
        return self.core.pipeline

    @property
    def mcp_manager(self):
        return self.core.mcp_manager

    @property
    def sticker_manager(self):
        return self.core.sticker_manager

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

            # 组装 HTML — 自动替换所有图标占位符
            html = html_mod.HTML
            for _icon_name in dir(icons):
                if _icon_name.isupper():
                    html = html.replace(f"__ICON_{_icon_name}__", getattr(icons, _icon_name))

            # 组装 JS — 自动替换所有图标占位符
            js = scripts.SCRIPTS
            for _icon_name in dir(icons):
                if _icon_name.isupper():
                    js = js.replace(f"__ICON_{_icon_name}__", getattr(icons, _icon_name))

            # 注入 i18n 翻译字典（前端通过 qvcT() 读取）
            try:
                i18n_js = {
                    "page.title": i18n.t("QvQChat.page_title", default="QvQChat"),
                    "page.desc": i18n.t("QvQChat.page_desc", default="智能对话模块 · 管理 AI 模型、行为、智能体、知识库与记忆"),
                    "tab.overview": i18n.t("QvQChat.tab_overview", default="概览"),
                    "tab.basic": i18n.t("QvQChat.tab_basic", default="基础设置"),
                    "tab.models": i18n.t("QvQChat.tab_models", default="模型管理"),
                    "tab.behaviors": i18n.t("QvQChat.tab_behaviors", default="行为管理"),
                    "tab.pipeline": i18n.t("QvQChat.tab_pipeline", default="注入管线"),
                    "tab.agents": i18n.t("QvQChat.tab_agents", default="多智能体"),
                    "tab.knowledge": i18n.t("QvQChat.tab_knowledge", default="知识库"),
                    "tab.tools": i18n.t("QvQChat.tab_tools", default="MCP工具"),
                    "tab.stickers": i18n.t("QvQChat.tab_stickers", default="表情包"),
                    "tab.memories": i18n.t("QvQChat.tab_memories", default="记忆管理"),
                    "tab.sessions": i18n.t("QvQChat.tab_sessions", default="会话管理"),
                    "tab.groups": i18n.t("QvQChat.tab_groups", default="群组管理"),
                    "btn.export_desensitize": i18n.t("QvQChat.btn_export_desensitize", default="脱敏导出"),
                    "btn.export_migrate": i18n.t("QvQChat.btn_export_migrate", default="迁移导出"),
                    "btn.import": i18n.t("QvQChat.btn_import", default="导入"),
                    "btn.reset": i18n.t("QvQChat.btn_reset", default="重置全部"),
                    "btn.save_config": i18n.t("QvQChat.btn_save_config", default="保存配置"),
                    "overview.runtime": i18n.t("QvQChat.overview_runtime", default="运行状态"),
                    "overview.stats": i18n.t("QvQChat.overview_stats", default="运行统计"),
                    "overview.ai": i18n.t("QvQChat.overview_ai", default="AI 子系统状态"),
                    "overview.features": i18n.t("QvQChat.overview_features", default="功能开关"),
                    "overview.human": i18n.t("QvQChat.overview_human", default="人类状态"),
                    "pipeline.title": i18n.t("QvQChat.pipeline_title", default="注入管线"),
                    "pipeline.desc": i18n.t("QvQChat.pipeline_desc", default="注入器按优先级顺序拼接系统提示词。可开关、调整顺序。"),
                    "pipeline.time_settings": i18n.t("QvQChat.pipeline_time_settings", default="时间叙述设置"),
                    "pipeline.time_prob": i18n.t("QvQChat.pipeline_time_prob", default="时间注入概率 (0~1，1=总是注入)"),
                    "pipeline.time_ttl": i18n.t("QvQChat.pipeline_time_ttl", default="时间叙述缓存 (秒)"),
                    "pipeline.save": i18n.t("QvQChat.pipeline_save", default="保存"),
                    "pipeline.saved": i18n.t("QvQChat.pipeline_saved", default="注入管线已保存"),
                    "pipeline.save_failed": i18n.t("QvQChat.pipeline_save_failed", default="保存失败"),
                    "pipeline.load_failed": i18n.t("QvQChat.pipeline_load_failed", default="加载注入管线失败"),
                    "pipeline.empty": i18n.t("QvQChat.pipeline_empty", default="无注入器"),
                    "pipeline.move_up": i18n.t("QvQChat.pipeline_move_up", default="上移"),
                    "pipeline.move_down": i18n.t("QvQChat.pipeline_move_down", default="下移"),
                }
                import json as _json
                js = "var _qvcI18n = " + _json.dumps(i18n_js, ensure_ascii=False) + ";\n" + js
            except Exception:
                pass

            self.sdk.Dashboard.register_view(
                id="QvQChat",
                title="QvQChat",
                title_en="QvQChat",
                titles={
                    "zh": "QvQChat",
                    "en": "QvQChat",
                    "zh-TW": "QvQChat",
                    "ja": "QvQChat",
                    "ru": "QvQChat",
                },
                icon_svg=icons.CHAT,
                html_content=html,
                js_content=js,
                css_content=styles.STYLES,
                loader="loadQvQChatView",
                group="qvq",
                group_title="QvQChat",
                group_title_en="QvQChat",
                group_titles={
                    "zh": "QvQChat",
                    "en": "QvQChat",
                    "zh-TW": "QvQChat",
                    "ja": "QvQChat",
                    "ru": "QvQChat",
                },
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
                "stickers": self.sticker_manager.get_stats(),
            },
            "ai_status": behavior_status,
            "features": features,
            "active_groups": len(self.config.list_all_groups()),
            "runtime": self.core.get_stats(),
            "human_state": self.core.get_human_state(),
            "debug": self.core.get_status(),
        }

    async def _api_get_config(self, request) -> Dict[str, Any]:
        return {"config": sdk.config.getConfig("QvQChat", {})}

    async def _api_save_config(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        # JS 发送 { config: {...} } 格式
        if "config" in body and isinstance(body["config"], dict):
            sdk.config.setConfig("QvQChat", body["config"])
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

    async def _api_test_agent(self, request) -> Dict[str, Any]:
        """测试智能体（Playground）"""
        body = await self._parse_body(request)
        agent_id = body.get("id", "")
        message = body.get("message", "")

        if not message.strip():
            return {"ok": False, "error": "消息不能为空"}

        agent = self.multi_agent.get_agent(agent_id)
        if not agent:
            return {"ok": False, "error": "智能体不存在"}

        if not self.ai_engine.is_available("dialogue"):
            return {"ok": False, "error": "对话行为未配置模型"}

        try:
            # 使用临时 session_key 构建提示词
            test_key = f"_test:{agent_id}"
            self.multi_agent.bind_agent(agent_id, test_key)
            prompt = self.multi_agent.get_effective_prompt(test_key)
            self.multi_agent.unbind_agent(test_key)

            messages = []
            if prompt:
                messages.append({"role": "system", "content": prompt})

            # 加载测试历史（如果有）
            test_history = body.get("history", [])
            for h in test_history[-10:]:
                messages.append(h)

            messages.append({"role": "user", "content": message})

            # 使用智能体的模型参数覆盖
            kwargs = {}
            params = self.multi_agent.get_effective_model_params(test_key)
            if "temperature" in params:
                kwargs["temperature"] = params["temperature"]
            if "max_tokens" in params:
                kwargs["max_tokens"] = params["max_tokens"]

            response = await self.ai_engine.dialogue(messages, **kwargs)
            reply = response if isinstance(response, str) else str(response)
            return {"ok": True, "reply": reply.strip()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _api_clone_agent(self, request) -> Dict[str, Any]:
        """克隆智能体"""
        body = await self._parse_body(request)
        agent_id = body.get("id", "")
        new_name = body.get("name", "")
        result = self.multi_agent.clone_agent(agent_id, new_name)
        return {"ok": result is not None, "agent": result}

    async def _api_bind_agent(self, request) -> Dict[str, Any]:
        """绑定/解绑智能体到会话"""
        body = await self._parse_body(request)
        agent_id = body.get("agent_id", "")
        session_key = body.get("session_key", "")
        action = body.get("action", "bind")  # bind | unbind

        if not session_key:
            return {"ok": False, "error": "缺少 session_key"}

        if action == "unbind":
            return {"ok": self.multi_agent.unbind_agent(session_key)}
        if not agent_id:
            return {"ok": False, "error": "缺少 agent_id"}
        return {"ok": self.multi_agent.bind_agent(agent_id, session_key)}

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

    # ----- MCP 服务器 -----

    async def _api_get_mcp_servers(self, request) -> Dict[str, Any]:
        return {"servers": self.mcp_manager.list_servers()}

    async def _api_save_mcp_server(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        name = body.get("name", "").strip()
        if not name:
            return {"ok": False, "error": "缺少服务器名称"}
        existing = self.mcp_manager.get_server(name)
        if existing:
            result = self.mcp_manager.update_server(name, body)
        else:
            result = self.mcp_manager.add_server(name, body)
        return {"ok": result is not None, "server": result}

    async def _api_delete_mcp_server(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        name = body.get("name", "")
        return {"ok": self.mcp_manager.delete_server(name)}

    async def _api_connect_mcp_server(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        name = body.get("name", "")
        if body.get("connect_all"):
            await self.mcp_manager.connect_all_servers()
            return {"ok": True, "servers": self.mcp_manager.list_servers()}
        success = await self.mcp_manager.connect_server(name)
        return {"ok": success, "servers": self.mcp_manager.list_servers()}

    # ----- 表情包 -----

    async def _api_get_stickers(self, request) -> Dict[str, Any]:
        return {"stickers": self.sticker_manager.list_stickers()}

    async def _api_save_sticker(self, request) -> Dict[str, Any]:
        """通过 URL 添加或更新表情包元数据"""
        body = await self._parse_body(request)
        sticker_id = body.get("id", "")
        if sticker_id:
            result = self.sticker_manager.update_sticker(sticker_id, body)
            return {"ok": result is not None, "sticker": result}
        # 新增（URL 方式）
        url = body.get("url", "")
        name = body.get("name", "").strip()
        if not name:
            return {"ok": False, "error": "缺少名称"}
        if not url:
            return {"ok": False, "error": "缺少图片 URL"}
        result = self.sticker_manager.add_sticker_by_url(
            name, body.get("description", ""), url
        )
        return {"ok": True, "sticker": result}

    async def _api_upload_sticker(self, request) -> Dict[str, Any]:
        """上传表情包图片（multipart/form-data）"""
        try:
            form = await request.form()
        except Exception:
            return {"ok": False, "error": "无法解析表单数据"}

        name = form.get("name", "")
        description = form.get("description", "")
        upload_file = form.get("file")

        if not name:
            return {"ok": False, "error": "缺少表情包名称"}
        if not upload_file:
            return {"ok": False, "error": "缺少图片文件"}

        try:
            file_data = await upload_file.read()
            filename = getattr(upload_file, "filename", "sticker.png")
            result = self.sticker_manager.add_sticker(
                name, description, file_data, filename
            )
            return {"ok": True, "sticker": result}
        except Exception as e:
            return {"ok": False, "error": f"上传失败: {e}"}

    async def _api_delete_sticker(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        return {"ok": self.sticker_manager.delete_sticker(body.get("id", ""))}

    async def _api_sticker_image(self, request) -> Any:
        """返回表情包图片（供 Dashboard 预览）"""
        import os
        import mimetypes

        sticker_id = request.path_params.get("sticker_id", "")
        sticker = self.sticker_manager.get_sticker(sticker_id)
        if not sticker:
            return {"error": "Not found"}

        # URL 引用的表情包直接返回 URL
        if sticker.get("is_url"):
            return {"url": sticker["file"]}

        filepath = sticker.get("file", "")
        if not filepath or not os.path.exists(filepath):
            return {"error": "File not found"}

        # 尝试使用 FastAPI 的 FileResponse（底层引擎为 FastAPI）
        try:
            from fastapi.responses import FileResponse
            mime = mimetypes.guess_type(filepath)[0] or "image/png"
            return FileResponse(filepath, media_type=mime)
        except ImportError:
            # 兜底：读取文件返回 base64
            import base64
            mime = mimetypes.guess_type(filepath)[0] or "image/png"
            with open(filepath, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode()
            return {"data_url": f"data:{mime};base64,{b64}"}

    async def _api_sticker_autofill(self, request) -> Dict[str, Any]:
        """用视觉模型自动填充表情包描述"""
        body = await self._parse_body(request)
        sticker_id = body.get("id", "")
        sticker = self.sticker_manager.get_sticker(sticker_id)
        if not sticker:
            return {"ok": False, "error": "表情包不存在"}

        if not self.ai_engine.is_available("vision"):
            return {"ok": False, "error": "视觉模型不可用，请在行为管理中启用并分配模型"}

        filepath = sticker.get("file", "")
        if sticker.get("is_url"):
            image_ref = filepath
        elif filepath and os.path.exists(filepath):
            image_ref = filepath
        else:
            return {"ok": False, "error": "图片文件不存在"}

        try:
            resp = await self.ai_engine.analyze_image(
                image_ref,
                "用 2~6 字概括画面内容作为名称，然后用一句话描述画面中具体发生了什么（15字以内）。"
                "格式：名称 | 描述。示例：猫咪瞪眼 | 猫瞪大眼睛表情包",
            )
            desc = resp.strip() if resp else ""
            name = sticker.get("name", "")
            if desc:
                # 解析 名称 | 描述 格式
                if "|" in desc:
                    parts = desc.split("|", 1)
                    ai_name = parts[0].strip()
                    ai_desc = parts[1].strip()
                elif "：" in desc:
                    parts = desc.split("：", 1)
                    ai_name = parts[0].strip()
                    ai_desc = parts[1].strip()
                else:
                    ai_name = desc[:6]
                    ai_desc = desc[:25]

                # 截断过长
                if len(ai_name) > 6:
                    ai_name = ai_name[:6]
                if len(ai_desc) > 30:
                    ai_desc = ai_desc[:30]

                # 如果名称是哈希/自动生成格式，用 AI 生成的重命名
                is_auto_name = (
                    not name
                    or name.startswith("sticker_")
                    or (len(name) > 10 and not any("\u4e00" <= c <= "\u9fff" for c in name))
                )
                if is_auto_name and ai_name:
                    name = ai_name

                self.sticker_manager.update_sticker(sticker_id, {
                    "name": name,
                    "description": ai_desc if ai_desc else desc[:25],
                })
                return {"ok": True, "name": name, "description": ai_desc or desc[:25]}
            return {"ok": True, "description": ""}
        except Exception as e:
            return {"ok": False, "error": f"视觉分析失败: {e}"}

    # ----- 导出/导入 -----

    async def _api_export(self, request) -> Any:
        """导出配置数据包

        支持两种模式：
        - desensitize: 脱敏导出（API Key 等敏感信息打码）
        - migrate: 迁移导出（全部原始数据）
        """
        import io
        import json
        import time
        import zipfile

        body = await self._parse_body(request)
        mode = body.get("mode", "desensitize")  # desensitize | migrate

        storage = self.sdk.storage

        # 收集所有数据
        data_keys = [
            "QvQChat.behaviors",
            "QvQChat.models",
            "QvQChat.agents",
            "QvQChat.knowledge_base",
            "QvQChat.mcp_tools",
            "QvQChat.mcp_servers",
            "QvQChat.stickers",
            "QvQChat._group_ids",
        ]

        export_data = {
            "_meta": {
                "version": "2.1.0",
                "exported_at": time.time(),
                "mode": mode,
            },
            "config": sdk.config.getConfig("QvQChat", {}),
            "storage": {},
        }

        for key in data_keys:
            try:
                export_data["storage"][key] = storage.get(key, None)
            except Exception:
                pass

        # 收集群组配置
        groups = {}
        for gid in self.config.list_all_groups():
            groups[gid] = self.config.get_group_config(gid)
        export_data["storage"]["QvQChat.groups"] = groups

        # 脱敏处理
        if mode == "desensitize":
            export_data["config"] = self._desensitize(export_data["config"])
            # 模型配置中的 api_key
            models_data = export_data["storage"].get("QvQChat.models", {})
            if models_data and isinstance(models_data, dict):
                for mid, m in models_data.get("models", {}).items():
                    if isinstance(m, dict) and m.get("api_key"):
                        m["api_key"] = ""

        # 构建 zip
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("qvqchat_export.json", json.dumps(export_data, ensure_ascii=False, indent=2))

            # 迁移模式打包表情包图片
            stickers = export_data["storage"].get("QvQChat.stickers", {})
            if stickers:
                for sid, s in stickers.get("stickers", {}).items():
                    if s.get("is_url"):
                        continue
                    fpath = s.get("file", "")
                    if fpath and os.path.exists(fpath):
                        arcname = f"stickers/{s.get('filename', sid)}"
                        zf.write(fpath, arcname)

        buf.seek(0)
        filename = f"qvqchat_export_{mode}_{int(time.time())}.zip"

        try:
            from fastapi.responses import StreamingResponse
            return StreamingResponse(
                buf,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except ImportError:
            import base64
            return {
                "filename": filename,
                "data": base64.b64encode(buf.read()).decode(),
            }

    async def _api_import(self, request) -> Dict[str, Any]:
        """导入配置数据包"""
        import json
        import os
        import zipfile

        try:
            form = await request.form()
        except Exception:
            return {"ok": False, "error": "无法解析表单数据"}

        upload_file = form.get("file")
        if not upload_file:
            return {"ok": False, "error": "缺少文件"}

        try:
            file_data = await upload_file.read()
            buf = io.BytesIO(file_data)

            with zipfile.ZipFile(buf, "r") as zf:
                names = zf.namelist()
                if "qvqchat_export.json" not in names:
                    return {"ok": False, "error": "无效的导出文件（缺少 qvqchat_export.json）"}

                export_data = json.loads(zf.read("qvqchat_export.json"))

                # 恢复配置
                if export_data.get("config"):
                    sdk.config.setConfig("QvQChat", export_data["config"])

                # 恢复存储数据
                storage = self.sdk.storage
                for key, value in export_data.get("storage", {}).items():
                    if value is not None:
                        storage.set(key, value)

                # 恢复表情包图片
                sticker_dir = self.sticker_manager.sticker_dir
                os.makedirs(sticker_dir, exist_ok=True)
                for name in names:
                    if name.startswith("stickers/") and not name.endswith("/"):
                        filename = os.path.basename(name)
                        dest = os.path.join(sticker_dir, filename)
                        with open(dest, "wb") as f:
                            f.write(zf.read(name))

            return {"ok": True, "msg": "导入成功，请重启模块使配置生效"}
        except Exception as e:
            return {"ok": False, "error": f"导入失败: {e}"}

    def _desensitize(self, obj):
        """递归脱敏配置数据"""
        import copy
        if isinstance(obj, dict):
            result = copy.deepcopy(obj)
            for key in list(result.keys()):
                lk = key.lower()
                if lk in ("api_key", "apikey", "token", "secret", "password"):
                    if result[key]:
                        result[key] = "***"
                elif isinstance(result[key], (dict, list)):
                    result[key] = self._desensitize(result[key])
            return result
        elif isinstance(obj, list):
            return [self._desensitize(item) for item in obj]
        return obj

    # ----- 群组 -----

    async def _api_get_groups(self, request) -> Dict[str, Any]:
        groups = []
        for gid in self.config.list_all_groups():
            groups.append({"id": gid, "config": self.config.get_group_config(gid)})
        return {"groups": groups, "agents": self.multi_agent.list_agents()}

    async def _api_save_group(self, request) -> Dict[str, Any]:
        body = await self._parse_body(request)
        group_id = body.get("group_id") or body.get("id", "")
        if not group_id:
            return {"ok": False, "error": "缺少 group_id"}
        config_data = body.get("config", body)
        existing = self.config.get_group_config(group_id)
        existing.update(config_data)
        self.config.set_group_config(group_id, existing)
        return {"ok": True}

    # ----- 重置 -----

    async def _api_reset_all(self, request) -> Dict[str, Any]:
        """清除所有 QvQChat 数据和存储"""
        storage = self.sdk.storage
        config_keys = [
            "QvQChat.behaviors",
            "QvQChat.models",
            "QvQChat.agents",
            "QvQChat.knowledge_base",
            "QvQChat.mcp_tools",
            "QvQChat.mcp_servers",
            "QvQChat.stickers",
            "QvQChat._group_ids",
        ]
        for key in config_keys:
            try:
                storage.delete(key)
            except Exception:
                pass

        # 清除所有 qvc 前缀的存储
        try:
            all_keys = storage.keys() if hasattr(storage, "keys") else []
            for key in list(all_keys):
                if key.startswith(("qvc:", "QvQChat")):
                    try:
                        storage.delete(key)
                    except Exception:
                        pass
        except Exception:
            pass

        # 清除配置
        try:
            self.sdk.config.setConfig("QvQChat", {}, immediate=True)
        except Exception:
            pass

        self.logger.info("已清除所有 QvQChat 数据")
        return {"ok": True, "msg": "已清除所有 QvQChat 数据，请重启模块使默认配置生效"}

    # ----- 人格模板 -----

    async def _api_get_templates(self, request) -> Dict[str, Any]:
        return {"templates": self.multi_agent.get_templates()}

    # ----- 记忆洞察 -----

    async def _api_get_memories(self, request) -> Dict[str, Any]:
        """获取所有用户的记忆摘要（包括会话历史概览）"""
        from ErisPulse import sdk as _sdk

        storage = _sdk.storage
        all_keys = storage.keys() if hasattr(storage, "keys") else []
        memories = []
        for key in all_keys:
            if key.startswith("qvc:user:") and key.endswith(":memory"):
                user_id = key.split(":")[2]
                mem = storage.get(key, {})
                long_term = mem.get("long_term", [])
                short_term = mem.get("short_term", [])
                memories.append(
                    {
                        "user_id": user_id,
                        "count": len(long_term),
                        "short_term_count": len(short_term),
                        "latest": [
                            m.get("content", "")[:80] for m in long_term[-5:]
                        ],
                        "updated": mem.get("last_updated", ""),
                    }
                )
        memories.sort(key=lambda x: x["count"], reverse=True)
        
        memory_enabled = self.ai_engine.is_available("memory")
        return {
            "memories": memories[:100],
            "memory_extraction_enabled": memory_enabled,
            "hint": "" if memory_enabled else "记忆提取行为未分配模型，长期记忆不会自动生成。请在行为管理中为 memory 行为分配模型。",
        }

    async def _api_delete_memory(self, request) -> Dict[str, Any]:
        """删除指定用户或群组的全部记忆"""
        body = await self._parse_body(request)
        user_id = body.get("user_id", "")
        mem_type = body.get("type", "user")  # user | group
        if not user_id:
            return {"ok": False, "error": "缺少 user_id"}
        from ErisPulse import sdk as _sdk

        if mem_type == "group":
            key = f"qvc:group:{user_id}:memory"
        else:
            key = f"qvc:user:{user_id}:memory"
        _sdk.storage.set(
            key,
            {
                "short_term": [],
                "long_term": [],
                "semantic": [],
                "last_updated": "",
            },
        )
        self.logger.info(f"已清除{mem_type}记忆: {user_id}")
        return {"ok": True}

    async def _api_get_group_memories(self, request) -> Dict[str, Any]:
        """获取所有群组的记忆摘要"""
        from ErisPulse import sdk as _sdk

        storage = _sdk.storage
        all_keys = storage.keys() if hasattr(storage, "keys") else []
        memories = []
        for key in all_keys:
            if key.startswith("qvc:group:") and key.endswith(":memory"):
                group_id = key.split(":")[2]
                mem = storage.get(key, {})
                long_term = mem.get("long_term", [])
                sender_memory = mem.get("sender_memory", {})
                sender_count = sum(len(v) for v in sender_memory.values())
                total = len(long_term) + sender_count
                if total > 0 or long_term:
                    memories.append(
                        {
                            "group_id": group_id,
                            "count": total,
                            "long_term_count": len(long_term),
                            "sender_count": sender_count,
                            "latest": [
                                m.get("content", "")[:80] for m in long_term[-5:]
                            ],
                            "updated": mem.get("last_updated", ""),
                        }
                    )
        memories.sort(key=lambda x: x["count"], reverse=True)
        return {"memories": memories[:100]}

    async def _api_clear_all_memories(self, request) -> Dict[str, Any]:
        """删除全部记忆（用户 + 群组）"""
        from ErisPulse import sdk as _sdk

        storage = _sdk.storage
        all_keys = storage.keys() if hasattr(storage, "keys") else []
        cleared = 0
        for key in list(all_keys):
            if (key.startswith("qvc:user:") and key.endswith(":memory")) or (
                key.startswith("qvc:group:") and key.endswith(":memory")
            ):
                try:
                    storage.set(
                        key,
                        {
                            "short_term": [],
                            "long_term": [],
                            "semantic": [],
                            "last_updated": "",
                        },
                    )
                    cleared += 1
                except Exception:
                    pass
        self.logger.info(f"已清空全部记忆，共清理 {cleared} 条")
        return {"ok": True, "msg": f"已清空 {cleared} 条记忆"}

    async def _api_get_memory_detail(self, request) -> Dict[str, Any]:
        """获取用户/群组的完整记忆详情"""
        from ErisPulse import sdk as _sdk

        user_id = request.query_params.get("user_id", "")
        mem_type = request.query_params.get("type", "user")
        if not user_id:
            return {"ok": False, "error": "缺少 user_id"}

        storage = _sdk.storage
        if mem_type == "group":
            key = f"qvc:group:{user_id}:memory"
            mem = storage.get(key, {})
            return {
                "ok": True,
                "type": "group",
                "id": user_id,
                "long_term": mem.get("long_term", []),
                "sender_memory": mem.get("sender_memory", {}),
                "shared_context": mem.get("shared_context", []),
            }
        else:
            key = f"qvc:user:{user_id}:memory"
            mem = storage.get(key, {})
            return {
                "ok": True,
                "type": "user",
                "id": user_id,
                "short_term": mem.get("short_term", []),
                "long_term": mem.get("long_term", []),
                "semantic": mem.get("semantic", []),
            }

    async def _api_edit_memory(self, request) -> Dict[str, Any]:
        """编辑单条长期记忆"""
        from ErisPulse import sdk as _sdk

        body = await self._parse_body(request)
        user_id = body.get("user_id", "")
        mem_type = body.get("type", "user")
        index = body.get("index", -1)
        content = body.get("content", "")
        action = body.get("action", "edit")  # edit | delete

        if not user_id or index < 0:
            return {"ok": False, "error": "参数不完整"}

        storage = _sdk.storage
        key = f"qvc:{mem_type}:{user_id}:memory"
        mem = storage.get(key, {})
        long_term = mem.get("long_term", [])

        if index >= len(long_term):
            return {"ok": False, "error": "索引超出范围"}

        if action == "delete":
            long_term.pop(index)
        else:
            if not content.strip():
                return {"ok": False, "error": "内容不能为空"}
            long_term[index]["content"] = content.strip()

        mem["long_term"] = long_term
        storage.set(key, mem)
        return {"ok": True}

    # ----- 会话历史管理 -----

    async def _api_get_sessions(self, request) -> Dict[str, Any]:
        """获取所有会话列表（含消息数、最后活跃时间）"""
        from ErisPulse import sdk as _sdk

        storage = _sdk.storage
        all_keys = storage.keys() if hasattr(storage, "keys") else []
        sessions = []
        for key in all_keys:
            if key.startswith("qvc:session:"):
                chat_id = key[len("qvc:session:") :]
                history = storage.get(key, [])
                if not history:
                    continue
                is_group = chat_id.startswith("group:")
                raw_id = chat_id.split(":", 1)[1] if ":" in chat_id else chat_id
                last_msg = history[-1] if history else {}
                sessions.append(
                    {
                        "session_key": chat_id,
                        "type": "group" if is_group else "user",
                        "id": raw_id,
                        "message_count": len(history),
                        "last_time": last_msg.get("timestamp", ""),
                        "last_role": last_msg.get("role", ""),
                        "preview": (last_msg.get("content", "")[:60] if last_msg else ""),
                    }
                )
        sessions.sort(
            key=lambda x: x.get("last_time", ""), reverse=True
        )
        return {"sessions": sessions}

    async def _api_get_session_history(self, request) -> Dict[str, Any]:
        """获取会话完整历史"""
        from ErisPulse import sdk as _sdk

        session_key = request.query_params.get("session_key", "")
        if not session_key:
            return {"ok": False, "error": "缺少 session_key"}

        storage = _sdk.storage
        history = storage.get(f"qvc:session:{session_key}", [])
        return {"session_key": session_key, "history": history}

    async def _api_edit_session_message(self, request) -> Dict[str, Any]:
        """编辑会话中的单条消息"""
        from ErisPulse import sdk as _sdk

        body = await self._parse_body(request)
        session_key = body.get("session_key", "")
        index = body.get("index", -1)
        content = body.get("content", "")

        if not session_key or index < 0:
            return {"ok": False, "error": "参数不完整"}

        storage = _sdk.storage
        key = f"qvc:session:{session_key}"
        history = storage.get(key, [])
        if index >= len(history):
            return {"ok": False, "error": "索引超出范围"}

        history[index]["content"] = content.strip()
        storage.set(key, history)
        return {"ok": True}

    async def _api_delete_session_message(self, request) -> Dict[str, Any]:
        """删除会话中的单条消息"""
        from ErisPulse import sdk as _sdk

        body = await self._parse_body(request)
        session_key = body.get("session_key", "")
        index = body.get("index", -1)

        if not session_key or index < 0:
            return {"ok": False, "error": "参数不完整"}

        storage = _sdk.storage
        key = f"qvc:session:{session_key}"
        history = storage.get(key, [])
        if index >= len(history):
            return {"ok": False, "error": "索引超出范围"}

        history.pop(index)
        storage.set(key, history)
        return {"ok": True}

    async def _api_clear_session(self, request) -> Dict[str, Any]:
        """清空会话历史"""
        from ErisPulse import sdk as _sdk

        body = await self._parse_body(request)
        session_key = body.get("session_key", "")
        if not session_key:
            return {"ok": False, "error": "缺少 session_key"}

        storage = _sdk.storage
        storage.set(f"qvc:session:{session_key}", [])
        self.logger.info(f"已清空会话: {session_key}")
        return {"ok": True}

    async def _api_add_session_message(self, request) -> Dict[str, Any]:
        """手动添加会话消息"""
        from ErisPulse import sdk as _sdk
        from datetime import datetime

        body = await self._parse_body(request)
        session_key = body.get("session_key", "")
        role = body.get("role", "user")
        content = body.get("content", "")

        if not session_key or not content.strip():
            return {"ok": False, "error": "参数不完整"}

        storage = _sdk.storage
        key = f"qvc:session:{session_key}"
        history = storage.get(key, [])
        history.append(
            {
                "role": role,
                "content": content.strip(),
                "timestamp": datetime.now().isoformat(),
            }
        )
        max_length = self.config.get("max_history_length", 20)
        if len(history) > max_length:
            history = history[-max_length:]
        storage.set(key, history)
        return {"ok": True}

    # ----- 人类状态 -----

    async def _api_get_human_state(self, request) -> Dict[str, Any]:
        """获取当前情绪/精力状态"""
        state = self.core.get_human_state()
        from datetime import datetime
        hour = datetime.now().hour
        state_cfg = self.config.get("human_state", {})
        return {
            "mood": round(state["mood"], 2),
            "energy": round(state["energy"], 2),
            "mood_text": self.core._mood_to_text(state["mood"]),
            "energy_text": self.core._energy_to_text(state["energy"]),
            "hour": hour,
            "enabled": state_cfg.get("enabled", True),
        }

    # ----- 注入管线 -----

    async def _api_get_pipeline(self, request) -> Dict[str, Any]:
        """获取注入管线状态"""
        try:
            injectors = self.pipeline.list_injectors()
            config = self.config.get("pipeline", {})
            return {
                "injectors": injectors,
                "config": config,
            }
        except Exception as e:
            return {"injectors": [], "config": {}, "error": str(e)}

    async def _api_save_pipeline(self, request) -> Dict[str, Any]:
        """更新注入管线（开关/排序/配置）"""
        try:
            data = await request.json()
            updated = 0

            injectors = data.get("injectors")
            if isinstance(injectors, list):
                for item in injectors:
                    iid = item.get("id")
                    inj = self.pipeline.get_injector(iid)
                    if not inj:
                        continue
                    if "enabled" in item:
                        inj.enabled = bool(item.get("enabled"))
                    if "priority" in item:
                        inj.priority = int(item.get("priority"))
                    updated += 1

            config = data.get("config")
            if isinstance(config, dict):
                for key, val in config.items():
                    self.config.set(f"pipeline.{key}", val)

            return {"ok": True, "updated": updated}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _api_upload_stickers_batch(self, request) -> Dict[str, Any]:
        """批量上传表情包（multipart/form-data，多个 file 字段）"""
        import os

        try:
            form = await request.form()
        except Exception:
            return {"ok": False, "error": "无法解析表单数据"}

        files = form.getlist("file")
        if not files:
            return {"ok": False, "error": "缺少图片文件"}

        results = []
        errors = []
        for upload_file in files:
            try:
                file_data = await upload_file.read()
                filename = getattr(upload_file, "filename", "sticker.png")
                # 用文件名作为默认名称
                name = filename
                dot_idx = filename.rfind(".")
                if dot_idx > 0:
                    name = filename[:dot_idx]
                result = self.sticker_manager.add_sticker(
                    name, "", file_data, filename
                )
                if result and result.get("id"):
                    # 自动视觉分析
                    try:
                        if self.ai_engine.is_available("vision"):
                            sticker_id = result["id"]
                            sticker = self.sticker_manager.get_sticker(sticker_id)
                            if sticker:
                                filepath = sticker.get("file", "")
                                if filepath and os.path.exists(filepath):
                                    desc = await self.ai_engine.analyze_image(
                                        filepath,
                                        "请用一句话描述这个表情包的内容、情绪和使用场景，用于让 AI 知道什么时候该发送它。",
                                    )
                                    desc = desc.strip() if desc else ""
                                    if desc:
                                        auto_name = desc[:8] if len(desc) > 8 else desc
                                        self.sticker_manager.update_sticker(sticker_id, {
                                            "name": auto_name,
                                            "description": desc,
                                        })
                                        result["name"] = auto_name
                                        result["description"] = desc
                    except Exception:
                        pass
                    results.append(result)
                else:
                    errors.append(f"{filename}: 保存失败")
            except Exception as e:
                errors.append(f"{filename}: {e}")

        return {
            "ok": len(results) > 0,
            "stickers": results,
            "errors": errors[:10],
            "total": len(files),
            "success": len(results),
            "fail": len(errors),
        }
