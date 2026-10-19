from QvQChat.Main import is_admin_user, tool_allowed
from QvQChat.agent.tools import Tool, ToolRegistry

from fakes import make_config


def make_policy_config(**overrides):
    return make_config(**overrides)


SAFE_TOOLS = {"send_message", "send_dsl", "read_file", "list_dir", "recall", "create_scheduled_task"}


def make_tool(name):
    return Tool(
        name=name,
        description="t",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=None,
        access="safe" if name in SAFE_TOOLS else "admin",
    )


class StubCtx:
    def __init__(self, user_id="1", origin="chat"):
        self.user_id = user_id
        self.origin = origin


def test_is_admin_semantics():
    cfg = make_policy_config()
    assert is_admin_user(cfg, "1", "dashboard") is True
    assert is_admin_user(cfg, "1", "rpc") is True
    assert is_admin_user(cfg, "1", "chat") is False

    cfg = make_policy_config(admins=["10001"])
    assert is_admin_user(cfg, "10001", "chat") is True
    assert is_admin_user(cfg, "1", "chat") is False


def test_base_safe_tools_allowed_for_everyone():
    cfg = make_policy_config()
    for name in ("send_message", "send_dsl", "read_file", "list_dir", "recall", "create_scheduled_task"):
        allowed, reason = tool_allowed(cfg, make_tool(name), StubCtx().user_id, StubCtx().origin)
        assert allowed, name


def test_default_admin_tools_blocked_for_non_admin():
    cfg = make_policy_config()
    for name in ("run_command", "run_python", "write_file", "call_adapter_api", "call_module", "takeover_session"):
        allowed, reason = tool_allowed(cfg, name, "1", "chat")
        assert not allowed, name
        assert reason


async def test_registry_invoke_enforces_policy():
    registry = ToolRegistry()

    async def handler(ctx, **kwargs):
        return "ran"

    registry.register(Tool(
        name="run_command",
        description="t",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=handler,
    ))

    class PolicyMain:
        def __init__(self, allowed):
            self.allowed = allowed
            self.sdk = None
            self.cfg = None

        def check_tool_permission(self, tool, ctx):
            return (True, "") if self.allowed else (False, "需要管理员权限")

    from fakes import make_ctx

    denied = make_ctx(main=PolicyMain(False))
    out = await registry.invoke("run_command", {}, denied)
    assert "管理员" in out

    allowed = make_ctx(main=PolicyMain(True))
    out = await registry.invoke("run_command", {}, allowed)
    assert out == "ran"


def test_safe_tools_override_and_prefix_wildcards():
    cfg = make_policy_config(safe_tools=["eco_Draw_*"])
    allowed, _ = tool_allowed(cfg, make_tool("eco_Draw_draw"), "1", "chat")
    assert allowed
    allowed, _ = tool_allowed(cfg, make_tool("eco_Notes_search"), "1", "chat")
    assert not allowed

    cfg = make_policy_config(admin_tools=["run_command"])
    allowed, _ = tool_allowed(cfg, make_tool("run_command"), "1", "chat")
    assert not allowed
    allowed, _ = tool_allowed(cfg, make_tool("call_module"), "1", "chat")
    assert not allowed

    cfg = make_policy_config(safe_tools=["call_module"])
    allowed, _ = tool_allowed(cfg, make_tool("call_module"), "1", "chat")
    assert allowed


def test_admin_users_pass_everything():
    cfg = make_policy_config(admins=["10001"])
    for name in ("run_command", "eco_Cron_cron", "mcp_x_y"):
        allowed, _ = tool_allowed(cfg, make_tool(name), "10001", "chat")
        assert allowed, name


def test_task_origin_uses_creator_permissions():
    cfg = make_policy_config(admins=["10001"])
    allowed, _ = tool_allowed(cfg, make_tool("run_command"), "10001", "task")
    assert allowed
    allowed, _ = tool_allowed(cfg, make_tool("run_command"), "other", "task")
    assert not allowed


def test_access_override_and_dynamic_tools():
    cfg = make_policy_config(admin_tools=["recall"])
    allowed, _ = tool_allowed(cfg, make_tool("recall"), "1", "chat")
    assert not allowed

    cfg = make_policy_config()
    allowed, _ = tool_allowed(cfg, make_tool("eco_Notes_search"), "1", "chat")
    assert not allowed
    allowed, _ = tool_allowed(cfg, make_tool("mcp_srv_tool"), "1", "chat")
    assert not allowed
