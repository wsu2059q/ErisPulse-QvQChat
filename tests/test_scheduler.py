import time

from QvQChat.scheduler import Scheduler
from QvQChat.utils import parse_schedule

from fakes import FakeMain


def make_scheduler(catalog=None):
    main = FakeMain(catalog=catalog)
    main.registry = None
    return main, Scheduler(main)


def test_add_task_computes_next_run():
    main, scheduler = make_scheduler()
    task = scheduler.add(
        {
            "name": "demo",
            "schedule": parse_schedule("in:30m"),
            "schedule_raw": "in:30m",
            "platform": "test",
            "target_type": "user",
            "target_id": "1",
            "prompt": "say hi",
        }
    )
    assert task["next_run"] > time.time() + 29 * 60
    assert len(scheduler.list()) == 1


def test_cancel_task():
    main, scheduler = make_scheduler()
    task = scheduler.add({"name": "x", "schedule": parse_schedule("every:1h"), "schedule_raw": "every:1h"})
    assert scheduler.cancel(task["id"]) is True
    assert scheduler.list() == []
    assert scheduler.cancel("missing") is False


async def test_tick_fires_due_once_task():
    main, scheduler = make_scheduler()
    task = scheduler.add(
        {
            "name": "once",
            "schedule": {"type": "once", "delay": -10},
            "schedule_raw": "in:0s",
            "platform": "test",
            "target_type": "user",
            "target_id": "7",
            "prompt": "fire me",
        }
    )
    await scheduler._tick()
    assert len(main.tasks_fired) == 1
    assert scheduler.list() == []


async def test_tick_reschedules_interval_task():
    main, scheduler = make_scheduler()
    scheduler.add(
        {
            "name": "loop",
            "schedule": {"type": "interval", "seconds": 600},
            "schedule_raw": "every:10m",
        }
    )
    before = scheduler.list()[0]["next_run"]
    await scheduler._tick()
    after = scheduler.list()[0]["next_run"]
    assert after > before - 1
    assert after > time.time()


def test_delegation_to_cron_module():
    registered = {}

    class FakeCron:
        def cron(self, expression, **kwargs):
            registered["expr"] = expression
            registered.update(kwargs)
            return "cron-1"

        def interval(self, **kwargs):
            return "iv-1"

        def once(self, **kwargs):
            return "once-1"

    main, scheduler = make_scheduler(catalog={"Cron": []})
    main.sdk.Cron = FakeCron()

    task = scheduler.add(
        {
            "name": "cronned",
            "schedule": parse_schedule("cron:0 9 * * 1-5"),
            "schedule_raw": "cron:0 9 * * 1-5",
        }
    )
    assert task["managed_by"] == "Cron"
    assert task["cron_ref"] == "cron-1"
    assert registered["expr"] == "0 9 * * 1-5"
    assert registered["callback_data"] == {"qvq_task_id": task["id"]}


def test_no_delegation_when_module_missing():
    main, scheduler = make_scheduler(catalog={})
    task = scheduler.add(
        {"name": "x", "schedule": parse_schedule("cron:0 9 * * *"), "schedule_raw": "cron:0 9 * * *"}
    )
    assert task["managed_by"] == ""


def test_no_delegation_when_disabled():
    main, scheduler = make_scheduler(catalog={"Cron": []})
    main.cfg.task_use_cron_module = False
    task = scheduler.add(
        {"name": "x", "schedule": parse_schedule("cron:0 9 * * *"), "schedule_raw": "cron:0 9 * * *"}
    )
    assert task["managed_by"] == ""


async def test_cron_trigger_dispatches_fire():
    main, scheduler = make_scheduler(catalog={})
    task = scheduler.add(
        {
            "name": "t",
            "schedule": parse_schedule("in:1h"),
            "schedule_raw": "in:1h",
            "platform": "test",
            "target_type": "user",
            "target_id": "1",
            "prompt": "p",
        }
    )
    main.spawned = []

    def spawn(coro):
        main.spawned.append(coro)
        coro.close()

    main.spawn = spawn
    await scheduler._on_cron_trigger({"callback_data": {"qvq_task_id": task["id"]}})
    assert len(main.spawned) == 1
    assert scheduler.list() == []
