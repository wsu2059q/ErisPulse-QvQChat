"""H 系列拟人化核心侧测试：H2 回声过滤与防抖分级。"""
from QvQChat.chat.inbox import debounce_window, is_self_event

from fakes import FakeChatEvent, FakeMain


def make_main(**overrides):
    return FakeMain(**overrides)


# ===== H2 防抖分级 =====


def test_debounce_window_group_vs_mention():
    cfg = type("C", (), {"aggregate_window": 5.0, "debounce_group_seconds": 2.0, "debounce_mention_seconds": 1.0})()
# 私聊沿用 aggregate_window
    assert debounce_window(cfg, is_group=False, is_at=False) == 5.0
# 群聊普通消息 → 群窗口
    assert debounce_window(cfg, is_group=True, is_at=False) == 2.0
# @ 触发 → 更短的 mention 窗口
    assert debounce_window(cfg, is_group=True, is_at=True) == 1.0


def test_debounce_window_fallbacks():
    cfg = type("C", (), {"aggregate_window": 5.0, "debounce_group_seconds": 0.0, "debounce_mention_seconds": 0.0})()
# 群窗口为 0 → 回退 aggregate_window；mention 为 0 → 用群窗口
    assert debounce_window(cfg, is_group=True, is_at=False) == 5.0
    assert debounce_window(cfg, is_group=True, is_at=True) == 5.0


# ===== H2 回声过滤 =====


def test_self_echo_dropped_by_self_id():
    main = make_main()
# FakeChatEvent.get_self_account_id() = "bot"：sender 即 bot 账号 → 回声
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


# ===== H4 输出过滤器 =====


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

# 3 句里 2 句是问句（占比过半）→ 去掉结尾硬造的反问，保留真实信息问句
    text, action = filter_reply("我吃了。你吃了吗？还要去哪？", "在干嘛", 5)
    assert action == "trimmed"
    assert text == "我吃了。你吃了吗？"


def test_filter_reply_passes_normal():
    from QvQChat.conversation.rhythm import filter_reply

    text, action = filter_reply("正常回答，一句话讲完。", "在干嘛", 3)
    assert action == "pass"
    assert text == "正常回答，一句话讲完。"


# ===== H6 记忆回捞限频 =====


async def test_recall_hint_gated_by_cooldown_and_initiation():
    from fakes import FakeMain

    main = FakeMain()
    svc = main.conversations
    main.memory_entries = None
# 有相关记忆 + 对方先开口 → 允许提示
    main.sdk.storage._data["QvQChat:mem:onebot11:group:1"] = [
        {"content": "上次一起去吃了火锅", "ts": 1.0, "importance": 5}
    ] if hasattr(main.sdk.storage, "_data") else None
    allowed = svc._recall_hint_allowed("onebot11:group:1", "吃什么", "u1")
    assert allowed is True
# 记录时间戳后冷却内不再允许
    main.sdk.storage.set("QvQChat:recall_last:u1", __import__("time").time())
    assert svc._recall_hint_allowed("onebot11:group:1", "吃什么", "u1") is False
# 冷却为 0 → 功能关闭
    main2 = FakeMain(humanize_recall_interval_hours=0)
    assert main2.conversations._recall_hint_allowed("k", "吃什么", "u1") is False
# 对方未开口（任务触发空文本）→ 不允许
    main3 = FakeMain(humanize_recall_on_cold_only=True)
    main3.sdk.storage.set("QvQChat:recall_last:u1", 0)
    assert main3.conversations._recall_hint_allowed("k", "", "u1") is False


# ===== H3 硬打断信号 =====


