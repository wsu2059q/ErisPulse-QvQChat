import asyncio
import json
from types import SimpleNamespace

from QvQChat.dashboard.manager import DashboardManager
from fakes import FakeMain


class FakeV1Request:
    def __init__(self, body=None, auth="", token="tok"):
        self._body = body or {}
        self.raw = SimpleNamespace(headers={"Authorization": auth})
        self._token = token

    async def json(self):
        return self._body


def make_manager(monkey_reply=None):
    main = FakeMain()
    manager = DashboardManager(main)

    async def fake_chat(session, text, **kwargs):
        main.v1_calls = getattr(main, "v1_calls", [])
        main.v1_calls.append((session, text, kwargs.get("on_delta")))
        if kwargs.get("on_delta"):
            kwargs["on_delta"]("流式")
        return "完整回复"

    main.run_dashboard_chat = fake_chat
    return manager, main


async def test_v1_models_auth():
    manager, main = make_manager()
    ok = FakeV1Request(auth="Bearer " + manager._own_token())
    bad = FakeV1Request(auth="Bearer wrong")
    r_ok = await manager.v1_models(ok)
    r_bad = await manager.v1_models(bad)
    assert r_ok["object"] == "list"
    assert r_bad[1] == 401


async def test_v1_completion_non_stream():
    manager, main = make_manager()
    req = FakeV1Request(
        body={"model": "p:m", "messages": [{"role": "user", "content": "你好"}], "user": "alice"},
        auth="Bearer " + manager._own_token(),
    )
    resp = await manager.v1_chat_completions(req)
    assert resp["object"] == "chat.completion"
    assert resp["choices"][0]["message"]["content"] == "完整回复"
    session, text, _ = main.v1_calls[0]
    assert text == "你好"
    assert session.startswith("dashboard:private:api_alice")


async def test_v1_completion_stream():
    manager, main = make_manager()
    req = FakeV1Request(
        body={"messages": [{"role": "user", "content": "画个圈"}], "stream": True},
        auth="Bearer " + manager._own_token(),
    )
    resp = await manager.v1_chat_completions(req)
    chunks = []
    async for piece in resp.body_iterator:
        chunks.append(piece if isinstance(piece, bytes) else piece.encode("utf-8"))
    text = b"".join(chunks).decode("utf-8")
    assert text.startswith("data: ")
    assert "chat.completion.chunk" in text
    assert "流式" in text
    assert text.rstrip().endswith("data: [DONE]")


async def test_v1_rejects_empty_messages():
    manager, main = make_manager()
    req = FakeV1Request(body={"messages": []}, auth="Bearer " + manager._own_token())
    resp = await manager.v1_chat_completions(req)
    assert resp[1] == 400
