import pytest

from QvQChat.dashboard.manager import DashboardManager

from fakes import FakeMain


def _manager_with_context(contexts):
    main = FakeMain()
    main.sessions.replace_contexts("dashboard:private:web", contexts)
    return DashboardManager(main)


class _Req:
    def __init__(self, body=None, query=None):
        self._body = body or {}
        self.query_params = query or {}

    async def json(self):
        return self._body


@pytest.mark.asyncio
async def test_share_create_fetch_revoke():
    mgr = _manager_with_context([
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
        {"role": "user", "content": "再见"},
    ])
    resp = await mgr.session_share(_Req({"chat_key": "dashboard:private:web", "expires_hours": 24, "max_tokens": 4000}))
    assert resp["ok"] is True
    token = resp["token"]

    got = await mgr.share_messages(_Req(query={"token": token}))
    assert got["chat_key"] == "dashboard:private:web"
    assert [m["content"] for m in got["messages"]] == ["你好", "你好！", "再见"]

    revoked = await mgr.session_share_revoke(_Req({"token": token}))
    assert revoked["ok"] is True
    denied = await mgr.share_messages(_Req(query={"token": token}))
    assert denied[1] == 403


@pytest.mark.asyncio
async def test_share_budget_trims_old_messages():
    mgr = _manager_with_context([
        {"role": "user", "content": "旧" * 500},
        {"role": "assistant", "content": "中" * 500},
        {"role": "user", "content": "新消息"},
    ])
    resp = await mgr.session_share(_Req({"chat_key": "dashboard:private:web", "max_tokens": 300}))
    got = await mgr.share_messages(_Req(query={"token": resp["token"]}))
    contents = [m["content"] for m in got["messages"]]
 
    assert "旧" * 500 not in contents
    assert contents[-1] == "新消息"


@pytest.mark.asyncio
async def test_share_expired_token_rejected():
    mgr = _manager_with_context([{"role": "user", "content": "hi"}])
    resp = await mgr.session_share(_Req({"chat_key": "dashboard:private:web", "expires_hours": 1}))
    token = resp["token"]
    from QvQChat import utils

    shares = mgr._shares()
    shares[token]["expires"] = utils.now_ts() - 100 
    mgr.sdk.storage.set("QvQChat:shares", shares)
    denied = await mgr.share_messages(_Req(query={"token": token}))
    assert denied[1] == 403


@pytest.mark.asyncio
async def test_share_chat_continuation_with_rounds_and_budget():
    """分享续聊：按轮数/token 配额继续对话，纯文本无工具。"""
    mgr = _manager_with_context([
        {"role": "user", "content": "我叫小明"},
        {"role": "assistant", "content": "你好小明！"},
    ])
    resp = await mgr.session_share(_Req({
        "chat_key": "dashboard:private:web", "rounds": 2, "chat_tokens": 500,
    }))
    token = resp["token"]

    calls = []

    class _Resp:
        content = "我记得你，小明"
        usage = {"total_tokens": 100}
        model = "m"

    async def fake_chat(request, **kw):
        calls.append(request)
        return _Resp()

    mgr.main.pool.chat = fake_chat
    out = await mgr.share_chat(_Req({"token": token, "text": "我是谁？"}))
    assert out["ok"] is True
    assert out["reply"] == "我记得你，小明"
    assert out["rounds_left"] == 1
 
    sent = calls[-1]
    assert not getattr(sent, "tools", None)
    joined = " ".join(str(m.get("content")) for m in sent.messages)
    assert "我叫小明" in joined
    assert "分享链接" in joined or "只读" in joined or "share" in joined.lower()

 
    await mgr.share_chat(_Req({"token": token, "text": "再问一句"}))
    exhausted = await mgr.share_chat(_Req({"token": token, "text": "还想问"}))
    assert exhausted[1] == 429
    assert "rounds" in exhausted[0]["error"]

 
    got = await mgr.share_messages(_Req(query={"token": token}))
    assert got["rounds_left"] == 0
    roles = [m["role"] for m in got["continuation"]]
    assert roles == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_share_chat_disabled_without_rounds():
    """rounds=0（默认）是只读分享，不允许续聊。"""
    mgr = _manager_with_context([{"role": "user", "content": "hi"}])
    resp = await mgr.session_share(_Req({"chat_key": "dashboard:private:web"}))
    out = await mgr.share_chat(_Req({"token": resp["token"], "text": "继续"}))
    assert out[1] == 429
