import json
import time
import types
from types import SimpleNamespace

import pytest

from QvQChat.chat.inbox import InboxMixin
from QvQChat.conversation.usermute import UserMuteStore
from QvQChat.tools_builtin import usermute as um

from fakes import FakeMain, make_ctx

MUTE_KEY = "QvQChat:usermute:c1"


@pytest.fixture(autouse=True)
def _no_framework_master(monkeypatch):
    """管理员判定只由 cfg.admins 决定，不受宿主框架主人表影响。"""
    import importlib

    main_mod = importlib.import_module("QvQChat.Main")  # import as 会被包属性遮蔽成类

    monkeypatch.setattr(main_mod, "framework_masters", lambda: (set(), {}))


def make_store():
    from fakes import FakeSDK

    sdk = FakeSDK()
    return UserMuteStore(sdk), sdk


def _loads(out):
    return json.loads(out)


async def test_store_add_refresh_remove():
    store, _ = make_store()
    item = store.add("c1", "u1", reason="骂人", hours=1, by="ai")
    assert item["until"] > time.time()
    assert [e["user_id"] for e in store.active("c1")] == ["u1"]
    assert store.get("c1", "u1")["reason"] == "骂人"
# 同一用户重复 add：刷新原因与期限，不新增条目
    store.add("c1", "u1", reason="又骂", hours=2, by="ai")
    assert len(store.active("c1")) == 1
    assert store.get("c1", "u1")["reason"] == "又骂"
    assert store.remove("c1", "u1") is True
    assert store.get("c1", "u1") is None
    assert store.remove("c1", "u1") is False


async def test_store_permanent_and_lazy_expiry():
    store, sdk = make_store()
    item = store.add("c1", "u1", "spam", hours=0, by="admin")
    assert item["until"] == 0
    assert store.get("c1", "u1") is not None
# 过期条目读取时惰性剔除
    items = sdk.storage.get(MUTE_KEY)
    items[0]["until"] = time.time() - 10
    sdk.storage.set(MUTE_KEY, items)
    assert store.active("c1") == []
    assert store.get("c1", "u1") is None


async def test_tool_ai_add_clamps_to_cap():
    main = FakeMain(user_mute_ai=True, user_mute_max_hours=24)
    ctx = make_ctx(main, chat_key="c1", user_id="u-asker")
    out = await um.user_mute(ctx, action="add", user_id="u1", reason="辱骂", hours=999)
    data = _loads(out)
    assert data["ok"] is True
    entry = main.conversations.user_mutes.get("c1", "u1")
    assert entry["by"] == "ai"
    assert 0 < entry["until"] - time.time() <= 24 * 3600 + 5
    assert main.audits and main.audits[-1]["tool"] == "user_mute_add"


async def test_tool_admin_mute_permanent_and_admin_target_rejected():
    main = FakeMain(admins=["boss", "u1"])
    ctx = make_ctx(main, chat_key="c1", user_id="boss")
    out = await um.user_mute(ctx, action="add", user_id="u2", reason="spam", hours=0)
    data = _loads(out)
    assert data["ok"] is True
    entry = main.conversations.user_mutes.get("c1", "u2")
    assert entry["until"] == 0 and entry["by"] == "admin"
# 管理员不可被屏蔽（管理员发起也不行）
    out2 = await um.user_mute(ctx, action="add", user_id="u1", reason="x")
    assert _loads(out2)["ok"] is False


async def test_tool_ai_mute_disabled_by_config():
    main = FakeMain(user_mute_ai=False, user_mute_max_hours=72)
    ctx = make_ctx(main, chat_key="c1", user_id="u-asker")
    out = await um.user_mute(ctx, action="add", user_id="u9", reason="x")
    assert "disabled" in _loads(out)["error"]


async def test_tool_list_and_remove():
    main = FakeMain(admins=["boss"])
    ctx = make_ctx(main, chat_key="c1", user_id="boss")
    await um.user_mute(ctx, action="add", user_id="u2", reason="r", hours=3)
    listed = _loads(await um.user_mute(ctx, action="list"))
    assert [m["user_id"] for m in listed["muted"]] == ["u2"]
    removed = _loads(await um.user_mute(ctx, action="remove", user_id="u2"))
    assert removed["ok"] is True
    listed2 = _loads(await um.user_mute(ctx, action="list"))
    assert listed2["muted"] == []


def _sender_muted(main, user_id, chat_key="c1"):
    obj = SimpleNamespace(is_admin=main.is_admin, sessions=main.sessions, logger=main.logger)

    class FakeEvent:
        def get_user_id(self):
            return user_id

        def get_platform(self):
            return "onebot11"

    return types.MethodType(InboxMixin._sender_muted, obj)(chat_key, FakeEvent())


def test_intake_gate_mutes_non_admin_only():
    main = FakeMain(admins=["boss"])
    main.conversations.user_mutes.add("c1", "u1", "reason", hours=5, by="ai")
    assert _sender_muted(main, "u1") is True
    assert _sender_muted(main, "boss") is False
    assert _sender_muted(main, "u2") is False
    assert _sender_muted(main, "", chat_key="c1") is False


def test_tool_registered():
    main = FakeMain()
    um.register(main.registry, main)
    names = {t.name for t in main.registry.list()}
    assert "user_mute" in names
