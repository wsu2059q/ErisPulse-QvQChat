from QvQChat.bridge.mcp import MCPClient, MCPManager

from fakes import FakeMain, make_ctx


def make_manager():
    main = FakeMain()
    return main, MCPManager(main)


async def test_mcp_register_tools_and_invoke():
    main, manager = make_manager()
    client = MCPClient(main.sdk, "srv", {"transport": "http", "url": "http://x"}, 10)
    client.tools = [
        {
            "name": "do_thing",
            "description": "does a thing",
            "inputSchema": {
                "type": "object",
                "properties": {"a": {"type": "string"}},
                "required": ["a"],
            },
        }
    ]

    async def fake_call(name, args):
        return f"ran {name} {args['a']}"

    client.call_tool = fake_call
    manager.clients["srv"] = client
    manager._register_tools("srv", client)
    tool = main.registry.get("mcp_srv_do_thing")
    assert tool is not None and tool.origin == "mcp"
    assert tool.parameters["required"] == ["a"]
    out = await tool.handler(make_ctx(main), a="x")
    assert out == "ran do_thing x"
    assert await manager.disconnect("srv") is True
    assert main.registry.get("mcp_srv_do_thing") is None


def test_mcp_sse_parsing():
    body = (
        ": ping\n\n"
        'data: {"jsonrpc":"2.0","id":1,"result":{"value":7}}\n\n'
        'data: {"jsonrpc":"2.0","method":"notify"}\n\n'
    )
    assert MCPClient._parse_sse(body, 1) == {"value": 7}
    assert MCPClient._parse_sse(body, 2) == {}


async def test_mcp_http_error_surfaces():
    main, manager = make_manager()
    client = MCPClient(main.sdk, "bad", {"transport": "http", "url": "http://x"}, 10)
    main.sdk.client.status = 500
    try:
        await client._post({"jsonrpc": "2.0", "id": 1, "method": "x", "params": {}}, 5)
        raise AssertionError("should raise")
    except RuntimeError as e:
        assert "500" in str(e)
