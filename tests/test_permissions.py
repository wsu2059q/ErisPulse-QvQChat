from QvQChat.Main import _flatten_masters, is_admin_user, is_framework_master, tool_allowed
from QvQChat.agent.tools import Tool, ToolRegistry

from fakes import make_config


def make_policy_config(**overrides):
    return make_config(**overrides)


SAFE_TOOLS = {"send_message", "send_dsl", "read_file", "list_dir", "recall", "create_scheduled_task",
# 内置联网工具（tools_builtin/web.py 注册为 safe）
              "web_search", "web_fetch"}


def make_tool(name):
    return Tool(
        name=name,
        description="t",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=None,
        access="safe" if name in SAFE_TOOLS else "admin",
    )


class StubCtx:
    def __init__(self, user_id="1", origin="chat", platform="onebot11"):
        self.user_id = user_id
        self.origin = origin
        self.platform = platform


def test_is_admin_semantics():
    cfg = make_policy_config()
    assert is_admin_user(cfg, "1", "dashboard") is True
    assert is_admin_user(cfg, "1", "rpc") is True
    assert is_admin_user(cfg, "1", "chat") is False

    cfg = make_policy_config(admins=["10001"])
    assert is_admin_user(cfg, "10001", "chat") is True
    assert is_admin_user(cfg, "1", "chat") is False


def test_master_checker_failure_logged_not_silent(monkeypatch):
    """框架主人判定抛错时不再静默（限频 warning），且退回 admins 名单。"""
    import importlib

    main_module = importlib.import_module("QvQChat.Main")
    main_module._WARNED.clear()
    logged = []

    class Logger:
        def warning(self, msg):
            logged.append(msg)

    def boom(platform, user_id):
        raise RuntimeError("framework broken")

    cfg = make_policy_config(admins=["777"])
    assert is_admin_user(cfg, "777", "chat", "onebot11", boom, Logger()) is True
    assert any("master_checker failed" in m for m in logged)


def test_global_master_fallback_list(monkeypatch):
    """框架 is_master 判否时直读主人表兜底：全局 list 主人默认就是管理员。"""
    import importlib

    main_module = importlib.import_module("QvQChat.Main")
    monkeypatch.setattr(main_module, "framework_masters", lambda: ({"42", "43"}, {}))
    cfg = make_policy_config()
    assert is_admin_user(cfg, "42", "chat", "onebot11", lambda p, u: False) is True
    assert is_admin_user(cfg, "99", "chat", "onebot11", lambda p, u: False) is False


def test_platform_master_matching_tolerates_platform_alias(monkeypatch):
    """平台主人：配置写 onebot、事件平台是 onebot11 也要认（前缀宽容匹配）。"""
    import importlib

    main_module = importlib.import_module("QvQChat.Main")
    monkeypatch.setattr(main_module, "framework_masters", lambda: (set(), {"onebot": {"42"}}))
    cfg = make_policy_config()
    assert is_admin_user(cfg, "42", "chat", "onebot11", lambda p, u: False) is True
# 不相关平台不认
    assert is_admin_user(cfg, "42", "chat", "telegram", lambda p, u: False) is False


def test_no_master_and_no_admins_means_no_chat_admin(monkeypatch):
    """两者都没配时不瞎猜：聊天侧无人是管理员（Dashboard/本地来源除外）。"""
    import importlib

    main_module = importlib.import_module("QvQChat.Main")
    monkeypatch.setattr(main_module, "framework_masters", lambda: (set(), {}))
    cfg = make_policy_config()
    assert is_admin_user(cfg, "42", "chat", "onebot11", lambda p, u: False) is False
    assert is_admin_user(cfg, "42", "dashboard") is True


def test_framework_masters_reads_runtime_list(monkeypatch):
    """master.list() 可用时以它为准（含运行时 add 的主人）。"""
    import importlib

    main_module = importlib.import_module("QvQChat.Main")
    fake_master = type("M", (), {"list": staticmethod(lambda: {"global": ["7"], "onebot11": ["8"]})})
    monkeypatch.setattr(main_module, "_master_config_users", lambda: None)
    monkeypatch.setitem(__import__("sys").modules, "ErisPulse.Core", __import__("types").SimpleNamespace(master=fake_master))
    global_ids, platform_ids = main_module.framework_masters()
    assert global_ids == {"7"} and platform_ids == {"onebot11": {"8"}}


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


def test_flatten_masters_nested_account_shape():
    """多账户部署：平台→账户→主人列表 的嵌套形态要能展平识别（主人不算主人的根因）。"""
    g, p2 = _flatten_masters({"onebot11": {"643319481": [1345197918]}})
    assert "1345197918" in p2["onebot11"]
    # 平台匹配走宽容前缀
    g2, p3 = _flatten_masters({"global": [42], "yunhu": [77]})
    assert 42 in g2 or "42" in g2
    assert "77" in p3["yunhu"]
    # 散值形态
    g4, p4 = _flatten_masters({"onebot11": 1345197918})
    assert "1345197918" in p4["onebot11"]


def test_command_args_text_accepts_list():
    """回归：Napcat 等适配器 get_command_args 返回 list——此前直接 strip 炸掉整条 /qvq 命令。"""
    from QvQChat.chat.cli import command_args_text

    assert command_args_text(["whoami"]) == "whoami"
    assert command_args_text(["persona", "switch ", "cat "]) == "persona switch cat"
    assert command_args_text("whoami") == "whoami"
    assert command_args_text(None) == ""
    assert command_args_text([]) == ""


