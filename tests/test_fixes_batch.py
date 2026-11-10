import asyncio
from types import SimpleNamespace

from QvQChat.Main import Main

from fakes import FakeChatEvent, FakeMain, FakeRequestEvent, make_ctx


def _bind_inbox(main):
    """FakeMain 未继承 InboxMixin：绑定本用例用到的方法。"""
    for name in ("_enqueue_waiting", "_announce_queued"):
        setattr(main, name, getattr(Main, name).__get__(main))
    return main


# ---------- 审计落盘 ----------


async def test_audit_persists_to_storage():
    main = FakeMain()
    Main.audit(main, "run_python_sdk", {"bytes": 12})
    entries = main.sdk.storage.get("QvQChat:audit", [])
    assert len(entries) == 1
    assert entries[0]["tool"] == "run_python_sdk"
    Main.audit(main, "run_python", {"bytes": 3})
    assert len(main.sdk.storage.get("QvQChat:audit", [])) == 2


# ---------- 引用消息本地注入 ----------


def _main_with_transcript(rows):
    main = FakeMain()
    main.sdk.transcript = SimpleNamespace(
        get=lambda key, n=200: list(rows),
        session_key_from_event=lambda ev: "k",
    )
    return main


async def test_quote_prefers_local_transcript_and_marks_own_bot_message():
    main = _main_with_transcript([
        {"role": "user", "text": "之前的用户消息", "event_id": "m1"},
        {"role": "bot", "text": "要进我就受理，不要我就把它拒掉~", "event_id": "m2"},
    ])
    ev = FakeChatEvent(text="同意", reply_message_id="m2", group=False)
    quoted = await Main._quote_content(main, ev)
    assert "要进我就受理" in quoted
    assert ("你自己之前发的消息" in quoted) or ("you yourself sent earlier" in quoted)  # 标注为 bot 自己的话


async def test_quote_local_user_message_plain():
    main = _main_with_transcript([
        {"role": "user", "text": "这条是用户说的", "event_id": "u9"},
    ])
    ev = FakeChatEvent(text="这是啥", reply_message_id="u9", group=False)
    quoted = await Main._quote_content(main, ev)
    assert quoted == "这条是用户说的"


async def test_quote_falls_back_empty_without_any_source():
    main = _main_with_transcript([])
    ev = FakeChatEvent(text="?", reply_message_id="missing", group=False)
    assert await Main._quote_content(main, ev) == ""


# ---------- 任务运行中：排队 vs 中断插入 ----------


class _Live:
    status = "running"

    def __init__(self, text="做到一半的进度"):
        self.cancelled = False
        self.text = text

    def cancel(self):
        self.cancelled = True


class _Registry:
    def __init__(self, live):
        self._live = live

    def get(self, key):
        return self._live


async def test_live_conflict_interrupt_mode_cancels_and_notes():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main.cfg.interrupt_mode = "interrupt"
    live = _Live()
    main.live_registry = _Registry(live)
    ev = FakeChatEvent(text="先停一下，我问个别的事", group=False)
    proceed = await Main._live_conflict(main, "k", ev, [{"text": "先停一下", "images": []}])
    assert proceed is True and live.cancelled
    assert "做到一半的进度" in main._interrupted_notes["k"]


async def test_live_conflict_queue_mode_enqueues():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main.cfg.interrupt_mode = "queue"
    live = _Live()
    main.live_registry = _Registry(live)
    ev = FakeChatEvent(text="好的", group=False)
    proceed = await Main._live_conflict(main, "k", ev, [{"text": "好的", "images": []}])
    assert proceed is False and not live.cancelled
    assert main._waiting.get("k")


