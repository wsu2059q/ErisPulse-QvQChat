import inspect
from types import SimpleNamespace

from QvQChat.Main import Main
from QvQChat import texts

from fakes import FakeChatEvent, FakeMain


def make_main(**overrides):
    main = FakeMain(**overrides)
    main.cfg.context_compress_tokens = 0
    main._pending = {}
    main._chat_locks = {}
    main._rate_window = {}
    main._rate_notice_shown = {}
    for name in (
        "_seed_history", "_transcript_rows", "_label_seed_rows", "_group_nicknames",
    ):
        static_attr = inspect.getattr_static(Main, name)
        if isinstance(static_attr, staticmethod):
            setattr(main, name, static_attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))
    return main


def _transcript(rows):
    def recent(seconds, limit=200):
        return rows

    return SimpleNamespace(recent=recent)


GROUP_KEY = "onebot11:group:1"


async def test_seed_labels_user_with_sender():
    main = make_main()
    main.sdk.transcript = _transcript(
        [
            {"role": "user", "text": "更新框架到2.11.0", "sender": "u2", "session_key": GROUP_KEY},
        ]
    )

    class NickAdapter:
        calls = []

        async def call_api(self, endpoint, **params):
            NickAdapter.calls.append(params)
            return {"card": "路人", "nickname": "路人nick"}

    main.sdk.adapter._adapters["onebot11"] = NickAdapter()
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u9")
    seeded = await main._seed_history(ev)
    assert seeded[0]["role"] == "user"
    assert "路人(u2)" in seeded[0]["content"]
    assert "更新框架到2.11.0" in seeded[0]["content"]
    assert seeded[0]["content"].startswith(texts.t("seed_history_header"))


async def test_seed_marks_bot_rows():
    main = make_main()
    main.sdk.transcript = _transcript(
        [
            {"role": "bot", "text": "📢 框架更新情况说明", "sender": "bot", "session_key": GROUP_KEY},
        ]
    )
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u9")
    seeded = await main._seed_history(ev)
    entry = seeded[0]
    assert entry["role"] == "assistant"
    assert texts.t("seed_bot_note") in entry["content"]
    assert "📢 框架更新情况说明" in entry["content"]


async def test_seed_unknown_sender_fallback():
    main = make_main()
    main.sdk.transcript = _transcript(
        [{"role": "user", "text": "旧消息", "sender": "", "session_key": GROUP_KEY}]
    )
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u9")
    seeded = await main._seed_history(ev)
    assert texts.t("seed_unknown_speaker") in seeded[0]["content"]
    assert "旧消息" in seeded[0]["content"]


async def test_seed_falls_back_to_event_history():
    main = make_main()# FakeSDK 无 transcript → 走降级路径
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u9")

    async def history(n):
        return [{"role": "user", "text": "降级历史", "sender": ""}]

    ev.history = history
    seeded = await main._seed_history(ev)
    assert len(seeded) == 1
    assert texts.t("seed_unknown_speaker") in seeded[0]["content"]


async def test_seed_filters_other_session_keys():
    main = make_main()
    main.sdk.transcript = _transcript(
        [
            {"role": "user", "text": "别群消息", "sender": "x", "session_key": "onebot11:group:2"},
            {"role": "user", "text": "本群消息", "sender": "u2", "session_key": GROUP_KEY},
        ]
    )
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u9")
    seeded = await main._seed_history(ev)
    joined = "\n".join(e["content"] for e in seeded)
    assert "本群消息" in joined
    assert "别群消息" not in joined


async def test_seed_respects_history_seed_limit():
    main = make_main(history_seed=2)
    rows = [
        {"role": "user", "text": f"m{i}", "sender": f"u{i}", "session_key": GROUP_KEY}
        for i in range(5)
    ]
    main.sdk.transcript = _transcript(rows)
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u9")
    seeded = await main._seed_history(ev)
    assert len(seeded) == 2
    assert "m4" in seeded[-1]["content"]
    assert "m0" not in "\n".join(e["content"] for e in seeded)


async def test_nickname_cache_roundtrip():
    main = make_main()
    main.sdk.transcript = _transcript(
        [{"role": "user", "text": "hi", "sender": "u2", "session_key": GROUP_KEY}]
    )

    class NickAdapter:
        calls = []

        async def call_api(self, endpoint, **params):
            NickAdapter.calls.append(params)
            return {"card": "路人"}

    adapter = NickAdapter()
    main.sdk.adapter._adapters["onebot11"] = adapter
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u9")
    await main._seed_history(ev)
    await main._seed_history(ev)
    assert len(NickAdapter.calls) == 1# 第二次走缓存


async def test_persist_sender_group():
    main = FakeMain()
    svc = main.sessions
    await svc.prepare(
        GROUP_KEY,
        "hello",
        persist=True,
        sender_id="u9",
    )
    stored = svc.get_contexts(GROUP_KEY)
    assert stored and stored[-1].get("sender") == "u9"


def test_new_texts_keys_all_locales():
    for key in (
        "scene_speaker_note",
        "scene_group_noid",
        "scene_group_attribution",
        "scene_isolation_note",
        "seed_bot_note",
        "seed_unknown_speaker",
        "seed_history_header",
    ):
        block = texts.STRINGS.get(key)
        assert isinstance(block, dict) and len(block) >= 5, key
        assert all(str(v).strip() for v in block.values()), key


async def test_scene_attribution_note_injected():
    """群聊 system 应包含"当前发言者"认知；隔离模式追加隔离说明。"""
    import asyncio

    from test_aggregate import make_main as aggregate_make_main

    main = aggregate_make_main(group_isolation=True, aggregate_window=0.05)
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u2", user_name="活塞头", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert main.captured
    system = main.captured[0]["system"]
# 当前发言者明确注入，且提示不要把历史发言者当作当前发言者
    assert "活塞头" in system and "u2" in system
    assert texts.t("scene_isolation_note")[:8] in system


async def test_scene_attribution_without_isolation():
    import asyncio

    from test_aggregate import make_main as aggregate_make_main

    main = aggregate_make_main(group_isolation=False, aggregate_window=0.05)
    ev = FakeChatEvent(text="捏", group=True, group_id="1", user_id="u2", user_name="活塞头", at=True)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.15)
    assert main.captured
    system = main.captured[0]["system"]
    assert "活塞头" in system
    assert texts.t("scene_isolation_note")[:8] not in system

