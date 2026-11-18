# 4.8 新端点：让渡状态/结束 / 后台子智能体列表与取消 / 会话行 sub: 装饰 / full_access 策略
import time

import pytest

from QvQChat.conversation.policy import get_policy, set_policy
from QvQChat.dashboard.api_sessions import _sub_decoration
from QvQChat.dashboard.manager import DashboardManager
from QvQChat.tools_builtin import agent as agent_tools

from fakes import FakeMain

PARENT = "onebot11:group:1@bot_a"


class _Req:
    def __init__(self, body=None, query=None):
        self._body = body or {}
        self.query_params = query or {}

    async def json(self):
        return self._body


def make_manager():
    main = FakeMain()
    return main, DashboardManager(main)


# ---------- sub: 会话键装饰 ----------


def test_sub_decoration_spawn_key():
    deco = _sub_decoration("sub:" + PARENT + ":abcd1234")
    assert deco == {"kind": "sub", "sub_of": PARENT}


def test_sub_decoration_demote_key():
    deco = _sub_decoration("sub:" + PARENT + ":demote:abcd1234")
    assert deco == {"kind": "sub", "sub_of": PARENT}


def test_sub_decoration_handover_key():
    deco = _sub_decoration("sub:handover:" + PARENT + ":abcd1234")
    assert deco == {"kind": "handover", "sub_of": PARENT}


def test_sub_decoration_ignores_plain_keys():
    assert _sub_decoration(PARENT) == {}
    assert _sub_decoration("") == {}


async def test_sessions_rows_carry_sub_decoration():
    main, manager = make_manager()
    store = main.sdk.storage
    store.set("QvQChat:conv:" + PARENT, {"contexts": []})
    store.set("QvQChat:conv:sub:handover:" + PARENT + ":abcd1234", {"contexts": []})
    resp = await manager.sessions_get(_Req(query={"limit": "50"}))
    by_key = {s["chat_key"]: s for s in resp["sessions"]}
    assert by_key["sub:handover:" + PARENT + ":abcd1234"]["kind"] == "handover"
    assert by_key["sub:handover:" + PARENT + ":abcd1234"]["sub_of"] == PARENT
    assert "kind" not in by_key[PARENT]


# ---------- 让渡状态 / 结束 ----------


async def test_handover_get_idle():
    main, manager = make_manager()
    resp = await manager.handover_get(_Req(query={"chat_key": PARENT}))
    assert resp == {"active": False}


async def test_handover_get_strips_role_prompt():
    main, manager = make_manager()
    main.sdk.storage.set("QvQChat:handover:" + PARENT, {
        "active": True, "sub_key": "sub:handover:" + PARENT + ":abcd1234",
        "role_prompt": "SECRET-ROLE", "setup": "扮演病人",
        "turns": 2, "max_turns": 30, "started": time.time(),
    })
    resp = await manager.handover_get(_Req(query={"chat_key": PARENT}))
    assert resp["active"] is True
    assert resp["setup"] == "扮演病人"
    assert "role_prompt" not in resp
    assert "SECRET-ROLE" not in str(resp)


async def test_handover_stop_404_when_idle():
    main, manager = make_manager()
    resp = await manager.handover_stop(_Req(body={"chat_key": PARENT}))
    assert resp[1] == 404 and "error" in resp[0]


async def test_handover_stop_delegates_to_main():
    main, manager = make_manager()
    calls = []

    async def fake_stop(chat_key, **_):
        calls.append(chat_key)
        return True

    main.handover_stop = fake_stop
    main.sdk.storage.set("QvQChat:handover:" + PARENT, {"active": True, "sub_key": "sub:handover:" + PARENT + ":abcd1234"})
    resp = await manager.handover_stop(_Req(body={"chat_key": PARENT}))
    assert resp == {"ok": True}
    assert calls == [PARENT]


# ---------- 后台子智能体列表 / 取消 ----------


async def test_subjobs_lists_terminal_probe():
    main, manager = make_manager()
    sub_key = "sub:" + PARENT + ":abcd1234"
    main.sdk.storage.set("QvQChat:subjob:" + sub_key, {
        "sub_key": sub_key, "parent_chat_key": PARENT, "task": "抓数据",
        "status": "done", "started": time.time(), "finished": time.time(), "ms": 42,
    })
    index = main.sdk.storage.get("QvQChat:subjob_index", [])
    main.sdk.storage.set("QvQChat:subjob_index", index + [sub_key])
    resp = await manager.subjobs_get(_Req())
    assert resp["total"] == 1
    row = resp["jobs"][0]
    assert row["status"] == "done" and row["parent_chat_key"] == PARENT and row["ms"] == 42


async def test_subjob_cancel_404_when_not_running():
    main, manager = make_manager()
    resp = await manager.subjobs_cancel(_Req(body={"sub_key": "sub:x:abcd1234"}))
    assert resp[1] == 404


async def test_subjob_cancel_running_task():
    main, manager = make_manager()
    sub_key = "sub:" + PARENT + ":abcd1234"

    async def sleeper():
        await pytest.__class__.__name__ and None  # pragma: no cover

    import asyncio

    task = asyncio.ensure_future(asyncio.sleep(60))
    agent_tools.register_live_subjob(sub_key, task)
    try:
        resp = await manager.subjobs_cancel(_Req(body={"sub_key": sub_key}))
        assert resp == {"ok": True}
        await asyncio.sleep(0)
        assert task.cancelled() or task.done()
    finally:
        agent_tools.unregister_live_subjob(sub_key)
        task.cancel()


# ---------- 会话级完全信任 ----------


async def test_full_access_policy_roundtrip_and_audit():
    main, manager = make_manager()
    resp = await manager.session_policy(_Req(body={"chat_key": PARENT, "full_access": True}))
    assert resp["policy"]["full_access"] is True
    assert get_policy(main.sdk, PARENT)["full_access"] is True
    assert any(e["tool"] == "session_full_access" for e in main.audits)
    resp = await manager.session_policy(_Req(body={"chat_key": PARENT, "full_access": False}))
    assert resp["policy"]["full_access"] is False


def test_set_policy_rejects_junk():
    set_policy(FakeMain().sdk, PARENT, full_access="not-a-bool")