def test_interrupt_signal_detection():
    from QvQChat.chat.inbox import detect_interrupt

    signals = ["mention", "reply", "burst", "urge"]
    assert detect_interrupt("随便说", True, False, None, signals) == (True, False)   # @
    assert detect_interrupt("嗯", False, True, None, signals) == (True, False)       # 引用
    assert detect_interrupt("嗯", False, False, 5.0, signals) == (True, False)       # 连发
    assert detect_interrupt("在吗", False, False, None, signals) == (True, False)    # 催促
    assert detect_interrupt("说错了 撤回", False, False, None, signals)[0] is True   # 纠错→打断
    assert detect_interrupt("说错了 撤回", False, False, None, signals)[1] is True   # 且要撤回
    assert detect_interrupt("我们聊点别的吧", False, False, None, signals) == (False, False)
# 信号集合为空 → 功能关闭
    assert detect_interrupt("在吗", True, True, 1.0, []) == (False, False)


# ===== H3 响应预算降级 + 打断丢弃 =====


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

        async def reply(self, content, method="Text", quote=False):
            main.sent.append(content)
            return {"message_id": 1}

    main.sent = []
    ev = Ev()

# 1) 预算耗尽：多条合并为一条、无延迟
    delivery.begin_budget("test:private:u1", 7.0)
    delivery._budget_start["test:private:u1"] = __import__("time").time() - 99
    await delivery._send_split(ev, "随便什么")
    assert len(main.sent) == 1
    assert main.sent[0] == "一。\n\n二。\n\n三。"
    delivery.end_budget("test:private:u1")

# 2) 硬打断：第二条段发送前打断，剩余段丢弃
    main.sent = []
    delivery.begin_budget("test:private:u1", 0)  # 关预算避免合并
    real_plain = delivery._send_plain

    async def plain_then_interrupt(event, text, quote=False):
        await real_plain(event, text, quote=quote)
        if len(main.sent) >= 1:
            delivery.interrupt("test:private:u1")
        return True

    delivery._send_plain = plain_then_interrupt
    await delivery._send_split(ev, "随便什么")
    assert main.sent == ["一。"]
    delivery.end_budget("test:private:u1")


# ===== H5 撤回 =====


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
# 撤回后再次调用：无记录 → False
    assert await delivery.recall_last("onebot11:group:1") is False


# ===== 审计分页 =====


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
    assert page1["entries"][0]["tool"] == "t49"  # 最新在前

    page3 = await manager.audit_get(Q({"limit": "20", "offset": "40"}))
    assert len(page3["entries"]) == 10
    assert page3["entries"][-1]["tool"] == "t0"


# ===== 撤销删除（回收站） =====


async def test_delete_with_undo_roundtrip():
    from QvQChat.dashboard.manager import DashboardManager
    from fakes import FakeMain

    main = FakeMain()
    main.pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://x/v1", "api_key": "k",
                             "models": [{"id": "m", "enabled": True}]})
    manager = DashboardManager(main)

    class R:
        def __init__(self, body): self._b = body
        async def json(self): return self._b

    resp = await manager.providers_delete(R({"id": "p1"}))
    assert resp["ok"] is True
    assert resp["undo"]
    assert main.pool.get_provider("p1") is None

    restored = await manager.trash_restore(R({"token": resp["undo"]}))
    assert restored["ok"] is True and restored["kind"] == "provider"
    assert main.pool.get_provider("p1") is not None
# 令牌一次性：再次还原失效
    again = await manager.trash_restore(R({"token": resp["undo"]}))
    assert again[1] == 410


async def test_undo_expired_token_rejected():
    from QvQChat.dashboard.manager import DashboardManager
    from fakes import FakeMain

    main = FakeMain()
    manager = DashboardManager(main)

    class R:
        def __init__(self, body): self._b = body
        async def json(self): return self._b

    token = manager._trash_put("skill", {"name": "x", "body": "y"})
    import time as _time
    main.sdk.storage.set("QvQChat:trash:" + token, {"kind": "skill", "payload": {"name": "x"}, "ts": _time.time() - 9999})
    resp = await manager.trash_restore(R({"token": token}))
    assert resp[1] == 410
