"""会话让渡（handover）端到端行为：工具开启 / 路由隔离 / 退出协议 / 命令管理 / 触发放行。

让渡的核心承诺：扮演过程绝不进主会话上下文——路由测试与退出注记测试都盯死这一点。
"""
import asyncio
import inspect

from QvQChat.Main import Main
from QvQChat.conversation import handover
from QvQChat.tools_builtin import handover as handover_tool

from fakes import FakeChatEvent, FakeMain

KEY = "onebot11:private:u1"


def make_main(**overrides):
    main = FakeMain(**overrides)
    main._pending = {}
    main._waiting = {}
    main._chat_locks = {}
    main._rate_window = {}
    main._rate_notice_shown = {}
    from QvQChat.chat.inbox import INBOX_BOUND_METHODS

    for name in INBOX_BOUND_METHODS:
        static_attr = inspect.getattr_static(Main, name)
        if isinstance(static_attr, staticmethod):
            setattr(main, name, static_attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))
    captured = []

    class Runner:
        async def run(self, **kwargs):
            captured.append(kwargs)
            return type("R", (), {"text": "（咳嗽两声）医生你好……", "usage": {"total": 10}, "tool_trace": [], "rounds": []})()

    main.runner = Runner()
    main.captured = captured
    spawned = []

    def spawn(coro):
        task = asyncio.get_running_loop().create_task(coro)
        spawned.append(task)
        return task

    main.spawn = spawn
    main.spawned = spawned
    return main


async def drain(main):
    """收敛后台任务（让渡剧情摘要等），异常不外抛。"""
    await asyncio.gather(*main.spawned, return_exceptions=True)


async def drive(main, text="我头疼", key=KEY):
    ev = FakeChatEvent(text=text, group=False)
    await Main._process_locked(main, ev, [{"text": text, "sender_id": "u1", "sender_name": "甲"}], key)
    return ev


async def test_tool_starts_handover():
    main = make_main()
    ctx = Main._chat_ctx(main, FakeChatEvent(text="", group=False), KEY)
    out = await handover_tool.handover_session(ctx, setup="你扮演一位感冒来就诊的病人，我是医生")
    state = handover.get_state(main.sdk, KEY)
    assert state is not None
    assert state["sub_key"].startswith("sub:handover:" + KEY + ":")
    assert "感冒来就诊的病人" in state["role_prompt"]
    assert state["listen"] == "inherit"
    assert "handover_session" in out or state["sub_key"] in out


async def test_tool_refuses_nested_and_duplicate():
    main = make_main()
    ctx = Main._chat_ctx(main, FakeChatEvent(text="", group=False), KEY)
    await handover_tool.handover_session(ctx, setup="角色一")
    out = await handover_tool.handover_session(ctx, setup="角色二")
    assert handover.get_state(main.sdk, KEY)["setup"] == "角色一"
    sub_key = handover.get_state(main.sdk, KEY)["sub_key"]
    sub_ctx = Main._chat_ctx(main, FakeChatEvent(text="", group=False), sub_key)
    out2 = await handover_tool.handover_session(sub_ctx, setup="角色三")
    assert out and out2
    assert "角色二" not in handover.get_state(main.sdk, KEY)["role_prompt"]


async def test_message_routes_to_sub_session_and_main_stays_clean():
    main = make_main()
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人", model="p:m1")
    ev = await drive(main, "我头疼")
    assert main.captured, "让渡中的回合必须走 runner"
    kwargs = main.captured[0]
# 路由特征：无工具 + 角色设定 system + 模型按场指定
    assert kwargs["persona_tools"] == []
    assert "你扮演病人" in kwargs["system"]
    assert kwargs["model"] == "p:m1"
    assert kwargs["messages"][-1]["content"] == "我头疼"
# 历史落在 sub: 会话，主会话上下文一动不动
    sub_contexts = main.sessions.get_contexts(state["sub_key"])
    assert [c["content"] for c in sub_contexts] == ["我头疼", "（咳嗽两声）医生你好……"]
    assert main.sessions.get_contexts(KEY) == []