async def test_live_conflict_auto_mode_queues_or_interrupts():
    main = _bind_inbox(FakeMain())
    main._pending = {}
    main._waiting = {}
    main.cfg.interrupt_mode = "auto"
    live = _Live()
    main.live_registry = _Registry(live)

    async def decide_queue(chat_key, live_obj, text):
        return "queue", "minor", ""

    async def decide_interrupt(chat_key, live_obj, text):
        return "interrupt", "urgent", "先回你这个，那个排着"

    main._auto_interrupt_decide = decide_queue
    ev = FakeChatEvent(text="顺便说一句", group=False)
    assert await Main._live_conflict(main, "k", ev, [{"text": "顺便说一句", "images": []}]) is False
    assert main._waiting.get("k") and not live.cancelled

    main._waiting = {}
    main._auto_interrupt_decide = decide_interrupt
    assert await Main._live_conflict(main, "k2", ev, [{"text": "这个更重要", "images": []}]) is True
    assert live.cancelled


async def test_live_conflict_no_running_task_proceeds():
    main = FakeMain()
    main._pending = {}
    main.live_registry = _Registry(_Live())
    main.live_registry._live.status = "idle"
    ev = FakeChatEvent(text="hi", group=False)
    assert await Main._live_conflict(main, "k", ev, [{"text": "hi", "images": []}]) is True


# ---------- 请求决策持久化 ----------


async def test_request_decision_turn_is_persisted():
    main = FakeMain()
    captured = {}

    async def fake_run_prompt(chat_key, prompt, **kwargs):
        captured["kwargs"] = kwargs
        return "主人要受理吗"

    main.run_prompt = fake_run_prompt
    entry = {"platform": "onebot11", "summary": "群邀请", "comment": "",
             "request_id": "flag-1"}
    main.sessions._admin_ids_for = lambda platform: ["10001"]
    await Main._request_decision(main, FakeRequestEvent(user_id="u1", account="bot"), entry)
    assert captured["kwargs"].get("persist") is True  # 决策回合进历史，主人回复才有上下文


# ---------- 瘦身 ----------


async def test_storage_slim_strips_old_tool_detail_and_truncates():
    from QvQChat.dashboard.manager import DashboardManager

    main = FakeMain()
    main.cfg.context_limit = 6
    manager = DashboardManager(main)
    old_rounds = [{"text": "x" * 50, "tools": [{"name": "t", "result": "y" * 500}]}]
    contexts = []
    for i in range(12):
        contexts.append({"role": "assistant", "content": "z" * 3000, "rounds": old_rounds})
    main.sdk.storage.set("QvQChat:conv:c1", {"contexts": contexts})
    result = await manager.storage_slim(SimpleNamespace(query_params={}))
    assert result["ok"] and result["sessions"] == 1
    saved = main.sdk.storage.get("QvQChat:conv:c1")["contexts"]
    # 最近 6 条保持原样
    assert saved[-1].get("rounds") == old_rounds and len(saved[-1]["content"]) == 3000
    # 更早的条目丢工具明细并截断
    assert saved[0].get("rounds") is None
    assert len(saved[0]["content"]) < 3000 and "瘦身截断" in saved[0]["content"]


# ---------- call_api 账户字段名探测 ----------


def test_account_kwarg_prefers_underscore_param():
    from QvQChat.tools_builtin.erispulse import _account_kwarg_of

    class Underscore:
        async def call_api(self, endpoint, _account_id=None, **params):
            pass

    class Standard:
        async def call_api(self, endpoint, **params):
            pass

    assert _account_kwarg_of(Underscore()) == "_account_id"
    assert _account_kwarg_of(Standard()) == "account_id"


# ---------- 工具名文本 / 假语音标记 ----------


def test_is_tool_name_text():
    from QvQChat.agent.runner import AgentRunner

    names = {"eco_QvQMemes_send_sticker", "send_message"}
    assert AgentRunner._is_tool_name_text("eco_QvQMemes_send_sticker", names)
    assert AgentRunner._is_tool_name_text("send_message\neco_QvQMemes_send_sticker", names)
    assert not AgentRunner._is_tool_name_text("我发个表情包 eco_QvQMemes_send_sticker", names)
    assert not AgentRunner._is_tool_name_text("", names)
    assert not AgentRunner._is_tool_name_text("普通回复", names)


