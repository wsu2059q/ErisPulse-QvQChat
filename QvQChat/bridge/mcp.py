from __future__ import annotations

import asyncio
import json
import os
import time

from .. import texts, utils
from ..agent.tools import Tool
from ..utils import sanitize_name

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "QvQChat", "version": "4.0.0"}
SERVERS_KEY = "QvQChat:mcp_servers"


class MCPClient:
    def __init__(self, sdk, name: str, server_cfg: dict, timeout: float):
        self._sdk = sdk
        self.name = name
        self.transport = str(server_cfg.get("transport") or "stdio").lower()
        self.command = str(server_cfg.get("command") or "")
        self.args = list(server_cfg.get("args") or [])
        self.env = dict(server_cfg.get("env") or {})
        self.url = str(server_cfg.get("url") or "")
        self.headers = dict(server_cfg.get("headers") or {})
        self.timeout = float(timeout or 30)
        self.status = "disconnected"
        self.tools: list[dict] = []
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 0
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self.transport == "stdio":
            if not self.command:
                raise ValueError(f"MCP server {self.name}: stdio transport needs command")
            env = dict(os.environ)
            env.update({str(k): str(v) for k, v in self.env.items()})
            self._proc = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
        elif self.transport != "http":
            raise ValueError(f"MCP server {self.name}: unknown transport {self.transport}")
        await self._rpc(
            "initialize",
            {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO},
        )
        await self._notify("notifications/initialized")
        result = await self._rpc("tools/list", {})
        tools = result.get("tools") if isinstance(result, dict) else None
        self.tools = tools if isinstance(tools, list) else []
        self.status = "connected"

    async def _notify(self, method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        if self.transport == "stdio":
            await self._write_stdio(payload)

    async def _write_stdio(self, payload: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise ConnectionError(f"MCP server {self.name}: stdio not open")
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        await self._proc.stdin.drain()

    async def _rpc(self, method: str, params: dict | None = None, timeout: float | None = None) -> dict:
        self._next_id += 1
        request_id = self._next_id
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        effective = timeout or self.timeout
        async with self._lock:
            if self.transport == "stdio":
                await self._write_stdio(payload)
                return await self._read_stdio(request_id, effective)
            return await self._post(payload, effective)

    async def _read_stdio(self, request_id: int, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        if self._proc is None or self._proc.stdout is None:
            raise ConnectionError(f"MCP server {self.name}: stdio not open")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"MCP server {self.name}: request timed out")
            try:
                line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=remaining)
            except asyncio.TimeoutError:
                raise TimeoutError(f"MCP server {self.name}: request timed out") from None
            if not line:
                raise ConnectionError(f"MCP server {self.name}: stream closed")
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("id") == request_id:
                if message.get("error"):
                    raise RuntimeError(f"MCP error: {message['error']}")
                return message.get("result") or {}

    async def _post(self, payload: dict, timeout: float) -> dict:
        resp = await self._sdk.client.post(
            self.url,
            json=payload,
            headers=self.headers,
            timeout=timeout,
        )
        if resp.status != 200:
            raise RuntimeError(f"MCP HTTP {resp.status}")
        content_type = resp.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(await resp.text(), payload["id"])
        message = await resp.json()
        if isinstance(message, dict) and message.get("error"):
            raise RuntimeError(f"MCP error: {message['error']}")
        return (message or {}).get("result") or {}

    @staticmethod
    def _parse_sse(body: str, request_id: int) -> dict:
        for line in body.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if not chunk:
                continue
            try:
                message = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("id") == request_id:
                if message.get("error"):
                    raise RuntimeError(f"MCP error: {message['error']}")
                return message.get("result") or {}
        return {}

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments}, timeout=max(self.timeout, 120))
        if not isinstance(result, dict):
            return ""
        content = result.get("content") or []
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        text = "\n".join(parts)
        if result.get("isError"):
            raise RuntimeError(text or "tool reported an error")
        return text

    async def close(self) -> None:
        self.status = "disconnected"
        if self._proc is not None:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    self._proc.kill()
                except ProcessLookupError:
                    pass
            self._proc = None


