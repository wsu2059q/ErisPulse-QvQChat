"""触发规则开关：all 默认不变 / at_only 群里仅点名 / lurk 只旁听 / off 不响应；
会话级只能收紧不能放宽；listen_off 隐私开关阻断 observe/replied 外发。"""

import asyncio

from QvQChat.Main import Main

from fakes import FakeChatEvent, FakeMain


def make_main(**overrides):
    from test_aggregate import make_main as base

    overrides.setdefault("aggregate_window", 0.01)
    return base(**overrides)


async def _send(main, text="在吗", at=True):
    ev = FakeChatEvent(text=text, group=True, group_id="1", user_id="u9", at=at)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.05)
    return ev


async def test_default_all_unchanged():
    main = make_main(aggregate_window=0.01)
    await _send(main)
    assert main.captured, "默认 all：现有触发规则不变"


async def test_at_only_blocks_plain_group_message():
    main = make_main(aggregate_window=0.01, trigger_mode="at_only")
    await _send(main, at=False)  # 群里没 @：不响应
    assert not main.captured
    await _send(main, at=True)  # @ 了：正常触发
    assert main.captured


async def test_at_only_wake_prefix_counts_as_address():
    main = make_main(aggregate_window=0.01, trigger_mode="at_only", wake_prefixes=["Amer"])
    await _send(main, text="Amer 帮我查个东西", at=False)
    assert main.captured


async def test_at_only_private_still_works():
    main = make_main(aggregate_window=0.01, trigger_mode="at_only")
    ev = FakeChatEvent(text="在吗", group=False, user_id="u1")
    await Main._on_message(main, ev)
    await asyncio.sleep(0.05)
    assert main.captured


async def test_lurk_and_off_never_reply():
    for mode in ("lurk", "off"):
        main = make_main(aggregate_window=0.01, trigger_mode=mode)
        await _send(main, at=True)
        assert not main.captured, mode


async def test_session_override_beats_global():
    main = make_main(aggregate_window=0.01)
    key = "onebot11:group:1"
    main.sessions.set_trigger(key, "off")
    await _send(main, at=True)
    assert not main.captured
# 改回 all：恢复触发
    main.sessions.set_trigger(key, "all")
    await _send(main, at=True)
    assert main.captured
    assert main.sessions.trigger_mode_of(key) == ""  # all 视为未覆盖


def test_set_trigger_validates_mode():
    main = FakeMain()
    main.sessions.set_trigger("k", "bogus")
    assert main.sessions.trigger_mode_of("k") == ""  # 非法值不落库


async def test_session_cannot_exceed_global():
    """会话级只能收紧：全局 at_only 时，会话设 all 被钳回 at_only。"""
    main = make_main(aggregate_window=0.01, trigger_mode="at_only")
    main.sessions.set_trigger("onebot11:group:1", "all")
    await _send(main, at=False)
    assert not main.captured  # 仍不响应未 @ 消息
    await _send(main, at=True)
    assert main.captured  # @ 正常


async def test_session_can_tighten_beyond_global():
    main = make_main(aggregate_window=0.01, trigger_mode="at_only")
    main.sessions.set_trigger("onebot11:group:1", "lurk")  # 收紧到窥屏：@ 也不回
    await _send(main, at=True)
    assert not main.captured


async def test_global_lurk_clamps_looser_session():
    main = make_main(aggregate_window=0.01, trigger_mode="lurk")
    main.sessions.set_trigger("onebot11:group:1", "at_only")  # 想放宽 → 钳回 lurk
    await _send(main, at=True)
    assert not main.captured


async def test_listen_off_blocks_observe_and_replied():
    """隐私开关：listen_off 时 observe/replied 事件不再外发；恢复监听后照常。"""
    main = make_main(aggregate_window=0.01)
    key = "onebot11:group:1"
    main.sessions.set_flags(key, {"listen_off": True})
    await _send(main, at=True)
    events = [e for e, _ in main.sdk.lifecycle.emitted]
    assert "qvq.observe" not in events
    assert "qvq.replied" not in events
# 恢复监听
    main.sessions.set_flags(key, {"listen_off": False})
    await _send(main, at=True)
    events = [e for e, _ in main.sdk.lifecycle.emitted]
    assert "qvq.observe" in events


def test_restricted_note_only_for_non_admin():
    """受限模式：非管理员注入 permission 部件（遇边界提醒找管理员），管理员不注入。"""
    main = FakeMain()
    main.cfg.admins = ["10001"]
    persona = {"id": "p", "name": "P", "system": "sys"}

    parts = main.sessions.build_system_parts(persona, restricted=True)
    joined = "\n".join(p.text for p in parts if p.kind == "permission")
# 测试环境语言不定：中英任一命中即可
    assert ("管理员" in joined) or ("admin" in joined.lower())

    parts_admin = main.sessions.build_system_parts(persona, restricted=False)
    assert all(p.kind != "permission" for p in parts_admin)


def test_sender_restricted_uses_is_admin():
    main = FakeMain()
    main.is_admin = lambda user_id, origin="chat", platform="": user_id == "10001"
    assert main.sessions._sender_restricted("999", "onebot11:999") is True
    assert main.sessions._sender_restricted("10001", "onebot11:10001") is False
    assert main.sessions._sender_restricted("", "onebot11:x") is False  # 无发送者不限制


def test_restricted_note_includes_platform_admin_ids():
    """受限提示带本平台管理员 id（该找谁一目了然）。"""
    main = FakeMain()
    main.cfg.admins = ["10001"]
    persona = {"id": "p", "name": "P", "system": "sys"}
    parts = main.sessions.build_system_parts(persona, restricted=True, admin_ids=["10001", "42"])
    joined = "\n".join(p.text for p in parts if p.kind == "permission")
    assert "10001" in joined and "42" in joined


def test_admin_ids_for_platform_merges_sources():
    """平台管理员 = 配置 admins ∪ 框架主人表（全局 + 本平台）。"""
    import importlib

    main = FakeMain()
    main.cfg.admins = ["10001"]
    main_mod = importlib.import_module("QvQChat.Main")  # 取模块本体（import as 会被包属性遮蔽成类）

    original = getattr(main_mod, "framework_masters", None)
    try:
        main_mod.framework_masters = lambda: ({"7"}, {"onebot11": {"8"}})
        ids = main.sessions._admin_ids_for("onebot11")
    finally:
        if original is not None:
            main_mod.framework_masters = original
    assert {"10001", "7", "8"} <= set(ids)
