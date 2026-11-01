"""H 系列拟人化核心侧测试：H2 回声过滤与防抖分级。"""
from QvQChat.chat.inbox import debounce_window, is_self_event

from fakes import FakeChatEvent, FakeMain


def make_main(**overrides):
    return FakeMain(**overrides)


 


def test_debounce_window_group_vs_mention():
    cfg = type("C", (), {"aggregate_window": 5.0, "debounce_group_seconds": 2.0, "debounce_mention_seconds": 1.0})()
 
    assert debounce_window(cfg, is_group=False, is_at=False) == 5.0
 
    assert debounce_window(cfg, is_group=True, is_at=False) == 2.0
 
    assert debounce_window(cfg, is_group=True, is_at=True) == 1.0


def test_debounce_window_fallbacks():
    cfg = type("C", (), {"aggregate_window": 5.0, "debounce_group_seconds": 0.0, "debounce_mention_seconds": 0.0})()
 
    assert debounce_window(cfg, is_group=True, is_at=False) == 5.0
    assert debounce_window(cfg, is_group=True, is_at=True) == 5.0


 


def test_self_echo_dropped_by_self_id():
    main = make_main()
 
    ev = FakeChatEvent(text="回声", group=True, group_id="1", user_id="bot")
    assert is_self_event(main.cfg, main.sdk, ev) is True


def test_other_sender_not_dropped():
    main = make_main()
    ev = FakeChatEvent(text="你好", group=True, group_id="1", user_id="u9")
    assert is_self_event(main.cfg, main.sdk, ev) is False


def test_echo_filter_can_be_disabled():
    main = make_main(humanize_echo_filter=False)
    ev = FakeChatEvent(text="回声", group=True, group_id="1", user_id="bot")
    assert is_self_event(main.cfg, main.sdk, ev) is False


 


def test_filter_reply_parrot_detection():
    from QvQChat.conversation.rhythm import filter_reply

    text, action = filter_reply("今天天气不错，你说今天天气不错。", "今天天气不错", 3)
    assert action == "parrot"


def test_filter_reply_trims_sentences():
    from QvQChat.conversation.rhythm import filter_reply

    text, action = filter_reply("一。二。三。四。五。", "别的", 3)
    assert action == "trimmed"
    assert text == "一。二。三。"


def test_filter_reply_strips_trailing_question():
    from QvQChat.conversation.rhythm import filter_reply

 
    text, action = filter_reply("我吃了。你吃了吗？还要去哪？", "在干嘛", 5)
    assert action == "trimmed"
    assert text == "我吃了。你吃了吗？"


def test_filter_reply_passes_normal():
    from QvQChat.conversation.rhythm import filter_reply

    text, action = filter_reply("正常回答，一句话讲完。", "在干嘛", 3)
    assert action == "pass"
    assert text == "正常回答，一句话讲完。"


 


async def test_recall_hint_gated_by_cooldown_and_initiation():
    from fakes import FakeMain

    main = FakeMain()
    svc = main.conversations
    main.memory_entries = None
 
    main.sdk.storage._data["QvQChat:mem:onebot11:group:1"] = [
        {"content": "上次一起去吃了火锅", "ts": 1.0, "importance": 5}
    ] if hasattr(main.sdk.storage, "_data") else None
    allowed = svc._recall_hint_allowed("onebot11:group:1", "吃什么", "u1")
    assert allowed is True
 
    main.sdk.storage.set("QvQChat:recall_last:u1", __import__("time").time())
    assert svc._recall_hint_allowed("onebot11:group:1", "吃什么", "u1") is False
 
    main2 = FakeMain(humanize_recall_interval_hours=0)
    assert main2.conversations._recall_hint_allowed("k", "吃什么", "u1") is False
 
    main3 = FakeMain(humanize_recall_on_cold_only=True)
    main3.sdk.storage.set("QvQChat:recall_last:u1", 0)
    assert main3.conversations._recall_hint_allowed("k", "", "u1") is False


 


