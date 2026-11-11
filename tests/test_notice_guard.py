"""通知场景治理 + 工具名拦截修源的回归测试（线上事故回归）。

覆盖：
- 工具名拦截修源：全注册表（含 eco 桥接动态工具）+ 历史 eco_ 名进集合；
  行清洗后仍整段命中才算（反引号/中文引号/句末标点包裹的线上形态不再漏拦）
- 自己入群：group_increase 且 user==bot → stimulus 是 notice_self_join 场景注记，
  不是"新人来了"的普通摘要（不再跟着"欢迎欢迎"）
- 合并入群：窗口内同群多个不同用户 → 只一个 _batch_message、names 含整批；
  单人同路径；窗口内 self-join 与他人入群不混
- 好友静默：刚受理过好友申请的用户，10 分钟内私聊通知不再唤醒（决策回执已是欢迎）
"""

import asyncio
import inspect
import time
from types import SimpleNamespace

from QvQChat import texts
from QvQChat.Main import Main
from QvQChat.agent.runner import AgentRunner
from QvQChat.agent.tools import Tool, ToolRegistry
from QvQChat.chat import events as chat_events

from fakes import FakeNoticeEvent, FakePool, FakeRequestEvent
from test_aggregate import make_main as base_make_main

# 通知治理走模块级纯函数（老测试宿主只按名单绑定既有 mixin 方法），宿主只需
# 绑定既有方法链 + _request_decision
_EVENT_METHODS = (
    "_maybe_wake_on_notice", "_notice_type_hit", "_notice_rate_ok", "_ev_s",
    "_event_self_id", "_event_sub_type", "_event_chat_key",
    "_request_decision", "_trigger_mode_of",
)


def make_main(**overrides):
    main = base_make_main(**overrides)
    for name in _EVENT_METHODS:
        attr = inspect.getattr_static(Main, name)
        if isinstance(attr, staticmethod):
            setattr(main, name, attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))
    return main


def install_batch_recorder(main):
    """把 _batch_message 换成同步记录器：直接断言"唤醒了几回合、stimulus 是什么"。"""
    calls = []

    def record(event, chat_key, text, images, origin="chat", items=None):
        calls.append({"chat_key": chat_key, "text": text, "event": event})

    main._batch_message = record
    return calls


# ---------- 工具名拦截修源 ----------

def _make_runner(tool_names):
    registry = ToolRegistry()
    for name in tool_names:
        registry.register(Tool(name=name, description="d", parameters={"type": "object"}, handler=None))
    config = SimpleNamespace(
        tool_self_heal=True, disabled_tools=[], admin_tools=[], safe_tools=[],
        max_tool_rounds=5, max_tool_calls=5, tool_timeout=5, tools_fallback="strip",
    )
    return AgentRunner(FakePool([]), registry, config)


def test_tool_name_text_intercepts_eco_name_outside_current_schemas():
    """eco 工具在注册表但不在本回合 schemas：集合含它时整段工具名文本判 True。"""
    runner = _make_runner(["send_message", "eco_TTS_tts_speak"])
    current_round = {"send_message"}  # 模拟工具选择器裁剪后的本回合 schemas
    names = current_round | runner._all_tool_names()
    assert "eco_TTS_tts_speak" in names

    assert AgentRunner._is_tool_name_text("eco_TTS_tts_speak", names)
    # 线上形态：包裹符/句末标点清洗后仍整段命中才算
    assert AgentRunner._is_tool_name_text("`eco_TTS_tts_speak`", names)
    assert AgentRunner._is_tool_name_text("eco_TTS_tts_speak。", names)
    assert AgentRunner._is_tool_name_text("「eco_TTS_tts_speak」", names)
    assert AgentRunner._is_tool_name_text("`send_message`\neco_TTS_tts_speak。", names)
    # 夹带人话不是工具名文本，不拦
    assert not AgentRunner._is_tool_name_text("我用 eco_TTS_tts_speak 说句话", names)
    assert not AgentRunner._is_tool_name_text("send_message 是发消息的工具", names)
    assert not AgentRunner._is_tool_name_text("", names)


