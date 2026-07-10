"""
MCP Server 客户端（Streamable HTTP）

管理与 MCP 服务器的 JSON-RPC 通信（HTTP/SSE 传输）。
支持标准 MCP 协议：
- initialize / initialized 握手
- tools/list 工具发现
- tools/call 工具调用

配置格式：
    {
        "erispulse": {
            "url": "https://mcp.erisdev.com/"
        }
    }
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk


class MCPServerClient:
    """
    单个 MCP HTTP 服务器的客户端

    通过 HTTP POST 发送 JSON-RPC 2.0 请求，
    支持 SSE（text/event-stream）和普通 JSON 响应。
    """

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(
        self,
        name: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        logger=None,
    ):
        self.name = name
        self.url = url
        self.headers = headers or {}
        self.logger = logger or sdk.logger.get_child("MCPServer")
        self._tools: List[Dict[str, Any]] = []
        self._initialized = False

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return self._tools

    @property
    def is_connected(self) -> bool:
        return self._initialized

    async def connect(self) -> bool:
        """连接服务器并完成 initialize 握手 + 工具发现"""
        try:
            await self._initialize()
            await self._refresh_tools()
            self._initialized = True
            self.logger.info(
                f"MCP 服务器 [{self.name}] 已连接，发现 {len(self._tools)} 个工具"
            )
            return True
        except Exception as e:
            self.logger.error(f"MCP 服务器 [{self.name}] 连接失败: {e}")
            self._initialized = False
            return False

    async def disconnect(self) -> None:
        """断开连接（HTTP 无状态，仅清理标记）"""
        self._initialized = False

    async def _initialize(self) -> None:
        """完成 MCP initialize 握手"""
        resp = await self._request("initialize", {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {
                "name": "QvQChat",
                "version": "2.1.0",
            },
        })

        server_info = resp.get("serverInfo", {})
        self.logger.debug(
            f"MCP 服务器 [{self.name}] "
            f"{server_info.get('name', '?')} v{server_info.get('version', '?')}"
        )

        # 发送 initialized 通知
        await self._notify("notifications/initialized", {})

    async def _refresh_tools(self) -> None:
        """从服务器获取工具列表"""
        resp = await self._request("tools/list", {})
        self._tools = resp.get("tools", [])

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """调用服务器上的工具"""
        if not self._initialized:
            return f"MCP 服务器 [{self.name}] 未连接"

        try:
            resp = await self._request("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            return self._extract_text(resp)
        except Exception as e:
            self.logger.error(
                f"MCP 服务器 [{self.name}] 调用工具 {tool_name} 失败: {e}"
            )
            return f"工具调用失败: {e}"

    def _extract_text(self, result: Dict[str, Any]) -> str:
        """从 tools/call 响应中提取文本"""
        content = result.get("content", [])
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "image":
                    texts.append("[图片]")
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts) if texts else str(result)

    # ==================== HTTP JSON-RPC ====================

    async def _request(self, method: str, params: Any, timeout: float = 30) -> Dict[str, Any]:
        """发送 JSON-RPC 请求并等待响应"""
        req_id = str(uuid.uuid4())
        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        headers = dict(self.headers)
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json, text/event-stream")

        resp = await sdk.client.post(
            self.url,
            json=message,
            headers=headers,
            timeout=timeout,
        )

        resp_text = resp.text if hasattr(resp, "text") else str(resp)

        # 尝试解析 SSE 格式（data: {...}）
        if "text/event-stream" in str(getattr(resp, "headers", {}).get("content-type", "")):
            for line in resp_text.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data:
                        msg = json.loads(data)
                        if msg.get("id") == req_id:
                            if "error" in msg:
                                err = msg["error"]
                                raise RuntimeError(
                                    f"RPC 错误 {err.get('code')}: {err.get('message')}"
                                )
                            return msg.get("result", {})
        else:
            msg = json.loads(resp_text)
            if msg.get("id") == req_id:
                if "error" in msg:
                    err = msg["error"]
                    raise RuntimeError(
                        f"RPC 错误 {err.get('code')}: {err.get('message')}"
                    )
                return msg.get("result", {})

        raise RuntimeError(f"无法解析 MCP 响应: {resp_text[:200]}")

    async def _notify(self, method: str, params: Any) -> None:
        """发送 JSON-RPC 通知（fire-and-forget）"""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        headers = dict(self.headers)
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json, text/event-stream")

        try:
            await sdk.client.post(
                self.url,
                json=message,
                headers=headers,
                timeout=10,
            )
        except Exception:
            pass  # 通知不需要等待响应