def test_check_tool_permission_passes_tool_object():
    """回归：check_tool_permission 此前把 tool.name（str）传给 tool_allowed——
    getattr(tool, "access", "admin") 恒为 admin，普通用户连 safe 工具（联网搜索）都被拒。"""
    from QvQChat.Main import Main

    class StubSelf:
        cfg = make_policy_config(admins=["10001"])

        def _master_checker(self):
            return lambda platform, uid: False

    # safe 工具（如 web_search）：非管理员也能在调用期放行
    ok, reason = Main.check_tool_permission(StubSelf(), make_tool("web_search"), StubCtx(user_id="999"))
    assert ok, reason
    # admin 工具：非管理员仍然拒绝
    ok, reason = Main.check_tool_permission(StubSelf(), make_tool("run_command"), StubCtx(user_id="999"))
    assert not ok and reason
    # 管理员全放行
    ok, _ = Main.check_tool_permission(StubSelf(), make_tool("run_command"), StubCtx(user_id="10001", origin="chat"))
    assert ok


def test_web_tools_safe_for_everyone():
    """联网工具 access=safe：普通用户可搜索/读网页（用户报告"网络搜索需要框架主人"）。"""
    cfg = make_policy_config()
    for name in ("web_search", "web_fetch"):
        allowed, reason = tool_allowed(cfg, make_tool(name), "999", "chat", "onebot11")
        assert allowed, f"{name}: {reason}"


def test_command_yields_framework_prefix(monkeypatch):
    """命令让路：配置前缀 ∪ 框架命令系统动态前缀（如自定义 qvqchat），不拦截只放行。"""
    from QvQChat.Main import Main

    class StubSelf:
# 非绑定调用：stub 需要自带方法引用（self 查找发生在 stub 上）
        _command_yields = Main._command_yields
        _is_command_message = Main._is_command_message

        def __init__(self, prefixes):
            self.cfg = make_config(command_prefixes=prefixes)

    # 框架命令系统可导入：动态读 prefix（str 或 list 都要认）
    try:
        from ErisPulse.Core.Event import command as fw_command
    except Exception:
        fw_command = None
    if fw_command is not None:
        original = getattr(fw_command, "prefix", None)
        try:
            fw_command.prefix = ["/", "qvqchat"]
            yields = StubSelf(["#"])._command_yields()
            assert "#" in yields and "qvqchat" in yields and "/" in yields
            # 长前缀优先（qvqchat 长于 /），避免前缀互为前缀时误判；
            # 等长前缀（# 与 /）之间顺序不作要求（set 顺序不稳定）
            assert yields[0] == "qvqchat"
            # 框架前缀自定义后：qvqchat 开头的消息让路给分发器（前缀命中即让路，与分发器行为一致）
            assert StubSelf(["#"])._is_command_message(_StubEvent(False), "qvqchat status")
            assert not StubSelf(["#"])._is_command_message(_StubEvent(False), "qvq 状态")
        finally:
            if original is not None:
                fw_command.prefix = original
    else:
        # 测试环境无框架：仅验证配置前缀与排序不变量
        yields = StubSelf(["#", "/"])._command_yields()
        assert "#" in yields and "/" in yields


class _StubEvent:
    def __init__(self, is_command):
        self._is_command = is_command

    def is_command(self):
        return self._is_command


def test_is_command_message_yield_and_pass():
    """命令消息让路判定：前缀命中让路（不认领），普通聊天照常处理。"""
    from QvQChat.Main import Main

    class StubSelf:
# 非绑定调用：stub 需要自带方法引用
        _command_yields = Main._command_yields
        _is_command_message = Main._is_command_message
        cfg = type("Cfg", (), {"command_prefixes": ["#", "/"]})()

    # 让路：框架已打标的命令 + 前缀命中
    s = StubSelf()
    assert s._is_command_message(_StubEvent(True), "随便什么")
    assert s._is_command_message(_StubEvent(False), "/help")
    assert s._is_command_message(_StubEvent(False), "#话题")
    # 普通聊天：不命中任何前缀 → 走正常触发流程
    assert not s._is_command_message(_StubEvent(False), "今天天气怎么样")


def test_whoami_renders_identity_view():
    """whoami 精简为身份视角：身份/判定来源/账号/可用范围（完整诊断降级到 debug 日志）。"""
    from QvQChat import texts

    admin = texts.t("cmd_whoami", identity=texts.t("whoami_admin"), source=texts.t("whoami_source_master"),
                    uid="42", platform="onebot11", scope=texts.t("whoami_scope_admin"))
# 测试环境语言不定：关键内容中英任一命中即可
    assert ("管理员" in admin or "admin" in admin) and ("主人表" in admin or "master table" in admin) and "42" in admin
    member = texts.t("cmd_whoami", identity=texts.t("whoami_member"), source=texts.t("whoami_source_none"),
                     uid="999", platform="qq", scope=texts.t("whoami_scope_member"))
    assert ("普通用户" in member or "member" in member) and ("未命中" in member or "no admin source" in member) \
        and ("联网搜索" in member or "web search" in member)
