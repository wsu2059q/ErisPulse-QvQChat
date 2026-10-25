import json

from QvQChat import texts
from QvQChat.Main import Main
from QvQChat.agent.tools import ToolRegistry
from QvQChat.tools_builtin import selfconfig

from fakes import FakeMain, FakeSendChain, make_ctx


def _names(registry: ToolRegistry):
    return {t.name for t in registry.list()}


def test_tools_registered_and_flag_gated():
    registry = ToolRegistry()
    selfconfig.register(registry, FakeMain())
    assert {"manage_models", "manage_mcp", "manage_config"} <= _names(registry)
    off = ToolRegistry()
    selfconfig.register(off, FakeMain(self_config=False))
    assert not _names(off) & {"manage_models", "manage_mcp", "manage_config"}


def test_builtin_skill_present_and_gated():
    main = FakeMain()
    assert "self-config" in [s["name"] for s in main.skills.list_skills()]
    off = FakeMain(self_config=False)
    assert "self-config" not in [s["name"] for s in off.skills.list_skills()]
    disabled = FakeMain(skills_disabled=["self-config"])
    skill = next(s for s in disabled.skills.list_skills() if s["name"] == "self-config")
    assert skill["enabled"] is False
    assert skill["source"] == "builtin"


async def test_manage_models_roundtrip():
    ctx = make_ctx()
    out = json.loads(await selfconfig.manage_models(
        ctx,
        action="save",
        provider={"id": "p1", "name": "P1", "base_url": "https://api.p1/v1",
                  "api_key": "sk-secret", "models": [{"id": "m1", "enabled": True}]},
    ))
    assert out["ok"] is True
    assert out["provider"]["api_key"].endswith("cret") and "sk-secret" not in out

    listing = json.loads(await selfconfig.manage_models(ctx, action="list"))
    assert listing["providers"][0]["api_key"].endswith("cret")
    assert listing["providers"][0]["enabled_models"] == ["m1"]

    assert json.loads(await selfconfig.manage_models(ctx, action="set_default", model_id="p1:m1"))["ok"] is True
    assert ctx.sdk.config_sets[-1] == ("QvQChat.default_model", "p1:m1")
    assert "unknown model" in await selfconfig.manage_models(ctx, action="set_default", model_id="nope")

# api_key 留空保留原值
    await selfconfig.manage_models(ctx, action="save", provider={"id": "p1", "base_url": "https://api.p1/v1"})
    stored = ctx.main.pool.get_provider("p1")
    assert stored["api_key"] == "sk-secret"
    assert stored["models"][0]["id"] == "m1"

    assert json.loads(await selfconfig.manage_models(ctx, action="delete", provider_id="p1"))["ok"] is True


async def test_manage_mcp_save_remove():
    ctx = make_ctx()
    out = json.loads(await selfconfig.manage_mcp(
        ctx, action="save", name="srv", transport="http", url="http://127.0.0.1:9",
    ))
    assert out["ok"] is True and out["server"]["url"] == "http://127.0.0.1:9"
    assert any(s["name"] == "srv" for s in ctx.main.mcp.list_servers())
    assert json.loads(await selfconfig.manage_mcp(ctx, action="remove", name="srv"))["ok"] is True
    assert ctx.main.mcp.list_servers() == []


async def test_manage_config_roundtrip():
    ctx = make_ctx()
    everything = json.loads(await selfconfig.manage_config(ctx, action="get"))
    assert "aggregate_window" in everything
    assert json.loads(await selfconfig.manage_config(ctx, action="get", key="tool_notice_mode")) == {
        "tool_notice_mode": "brief"
    }
    out = json.loads(await selfconfig.manage_config(ctx, action="set", updates={"aggregate_window": 0, "bogus": 1}))
    assert out["applied"] == ["aggregate_window"]
    assert set(out["rejected"]) == {"bogus"} and out["rejected"]["bogus"]
    assert ctx.sdk.config_sets[-1] == ("QvQChat.aggregate_window", 0)


async def test_manage_config_rejects_bad_values_with_reason():
    """set 走统一 coerce：坏值拒收并带原因，好值照常抝合落盘。"""
    ctx = make_ctx()
    out = json.loads(await selfconfig.manage_config(
        ctx,
        action="set",
        updates={"context_limit": "", "wake_prefixes": "a\nb", "reply_private": "true", "security_level": "wild"},
    ))
    assert out["applied"] == ["wake_prefixes"]
    assert ctx.sdk.config_sets[-1] == ("QvQChat.wake_prefixes", ["a", "b"])
    assert set(out["rejected"]) == {"context_limit", "reply_private", "security_level"}
    for reason in out["rejected"].values():
        assert reason
    assert out["ok"] is False


