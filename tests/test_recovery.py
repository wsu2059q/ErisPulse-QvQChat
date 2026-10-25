"""实例重启恢复三件套：inflight 标记落/清、残留重跑（防 user 重复）、待发队列启动重放、任务中断对账。

恢复例程的延迟全部参数化注入（boot_delay/replay_gap 传 0），不真等 15s/2s。
"""
import asyncio
import inspect
import time

from QvQChat.Main import Main
from QvQChat.chat.recovery import INFLIGHT_KEY_PREFIX, RecoveryMixin
from QvQChat.conversation.delivery import PENDING_KEY_PREFIX
from QvQChat.scheduler import TASK_RUN_STATE_PREFIX, Scheduler

from fakes import FakeChatEvent, FakeMain

CHAT_KEY = "onebot11:private:u1"


def make_chat_main(fail_run=False):
    """完整 _on_message 驱动（复用 test_aggregate 范式）；Runner 顺带观测执行期 inflight 标记。"""
    main = FakeMain(aggregate_window=0)
    main._pending = {}
    main._waiting = {}
    main._chat_locks = {}
    main._rate_window = {}
    main._rate_notice_shown = {}
    for name in (
        "_process_locked", "_chat_ctx", "_sender_name", "_resolve_group_name",
        "_seed_history", "_transcript_rows", "_label_seed_rows", "_group_nicknames",
        "is_admin", "check_tool_permission", "_master_checker",
        "record_usage", "_usage_today", "_prune_usage", "_usage_history",
        "_lock_for", "_batch_message", "_flush_later", "_flush_pending",
        "_extract_images", "_to_model_image", "_cleanup_takeovers", "_should_trigger",
        "_chat_key_of", "_chat_confirmer", "_rate_allow", "_rate_notice",
        "_maybe_send_opening",
    ):
        static_attr = inspect.getattr_static(Main, name)
        if isinstance(static_attr, staticmethod):
            setattr(main, name, static_attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))
    captured = []
    inflight_seen = []

    class Runner:
        async def run(self, **kwargs):
            captured.append(kwargs)
            inflight_seen.append(main.sdk.storage.get(INFLIGHT_KEY_PREFIX + CHAT_KEY) is not None)
            if fail_run:
                raise RuntimeError("runner boom")
            return type("R", (), {"text": "收到", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = Runner()
    main.captured = captured
    main.inflight_seen = inflight_seen

    def spawn(coro):
        return asyncio.get_running_loop().create_task(coro)

    main.spawn = spawn
    return main


class RecoveryMain(RecoveryMixin, FakeMain):
    """FakeMain + RecoveryMixin：run_prompt 由 FakeMain 记录（chat_key, prompt, kwargs）。"""


def inflight_keys(sdk):
    return [k for k in sdk.storage.keys() if str(k).startswith(INFLIGHT_KEY_PREFIX)]


def set_marker(main, chat_key, text, age=600):
    main.sdk.storage.set(
        INFLIGHT_KEY_PREFIX + chat_key, {"text": text, "origin": "chat", "ts": time.time() - age}
    )


# ==================== inflight 标记：_process_locked 落/清 ====================

async def test_full_message_run_sets_then_clears_inflight():
    main = make_chat_main()
    ev = FakeChatEvent(text="你好", group=False)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.1)
# 执行期标记在位（进入 runner 前落盘）
    assert main.inflight_seen == [True]
# 完成后无残留
    assert inflight_keys(main.sdk) == []
    assert main.captured


async def test_runner_exception_still_clears_inflight():
    main = make_chat_main(fail_run=True)
    ev = FakeChatEvent(text="会失败", group=False)
    await Main._on_message(main, ev)
    await asyncio.sleep(0.1)
    assert main.inflight_seen == [True]
    assert inflight_keys(main.sdk) == []
# 异常路径用户收到失败提示
    assert any("收到" not in content for _, content in ev.replies)


# ==================== 残留恢复：run_prompt 重跑 + 防 user 重复 ====================

async def test_residue_recovers_via_run_prompt_and_pops_duplicated_user():
    main = RecoveryMain()
    chat_key = "test:private:1"
# 悬空现场：prepare 已把该轮 user 消息持久化为 contexts 末条 + inflight 残留标记
    main.sessions.append_user(chat_key, "在吗？")
    set_marker(main, chat_key, "在吗？", age=600)
    await main.recover_inflight_routine(boot_delay=0, replay_gap=0)
# 经 run_prompt 重跑（origin=recovery，send=True）
    assert main.prompts == [(chat_key, "在吗？", {"origin": "recovery", "send": True})]
# 标记已删；末条重复 user 被 pop，不再留在上下文
    assert inflight_keys(main.sdk) == []
    assert main.sessions.get_contexts(chat_key) == []


async def test_residue_pop_mismatch_still_recovers():
    main = RecoveryMain()
    chat_key = "test:private:1"
# 末条与记录文本不一致（pop 失败）：上下文原样保留，仍照常重跑
    main.sessions.append(chat_key, "assistant", "旧回答")
    main.sessions.append_user(chat_key, "另一句话")
    set_marker(main, chat_key, "在吗？", age=600)
    await main.recover_inflight_routine(boot_delay=0, replay_gap=0)
    assert main.prompts == [(chat_key, "在吗？", {"origin": "recovery", "send": True})]
    contexts = main.sessions.get_contexts(chat_key)
    assert contexts[-1] == {"role": "user", "content": "另一句话"}


async def test_recovery_disabled_clears_marker_without_rerun():
    main = RecoveryMain(recovery_enabled=False)
    chat_key = "test:private:1"
    set_marker(main, chat_key, "在吗？", age=600)
    await main.recover_inflight_routine(boot_delay=0, replay_gap=0)
    assert main.prompts == []
    assert inflight_keys(main.sdk) == []


async def test_fresh_marker_below_min_age_skipped():
    main = RecoveryMain(recovery_min_age=3600)
    chat_key = "test:private:1"
    set_marker(main, chat_key, "在吗？", age=10)
    await main.recover_inflight_routine(boot_delay=0, replay_gap=0)
    assert main.prompts == []
    assert inflight_keys(main.sdk) == []


# ==================== 待发队列启动重放 ====================

async def test_pending_queue_replayed_on_boot():
    main = RecoveryMain()
    chat_key = "test:private:1"
    main.sdk.storage.set(
        PENDING_KEY_PREFIX + chat_key,
        [{"text": " queued", "platform": "onebot11", "detail_type": "user", "target_id": "1"}],
    )
    called = []

    async def fake_replay(ck):
        called.append(ck)
        return True

    main.delivery.replay_pending = fake_replay
    await main.recover_inflight_routine(boot_delay=0, replay_gap=0)
    assert called == [chat_key]


async def test_replay_on_boot_disabled_skips():
    main = RecoveryMain(replay_on_boot=False)
    chat_key = "test:private:1"
    main.sdk.storage.set(PENDING_KEY_PREFIX + chat_key, [{"text": "queued"}])
    called = []

    async def fake_replay(ck):
        called.append(ck)
        return True

    main.delivery.replay_pending = fake_replay
    await main.recover_inflight_routine(boot_delay=0, replay_gap=0)
    assert called == []


# ==================== 定时任务执行中断标记 ====================

async def test_running_task_run_residue_marked_interrupted():
    main = RecoveryMain()
    main.sdk.storage.set(TASK_RUN_STATE_PREFIX + "t1", {"status": "running", "ts": 1})
    main.sdk.storage.set(TASK_RUN_STATE_PREFIX + "t2", {"status": "done", "ts": 1})
# 聚合执行历史键（列表）不受影响
    main.sdk.storage.set("QvQChat:task_runs", [{"task_id": "t1", "status": "ok"}])
    await main.recover_inflight_routine(boot_delay=0, replay_gap=0)
    assert main.sdk.storage.get(TASK_RUN_STATE_PREFIX + "t1")["status"] == "interrupted"
    assert main.sdk.storage.get(TASK_RUN_STATE_PREFIX + "t2")["status"] == "done"
    assert main.sdk.storage.get("QvQChat:task_runs") == [{"task_id": "t1", "status": "ok"}]


async def test_fire_marks_run_state_running_to_done():
    main = FakeMain()
    scheduler = Scheduler(main)
    await scheduler._fire({"id": "t1", "name": "x", "task_kind": "chat"})
    assert main.sdk.storage.get(TASK_RUN_STATE_PREFIX + "t1")["status"] == "done"


async def test_fire_marks_failed_on_error():
    main = FakeMain()

    async def boom(task):
        raise RuntimeError("boom")

    main.run_task = boom
    scheduler = Scheduler(main)
    await scheduler._fire({"id": "t2", "name": "y", "task_kind": "chat"})
    assert main.sdk.storage.get(TASK_RUN_STATE_PREFIX + "t2")["status"] == "failed"


async def test_scheduler_start_spawns_recovery_routine():
    main = FakeMain()
    spawned = []

    def spawn(coro):
        spawned.append(coro)
        coro.close()

    main.spawn = spawn

    async def recover(**kwargs):
        return None

    main.recover_inflight_routine = recover
    scheduler = Scheduler(main)
    await scheduler.start()
    assert any(c.cr_code.co_name == "recover" for c in spawned)


async def test_scheduler_start_tolerates_missing_recovery():
    main = FakeMain()
    spawned = []

    def spawn(coro):
        spawned.append(coro)
        coro.close()

    main.spawn = spawn
    scheduler = Scheduler(main)
    await scheduler.start()
    assert all(c.cr_code.co_name != "recover_inflight_routine" for c in spawned)


# ==================== pop_last_user_if 精确锚点 ====================

def test_pop_last_user_if_variants():
    main = FakeMain()
    service = main.sessions
    chat_key = "test:private:1"
    service.append_user(chat_key, "hello")
    assert service.pop_last_user_if(chat_key, "hello") is True
    assert service.get_contexts(chat_key) == []
# 末条非 user / 文本不匹配：不动
    service.append(chat_key, "assistant", "hi")
    assert service.pop_last_user_if(chat_key, "hello") is False
    service.append_user(chat_key, "别的")
    assert service.pop_last_user_if(chat_key, "hello") is False
    assert len(service.get_contexts(chat_key)) == 2
# 多模态 content（parts 列表）按文本部分拼接比对
    service.replace_contexts(chat_key, [{"role": "user", "content": [{"type": "text", "text": "看图"}]}])
    assert service.pop_last_user_if(chat_key, "看图") is True
    assert service.get_contexts(chat_key) == []