def test_eco_names_scanned_from_history_contexts():
    """兜底源：历史 messages（正文/多模态文本段/tool_calls）里的 eco_ 蛇形名进集合。"""
    contexts = [
        {"role": "assistant", "content": "好", "tool_calls": [
            {"id": "call_1", "function": {"name": "eco_TTS_tts_speak", "arguments": "{}"}},
        ]},
        {"role": "user", "content": [{"type": "text", "text": "用 eco_Emoji_maker_draw 画一个"}]},
        {"role": "user", "content": "普通文本没有工具名"},
    ]
    names = AgentRunner._eco_names_from_contexts(contexts)
    assert "eco_TTS_tts_speak" in names
    assert "eco_Emoji_maker_draw" in names
    assert AgentRunner._eco_names_from_contexts([]) == set()
    # 保守词形：非 eco_ 前缀不收
    assert all(not n.startswith("TTS") for n in names)


# ---------- 自己入群 ----------

def _join_event(**kw):
    kw.setdefault("detail_type", "group_increase")
    kw.setdefault("sub_type", "join")
    kw.setdefault("group_id", "1")
    kw.setdefault("account", "bot")
    return FakeNoticeEvent(**kw)


async def test_self_join_sends_self_note_not_welcome_summary():
    """bot 自己进群（user==self）：stimulus 是 notice_self_join 注记，无普通摘要头。"""
    main = make_main(notice_listen=True, notice_types=["group_increase"], trigger_mode="all")
    calls = install_batch_recorder(main)
    ev = _join_event(user_id="bot", nickname="小Q")
    chat_key = main._event_chat_key(ev)
    entry = {"summary": "【通知/group_increase:join】 群 1 用户 小Q(bot)", "target_id": ""}
    main._maybe_wake_on_notice(ev, chat_key, entry)
    assert len(calls) == 1
    assert calls[0]["text"] == texts.t("notice_self_join")
    assert "【通知/" not in calls[0]["text"]  # 不是"新人来了"的普通摘要


# ---------- 合并入群 ----------

async def test_joins_merge_into_one_wake_and_self_join_not_mixed(monkeypatch):
    """8 秒窗口内两个不同用户入群 → 只一次 _batch_message、names 含两人；
    窗口内 self-join 单独立即醒，不混进合并批。"""
    monkeypatch.setattr(chat_events, "JOIN_AGG_WINDOW", 0.05)
    main = make_main(notice_listen=True, notice_types=["group_increase"],
                     trigger_mode="all", aggregate_window=10.0)
    calls = install_batch_recorder(main)
    chat_key = "onebot11:group:1"
    entry = {"summary": "【通知/group_increase:join】 群 1", "target_id": ""}

    main._maybe_wake_on_notice(_join_event(user_id="u1", nickname="小明"), chat_key, entry)
    main._maybe_wake_on_notice(_join_event(user_id="bot", nickname="小Q"), chat_key, entry)
    main._maybe_wake_on_notice(_join_event(user_id="u2", nickname="小红"), chat_key, entry)
    assert len(calls) == 1 and calls[0]["text"] == texts.t("notice_self_join")  # self-join 立即单独醒

    await asyncio.sleep(0.3)
    assert len(calls) == 2
    merged = calls[1]["text"]
    assert merged.startswith("【通知/group_increase:join】 群 1")  # 原摘要的群头部
    assert merged.endswith(texts.t("notice_join_merged", names="小明(u1)、小红(u2)"))


async def test_single_join_goes_through_same_merged_path():
    """单人入群同路径：一次唤醒、names 只有一个。"""
    main = make_main(notice_listen=True, notice_types=["group_increase"],
                     trigger_mode="all", aggregate_window=0.01)
    calls = install_batch_recorder(main)
    chat_key = "onebot11:group:1"
    entry = {"summary": "【通知/group_increase:join】 群 1", "target_id": ""}
    main._maybe_wake_on_notice(_join_event(user_id="u9", nickname="路人甲"), chat_key, entry)
    await asyncio.sleep(0.2)
    assert len(calls) == 1
    assert calls[0]["text"].endswith(texts.t("notice_join_merged", names="路人甲(u9)"))


