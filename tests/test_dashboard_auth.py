from QvQChat.Main import Main
from QvQChat.dashboard.manager import DashboardManager
from QvQChat.tools_builtin import code, computer

from fakes import FakeMain, FakeRequest, make_ctx


def make_manager(view_token=""):
    main = FakeMain(view_token=view_token)
    return main, DashboardManager(main)


def test_own_token_generated_and_stable():
    main, manager = make_manager()
    token = manager._own_token()
    assert len(token) >= 20
    assert manager._own_token() == token
    assert main.sdk.storage.get("QvQChat:auth_token") == token


def test_own_token_config_override():
    main, manager = make_manager(view_token="my-fixed-token")
    assert manager._own_token() == "my-fixed-token"


def test_authorized_rejects_missing_and_wrong():
    main, manager = make_manager()
    assert manager._authorized(FakeRequest()) is False
    assert manager._authorized(FakeRequest(bearer="nope")) is False
    assert manager._authorized(FakeRequest(token="nope")) is False


def test_authorized_accepts_own_token():
    main, manager = make_manager()
    token = manager._own_token()
    assert manager._authorized(FakeRequest(bearer=token)) is True
    assert manager._authorized(FakeRequest(token=token)) is True


def test_authorized_accepts_dashboard_token():
    class FakeDashboard:
        def verify_token(self, token):
            return token == "dash-token"

        def verify_request(self, request):
            return False

    main, manager = make_manager()
    main.sdk.module._catalog = {"Dashboard": FakeDashboard()}
    assert manager._authorized(FakeRequest(bearer="dash-token")) is True
    assert manager._authorized(FakeRequest(bearer="still-own")) is False
    own = manager._own_token()
    assert manager._authorized(FakeRequest(bearer=own)) is True


async def test_guard_returns_401_when_unauthorized():
    main, manager = make_manager()

    async def handler(request):
        return {"ok": True}

    wrapped = manager._guard(handler)
    result = await wrapped(FakeRequest(bearer="wrong"))
    assert result[1] == 401
    token = manager._own_token()
    result = await wrapped(FakeRequest(bearer=token))
    assert result == {"ok": True}


def test_is_recap_suppression():
    trace = [{"tool": "send_message", "arguments": "{}", "output": "ok"}]
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("已把 15 个适配器列表发到群里。", trace) is True
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("已经完成安装。", trace) is True
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("这是正文回答，不是复述。", trace) is False
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("已把列表发到群里，另外这个问题的根因是……" + "补充" * 100, trace) is False
    assert __import__('QvQChat.conversation.delivery', fromlist=['Delivery']).Delivery._is_recap("已把列表发到群里", []) is False


async def test_run_command_skips_confirm_when_trusted():
    ctx = make_ctx(admins=["1"], trust_agent=True)
    out = await computer.run_command(ctx, "taskkill /f /pid 999999")
    assert "cancel" not in out.lower() and "取消" not in out


async def test_run_python_confirm_shows_code():
    captured = {}

    async def confirmer(ctx, text, timeout=60):
        captured["text"] = text
        return False

    ctx = make_ctx(admins=["1"], confirmer=confirmer)
    out = await code.run_python(ctx, code="print('qvq-secret-42')", timeout=5)
    assert "qvq-secret-42" in captured["text"]
    assert "cancel" in out.lower() or "取消" in out


async def test_run_python_skips_confirm_when_trusted():
    ctx = make_ctx(admins=["1"], trust_agent=True)
    out = await code.run_python(ctx, code="print('trusted-run')", timeout=20)
    assert "trusted-run" in out


async def test_config_get_returns_localized_meta():
    main, manager = make_manager()

    class FakeQp:
        pass

    data = await manager.config_get(FakeQp())
    fields = {f["key"]: f for f in data["fields"]}
    assert fields["default_model"]["group"] == "model"
    assert fields["security_level"]["widget"] == "select"
    assert fields["security_level"]["options"] == ["strict", "standard", "permissive"]
    assert fields["default_model"]["description"]
    assert fields["view_token"]["group"] == "access"
