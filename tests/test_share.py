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
# 预算内只保留最新部分；第一条超预算被裁掉
    assert "旧" * 500 not in contents
    assert contents[-1] == "新消息"


@pytest.mark.asyncio
async def test_share_expired_token_rejected():
    mgr = _manager_with_context([{"role": "user", "content": "hi"}])
    resp = await mgr.session_share(_Req({"chat_key": "dashboard:private:web", "expires_hours": 1}))
    token = resp["token"]
    from QvQChat import utils

    shares = mgr._shares()
    shares[token]["expires"] = utils.now_ts() - 100# 已过期
    mgr.sdk.storage.set("QvQChat:shares", shares)
    denied = await mgr.share_messages(_Req(query={"token": token}))
    assert denied[1] == 403
