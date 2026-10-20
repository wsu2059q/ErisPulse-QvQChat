import asyncio
import inspect

from QvQChat.Main import Main
from QvQChat.conversation.service import ConversationService

from fakes import FakeChatEvent, FakeMain


def make_main(**overrides):
    main = FakeMain(**overrides)
    if not hasattr(main.cfg, "context_compress_tokens"):
        main.cfg.context_compress_tokens = 0
    main._pending = {}
    main._chat_locks = {}
    main._rate_window = {}
    main._rate_notice_shown = {}
    for name in (
        "_process_locked", "_chat_ctx", "_sender_name", "_resolve_group_name",
        "_seed_history",
        "is_admin", "check_tool_permission", "_master_checker",
        "record_usage", "_usage_today", "_prune_usage", "_usage_history",
        "_lock_for", "_batch_message", "_flush_later", "_flush_pending",
        "_extract_images", "_to_model_image", "_cleanup_takeovers", "_should_trigger",
        "_chat_key_of", "_chat_confirmer", "_rate_allow", "_rate_notice",
    ):
        static_attr = inspect.getattr_static(Main, name)
        if isinstance(static_attr, staticmethod):
            setattr(main, name, static_attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))
    captured = []

    class Runner:
        async def run(self, **kwargs):
            captured.append(kwargs)
            return type("R", (), {"text": "收到", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = Runner()
    main.captured = captured

    def spawn(coro):
        return asyncio.get_running_loop().create_task(coro)

    main.spawn = spawn
    return main


async def test_batch_merges_image_and_text():
    main = make_main(aggregate_window=0.05)
    ev1 = FakeChatEvent(text="", images=["https://example.com/a.jpg"], group=False)
    ev2 = FakeChatEvent(text="这是啥", group=False)
    await Main._on_message(main, ev1)
    await Main._on_message(main, ev2)
    assert main._pending["onebot11:private:u1"]["items"]
    await asyncio.sleep(0.2)
    assert not main._pending
    assert main.captured
    assert ev1.claimed and ev2.claimed
    messages = main.captured[0]["messages"]
    user_msg = [m for m in messages if m.get("role") == "user"][-1]
    assert isinstance(user_msg["content"], list)
    image_parts = [p for p in user_msg["content"] if p.get("type") == "image_url"]
    assert image_parts and image_parts[0]["image_url"]["url"] == "https://example.com/a.jpg"
    text_part = [p for p in user_msg["content"] if p.get("type") == "text"][0]
    assert "这是啥" in text_part["text"]


async def test_batch_single_message_after_window():
    main = make_main(aggregate_window=0.05)
    ev = FakeChatEvent(text="你好", group=False)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.2)
    user_msgs = [m for m in main.captured[0]["messages"] if m.get("role") == "user"]
    assert user_msgs and user_msgs[-1]["content"] == "你好"
    assert any(m[0] == "Text" for m in ev.replies)


async def test_group_labels_apply_per_item():
    main = make_main(aggregate_window=0.05)
    ev1 = FakeChatEvent(text="大家好", user_id="u1", user_name="群主", at=True)
    ev2 = FakeChatEvent(text="我是路人", user_id="u2", user_name="路人", at=True)
    await Main._on_message(main, ev1)
    await Main._on_message(main, ev2)
    await asyncio.sleep(0.2)
    user_msg = [m for m in main.captured[0]["messages"] if m.get("role") == "user"][-1]
    content = user_msg["content"]
    assert "群主(u1): 大家好" in content
    assert "路人(u2): 我是路人" in content


async def test_window_zero_flushes_immediately():
    main = make_main(aggregate_window=0)
    ev = FakeChatEvent(text="直发", group=False)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.05)
    user_msgs = [m for m in main.captured[0]["messages"] if m.get("role") == "user"]
    assert user_msgs and user_msgs[-1]["content"] == "直发"


async def test_process_locked_lock_serializes():
    main = make_main()
    lock = Main._lock_for(main, "k")
    assert Main._lock_for(main, "k") is lock