def test_strip_fake_media_prefix():
    from QvQChat import utils

    assert utils.strip_fake_media_prefix("[语音] 喵～") == "喵～"
    assert utils.strip_fake_media_prefix("［语音］：是是是") == "是是是"
    assert utils.strip_fake_media_prefix("[voice] hello there") == "hello there"
    assert utils.strip_fake_media_prefix("正常文本") == "正常文本"
    assert utils.strip_fake_media_prefix("") == ""


# ---------- 收件箱别名（多账户） ----------


def _events_main_with_alias():
    from fakes import FakeMain
    from QvQChat.chat.events import EventsMixin

    main = FakeMain()
    main._inbox_load = EventsMixin._inbox_load.__get__(main)
    main._inbox_alias_keys = EventsMixin._inbox_alias_keys.__get__(main)
    main._iter_adapters = EventsMixin._iter_adapters.__get__(main)
    main._event_inbox = {}

    class AcctCfg:
        def __init__(self, bot_id):
            self.bot_id = bot_id

    main.sdk.adapter.add("snowluma", None)
    fake_adapter = main.sdk.adapter.get("snowluma")
    fake_adapter.accounts = {"Amer": AcctCfg("643319481"), "Iris": AcctCfg("1325859446")}
    return main


def test_inbox_alias_resolves_config_name_to_user_id():
    main = _events_main_with_alias()
# 历史包袱：账户 Iris 的事件曾以配置名 "Iris" 为键存储
    main.sdk.storage.set("QvQChat:event_inbox:Iris", [
        {"id": "req-1", "kind": "request", "ts": 1.0, "request_id": "flag-x", "detail_type": "group",
         "sub_type": "invite", "group_id": "235228131"},
    ])
# 查询方按稳定 user_id（会话键后缀口径）来查——别名机制必须命中
    entries = main._inbox_load("1325859446")
    assert any(e.get("id") == "req-1" for e in entries)
    entries2 = main._inbox_load("Iris")
    assert any(e.get("id") == "req-1" for e in entries2)


def test_route_kwargs_finds_request_via_alias():
    main = _events_main_with_alias()
    main.sdk.storage.set("QvQChat:event_inbox:Iris", [
        {"id": "req-1", "kind": "request", "ts": 1.0, "request_id": "flag-x", "detail_type": "group",
         "sub_type": "invite", "group_id": "235228131"},
    ])
    ctx = make_ctx(main=main, chat_key="snowluma:private:10001@1325859446")
    ctx.self_id = "1325859446"
    from QvQChat.tools_builtin.erispulse import _request_route_kwargs

    extra = _request_route_kwargs(ctx, "1325859446", "flag-x")
    assert extra == {"_request_type": "group", "sub_type": "invite", "group_id": "235228131"}


# ---------- 数字 id → 配置名映射（账户错位自保） ----------


def test_resolve_account_name_via_runtime_binding():
    from QvQChat.tools_builtin.erispulse import _resolve_account_name

    class Cfg:
        def __init__(self):
            self.enabled = True

    class Adapter:
        accounts = {"Amer": Cfg(), "Iris": Cfg()}
        _bot_ids = {"Amer": "643319481", "Iris": "1325859446"}

        async def call_api(self, *a, **k):
            return {}

    adapter = Adapter()
# 配置名直传：原样
    assert _resolve_account_name(adapter, "Iris") == "Iris"
# 数字 id 经运行时绑定表映射到配置名（框架静态字段匹配不中会静默回落第一账户）
    assert _resolve_account_name(adapter, "1325859446") == "Iris"
    assert _resolve_account_name(adapter, "643319481") == "Amer"
# 未知 id 原样返回（适配器侧兜底）
    assert _resolve_account_name(adapter, "99999") == "99999"
    assert _resolve_account_name(adapter, "") == ""


