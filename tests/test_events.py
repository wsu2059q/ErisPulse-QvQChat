"""事件收件箱：notice/request 一律入箱 + 生态广播（qvq.notice/qvq.request）+
受控唤醒（通知默认关、白名单+档位+限频；请求默认只广播，开启后 AI 决策汇报管理员）。"""

import asyncio
import inspect

from QvQChat.Main import Main
from QvQChat.agent.tools import ToolContext
from QvQChat.tools_builtin import erispulse

from fakes import FakeNoticeEvent, FakeRequestEvent

# EventsMixin 的方法挂 Main（mixin 宿主），FakeMain 需按名绑定后才能像 inbox 一样自测
_EVENT_METHODS = (
    "_on_notice", "_on_request", "_request_decision", "_maybe_wake_on_notice",
    "_event_chat_key", "_event_self_id", "_event_sub_type", "_event_summary",
    "_event_raw_text", "_inbox_load", "_inbox_save", "_inbox_add", "_inbox_pick",
    "_notice_type_hit", "_notice_rate_ok", "_ev_s",
)


def make_main(**overrides):
    from test_aggregate import make_main as base

    overrides.setdefault("aggregate_window", 0.01)
    main = base(**overrides)
    for name in _EVENT_METHODS:
        attr = inspect.getattr_static(Main, name)
        if isinstance(attr, staticmethod):
            setattr(main, name, attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))
    return main


def emitted(main):
    return [e for e, _ in main.sdk.lifecycle.emitted]


async def test_notice_inboxed_and_broadcast_but_no_wake_by_default():
    """默认全关：通知入箱 + qvq.notice 广播，但不唤醒 AI。"""
    main = make_main()
    ev = FakeNoticeEvent(detail_type="notify", sub_type="poke", group_id="1",
                         target_id="bot", account="bot", event_id="n1")
    await Main._on_notice(main, ev)
    assert not main.captured
    inbox = main._inbox_load("bot")
    assert len(inbox) == 1
    assert inbox[0]["sub_type"] == "poke" and inbox[0]["read"] is False
    assert "qvq.notice" in emitted(main)


async def test_notice_wake_requires_listen_and_whitelist():
    """唤醒三道门：开关、白名单（detail:sub / 平台前缀短名均可）。"""
    main = make_main(notice_listen=True)  # 白名单空：不醒
    await Main._on_notice(main, FakeNoticeEvent(group_id="1", target_id="bot", account="bot"))
    assert not main.captured

    main2 = make_main(notice_listen=True, notice_types=["poke"])  # 命中：醒
    await Main._on_notice(main2, FakeNoticeEvent(group_id="1", target_id="bot", account="bot"))
    await asyncio.sleep(0.05)
    assert main2.captured

    main3 = make_main(notice_listen=True, notice_types=["poke"])  # 平台前缀 detail 去前缀命中
    await Main._on_notice(main3, FakeNoticeEvent(detail_type="onebot11_poke", sub_type="",
                                                 group_id="1", target_id="bot", account="bot"))
    await asyncio.sleep(0.05)
    assert main3.captured


async def test_notice_wake_respects_trigger_modes():
    """档位：off/lurk 永不醒；at_only 只醒被点名的直接互动（target=本账户）；
    环境类通知只在 all 模式醒。"""
    main = make_main(notice_listen=True, notice_types=["poke"], trigger_mode="at_only")
    await Main._on_notice(main, FakeNoticeEvent(group_id="1", target_id="bot", account="bot"))
    await asyncio.sleep(0.05)
    assert main.captured  # 戳的是我 = 被点名

    main2 = make_main(notice_listen=True, notice_types=["group_member_increase"], trigger_mode="at_only")
    await Main._on_notice(main2, FakeNoticeEvent(detail_type="group_member_increase", sub_type="",
                                                 group_id="1", user_id="u5", target_id="u5", account="bot"))
    await asyncio.sleep(0.05)
    assert not main2.captured  # 环境类：at_only 不醒

    main3 = make_main(notice_listen=True, notice_types=["group_member_increase"])
    await Main._on_notice(main3, FakeNoticeEvent(detail_type="group_member_increase", sub_type="",
                                                 group_id="1", user_id="u5", target_id="u5", account="bot"))
    await asyncio.sleep(0.05)
    assert main3.captured  # all：环境类醒

    main4 = make_main(notice_listen=True, notice_types=["poke"], trigger_mode="off")
    await Main._on_notice(main4, FakeNoticeEvent(group_id="1", target_id="bot", account="bot"))
    assert not main4.captured  # off：永不醒


def test_notice_rate_limit():
    """限频：每会话每窗口最多 5 次唤醒。"""
    main = make_main()
    assert all(main._notice_rate_ok("k") for _ in range(5))
    assert not main._notice_rate_ok("k")
    assert main._notice_rate_ok("other")  # 其他会话不受影响


async def test_notice_respects_listen_off_but_request_broadcasts():
    """隐私：listen_off 静音 qvq.notice；请求是冲着 bot 来的，恒广播 qvq.request。"""
    main = make_main()
    main.sessions.set_flags("onebot11:group:1", {"listen_off": True})
    await Main._on_notice(main, FakeNoticeEvent(group_id="1", target_id="bot", account="bot",
                                                event_id="n-off"))
    assert "qvq.notice" not in emitted(main)
    await Main._on_request(main, FakeRequestEvent(user_id="u7", account="bot", event_id="r-off"))
    assert "qvq.request" in emitted(main)


