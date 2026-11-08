"""触发规则开关：all 默认不变 / at_only 群里仅点名 / lurk 只旁听 / off 不响应；
会话级只能收紧不能放宽；listen_off 隐私开关阻断 observe/replied 外发。"""

import asyncio
import inspect

from QvQChat.Main import Main

from fakes import FakeChatEvent, FakeMain


def make_main(**overrides):
    from test_aggregate import make_main as base

    overrides.setdefault("aggregate_window", 0.01)
    return base(**overrides)


async def _send(main, text="在吗", at=True, **ev_kw):
    ev = FakeChatEvent(text=text, group=True, group_id="1", user_id="u9", at=at, **ev_kw)
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


async def test_identity_migration_alias_and_merge():
    """身份迁移：alias 只映射；merge 上下文/事实/记忆按时间去重并入，历史跟随新键。"""
    main = make_main()
    key_old = "onebot11:private:3838648009@643319481"
    key_new = "snowluma:private:3838648009@643319481"
# 旧键里已有历史与事实
    old_ev = FakeChatEvent(text="我玩 UNDERVALE", group=False, user_id="3838648009@643319481", account="643319481")
    await Main._on_message(main, old_ev)
    await asyncio.sleep(0.05)  # 等聚合窗：第一条也要真正进会话
    assert main.captured
# 迁移（合并模式）
    summary = main.sessions.migrate_identity(key_old, key_new, "merge")
    assert summary["ok"] and summary["contexts"] >= 1
# 新键来的消息：历史跟到新会话（上下文里带着旧对话）
    new_ev = FakeChatEvent(text="我刚才说我玩什么来着", group=False,
                           user_id="3838648009@643319481", account="643319481")
    await Main._on_message(main, new_ev)
    await asyncio.sleep(0.05)
    assert main.captured[-1]["ctx"].chat_key == key_new
    system = main.captured[-1]["system"] + str(main.captured[-1].get("messages") or "")
# 上下文合并：旧键的消息在新会话上下文里可见
    assert any("UNDERVALE" in str(m.get("content") or "") for m in main.captured[-1].get("messages") or [])
# 映射登记在案
    assert main.sessions.identity_map()[key_old] == key_new
    assert main.sessions.resolve_identity(key_old) == key_new


def test_identity_merge_dedup_and_overwrite_backup():
    """合并去重（完全重复条目只留一份）；覆盖替换上下文且先进回收站。"""
    main = make_main()
    s, t = "k:src", "k:dst"
    main.sessions._save_no_touch(s, {"contexts": [
        {"role": "user", "content": "hello", "ts": 100},
        {"role": "user", "content": "world", "ts": 200},
    ], "facts": ["喜欢猫"]})
    main.sessions._save_no_touch(t, {"contexts": [
        {"role": "user", "content": "hello", "ts": 150},  # 与 source 重复
        {"role": "assistant", "content": "hi", "ts": 160},
    ], "facts": ["喜欢狗"]})
    summary = main.sessions.migrate_identity(s, t, "merge")
    merged = main.sessions._state(t)["contexts"]
    assert summary["contexts"] == 3  # hello 去重，world/hi 保留
    assert [e["content"] for e in merged] == ["hello", "hi", "world"]
    assert set(main.sessions._state(t)["facts"]) == {"喜欢猫", "喜欢狗"}

    summary2 = main.sessions.migrate_identity(t, s, "overwrite")
    assert summary2["ok"] and summary2["backup"]  # 覆盖前备份
    now_src = main.sessions._state(s)["contexts"]
    assert [e["content"] for e in now_src] == ["hello", "hi", "world"]  # 被目标历史替换
    # 回收站里有被覆盖前的目标历史
    hits = [k for k in main.sdk.storage.keys() if "trash" in str(k)]
    assert hits


def _patched_quote_adapter(main, sender_id):
    main.sdk.adapter.add("onebot11", None)
    adapter = main.sdk.adapter.get("onebot11")

    async def fake_call(endpoint, **params):
        return {"sender": {"user_id": sender_id},
                "message": [{"type": "text", "data": {"text": "被引用的那条"}}]}

    adapter.call_api = fake_call


async def test_quote_of_my_message_counts_as_address():
    """引用=艾特：引用本账户的消息等同被点名（get_msg 拉被引用者判定）。"""
    main = make_main(aggregate_window=0.01, trigger_mode="at_only")
    _patched_quote_adapter(main, "bot")  # 被引用的是本账户
    await _send(main, text="接着刚才说", at=False, reply_message_id="M1")
    assert main.captured


async def test_quote_of_my_message_triggers_in_all_mode():
    """all 模式：引用本账户消息也走直触（reply_at），不等插话决策。"""
    main = make_main(aggregate_window=0.01)
    _patched_quote_adapter(main, "bot")
    await _send(main, text="在吗", at=False, reply_message_id="M2")
    assert main.captured