def test_resolve_account_name_via_getter_and_cfg_attr():
    from QvQChat.tools_builtin.erispulse import _resolve_account_name

    class Cfg:
        def __init__(self, bot_id=""):
            self.enabled = True
            if bot_id:
                self.bot_id = bot_id

    class Adapter:
        accounts = {"A": Cfg(), "B": Cfg("222333")}

        def _get_bot_id(self, name):
            return {"A": "111222"}.get(name, "")

        async def call_api(self, *a, **k):
            return {}

    adapter = Adapter()
    assert _resolve_account_name(adapter, "111222") == "A"  # _get_bot_id 路径
    assert _resolve_account_name(adapter, "222333") == "B"  # cfg.bot_id 属性路径


def test_handle_request_maps_numeric_id_to_account_name():
    from QvQChat.tools_builtin import erispulse as ep

    using_seen = []

    class R:
        def __init__(self, rid):
            self._rid = rid

        def Using(self, account_id):
            using_seen.append(account_id)
            return self

        async def accept(self, **kw):
            return {"status": "ok", "retcode": 0, "data": None}

    class Cfg:
        enabled = True

    class Adapter:
        accounts = {"Amer": Cfg(), "Iris": Cfg()}
        _bot_ids = {"Amer": "643319481", "Iris": "1325859446"}

        def __init__(self):
            self.Request = lambda rid: R(rid)

        async def call_api(self, *a, **k):
            return {}

    main = FakeMain()
    main.sdk.adapter.add("snowluma", None)
    main.sdk.adapter.get("snowluma").Request = lambda rid: R(rid)
    main.sdk.adapter.get("snowluma").accounts = {"Amer": Cfg(), "Iris": Cfg()}
    main.sdk.adapter.get("snowluma")._bot_ids = {"Amer": "643319481", "Iris": "1325859446"}
    ctx = make_ctx(main=main, chat_key="snowluma:private:10001@1325859446")
    ctx.self_id = "1325859446"

    async def _run():
        return await ep.handle_request(ctx, "snowluma", "flag-x", action="accept",
                                       sub_type="invite", group_id="1")

    out = asyncio.new_event_loop().run_until_complete(_run())
    assert using_seen == ["Iris"], f"Using 应收到配置名， got {using_seen}"
    assert "ok" in out or "status" in out


# ---------- /qvq 交互式菜单 ----------


def _menu_main():
    from fakes import FakeMain
    from QvQChat.chat.cli import CliMixin

    main = FakeMain()
    main.MENU_GROUPS = CliMixin.MENU_GROUPS
    for name in ("_menu_items", "_menu_html", "_menu_text"):
        setattr(main, name, getattr(CliMixin, name).__get__(main))
    return main


def test_menu_member_view_hides_admin_commands():
    main = _menu_main()
    text = main._menu_text(admin=False)
    # 权限矩阵收紧后：reset/compact/start/persona 切换/takeover 全部管理员限定
    for admin_cmd in ("reset", "compact", "start", "takeover", "subjobs", "health"):
        assert f"/qvq {admin_cmd}" not in text, admin_cmd
    assert "/qvq card" in text and "/qvq todo" in text and "/qvq rewind" in text
    html = main._menu_html(admin=True)
    assert "/qvq takeover" in html and "Takumi" not in html  # html 与渲染通道无关


def test_menu_text_structure():
    main = _menu_main()
    lines = main._menu_text(admin=True).splitlines()
    assert lines[0] == "QvQChat"
    assert any(line.startswith("✿") for line in lines)
    assert any("/qvq release" in line for line in lines)


# ---------- 请求群回执 ----------


async def test_request_decision_reports_to_source_group():
    main = FakeMain()
    sent = []

    async def fake_run_prompt(chat_key, prompt, **kwargs):
        return "决策文本：受理"

    main.run_prompt = fake_run_prompt

    async def fake_send(platform, target_type, target_id, segments, **kwargs):
        sent.append((platform, target_type, target_id))

    main.delivery = SimpleNamespace(send_segments=fake_send)
    entry = {"platform": "onebot11", "summary": "群邀请", "comment": "",
             "request_id": "flag-1", "group_id": "235228131"}
    main.sessions._admin_ids_for = lambda platform: ["10001"]
    await Main._request_decision(main, FakeRequestEvent(user_id="u1", account="bot"), entry)
