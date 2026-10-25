"""开场白消费：first_contact 标记 / _process_locked 发送与防重 / seed·dashboard 排除 / /qvq start。"""
import asyncio
import inspect

from QvQChat.Main import Main

from fakes import FakeChatEvent, FakeMain

from test_aggregate import make_main as aggregate_make_main


def bind_cli(main):
    """把 cli mixin 的命令方法绑到 FakeMain（与 aggregate harness 同套路）。"""
    from QvQChat.chat.cli import CliMixin

    for name in ("_cmd_agent", "_cmd_start", "_cmd_persona"):
        static_attr = inspect.getattr_static(CliMixin, name)
        if isinstance(static_attr, staticmethod):
            setattr(main, name, static_attr.__func__)
        else:
            setattr(main, name, getattr(CliMixin, name).__get__(main))
    return main


def persona_with_opening(main, opening, **extra):
    payload = {"name": "阿波", "system": "你是阿波。", "opening": opening}
    payload.update(extra)
    saved = main.personas.save(payload)
    main.personas.bind("onebot11:private:u1", saved["id"])
    return saved["id"]


def reply_texts(ev):
    return [c for _, c in ev.replies]


async def drive(main, ev, wait=1.5):
    await Main._on_message(main, ev)
    await asyncio.sleep(wait)
    return main.captured


async def test_prepare_first_contact_and_seeded_flags():
    main = FakeMain()
    main.cfg.context_compress_tokens = 0
    svc = main.sessions
    key = "onebot11:private:u1"
 
    prepared = await svc.prepare(key, "hi", seed_provider=lambda: [], persist=False)
    assert prepared["first_contact"] is True
    assert prepared["seeded"] is False
 
    svc.reset(key)
    prepared = await svc.prepare(key, "hi", seed_provider=lambda: [{"role": "user", "content": "旧"}], persist=False)
    assert prepared["first_contact"] is True and prepared["seeded"] is True
 
    prepared = await svc.prepare(key, "hi", persist=False)
    assert prepared["first_contact"] is False
 
    svc.reset(key)
    prepared = await svc.prepare(key, "hi", seed_provider=None, persist=False)
    assert prepared["first_contact"] is False and prepared["seeded"] is False


async def test_opening_sent_once_and_before_reply():
    main = aggregate_make_main(aggregate_window=0.05)
    persona_with_opening(main, ["初次见面，我是阿波！"])
    ev = FakeChatEvent(text="在吗", group=False)
    captured = await drive(main, ev)
    assert captured, "runner should run"
    replies = reply_texts(ev)
 
    assert replies[0] == "初次见面，我是阿波！"
    assert replies[1] == "收到"
    assert replies.count("初次见面，我是阿波！") == 1
    assert main.sessions.get_flag("onebot11:private:u1", "opening_sent") is True
 
    ev2 = FakeChatEvent(text="再说点啥", group=False)
    captured2 = await drive(main, ev2, wait=0.4)
    assert captured2
    assert "初次见面，我是阿波！" not in reply_texts(ev2)


async def test_opening_respects_switch_seed_and_dashboard():
 
    main = aggregate_make_main(aggregate_window=0.05, opening_enabled=False)
    persona_with_opening(main, ["你好呀"])
    ev = FakeChatEvent(text="hi", group=False)
    assert await drive(main, ev, wait=0.4)
    assert "你好呀" not in reply_texts(ev)

 
    main2 = aggregate_make_main(aggregate_window=0.05)

    async def history(n):
        return [{"role": "user", "text": "旧消息", "sender": ""}]

    persona_with_opening(main2, ["回填也问好"])
    ev2 = FakeChatEvent(text="hi", group=False)
    ev2.history = history
    assert await drive(main2, ev2, wait=0.4)
    assert main2.captured
    assert "回填也问好" not in reply_texts(ev2)

 
    main3 = aggregate_make_main(aggregate_window=0.05, opening_on_seed=True)
    persona_with_opening(main3, ["回填也问好"])
    ev3 = FakeChatEvent(text="hi", group=False)
    ev3.history = history
    assert await drive(main3, ev3)
    assert reply_texts(ev3)[0] == "回填也问好"

 
    main4 = aggregate_make_main(aggregate_window=0.05)
    persona_with_opening(main4, ["面板不问好"])
    ev4 = FakeChatEvent(text="hi", group=False, platform="dashboard")
    assert await drive(main4, ev4, wait=0.4)
    assert main4.captured
    assert "面板不问好" not in reply_texts(ev4)


