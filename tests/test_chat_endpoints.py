from QvQChat.dashboard.manager import DashboardManager

from fakes import FakeMain


class _ChatRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def make_manager():
    main = FakeMain()
    return main, DashboardManager(main)


async def test_chat_post_rejects_when_busy():
    """回归：SSE 回退路径盲 POST /chat 不得与服务端运行中的任务双跑。"""

    main, manager = make_manager()
    manager._live.start("dashboard:private:web")
    resp = await manager.chat_post(_ChatRequest({"text": "hi", "session": "dashboard:private:web"}))
    assert resp == ({"error": "session busy"}, 409)


async def test_chat_post_allows_when_idle():
    calls = []

    class _Main(FakeMain):
        async def run_dashboard_chat(self, session, text, **kw):
            calls.append((session, text))
            return "ok"

    main = _Main()
    manager = DashboardManager(main)
    resp = await manager.chat_post(_ChatRequest({"text": "hi", "session": "dashboard:private:web"}))
    assert resp == {"reply": "ok", "session": "dashboard:private:web"}
    assert calls == [("dashboard:private:web", "hi")]


async def test_session_rename_and_regenerate():
    """F2：改名走 set_name；重新生成弹出末轮交换并返回 user 文本。"""
    main, manager = make_manager()
    key = "dashboard:private:web"
    main.sessions.append_user(key, "原始问题")
    main.sessions.append(key, "assistant", "原回答")

    resp = await manager.session_rename(_ChatRequest({"chat_key": key, "name": "新名字"}))
    assert resp["ok"] is True
    assert main.sessions.list_sessions()[0]["name"] == "新名字"

    resp = await manager.session_regenerate(_ChatRequest({"chat_key": key}))
    assert resp["ok"] is True
    assert resp["text"] == "原始问题"
    assert main.sessions.get_contexts(key) == []


async def test_session_regenerate_requires_trailing_assistant():
    _, manager = make_manager()
    main = manager.main
    main.sessions.append_user("dashboard:private:web", "只有用户消息")
    resp = await manager.session_regenerate(_ChatRequest({"chat_key": "dashboard:private:web"}))
    assert resp == ({"error": "nothing to regenerate"}, 409)
