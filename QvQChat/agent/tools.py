"""
MCP 工具管理器

管理 AI 函数调用工具定义（Model Context Protocol 风格）。
支持通过 HTTP 端点调用外部工具，并将工具能力注入到对话 AI 中。
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk


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

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("MCPManager")
        self.storage = sdk.storage
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """从存储加载工具数据"""
        data = self.storage.get(self.STORAGE_KEY, {})
        self._tools = data.get("tools", {})

    def _save(self) -> None:
        """保存工具数据到存储"""
        self.storage.set(self.STORAGE_KEY, {"tools": self._tools})

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

        只返回已启用且有名称的工具。

        Returns:
            OpenAI tools 格式的列表
        """
        tools = []
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

        如果工具配置了 HTTP 端点，则请求该端点获取结果。
        否则返回提示信息。

        Args:
            tool_name: 工具名称
            arguments: 调用参数

        Returns:
            工具调用结果（字符串）
        """
        tool = self.get_tool_by_name(tool_name)
        if not tool:
            return f"工具 '{tool_name}' 不存在"

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
        return {
            "total": total,
            "enabled": enabled,
            "disabled": total - enabled,
            "with_endpoint": with_endpoint,
        }