async def test_opening_truncated_to_max_len():
    main = aggregate_make_main(aggregate_window=0.05, opening_max_len=10)
    persona_with_opening(main, ["一二三四五六七八九十零壹贰叁"])
    ev = FakeChatEvent(text="hi", group=False)
    await drive(main, ev, wait=1.2)
    sent = [c for c in reply_texts(ev) if c.startswith("一二三四五六七八九")][0]
 
    assert sent.splitlines()[0] == "一二三四五六七八九十"
    assert "(truncated" in sent or len(sent) <= 10


async def test_qvq_start_resends_opening_for_admin():
    main = bind_cli(aggregate_make_main(aggregate_window=0.05, admins=["u1"]))
    persona_with_opening(main, ["手动重发开场白"])
    ev = FakeChatEvent(text="", group=False)
    ev.get_command_args = lambda: "start"
    await Main._cmd_agent(main, ev)
    assert reply_texts(ev) == ["手动重发开场白"]
    assert main.sessions.get_flag("onebot11:private:u1", "opening_sent") is True

 
    main2 = bind_cli(aggregate_make_main(aggregate_window=0.05, admins=["boss"]))
    persona_with_opening(main2, ["不该发"])
    ev2 = FakeChatEvent(text="", group=False)
    ev2.get_command_args = lambda: "start"
    await Main._cmd_agent(main2, ev2)
    assert "不该发" not in reply_texts(ev2)

 
    main3 = bind_cli(aggregate_make_main(aggregate_window=0.05, admins=["u1"]))
    ev3 = FakeChatEvent(text="", group=False)
    ev3.get_command_args = lambda: "start"
    from QvQChat import texts

    await Main._cmd_agent(main3, ev3)
    assert reply_texts(ev3) == [texts.t("opening_empty")]


async def test_reset_clears_opening_flag_when_enabled():
    main = bind_cli(aggregate_make_main(aggregate_window=0.05, admins=["u1"], opening_on_reset=True))
    persona_with_opening(main, ["重来一次问好"])
    ev = FakeChatEvent(text="hi", group=False)
    await drive(main, ev, wait=1.5)
    assert main.sessions.get_flag("onebot11:private:u1", "opening_sent") is True
    ev_reset = FakeChatEvent(text="", group=False)
    ev_reset.get_command_args = lambda: "reset"
    await Main._cmd_agent(main, ev_reset)
    assert main.sessions.get_flag("onebot11:private:u1", "opening_sent") is False
    from QvQChat import texts

    assert texts.t("opening_sent") in reply_texts(ev_reset)[-1]
 
    ev2 = FakeChatEvent(text="again", group=False)
    await drive(main, ev2, wait=1.5)
    assert reply_texts(ev2)[0] == "重来一次问好"


async def test_reset_keeps_opening_flag_by_default():
    main = bind_cli(aggregate_make_main(aggregate_window=0.05, admins=["u1"]))
    persona_with_opening(main, ["只问一次好"])
    ev = FakeChatEvent(text="hi", group=False)
    await drive(main, ev, wait=1.5)
    ev_reset = FakeChatEvent(text="", group=False)
    ev_reset.get_command_args = lambda: "reset"
    await Main._cmd_agent(main, ev_reset)
 
    assert main.sessions.get_flag("onebot11:private:u1", "opening_sent") is True


def test_set_flags_dict_and_legacy_kwargs():
    main = FakeMain()
    svc = main.sessions
    key = "onebot11:private:u1"
    assert svc.get_flag(key, "opening_sent") is False
    svc.set_flags(key, {"opening_sent": True})
    assert svc.get_flag(key, "opening_sent") is True
    svc.set_flags(key, {"opening_sent": False})
    assert svc.get_flag(key, "opening_sent") is False
 
    svc.set_flags(key, pinned=True, archived=False)
    assert svc.get_flag(key, "opening_sent") is False
    session = next(s for s in svc.list_sessions() if s["chat_key"] == key)
    assert session["pinned"] is True