# 回复照常投递、轮数推进
    assert ev.replies
    assert handover.get_state(main.sdk, KEY)["turns"] == 1


async def test_model_falls_back_to_cfg_handover_model():
    main = make_main(handover_model="p:cheap")
    handover.start(main.sdk, main.cfg, KEY, setup="角色")
    await drive(main)
    assert main.captured[0]["model"] == "p:cheap"


async def test_tool_injects_orientation_into_role_prompt():
    main = make_main()
    main.sessions.append(KEY, "user", "我们来玩看病游戏吧")
    ctx = Main._chat_ctx(main, FakeChatEvent(text="", group=False), KEY)
    ctx.scene_note = "〔场景〕群「喵之领域」 当前说话人：甲(u1)"
    await handover_tool.handover_session(ctx, setup="你扮演一位感冒来就诊的病人")
    prompt = handover.get_state(main.sdk, KEY)["role_prompt"]
    assert "感冒来就诊的病人" in prompt
    assert "喵之领域" in prompt                      # 场景注记进角色 system
    assert "看病游戏" in prompt                      # 最近对话进角色 system
    assert "不要回应" in prompt or "do NOT respond" in prompt  # 带别回应旧话题的定向说明（语言随测试环境 locale）


async def test_exit_tag_ends_handover_and_leaves_note():
    main = make_main()

    class Runner:
        async def run(self, **kwargs):
            main.captured.append(kwargs)
            return type("R", (), {"text": "那我先回去啦\n[[交还]]", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = Runner()
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人")
    ev = await drive(main)
# 告别语照发，退出标签不外漏
    sent = "".join(str(c) for _, c in ev.replies)
    assert "回去啦" in sent and "交还" not in sent
    await drain(main)
# 状态清空 + 主会话恰好多出一条事实注记（user 角色），让渡内容仍在 sub: 会话
    assert handover.get_state(main.sdk, KEY) is None
    contexts = main.sessions.get_contexts(KEY)
    assert len(contexts) == 1 and contexts[0]["role"] == "user"
    assert "你扮演病人" in contexts[0]["content"]
    assert main.sessions.get_contexts(state["sub_key"])


async def test_end_handover_appends_plot_summary():
    main = make_main()

    class SummaryPool:
        def __init__(self):
            self.specs = []
            self.prompts = []

        def background_blocked(self):
            return False

        async def dispatch(self, spec, request):
            self.specs.append(spec)
            self.prompts.append(str(request.messages[-1]["content"]))
            return type("R", (), {"text": "病人来诊感冒，寒暄两轮后自行退场；用户全程投入扮演医生。"})()

    pool = SummaryPool()
    main.pool = pool
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人")
    await drive(main)  # 一轮（turns=1）
    main._end_handover(KEY, state)
    await drain(main)
    contexts = main.sessions.get_contexts(KEY)
    joined = "\n".join(str(c.get("content") or "") for c in contexts)
    assert "会话让渡" in joined or "handover" in joined.lower()  # 事实注记先行
    assert "病人来诊感冒" in joined      # 剧情摘要随后
# 送入总结模型的转写必须是让渡会话内容（locale 无关：直接查对话原文）
    assert pool.prompts and "我头疼" in pool.prompts[0]
    assert pool.specs[0].kind == "compact" and pool.specs[0].prefer == "cheap"


async def test_summary_failure_leaves_fact_note_only():
    main = make_main()

    class BrokenPool:
        def background_blocked(self):
            return False

        async def dispatch(self, spec, request):
            raise RuntimeError("pool down")

    main.pool = BrokenPool()
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人")
    await drive(main)
    main._end_handover(KEY, state)
    await drain(main)  # 异常被吞，不外抛
    contexts = main.sessions.get_contexts(KEY)
    joined = str(contexts[0].get("content"))
    assert len(contexts) == 1 and ("会话让渡" in joined or "handover" in joined.lower())


async def test_max_turns_auto_end():
    main = make_main()
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人", max_turns=1)
    assert state["max_turns"] == 1
    await drive(main)
    await drain(main)
    assert handover.get_state(main.sdk, KEY) is None
    contexts = main.sessions.get_contexts(KEY)
    assert len(contexts) == 1 and contexts[0]["role"] == "user"


async def test_idle_timeout_ends_handover_on_next_message():
    main = make_main()
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人")
    state["idle_minutes"] = 0.01
    state["last_ts"] -= 60.0
    main.sdk.storage.set(handover.state_key(KEY), state)
    await drive(main)
    assert handover.get_state(main.sdk, KEY) is None
# 收场后本条消息落回主链路：正常 prepare→runner 一轮（captured 里是主链路回合）
    assert main.captured and main.captured[-1]["persona_tools"] is None
    await drain(main)


async def test_cmd_handover_start_status_off():
    main = make_main()
    ev = FakeChatEvent(text="", group=False)
# 开启：tokens[1:] 即设定文本
    await Main._cmd_handover(main, ev, KEY, ["handover", "你", "扮演", "病人"])
    state = handover.get_state(main.sdk, KEY)
    assert state is not None and state["setup"] == "你 扮演 病人"
# 状态
    ev2 = FakeChatEvent(text="", group=False)
    await Main._cmd_handover(main, ev2, KEY, ["handover", "status"])
    assert any("你 扮演 病人" in str(c) for _, c in ev2.replies)
# 结束
    ev3 = FakeChatEvent(text="", group=False)
    await Main._cmd_handover(main, ev3, KEY, ["handover", "off"])
    assert handover.get_state(main.sdk, KEY) is None
    assert any("handover" in str(c).lower() or "结束" in str(c) or "讓渡" in str(c) or "让渡" in str(c) for _, c in ev3.replies)
    await drain(main)
    contexts = main.sessions.get_contexts(KEY)
    assert len(contexts) == 1 and contexts[0]["role"] == "user"


async def test_cmd_handover_off_without_active():
    main = make_main()
    ev = FakeChatEvent(text="", group=False)
    await Main._cmd_handover(main, ev, KEY, ["handover", "off"])
    assert any("handover" in str(c).lower() or "让渡" in str(c) or "讓渡" in str(c) for _, c in ev.replies)


async def test_listen_all_triggers_without_at():
    main = make_main(aggregate_window=0.05)
    handover.start(main.sdk, main.cfg, "onebot11:group:1", setup="病人", listen="all")
    ev = FakeChatEvent(text="大家看看病人脸色", group=True, user_id="u2", at=False)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.2)
    assert main.captured, "listen=all 时未 @ 的群消息也要触发让渡回合"
    assert main.captured[-1]["persona_tools"] == []


async def test_listen_inherit_keeps_group_trigger_rules():
    main = make_main(aggregate_window=0.05)
    handover.start(main.sdk, main.cfg, "onebot11:group:1", setup="病人", listen="inherit")
    ev = FakeChatEvent(text="路人在聊天", group=True, user_id="u2", at=False)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.2)
    assert not main.captured, "inherit 时未 @ 的群消息不触发"
    assert handover.get_state(main.sdk, "onebot11:group:1") is not None


