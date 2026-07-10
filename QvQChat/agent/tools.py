"""
MCP 工具管理器

管理 AI 函数调用工具定义（Model Context Protocol 风格）。
支持两种工具来源：
1. 手动定义的 HTTP 端点工具
2. stdio MCP 服务器自动发现的工具（兼容 Claude Desktop / Cursor 配置格式）
"""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk

from .mcp_client import MCPServerClient


class MCPManager:
    """
    MCP 工具管理器

    管理 AI 工具（function calling）定义，每个工具包含：
    - 工具名称和描述
    - 参数 JSON Schema
    - 可选的 HTTP 端点（工具被调用时请求该地址）
    - 启用/禁用控制

    工具定义会被转换为 OpenAI function calling 格式，
    供对话 AI 在对话中自动调用。
    """

    STORAGE_KEY = "QvQChat.mcp_tools"
    SERVERS_STORAGE_KEY = "QvQChat.mcp_servers"

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("MCPManager")
        self.storage = sdk.storage
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._server_clients: Dict[str, MCPServerClient] = {}
        self._load()
        self._load_servers()

    def _load(self) -> None:
        """从存储加载工具数据"""
        data = self.storage.get(self.STORAGE_KEY, {})
        self._tools = data.get("tools", {})

    def _save(self) -> None:
        """保存工具数据到存储"""
        self.storage.set(self.STORAGE_KEY, {"tools": self._tools})

    def _load_servers(self) -> None:
        """从存储加载 MCP 服务器配置"""
        data = self.storage.get(self.SERVERS_STORAGE_KEY, {})
        self._servers = data.get("servers", {})

    def _save_servers(self) -> None:
        """保存 MCP 服务器配置到存储"""
        self.storage.set(self.SERVERS_STORAGE_KEY, {"servers": self._servers})

    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        return list(self._tools.values())

    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """获取指定工具"""
        return self._tools.get(tool_id)

    def create_tool(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建工具定义

        Args:
            data: 工具配置，包含 name/description/parameters/endpoint 等

        Returns:
            创建的工具数据
        """
        tool_id = f"tool_{uuid.uuid4().hex[:8]}"
        now = time.time()
        tool = {
            "id": tool_id,
            "name": data.get("name", "unnamed_tool"),
            "description": data.get("description", ""),
            "parameters": data.get(
                "parameters",
                {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            "endpoint": data.get("endpoint", ""),
            "method": data.get("method", "POST"),
            "headers": data.get("headers", {}),
            "enabled": data.get("enabled", True),
            "created_at": now,
            "updated_at": now,
        }
        self._tools[tool_id] = tool
        self._save()
        self.logger.info(f"创建工具: {tool['name']} ({tool_id})")
        return tool

    def update_tool(
        self, tool_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        更新工具定义

        Args:
            tool_id: 工具ID
            data: 要更新的字段

        Returns:
            更新后的工具数据
        """
        tool = self._tools.get(tool_id)
        if not tool:
            return None

        for key in (
            "name",
            "description",
            "parameters",
            "endpoint",
            "method",
            "headers",
            "enabled",
        ):
            if key in data:
                tool[key] = data[key]

        tool["updated_at"] = time.time()
        self._save()
        self.logger.info(f"更新工具: {tool.get('name')} ({tool_id})")
        return tool

    def delete_tool(self, tool_id: str) -> bool:
        """删除工具"""
        if tool_id not in self._tools:
            return False
        del self._tools[tool_id]
        self._save()
        self.logger.info(f"删除工具: {tool_id}")
        return True

    def get_openai_tools_schema(self) -> List[Dict[str, Any]]:
        """
        获取 OpenAI function calling 格式的工具定义

        合并手动定义的 HTTP 工具和 MCP 服务器发现的工具。
        只返回已启用的工具。

        Returns:
            OpenAI tools 格式的列表
        """
        tools = []
        # 手动定义的 HTTP 工具
        for tool in self._tools.values():
            if not tool.get("enabled", True):
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get(
                            "parameters",
                            {
                                "type": "object",
                                "properties": {},
                                "required": [],
                            },
                        ),
                    },
                }
            )
        # MCP 服务器发现的工具
        for server_name, client in self._server_clients.items():
            if not client.is_connected:
                continue
            for mcp_tool in client.tools:
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": mcp_tool.get("name", ""),
                            "description": mcp_tool.get("description", ""),
                            "parameters": mcp_tool.get(
                                "inputSchema",
                                {
                                    "type": "object",
                                    "properties": {},
                                    "required": [],
                                },
                            ),
                        },
                    }
                )
        return tools

    def get_tool_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """通过名称查找工具"""
        for tool in self._tools.values():
            if tool.get("name") == name:
                return tool
        return None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """
        调用工具

        优先检查手动定义的 HTTP 端点工具，
        其次检查已连接的 MCP 服务器工具。

        Args:
            tool_name: 工具名称
            arguments: 调用参数

        Returns:
            工具调用结果（字符串）
        """
        # 先检查手动定义的 HTTP 工具
        tool = self.get_tool_by_name(tool_name)
        if tool:
            return await self._call_http_tool(tool, tool_name, arguments)

        # 再检查 MCP 服务器工具
        for server_name, client in self._server_clients.items():
            if not client.is_connected:
                continue
            for mcp_tool in client.tools:
                if mcp_tool.get("name") == tool_name:
                    self.logger.info(f"通过 MCP 服务器 [{server_name}] 调用工具: {tool_name}")
                    return await client.call_tool(tool_name, arguments)

        return f"工具 '{tool_name}' 不存在"

    async def _call_http_tool(
        self, tool: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]
    ) -> str:
        """调用 HTTP 端点工具"""
        endpoint = tool.get("endpoint", "")
        if not endpoint:
            return f"工具 '{tool_name}' 未配置调用端点，参数: {json.dumps(arguments, ensure_ascii=False)}"

        try:
            method = tool.get("method", "POST")
            headers = tool.get("headers", {})
            headers.setdefault("Content-Type", "application/json")

            if method.upper() == "GET":
                params = "&".join(f"{k}={v}" for k, v in arguments.items())
                url = (
                    f"{endpoint}?{params}"
                    if "?" not in endpoint
                    else f"{endpoint}&{params}"
                )
                resp = await sdk.client.get(url, headers=headers, timeout=30)
            else:
                resp = await sdk.client.post(
                    endpoint,
                    json=arguments,
                    headers=headers,
                    timeout=30,
                )

            result_text = resp.text if hasattr(resp, "text") else str(resp)

            self.logger.info(f"工具 '{tool_name}' 调用成功")
            return result_text

        except Exception as e:
            self.logger.error(f"工具 '{tool_name}' 调用失败: {e}")
            return f"工具调用失败: {e}"

    def get_stats(self) -> Dict[str, Any]:
        """获取工具统计信息"""
        total = len(self._tools)
        enabled = sum(1 for t in self._tools.values() if t.get("enabled", True))
        with_endpoint = sum(1 for t in self._tools.values() if t.get("endpoint"))
        connected_servers = sum(
            1 for c in self._server_clients.values() if c.is_connected
        )
        server_tools = sum(
            len(c.tools)
            for c in self._server_clients.values()
            if c.is_connected
        )
        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "with_endpoint": with_endpoint,
            "servers_configured": len(self._servers),
            "servers_connected": connected_servers,
            "server_tools": server_tools,
        }

    # ==================== MCP 服务器管理 ====================

    def list_servers(self) -> List[Dict[str, Any]]:
        """列出所有 MCP 服务器配置"""
        result = []
        for name, cfg in self._servers.items():
            client = self._server_clients.get(name)
            result.append({
                "name": name,
                "url": cfg.get("url", ""),
                "headers": cfg.get("headers", {}),
                "enabled": cfg.get("enabled", True),
                "connected": client.is_connected if client else False,
                "tool_count": len(client.tools) if client and client.is_connected else 0,
            })
        return result

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """获取指定 MCP 服务器配置"""
        return self._servers.get(name)

    def add_server(self, name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        添加/更新 MCP 服务器配置

        配置格式（Streamable HTTP）：
            {
                "url": "https://mcp.erisdev.com/",
                "headers": {"Authorization": "Bearer xxx"}
            }
        """
        self._servers[name] = {
            "url": data.get("url", ""),
            "headers": data.get("headers", {}),
            "enabled": data.get("enabled", True),
        }
        self._save_servers()
        self.logger.info(f"添加 MCP 服务器配置: {name}")
        return self._servers[name]

    def update_server(self, name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新 MCP 服务器配置"""
        if name not in self._servers:
            return None
        for key in ("url", "headers", "enabled"):
            if key in data:
                self._servers[name][key] = data[key]
        self._save_servers()
        return self._servers[name]

    def delete_server(self, name: str) -> bool:
        """删除 MCP 服务器配置并断开连接"""
        if name not in self._servers:
            return False
        del self._servers[name]
        self._save_servers()
        # 断开连接
        client = self._server_clients.pop(name, None)
        if client:
            asyncio.create_task(client.disconnect())
        self.logger.info(f"删除 MCP 服务器: {name}")
        return True

    async def connect_all_servers(self) -> None:
        """连接所有已启用的 MCP 服务器"""
        for name, cfg in self._servers.items():
            if not cfg.get("enabled", True):
                continue
            if name in self._server_clients and self._server_clients[name].is_connected:
                continue
            await self.connect_server(name)

    async def connect_server(self, name: str) -> bool:
        """连接指定的 MCP 服务器"""
        cfg = self._servers.get(name)
        if not cfg:
            return False

        # 已连接则先断开
        old = self._server_clients.pop(name, None)
        if old:
            await old.disconnect()

        client = MCPServerClient(
            name=name,
            url=cfg.get("url", ""),
            headers=cfg.get("headers", {}),
            logger=self.logger,
        )
        success = await client.connect()
        if success:
            self._server_clients[name] = client
        return success

    async def disconnect_all_servers(self) -> None:
        """断开所有 MCP 服务器连接"""
        tasks = [c.disconnect() for c in self._server_clients.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._server_clients.clear()

    async def refresh_server_tools(self, name: str) -> int:
        """刷新指定服务器的工具列表，返回工具数量"""
        client = self._server_clients.get(name)
        if not client or not client.is_connected:
            return 0
        await client._refresh_tools()
        return len(client.tools)
