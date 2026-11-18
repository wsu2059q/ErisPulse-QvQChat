"""内置定时任务管理：ensure 幂等，配置通知仅在值或周期实际变化时更新任务。"""
import types

from QvQChat.Main import Main

from fakes import FakeMain


def make_main(**overrides):
    main = FakeMain(**overrides)
    return main


async def test_ensure_profile_task_idempotent():
    main = make_main()
    t1 = main.scheduler.ensure_profile_task()
    assert t1 is not None
    t2 = main.scheduler.ensure_profile_task()
    assert t2 is None
    tasks = main.scheduler.list()
    assert len([t for t in tasks if t.get("task_kind") == "profile_consolidate"]) == 1
    assert tasks[0]["id"] == t1["id"]


async def test_ensure_updates_period_keeping_id():
    main = make_main()
    t1 = main.scheduler.ensure_storage_maintain_task()
    main.cfg.storage_maintain_hours = 12
    t2 = main.scheduler.ensure_storage_maintain_task()
    assert t2 is not None and t2["id"] == t1["id"]
    assert t2["schedule_raw"] == "every:12h"
    assert len(main.scheduler.list()) == 1


async def test_ensure_disabled_or_zero_keeps_absent():
    main = make_main(storage_auto_maintain=False)
    assert main.scheduler.ensure_storage_maintain_task() is None
    main2 = make_main(storage_maintain_hours=0)
    assert main2.scheduler.ensure_storage_maintain_task() is None
    main3 = make_main(profile_enabled=False)
    assert main3.scheduler.ensure_profile_task() is None


async def test_on_config_update_skips_when_new_matches_effective():
    """old=None（config.set 通知无快照）且 new 与当前生效值一致：不得重建任务。"""
    main = make_main()
    t1 = main.scheduler.ensure_profile_task()
    new = types.SimpleNamespace(**{
        "profile_enabled": True,
        "profile_consolidate_hours": getattr(main.cfg, "profile_consolidate_hours", 6),
        "storage_auto_maintain": True,
        "storage_maintain_hours": getattr(main.cfg, "storage_maintain_hours", 24),
    })
    await Main.on_config_update(main, None, new)
    tasks = main.scheduler.list()
    assert len([t for t in tasks if t.get("task_kind") == "profile_consolidate"]) == 1
    assert tasks[0]["id"] == t1["id"]


async def test_on_config_update_reconciles_on_real_change():
    main = make_main()
    t1 = main.scheduler.ensure_profile_task()
    main.cfg.profile_consolidate_hours = 12
    new = types.SimpleNamespace(
        profile_enabled=True,
        profile_consolidate_hours=12,
        storage_auto_maintain=True,
        storage_maintain_hours=24,
    )
    await Main.on_config_update(main, None, new)
    tasks = [t for t in main.scheduler.list() if t.get("task_kind") == "profile_consolidate"]
    assert len(tasks) == 1 and tasks[0]["id"] == t1["id"]
    assert tasks[0]["schedule_raw"] == "every:12h"


async def test_on_config_update_tolerates_none_new():
    main = make_main()
    main.scheduler.ensure_profile_task()
    await Main.on_config_update(main, None, None)
    assert main.scheduler.list()