async def test_send_message_forward_fallback_reports_honestly():
    """转发尝试失败必须如实回报回落，且记录已发送目标。"""
    from QvQChat.tools_builtin import erispulse

    ctx = make_ctx(forward_threshold=10)
    ctx.main.sdk.adapter.add(
        "test",
        FakeSendChain(sends=("MergeForward", "Text"), fail_on=("MergeForward",)),
        sends=("MergeForward", "Text"),
    )
    out = await erispulse.send_message(ctx, "test", "group", "g1", text="内容" * 40)
    assert texts.t("forward_fallback") in out
    assert ctx.sent_log == [("test", "group", "g1")]


async def test_send_message_failed_status_retries_next_method():
    """OneBot11 式 status=failed 不抛异常，需换下一个发送方式而不是当成功。"""
    from fakes import _Pending
    from QvQChat.tools_builtin import erispulse

    calls = []

    class FailedChain:
        def To(self, *args):
            return self

        def __getattr__(self, name):
            def record(*args, **kwargs):
                calls.append(name)
                return _Pending({"status": "failed", "retcode": 1400})

            return record

    ctx = make_ctx(forward_threshold=0)
    ctx.main.sdk.adapter.add("test", FailedChain(), sends=("Markdown", "Text"))
    out = await erispulse.send_message(ctx, "test", "group", "g1", text="hello")
    assert "send_message" in out and "failed" in out.lower()
    assert calls.count("Markdown") == 1 and calls.count("Text") == 1
    assert ctx.sent_log == []


async def test_run_prompt_skips_final_send_when_ai_delivered():
    """主动任务里 AI 已用 send_message 投递过目标 → 不再补发总结段。"""
    from test_aggregate import make_main

    main = make_main()

    class Runner:
        async def run(self, **kwargs):
            kwargs["ctx"].sent_log.append(("onebot11", "private", "u1"))
            assert any(m.get("role") == "system" and "send_message" in str(m.get("content")) for m in kwargs["messages"])
            return type("R", (), {"text": "日报已发", "usage": {}, "tool_trace": [{"tool": "send_message"}], "rounds": []})()

    main.runner = Runner()
    sends = []

    async def fake_send(platform, detail_type, target_id, segments, from_tools=False):
        sends.append((platform, detail_type, target_id))

    main.delivery = type('D', (), {'send_segments': staticmethod(fake_send)})()
    await Main.run_prompt(main, "onebot11:private:u1", "发日报", origin="task")
    assert sends == []


async def test_run_prompt_tool_run_delivers_as_forward():
    from test_aggregate import make_main

    main = make_main()
    sends = []

    async def fake_send(platform, detail_type, target_id, segments, from_tools=False):
        sends.append((platform, detail_type, target_id, from_tools))

    main.delivery = type('D', (), {'send_segments': staticmethod(fake_send)})()
    await Main.run_prompt(main, "onebot11:private:u1", "纯回答", origin="task")
    assert sends == [("onebot11", "private", "u1", False)]


async def test_manage_personas_bind_and_global():
    ctx = make_ctx()
    out = json.loads(await selfconfig.manage_personas(
        ctx, action="save", persona_id="terse",
        name="Terse", system="Keep it to one sentence.",
    ))
    assert out["ok"] is True
    listing = json.loads(await selfconfig.manage_personas(ctx, action="list"))
    assert any(p["id"] == "terse" for p in listing["personas"])

    out = json.loads(await selfconfig.manage_personas(ctx, action="bind", persona="terse"))
    assert out["chat_key"] == ctx.chat_key
    resolved = ctx.main.personas.resolve(ctx.chat_key)
    assert resolved["id"] == "terse"

    out = json.loads(await selfconfig.manage_personas(ctx, action="set_global", persona_id="concise"))
    assert ctx.main.personas.global_default() == "concise"
    fallback = ctx.main.personas.resolve("other:private:9")
    assert fallback["id"] == "concise"

    out = json.loads(await selfconfig.manage_personas(ctx, action="unbind"))
    assert out["ok"] is True
    out = json.loads(await selfconfig.manage_personas(ctx, action="delete", persona_id="terse"))
    assert out["ok"] is True