async def test_quote_of_others_does_not_address():
    """引用别人的消息不点名本账户。"""
    main = make_main(aggregate_window=0.01, trigger_mode="at_only")
    _patched_quote_adapter(main, "someone_else")
    await _send(main, text="帮我看看这条", at=False, reply_message_id="M3")
    assert not main.captured


async def test_quote_inline_sender_skips_api():
    """reply 段内联被引用者时直接判定，不再走适配器调用（调了就会炸）。"""
    main = make_main(aggregate_window=0.01, trigger_mode="at_only")
    main.sdk.adapter.add("onebot11", None)
    adapter = main.sdk.adapter.get("onebot11")

    async def boom(endpoint, **params):
        raise AssertionError("get_msg should not be called")

    adapter.call_api = boom
    await _send(main, text="回复你上一条", at=False,
                reply_message_id="M4", reply_sender="bot")
    assert main.captured


def test_dup_gate_cleanup_never_crashes():
    """容量清理曾把纯 float 时间戳当元组下标（'float' object is not subscriptable，
    claims 超 256 条后每条消息死在触发判定前）——回归：清理安全淘汰、拦截仍有效。"""
    import time as _time

    main = make_main()

    class IdEv(FakeChatEvent):
        def __init__(self, mid, text):
            super().__init__(text=text, group=True, group_id="1", user_id="u9")
            self._mid = mid

        def get(self, key, default=None):
            if key == "message_id":
                return self._mid
            if key == "time":
                return 1000
            return default

    for i in range(300):
        assert main._dup_delivery_gate(IdEv(f"M{i}", f"消息{i}"), f"消息{i}") is True
# 清理路径安全（此前在这里 v[1] 下标炸 float）：过期条目被淘汰
    main._msg_claims["bot:Mold"] = _time.time() - 100
    assert main._dup_delivery_gate(IdEv("Mnew", "新消息"), "新消息") is True
    assert "bot:Mold" not in main._msg_claims
    ev = IdEv("MX", "hello")
    assert main._dup_delivery_gate(ev, "hello") is True
    assert main._dup_delivery_gate(ev, "hello") is False  # 6s 窗内同 id 拦截


def test_account_suffix_prefers_self_user_id():
    """账户后缀取 get_self_user_id()（稳定 id）优先于 get_self_account_id()（配置名）。

    同一机器人换配置名（@Amer → @1325859446）不再散成两份会话。
    """
    import inspect

    from QvQChat.chat.inbox import _account_suffix_for
    from test_aggregate import make_main

    main = make_main()
    cfg, sdk = main.cfg, main.sdk
    sdk.adapter.bots = {"1325859446": {"status": "running"}, "Amer": {"status": "running"}}

    class Ev:
        _platform = "onebot11"
        _self = {"user_id": "1325859446", "account_id": "Amer"}

        def get_platform(self):
            return self._platform

        def get(self, key, default=None):
            if key == "self":
                return self._self
            return default

        def get_self_account_id(self):
            return "Amer"  # 配置名（漂移源）

        def get_self_user_id(self):
            return "1325859446"  # 稳定 id

    suffix = _account_suffix_for(cfg, sdk, Ev())
    assert suffix == "@1325859446"


async def test_identity_merge_account_bulk():
    """账户级批量归并：旧 @账户 全部会话 migrate 到新 @账户。"""
    main = make_main()
    s = main.sessions
# 旧账户两个会话
    s.append("snowluma:group:1@Amer", "user", "旧群聊一")
    s.append("snowluma:private:u9@Amer", "user", "旧私聊")
    s.append("onebot11:group:2@Amer", "user", "别的平台不动")
    _Req = type("R", (), {"__init__": lambda self, b: setattr(self, "_b", b),
                          "json": lambda self: _async_ret(self._b)})

    async def _async_ret(v):
        return v

    from types import SimpleNamespace
    from QvQChat.dashboard.api_sessions import SessionsApiMixin

    api = SimpleNamespace(main=main, sdk=main.sdk)
    attr = inspect.getattr_static(SessionsApiMixin, "identity_merge_account")
    api.identity_merge_account = attr.__get__(api)

    result = await api.identity_merge_account(_Req(
        {"platform": "snowluma", "from": "Amer", "to": "1325859446", "mode": "merge"}))
    assert result["migrated"] == 2 and result["ok"]
# 目标会话有旧账户的历史
    assert main.sessions.get_contexts("snowluma:group:1@1325859446")
    assert main.sessions.get_contexts("snowluma:private:u9@1325859446")
# 映射建立：旧键新消息由目标接手
    assert main.sessions.identity_map().get("snowluma:group:1@Amer") == "snowluma:group:1@1325859446"
# 别平台不动
    assert main.sessions.identity_map().get("onebot11:group:2@Amer") is None
