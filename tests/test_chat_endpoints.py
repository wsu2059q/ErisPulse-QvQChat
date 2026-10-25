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