def test_interrupt_signal_detection():
    from QvQChat.chat.inbox import detect_interrupt

    signals = ["mention", "reply", "burst", "urge"]
    assert detect_interrupt("随便说", True, False, None, signals) == (True, False)    
    assert detect_interrupt("嗯", False, True, None, signals) == (True, False)        
    assert detect_interrupt("嗯", False, False, 5.0, signals) == (True, False)        
    assert detect_interrupt("在吗", False, False, None, signals) == (True, False)     
    assert detect_interrupt("说错了 撤回", False, False, None, signals)[0] is True    
    assert detect_interrupt("说错了 撤回", False, False, None, signals)[1] is True    
    assert detect_interrupt("我们聊点别的吧", False, False, None, signals) == (False, False)
 
    assert detect_interrupt("在吗", True, True, 1.0, []) == (False, False)


 


async def test_budget_merge_and_interrupt_drop(monkeypatch):
    import QvQChat.conversation.delivery as delivery_mod
    from fakes import FakeMain
    from QvQChat.conversation.delivery import Delivery

    main = FakeMain(humanize_budget_seconds=7.0)
    delivery = Delivery(main, rng=__import__("random"))

    def fake_plan(reply, profile, rng=None):
        return [("一。", 0.0), ("二。", 0.0), ("三。", 0.0)]

    monkeypatch.setattr(delivery_mod, "plan_segments", fake_plan)

    class Ev:
        def get_platform(self): return "test"
        def is_group_message(self): return False
        def get_group_id(self): return ""
        def get_user_id(self): return "u1"

        async def reply(self, content, method="Text"):
            main.sent.append(content)
            return {"message_id": 1}

    main.sent = []
    ev = Ev()

 
    delivery.begin_budget("test:private:u1", 7.0)
    delivery._budget_start["test:private:u1"] = __import__("time").time() - 99
    await delivery._send_split(ev, "随便什么")
    assert len(main.sent) == 1
    assert main.sent[0] == "一。\n\n二。\n\n三。"
    delivery.end_budget("test:private:u1")

 
    main.sent = []
    delivery.begin_budget("test:private:u1", 0)   
    real_plain = delivery._send_plain

    async def plain_then_interrupt(event, text):
        await real_plain(event, text)
        if len(main.sent) >= 1:
            delivery.interrupt("test:private:u1")
        return True

    delivery._send_plain = plain_then_interrupt
    await delivery._send_split(ev, "随便什么")
    assert main.sent == ["一。"]
    delivery.end_budget("test:private:u1")


 


async def test_recall_last_message():
    from fakes import FakeMain
    from QvQChat.conversation.delivery import Delivery

    main = FakeMain()
    delivery = Delivery(main)

    class Adapter:
        calls = []

        async def call_api(self, endpoint, **params):
            Adapter.calls.append((endpoint, params))
            return {"ok": True}

    main.sdk.adapter._adapters["onebot11"] = Adapter()
    delivery._last_sent["onebot11:group:1"] = {
        "platform": "onebot11", "message_id": 42, "ts": __import__("time").time(),
    }
    assert await delivery.recall_last("onebot11:group:1") is True
    assert Adapter.calls[0][0] == "delete_msg"
    assert Adapter.calls[0][1]["message_id"] == 42
 
    assert await delivery.recall_last("onebot11:group:1") is False


 


async def test_audit_pagination():
    from QvQChat.dashboard.manager import DashboardManager
    from fakes import FakeMain

    main = FakeMain()
    manager = DashboardManager(main)
    main.sdk.storage.set("QvQChat:audit", [{"tool": f"t{i}", "ts": 1.0} for i in range(50)])

    class Q:
        def __init__(self, q): self.query_params = q

    page1 = await manager.audit_get(Q({"limit": "20", "offset": "0"}))
    assert page1["total"] == 50
    assert len(page1["entries"]) == 20
    assert page1["entries"][0]["tool"] == "t49"   

    page3 = await manager.audit_get(Q({"limit": "20", "offset": "40"}))
    assert len(page3["entries"]) == 10
    assert page3["entries"][-1]["tool"] == "t0"
