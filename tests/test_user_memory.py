"""用户级跨会话记忆：同一人在多个会话共享"关于 TA"的记忆库。

行为契约：remember/recall/forget/list_memory 的 scope=user 落 usermem:{platform}:{uid}
合成键；仅私聊把 user_mem_key 传进 prepare 注入系统提示，群聊绝不注入。
"""
import inspect

from QvQChat.Main import Main
from QvQChat.agent.tools import ToolContext
from QvQChat.tools_builtin import memory as memory_tool

from fakes import FakeChatEvent, FakeMain

PKEY = "onebot11:private:u1"
UKEY = "QvQChat:mem:usermem:onebot11:u1"


def make_ctx(**cfg_overrides):
    main = FakeMain(**cfg_overrides)
    return main, ToolContext(
        main=main, sdk=main.sdk, config=main.cfg,
        chat_key=PKEY, platform="onebot11", user_id="u1",
        origin="chat", detail_type="private",
    )


async def test_remember_user_scope_routes_to_shared_key():
    main, ctx = make_ctx()
    out = await memory_tool.remember(ctx, "用户有胃病，忌辛辣", category="fact", scope="user")
    assert main.sdk.storage.get(UKEY) is not None
    assert main.sdk.storage.get(f"QvQChat:mem:{PKEY}") is None  # 会话库不落
    assert "胃病" in str(out) or "ok" in str(out).lower() or out  # 有回执即可


async def test_user_scope_shared_across_sessions():
    """A 群/私聊两个会话键，同一 user_id 的 user 库互通；chat 库不互通。"""
    main, ctx = make_ctx()
    await memory_tool.remember(ctx, "用户养了只猫叫年糕", scope="user")
    await memory_tool.remember(ctx, "本群约定每晚开黑", scope="chat")
# 换一个会话键（同一人另一群），user scope 可查到，chat scope 查不到
    ctx2 = ToolContext(
        main=main, sdk=main.sdk, config=main.cfg,
        chat_key="onebot11:group:999", platform="onebot11", user_id="u1",
        origin="chat", detail_type="group",
    )
    user_hits = await memory_tool.recall(ctx2, query="年糕", scope="user")
    assert "年糕" in user_hits
    chat_miss = await memory_tool.recall(ctx2, query="开黑", scope="chat")
    assert "年糕" not in chat_miss


async def test_forget_and_list_user_scope():
    main, ctx = make_ctx()
    await memory_tool.remember(ctx, "用户在备考 CPA", scope="user")
    listed = await memory_tool.list_memory(ctx, scope="user")
    assert "CPA" in listed
    out = await memory_tool.forget(ctx, query="CPA", scope="user")
    assert "1" in out
    assert not await memory_tool.list_memory(ctx, scope="user") or "CPA" not in await memory_tool.list_memory(ctx, scope="user")


async def test_user_scope_falls_back_without_identity():
    """platform/user_id 缺失：退回本会话键（不炸、不误写 global）。"""
    main = FakeMain()
    ctx = ToolContext(main=main, sdk=main.sdk, config=main.cfg, chat_key="onebot11:private:x")
    from QvQChat.tools_builtin.memory import _scope_key

    assert _scope_key(ctx, "user") == "onebot11:private:x"
    assert _scope_key(ctx, "global") == "global"


async def test_prepare_injects_user_memory_only_when_key_given():
    main, ctx = make_ctx()
    main.memory.remember("usermem:onebot11:u1", "用户有胃病，忌辛辣", category="fact")
    prepared = await main.sessions.prepare(
        PKEY, "胃病 忌口 提醒我一下",
        user_mem_key="usermem:onebot11:u1", persist=False,
    )
    assert "胃病" in prepared["system"]
# 不传 user_mem_key（群聊路径）：不注入
    prepared2 = await main.sessions.prepare(
        PKEY, "胃病 忌口 提醒我一下",
        persist=False,
    )
    assert "跨会话记忆" not in prepared2["system"] and "胃病" not in prepared2["system"]


def make_pipeline_main(**overrides):
    """绑好 inbox 方法链的主干（复用 handover 测试的驱动模式）。"""
    main = FakeMain(**overrides)
    main._pending = {}
    main._waiting = {}
    main._chat_locks = {}
    main._rate_window = {}
    main._rate_notice_shown = {}
    from QvQChat.chat.inbox import INBOX_BOUND_METHODS

    for name in INBOX_BOUND_METHODS:
        static_attr = inspect.getattr_static(Main, name)
        if isinstance(static_attr, staticmethod):
            setattr(main, name, static_attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))
    return main


async def test_private_turn_passes_user_mem_key_group_does_not(monkeypatch):
    main = make_pipeline_main(aggregate_window=0.0)
    captured = {}
    real_prepare = main.sessions.prepare

    async def spy_prepare(chat_key, text, **kwargs):
        captured.update(kwargs)
        return await real_prepare(chat_key, text, **kwargs)

    monkeypatch.setattr(main.sessions, "prepare", spy_prepare)

    class Runner:
        async def run(self, **kwargs):
            return type("R", (), {"text": "好的", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = Runner()
    ev = FakeChatEvent(text="私聊一句", group=False)
    await Main._process_locked(main, ev, [{"text": "私聊一句", "sender_id": "u1", "sender_name": "甲"}], "onebot11:private:u1")
    assert captured.get("user_mem_key") == "usermem:onebot11:u1"

    captured.clear()
    ev2 = FakeChatEvent(text="群里一句", group=True, user_id="u1", at=True)
    await Main._process_locked(main, ev2, [{"text": "群里一句", "sender_id": "u1", "sender_name": "甲"}], "onebot11:group:1")
    assert captured.get("user_mem_key") == ""