async def test_request_inbox_and_auto_handle_flow():
    """请求：默认只入箱+广播；开启 auto handle 后以管理员身份决策并私聊汇报。"""
    main = make_main()
    await Main._on_request(main, FakeRequestEvent(detail_type="friend", user_id="u7",
                                                  nickname="陌生人", comment="交个朋友",
                                                  request_id="req-9", account="bot", event_id="r1"))
    inbox = main._inbox_load("bot")
    assert inbox[-1]["kind"] == "request" and inbox[-1]["request_id"] == "req-9"
    assert inbox[-1]["comment"] == "交个朋友"
    assert main.prompts == []  # 未开启决策

    main2 = make_main(request_auto_handle=True, admins=["10001"])
    decisions = []

    async def fake_run_prompt(chat_key, prompt, **kw):
        decisions.append((chat_key, prompt, kw))
        return "已拒绝：附言潦草"

    main2.run_prompt = fake_run_prompt
    sent = []

    async def fake_send(platform, detail_type, target_id, segments, **kw):
        sent.append((platform, detail_type, target_id, segments))

    main2.delivery.send_segments = fake_send
    await Main._on_request(main2, FakeRequestEvent(detail_type="friend", user_id="u7",
                                                   comment="交个朋友", request_id="req-9",
                                                   account="bot", event_id="r2"))
    await asyncio.sleep(0.05)
    assert decisions and "req-9" in decisions[0][1]
    assert decisions[0][0] == "onebot11:private:10001"  # 决策挂在管理员会话
    assert sent and sent[0][1] == "private" and sent[0][2] == "10001"  # 汇报到管理员私聊


async def test_list_events_tool_marks_read_and_filters():
    """list_events：过滤 kind、读取即标已读、新条目在前。"""
    main = make_main()
    await Main._on_notice(main, FakeNoticeEvent(group_id="1", target_id="bot", account="bot",
                                                event_id="n1"))
    await Main._on_request(main, FakeRequestEvent(user_id="u7", account="bot", event_id="r1"))
    ctx = ToolContext(main=main, sdk=main.sdk, config=main.cfg, chat_key="onebot11:group:1",
                      platform="onebot11", detail_type="group", target_id="1",
                      user_id="u9", event=None, origin="chat", self_id="bot")
    out = await erispulse.list_events(ctx, kind="request", limit=10)
    assert "req-1" in out
    inbox = main._inbox_load("bot")
    req_entry = next(e for e in inbox if e["kind"] == "request")
    notice_entry = next(e for e in inbox if e["kind"] == "notice")
    assert req_entry["read"] is True and notice_entry["read"] is False


def test_list_events_tool_registered():
    from QvQChat.agent.tools import ToolRegistry

    reg = ToolRegistry()

    class _M:
        pass

    erispulse.register(reg, _M())
    assert reg.get("list_events") is not None
    assert reg.get("handle_request") is not None


async def test_event_raw_and_platform_fields_preserved():
    """平台私有拓展：detail_type 原样入箱、原始载荷截断保留（不枚举、不丢弃）。"""
    main = make_main()
    await Main._on_notice(main, FakeNoticeEvent(detail_type="onebot11_honor", sub_type="talkative",
                                                group_id="1", user_id="u5", account="bot",
                                                event_id="n-raw", raw={"honor_type": "talkative", "nick": "某群友"}))
    entry = main._inbox_load("bot")[-1]
    assert entry["detail_type"] == "onebot11_honor"
    assert "honor_type" in (entry["raw"] or "")


# ---------- dashboard 收件箱面板（API 层） ----------

class _Req:
    def __init__(self, body):
        self._b = body or {}

    async def json(self):
        return self._b


def _api_stub(main):
    from types import SimpleNamespace

    from QvQChat.dashboard.api_sessions import SessionsApiMixin

    api = SimpleNamespace(main=main, sdk=main.sdk)
    for name in ("_inbox_entries", "_inbox_cache_drop", "inbox_delete", "inbox_clear", "inbox_get"):
        attr = inspect.getattr_static(SessionsApiMixin, name)
        setattr(api, name, getattr(SessionsApiMixin, name).__get__(api))
    return api


async def test_inbox_panel_api_aggregate_delete_clear():
    """面板 API：聚合多账户、类型过滤、新的在前；删除/清空且 AI 侧缓存同步失效。"""
    main = make_main()
    await Main._on_notice(main, FakeNoticeEvent(group_id="1", target_id="bot", account="bot", event_id="n1"))
    await Main._on_request(main, FakeRequestEvent(user_id="u7", account="bot", event_id="r1"))
    await Main._on_notice(main, FakeNoticeEvent(group_id="2", target_id="bot2", account="bot2", event_id="n2"))
    api = _api_stub(main)

    entries = api._inbox_entries()
    assert len(entries) == 3
    assert entries[0]["ts"] >= entries[-1]["ts"]  # 新的在前
    assert {e["account"] for e in entries} == {"bot", "bot2"}
    only_req = api._inbox_entries(kind="request")
    assert len(only_req) == 1 and only_req[0]["id"] == "r1"

    result = await api.inbox_delete(_Req({"account": "bot", "id": "n1"}))
    assert result["ok"] is True
    assert len(api._inbox_entries()) == 2
    # 缓存失效：AI 侧（list_events）读到的是删除后的收件箱
    assert "n1" not in [e["id"] for e in main._inbox_load("bot")]

    result2 = await api.inbox_clear(_Req({}))
    assert result2["ok"] is True and api._inbox_entries() == []
    assert main._inbox_load("bot") == []


def test_inbox_note_in_system_parts():
    """模型感知（默认开启）：system 部件带 inbox_note，模型才知道能自主查看收件箱。"""
    from fakes import FakeMain

    main = FakeMain()
    persona = {"id": "p", "name": "P", "system": "sys"}
    parts = main.sessions.build_system_parts(persona)
    note = next(p for p in parts if p.kind == "inbox_note")
    assert "list_events" in note.text