class MCPManager:
    def __init__(self, main):
        self.main = main
        self.clients: dict[str, MCPClient] = {}

    # ── 服务器配置（独立存储，Dashboard 可直接增删改） ──

    def list_servers(self) -> list[dict]:
        servers = self.main.sdk.storage.get(SERVERS_KEY, [])
        if not isinstance(servers, list):
            return []
        return [dict(s) for s in servers if isinstance(s, dict)]

    def replace_servers(self, servers: list[dict]) -> None:
        self.main.sdk.storage.set(SERVERS_KEY, [s for s in servers if isinstance(s, dict)])

    def save_server(self, entry: dict) -> dict:
        name = str(entry.get("name") or "").strip()
        if not name:
            raise ValueError(texts.t("mcp_name_required"))
        transport = str(entry.get("transport") or "stdio").lower()
        clean: dict = {"name": name, "transport": transport}
        if transport == "http":
            clean["url"] = str(entry.get("url") or "")
            headers = entry.get("headers")
            if isinstance(headers, dict) and headers:
                clean["headers"] = {str(k): str(v) for k, v in headers.items()}
        else:
            clean["command"] = str(entry.get("command") or "")
            args = entry.get("args")
            if isinstance(args, list):
                clean["args"] = [str(a) for a in args]
            env = entry.get("env")
            if isinstance(env, dict) and env:
                clean["env"] = {str(k): str(v) for k, v in env.items()}
        if entry.get("timeout"):
            clean["timeout"] = entry["timeout"]
        servers = [s for s in self.list_servers() if s.get("name") != name]
        servers.append(clean)
        self.replace_servers(servers)
        return clean

    def delete_server(self, name: str) -> bool:
        servers = self.list_servers()
        remaining = [s for s in servers if str(s.get("name") or "") != str(name)]
        if len(remaining) == len(servers):
            return False
        self.replace_servers(remaining)
        return True

    # ── 连接管理 ──

    async def connect_all(self) -> list[dict]:
        results = []
        for server_cfg in self.list_servers():
            name = str(server_cfg.get("name") or utils.new_id())
            try:
                info = await self.connect_one(name, server_cfg)
                results.append(info)
            except Exception as e:
                self.main.logger.warning(f"MCP {name} connect failed: {e}")
                results.append({"name": name, "error": str(e)})
        return results

    async def connect_one(self, name: str, server_cfg: dict) -> dict:
        old = self.clients.pop(name, None)
        if old is not None:
            await old.close()
            self._unregister(name)
        timeout = server_cfg.get("timeout") or getattr(self.main.cfg, "mcp_timeout", 30)
        client = MCPClient(self.main.sdk, name, server_cfg, timeout=float(timeout))
        await client.connect()
        self.clients[name] = client
        self._register_tools(name, client)
        return {"name": name, "tools": len(client.tools)}

    def _register_tools(self, name: str, client: MCPClient) -> None:
        registry = self.main.registry
        prefix = f"mcp_{sanitize_name(name)}_"
        registry.unregister_prefix(prefix)
        for tool in client.tools:
            raw_name = str(tool.get("name") or "")
            if not raw_name:
                continue
            schema = tool.get("inputSchema")
            if not isinstance(schema, dict) or schema.get("type") != "object":
                schema = {"type": "object", "properties": {}, "required": []}

            async def handler(ctx, _client=client, _name=raw_name, **kwargs):
                return await _client.call_tool(_name, kwargs)

            registry.register(Tool(
                name=prefix + sanitize_name(raw_name),
                description=str(tool.get("description") or raw_name),
                parameters=schema,
                handler=handler,
                origin="mcp",
                meta={"server": name},
            ))

    def _unregister(self, name: str) -> None:
        self.main.registry.unregister_prefix(f"mcp_{sanitize_name(name)}_")

    async def disconnect(self, name: str) -> bool:
        client = self.clients.pop(name, None)
        if client is None:
            return False
        await client.close()
        self._unregister(name)
        return True

    async def close_all(self) -> None:
        for name in list(self.clients):
            await self.disconnect(name)

    def status(self) -> list[dict]:
        return [
            {
                "name": client.name,
                "transport": client.transport,
                "status": client.status,
                "tools": len(client.tools),
                "tool_names": [getattr(t, "name", str(t)) for t in client.tools],
            }
            for client in self.clients.values()
        ]