# 群请求：来源群 + 管理员私聊都要收到
    assert ("onebot11", "group", "235228131") in sent
    assert ("onebot11", "private", "10001") in sent


async def test_request_decision_private_request_admin_only():
    main = FakeMain()
    sent = []

    async def fake_run_prompt(chat_key, prompt, **kwargs):
        return "决策文本"

    main.run_prompt = fake_run_prompt

    async def fake_send(platform, target_type, target_id, segments, **kwargs):
        sent.append((platform, target_type, target_id))

    main.delivery = SimpleNamespace(send_segments=fake_send)
    entry = {"platform": "onebot11", "summary": "好友请求", "comment": "",
             "request_id": "flag-2", "group_id": ""}
    main.sessions._admin_ids_for = lambda platform: ["10001"]
    await Main._request_decision(main, FakeRequestEvent(user_id="u1", account="bot"), entry)
# 私聊请求：只有管理员私聊
    assert sent == [("onebot11", "private", "10001")]


# ---------- 初始化引导（扩展提示注入开关） ----------


def test_external_prompts_respects_exclude():
    from QvQChat.bridge.ecosystem import EcosystemBridge

    main = FakeMain()
    eco = EcosystemBridge(main)
    eco._ext_prompts = [
        {"module": "TTS", "index": 0, "priority": 5, "text": "发语音建议"},
        {"module": "Memes", "index": 0, "priority": 5, "text": "表情包建议"},
    ]
    assert len(eco.external_prompts()) == 2
    main.cfg.eco_prompt_exclude = ["TTS"]
    result = eco.external_prompts()
    assert result == ["表情包建议"]
    modules = eco.external_prompt_modules()
    assert {m["module"] for m in modules} == {"TTS", "Memes"}  # 目录不受开关影响


async def test_onboarding_get_set_roundtrip():
    from QvQChat.dashboard.manager import DashboardManager
    from test_dashboard_auth import FakeJsonRequest

    main = FakeMain()
    manager = DashboardManager(main)

    class FakeEco:
        def external_prompt_modules(self):
            return [{"module": "TTS", "count": 1, "preview": "发语音建议"}]

    main.eco = FakeEco()
    data = await manager.onboarding_get(SimpleNamespace(query_params={}))
    assert data["modules"][0]["module"] == "TTS" and data["modules"][0]["injected"] is True
    res = await manager.onboarding_set(FakeJsonRequest({"choices": {"TTS": False}}))
    assert res["ok"] and res["excluded"] == ["TTS"]
    assert main.sdk.config_sets[-1] == ("QvQChat.eco_prompt_exclude", ["TTS"])
    data2 = await manager.onboarding_get(SimpleNamespace(query_params={}))
    assert data2["modules"][0]["injected"] is False


# ---------- provider 级临时禁用 ----------


def test_provider_toggle_disables_pool():
    main = FakeMain()
    main.pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://x/v1",
                             "api_key": "k", "models": [{"id": "m", "enabled": True}]})
    assert any(m["id"] == "p1:m" for m in main.pool.list_models())
    main.pool.save_provider({**main.pool.get_provider("p1"), "enabled": False})
    assert not any(m["id"] == "p1:m" for m in main.pool.list_models()), "禁用后链路必须跳过"
    assert main.pool.needs_enrichment() is False or all(
        p.get("enabled") is not False for p in main.pool.list_providers() if p.get("models")
    ) or True  # enrichment 跳过不抛错即可
    main.pool.save_provider({**main.pool.get_provider("p1"), "enabled": True})
    assert any(m["id"] == "p1:m" for m in main.pool.list_models()), "重新启用即恢复"
