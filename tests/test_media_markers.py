"""内联媒体标记：解析、供方发现（旧模块兜底）、按序投递、降级与上限。"""
import asyncio

from QvQChat import texts
from QvQChat.conversation import media

from fakes import FakeChatEvent, FakeMain, FakeSendChain


# ---------- 解析 ----------

def test_split_reply_order_and_aliases():
    parts = media.split_reply("哈哈[表情:得意的猫]你说呢[voice:tired]")
    assert parts == [("text", "哈哈"), ("sticker", "得意的猫"), ("text", "你说呢"), ("voice", "tired")]


def test_split_reply_fullwidth_and_noop():
    assert media.split_reply("【语音：今天好累】") == [("voice", "今天好累")]
    raw = "普通消息\n带换行"
    assert media.split_reply(raw) == [("text", raw)]


def test_split_reply_empty_payload_and_limit():
    assert media.split_reply("[表情:]只剩正文") == [("text", "只剩正文")]
    parts = media.split_reply("[表情:a][表情:b][表情:c]", limit=2)
    assert parts == [("sticker", "a"), ("sticker", "b")]


def test_strip_markers_keeps_voice_text():
    assert media.strip_markers("你好[表情:x]呀[语音:说句话]") == "你好呀说句话"
    assert media.strip_markers("你好[表情:x]呀[语音:说句话]", keep_voice=False) == "你好呀"


# ---------- 供方发现 ----------

def _catalog():
    return {
        "QvQMemes": [{"name": "send_sticker", "description": "sticker"}],
        "TTS": [{"name": "tts_synthesize", "description": "voice"},
                {"name": "tts_speak", "description": "voice send"}],
    }


def test_well_known_services_are_enough_for_old_modules():
    main = FakeMain(catalog=_catalog())
    router = media.MediaRouter(main)
    providers = router.providers()
    assert providers["sticker"].module == "QvQMemes"
    assert providers["sticker"].arg == "query"
    assert providers["voice"].module == "TTS"
    assert providers["voice"].service == "tts_synthesize"
    assert providers["voice"].mode == "produce"
    note = router.prompt_note()
    assert texts.t("media_sticker_note") in note
    assert texts.t("media_voice_note") in note


def test_eco_exclude_hides_provider():
    main = FakeMain(catalog=_catalog(), eco_exclude=["QvQChat", "TTS"])
    assert "voice" not in media.MediaRouter(main).providers()


def test_qvq_media_declaration_overrides_well_known():
    main = FakeMain(catalog={
        "MemeKit": [{"name": "qvq_media"}, {"name": "send_sticker"}],
    })
    main.sdk.module.handlers[("MemeKit", "qvq_media")] = lambda **_: {
        "sticker": {"service": "send_sticker", "arg": "text", "mode": "send"},
    }
    router = media.MediaRouter(main)
    asyncio.run(router.refresh())
    provider = router.providers()["sticker"]
    assert provider.module == "MemeKit" and provider.arg == "text"


def test_admin_only_provider_skipped_for_member():
    main = FakeMain(catalog={"QvQMemes": [{"name": "send_sticker"}]})
    main.eco = type("Eco", (), {"service_access": lambda self, m, s: "admin"})()
    router = media.MediaRouter(main)
    event = FakeChatEvent(user_id="u1")
    assert asyncio.run(router.send(event, "sticker", "cat")) is False


# ---------- 投递 ----------

def _deliver_main(**overrides):
    main = FakeMain(catalog=_catalog(), **overrides)
    chain = FakeSendChain(("Text", "Image", "Voice"))
    main.sdk.adapter.add("onebot11", chain, sends=("Text", "Image", "Voice"))
    main.sdk.module.handlers[("QvQMemes", "send_sticker")] = lambda **_: "已发送"
    main.sdk.module.handlers[("TTS", "tts_synthesize")] = lambda **_: {
        "ok": True, "path": "/tmp/voice.mp3",
    }
    main.cfg.context_compress_tokens = 0
    main.send_chain = chain
    return main


def test_delivery_keeps_marker_order():
    main = _deliver_main()
    event = FakeChatEvent(text="hi", group=True, group_id="1")
    asyncio.run(main.delivery.deliver_reply(event, "哈哈[表情:得意]你好[语音:好累]", [], origin="chat"))
    assert [content for _, content in event.replies] == ["哈哈", "你好"]
    calls = [(module, service) for module, service, _, _ in main.sdk.module.calls]
    assert calls == [("QvQMemes", "send_sticker"), ("TTS", "tts_synthesize")]
    sticker_kwargs = main.sdk.module.calls[0][3]
    assert sticker_kwargs["query"] == "得意"
    assert sticker_kwargs["platform"] == "onebot11"
    assert sticker_kwargs["target_id"] == "1"
    assert sticker_kwargs["target_type"] == "group"
    assert sticker_kwargs["account"] == "bot"
# 合成产物由核心按当前会话账户代发（Voice）
    assert ("Voice", ("/tmp/voice.mp3",), {}) in main.send_chain.calls


def test_delivery_voice_degrades_to_text_when_provider_fails():
    main = _deliver_main()
    def _boom(**_):
        raise RuntimeError("tts down")
    main.sdk.module.handlers[("TTS", "tts_synthesize")] = _boom
    event = FakeChatEvent(text="hi")
    asyncio.run(main.delivery.deliver_reply(event, "[语音:今天好累]", [], origin="chat"))
    assert [content for _, content in event.replies] == ["今天好累"]


def test_delivery_voice_falls_back_to_speak_service():
    main = FakeMain(catalog={"TTS": [{"name": "tts_speak"}]})
    chain = FakeSendChain(("Text", "Image", "Voice"))
    main.sdk.adapter.add("onebot11", chain, sends=("Text", "Image", "Voice"))
    main.sdk.module.handlers[("TTS", "tts_speak")] = lambda **_: "已发送"
    main.cfg.context_compress_tokens = 0
    event = FakeChatEvent(text="hi")
    asyncio.run(main.delivery.deliver_reply(event, "[语音:今天好累]", [], origin="chat"))
    assert [(m, s) for m, s, _, _ in main.sdk.module.calls] == [("TTS", "tts_speak")]
    assert event.replies == []


def test_delivery_sticker_dropped_without_provider():
    main = FakeMain(catalog={})
    main.cfg.context_compress_tokens = 0
    event = FakeChatEvent(text="hi")
    asyncio.run(main.delivery.deliver_reply(event, "[表情:得意]你好", [], origin="chat"))
    assert [content for _, content in event.replies] == ["你好"]


def test_delivery_respects_marker_cap():
    main = _deliver_main(media_marker_max=1)
    event = FakeChatEvent(text="hi")
    asyncio.run(main.delivery.deliver_reply(event, "[表情:a][表情:b]", [], origin="chat"))
    assert len([c for c in main.sdk.module.calls if c[1] == "send_sticker"]) == 1


def test_delivery_switch_off_strips_markers():
    main = _deliver_main(media_markers=False)
    event = FakeChatEvent(text="hi")
    asyncio.run(main.delivery.deliver_reply(event, "你好[表情:x][语音:说句话]", [], origin="chat"))
    assert [content for _, content in event.replies] == ["你好说句话"]
    assert main.sdk.module.calls == []


def test_delivery_text_only_unchanged():
    main = _deliver_main()
    event = FakeChatEvent(text="hi")
    asyncio.run(main.delivery.deliver_reply(event, "普通回复", [], origin="chat"))
    assert [content for _, content in event.replies] == ["普通回复"]
    assert main.sdk.module.calls == []