async def test_join_merge_disabled_keeps_per_notice_behavior():
    """合并显式关闭（join_agg_window=0）：逐条照旧，各开回合、普通摘要 stimulus。"""
    main = make_main(notice_listen=True, notice_types=["group_increase"],
                     trigger_mode="all", join_agg_window=0)
    calls = install_batch_recorder(main)
    chat_key = "onebot11:group:1"
    main._maybe_wake_on_notice(
        _join_event(user_id="u1", nickname="小明"), chat_key,
        {"summary": "s1", "target_id": ""})
    main._maybe_wake_on_notice(
        _join_event(user_id="u2", nickname="小红"), chat_key,
        {"summary": "s2", "target_id": ""})
    assert len(calls) == 2  # 不缓冲：每条通知立刻各自唤醒（现有行为）
    assert calls[0]["text"] == texts.t("notice_stimulus", summary="s1")
    assert calls[1]["text"] == texts.t("notice_stimulus", summary="s2")


# ---------- 好友静默 ----------

async def test_recent_friend_greet_suppresses_private_notice_wake():
    """刚受理过好友申请的用户：静默期内私聊通知不唤醒；过期或群聊不受影响。"""
    main = make_main(notice_listen=True, notice_types=["friend_increase", "poke"], trigger_mode="all")
    calls = install_batch_recorder(main)
    main._recent_friend_greeted = {"onebot11:u7": time.time()}
    private_key = "onebot11:private:u7"

    main._maybe_wake_on_notice(
        FakeNoticeEvent(detail_type="friend_increase", sub_type="", group_id="",
                        user_id="u7", account="bot"),
        private_key, {"summary": "好友已添加", "target_id": ""})
    assert calls == []  # 决策回执已经是欢迎，不再唤醒

    main._recent_friend_greeted = {"onebot11:u7": time.time() - 601}  # 过了静默期
    main._maybe_wake_on_notice(
        FakeNoticeEvent(detail_type="friend_increase", sub_type="", group_id="",
                        user_id="u7", account="bot"),
        private_key, {"summary": "好友已添加", "target_id": ""})
    assert len(calls) == 1
    assert calls[0]["text"] == texts.t("notice_stimulus", summary="好友已添加")

    main._recent_friend_greeted = {"onebot11:u7": time.time()}  # 群聊不受静默影响
    main._maybe_wake_on_notice(
        FakeNoticeEvent(detail_type="notify", sub_type="poke", group_id="9",
                        target_id="bot", user_id="u7", account="bot"),
        "onebot11:group:9", {"summary": "戳了戳", "target_id": "bot"})
    assert len(calls) == 2


async def test_friend_request_decision_marks_greeted():
    """好友申请决策回合正常完成 → 挂账 platform:user_id；群请求不挂账。"""
    main = make_main(admins=["10001"])
    sent = []

    async def fake_send(platform, detail_type, target_id, segments, **kw):
        sent.append((platform, detail_type, target_id))

    main.delivery.send_segments = fake_send
    ev = FakeRequestEvent(detail_type="friend", user_id="u7", request_id="req-1",
                          account="bot", comment="交个朋友")
    friend_entry = {"platform": "onebot11", "user_id": "u7", "group_id": "",
                    "summary": "【请求/friend】", "comment": "交个朋友", "request_id": "req-1"}
    await Main._request_decision(main, ev, friend_entry)
    assert isinstance(main._recent_friend_greeted.get("onebot11:u7"), float)
    assert sent  # 决策回执照常发出

    group_entry = dict(friend_entry, group_id="1", user_id="u8", request_id="req-2")
    await Main._request_decision(main, ev, group_entry)
    assert "onebot11:u8" not in main._recent_friend_greeted  # 群请求没有私聊欢迎面
