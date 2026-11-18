"""update_scheduled_task：AI 编辑任务（部分字段合并，系统任务转指引）。"""
import inspect

from QvQChat.Main import Main
from QvQChat.agent.tools import ToolContext
from QvQChat.tools_builtin import schedule

from fakes import FakeChatEvent, FakeMain


def make_main_with_task(**overrides):
    main = FakeMain(**overrides)
    main._chat_key_of = Main._chat_key_of.__get__(main)
    ev = FakeChatEvent(text="", group=False)
    task = main.scheduler.add({
        "name": "每日问候",
        "schedule": {"type": "interval", "seconds": 3600},
        "schedule_raw": "every:1h",
        "prompt": "问个好",
        "platform": "onebot11",
        "target_type": "group",
        "target_id": "42",
        "chat_key": "onebot11:group:42",
        "created_by": "u1",
    })
    ctx = ToolContext(
        main=main, sdk=main.sdk, config=main.cfg,
        chat_key="onebot11:private:u1", platform="onebot11", user_id="u1",
        origin="chat", event=ev, self_id="bot",
    )
    return main, ctx, task


async def test_update_edits_only_given_fields():
    main, ctx, task = make_main_with_task()
    out = await schedule.update_scheduled_task(ctx, task["id"], schedule="every:2h", prompt="改成道晚安")
    assert '"ok": true' in out.lower()
    updated = next(t for t in main.scheduler.list() if t["id"] == task["id"])
    assert updated["schedule_raw"] == "every:2h"
    assert "道晚安" in updated["prompt"]
    assert updated["name"] == "每日问候"          # 未提供字段保留
    assert updated["platform"] == "onebot11"
    assert len(main.scheduler.list()) == 1        # upsert 不追加


async def test_update_missing_task():
    main, ctx, _task = make_main_with_task()
    out = await schedule.update_scheduled_task(ctx, "nope", name="x")
    assert "nope" in out


async def test_update_invalid_schedule():
    main, ctx, task = make_main_with_task()
    out = await schedule.update_scheduled_task(ctx, task["id"], schedule="nonsense")
    assert "unrecognized" in out.lower() or "格式无法识别" in out


async def test_update_builtin_points_to_config():
    main, ctx, _task = make_main_with_task()
    main.scheduler.ensure_storage_maintain_task()
    sys_task = next(t for t in main.scheduler.list() if str(t.get("name")).startswith("qvq:"))
    out = await schedule.update_scheduled_task(ctx, sys_task["id"], schedule="every:2h")
    assert "storage_maintain_hours" in out


def test_register_includes_update_tool():
    from QvQChat.agent.tools import ToolRegistry

    main = FakeMain()
    reg = ToolRegistry()
    schedule.register(reg, main)
    names = {t.name for t in reg._tools.values()}
    assert "update_scheduled_task" in names