async def test_expired_state_cache_invalidation():
    main = make_main()
    handover.start(main.sdk, main.cfg, KEY, setup="角色")
    first = main._handover_state(KEY)
    assert first is not None
    handover.stop(main.sdk, KEY)
    main._handover_state_invalidate(KEY)
    assert main._handover_state(KEY) is None


async def test_service_wrappers():
    main = make_main()
    state = await Main.handover_start(main, KEY, setup="你扮演病人", listen="all", max_turns=5)
    assert state["listen"] == "all" and state["max_turns"] == 5
    status = await Main.handover_status(main, KEY)
    assert status["active"] and status["sub_key"] == state["sub_key"]
    stopped = await Main.handover_stop(main, KEY)
    assert stopped and handover.get_state(main.sdk, KEY) is None
    assert not await Main.handover_stop(main, KEY)
    assert await Main.handover_status(main, KEY) == {"active": False}


async def test_exit_phrase_ends_handover_without_model_call():
    """整句退出指令免模型调用直接收场——把它丢给角色"理解再决定"曾让推理型
    模型对着退出守则纠结流口水、回合挂死占锁整群假死。"""
    main = make_main()
    handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人", listen="all")
    captured_calls = []

    class CountingRunner:
        async def run(self, **kwargs):
            captured_calls.append(kwargs)
            return type("R", (), {"text": "好喵", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = CountingRunner()
    ev = await drive(main, "退出会话让渡")
    assert handover.get_state(main.sdk, KEY) is None
# 让渡模型全程零调用（唯一的 runner 调用是主链路接手本条消息）
    assert len(captured_calls) == 1
    assert captured_calls[0]["persona_tools"] is None
# 落回主链路：注记先行、本条消息由主智能体正常处理
    contexts = main.sessions.get_contexts(KEY)
    assert contexts and contexts[0]["role"] == "user"
    assert "你扮演病人" in contexts[0]["content"]
    assert "你扮演病人" not in (captured_calls[0]["system"] or "")  # 主链路 system 不带角色守则


async def test_exit_phrase_variants():
    main = make_main()
    for phrase in ("结束扮演", "不玩了", "会话让渡结束！", "退出扮演吧"):
        handover.start(main.sdk, main.cfg, KEY, setup="角色")
        await drive(main, phrase)
        assert handover.get_state(main.sdk, KEY) is None, phrase
# 普通对话里含词组的句子不误伤
    handover.start(main.sdk, main.cfg, KEY, setup="角色")
    await drive(main, "我们之前说的那个扮演游戏后来怎么样了")
    assert handover.get_state(main.sdk, KEY) is not None
    await drive(main, "退出会话让渡")


async def test_drool_watchdog_aborts_and_ends(monkeypatch):
    """推理模型对着收场守则纠结流口水：单轮思考流超量 → 哨兵 cancel → 收场保群活。"""
    main = make_main(handover_think_cap=50, handover_turn_timeout=0, turn_timeout=0)
    released = []

    class DroolingRunner:
        async def run(self, **kwargs):
            hook = kwargs.get("on_reasoning")
            for _ in range(200):
                if hook is not None:
                    hook("思考片段" * 3)
                await asyncio.sleep(0.05)
            released.append(True)
            return type("R", (), {"text": "答案", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = DroolingRunner()
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人")
    ev = await drive(main, "随便聊聊")
    assert handover.get_state(main.sdk, KEY) is None     # 收场
    assert not released                                   # runner 被中止
    sent = "".join(str(c) for _, c in ev.replies)
    assert "中止" in sent or "aborted" in sent.lower()
    await drain(main)


async def test_handover_turn_timeout(monkeypatch):
    """让渡回合专属超时（默认 180s，测试压到 1s）：中止回合但不收场。"""
    main = make_main(handover_turn_timeout=1.0)
    gate = asyncio.Event()

    class SlowRunner:
        async def run(self, **kwargs):
            await gate.wait()
            return type("R", (), {"text": "答案", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = SlowRunner()
    state = handover.start(main.sdk, main.cfg, KEY, setup="你扮演病人")
    ev = await drive(main, "慢慢答")
    assert handover.get_state(main.sdk, KEY) is not None  # 超时只中止回合，不收场
    sent = "".join(str(c) for _, c in ev.replies)
    lowered = sent.lower()
    assert "timeout" in lowered or "too long" in lowered or "超时" in sent or "秒" in sent
    gate.set()
    await drain(main)


async def test_chat_service_model_passthrough():
    main = make_main()
    calls = []

    async def fake_run_prompt(chat_key, prompt, **kwargs):
        calls.append(kwargs)
        return "ok"

    main.run_prompt = fake_run_prompt
    out = await Main.chat(main, KEY, "你好", model="provider:glm")
    assert out == "ok"
    assert calls and calls[0].get("model") == "provider:glm"
