from __future__ import annotations

import asyncio

from . import utils
from .utils import schedule_next

TASKS_KEY = "QvQChat:tasks"
TASK_RUNS_KEY = "QvQChat:task_runs"
TASK_RUNS_KEEP = 50


class Scheduler:
    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk

    def _cron_module(self):
        try:
            if "Cron" in self.sdk.module:
                return getattr(self.sdk, "Cron", None)
        except Exception:
            return None
        return None

    def _load(self) -> list[dict]:
        data = self.sdk.storage.get(TASKS_KEY, [])
        return data if isinstance(data, list) else []

    def _save(self, tasks: list[dict]) -> None:
        self.sdk.storage.set(TASKS_KEY, tasks)

    def list(self) -> list[dict]:
        return self._load()

    def runs(self, limit: int = TASK_RUNS_KEEP) -> list[dict]:
        data = self.sdk.storage.get(TASK_RUNS_KEY, [])
        runs = [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []
        return runs[-limit:]

    def _record_run(self, task: dict, status: str, error: str = "") -> None:
        try:
            runs = self.runs(TASK_RUNS_KEEP - 1)
            runs.append(
                {
                    "task_id": str(task.get("id") or ""),
                    "name": str(task.get("name") or ""),
                    "at": utils.now_ts(),
                    "status": status,
                    "error": utils.truncate(error, 160),
                }
            )
            self.sdk.storage.set(TASK_RUNS_KEY, runs)
        except Exception:
            pass

    def add(self, spec: dict) -> dict:
        schedule = spec["schedule"]
        now = utils.now_ts()
        task = {
            "id": utils.new_id(),
            "name": str(spec.get("name") or "task"),
            "schedule": schedule,
            "schedule_raw": str(spec.get("schedule_raw") or ""),
            "platform": str(spec.get("platform") or ""),
            "target_type": str(spec.get("target_type") or "user"),
            "target_id": str(spec.get("target_id") or ""),
            "prompt": str(spec.get("prompt") or ""),
            "persona": str(spec.get("persona") or ""),
            "chat_key": str(spec.get("chat_key") or ""),
            "created_by": str(spec.get("created_by") or ""),
            "created": now,
            "next_run": schedule_next(schedule, now),
            "managed_by": "",
            "cron_ref": "",
        }
        tasks = self._load()
        tasks.append(task)
        self._save(tasks)
        self._maybe_delegate(task, tasks)
        return task

    def _delegate_enabled(self) -> bool:
        return bool(getattr(self.main.cfg, "task_use_cron_module", True))

    def _maybe_delegate(self, task: dict, tasks: list[dict] | None = None) -> None:
        cron = self._cron_module() if self._delegate_enabled() else None
        if cron is None:
            return
        schedule = task.get("schedule", {})
        callback = {"qvq_task_id": task["id"]}
        try:
            if schedule.get("type") == "cron":
                ref = cron.cron(
                    expression=schedule.get("expr", "* * * * *"),
                    callback_data=callback,
                    label=f"QvQChat:{task['name']}",
                    source="QvQChat",
                )
            elif schedule.get("type") == "interval":
                ref = cron.interval(
                    interval_seconds=float(schedule.get("seconds", 60)),
                    callback_data=callback,
                    label=f"QvQChat:{task['name']}",
                    source="QvQChat",
                )
            else:
                ref = cron.once(
                    trigger_at=float(task.get("next_run", 0)),
                    callback_data=callback,
                    label=f"QvQChat:{task['name']}",
                    source="QvQChat",
                )
        except Exception as e:
            self.main.logger.warning(f"Cron delegation failed for {task['id']}: {e}")
            return
        task["managed_by"] = "Cron"
        task["cron_ref"] = str(ref)
        self._save(tasks if tasks is not None else self._load())

    def ensure_delegations(self) -> None:
        tasks = self._load()
        changed = False
        for task in tasks:
            if not task.get("managed_by"):
                self._maybe_delegate(task, tasks)
                if task.get("managed_by"):
                    changed = True
        if changed:
            self._save(tasks)

    def register_cron_handler(self) -> None:
        cron = self._cron_module()
        if cron is None:
            return
        if getattr(self, "_cron_handler", None) is not None:
            return
        self._cron_handler = self._on_cron_trigger
        try:
            cron.on_trigger(self._cron_handler)
        except Exception as e:
            self.main.logger.warning(f"Cron on_trigger register failed: {e}")

    async def _on_cron_trigger(self, info: dict) -> None:
        data = info.get("callback_data") if isinstance(info, dict) else None
        task_id = (data or {}).get("qvq_task_id") if isinstance(data, dict) else None
        if not task_id:
            return
        for task in self._load():
            if task.get("id") == task_id:
                if (task.get("schedule") or {}).get("type") == "once":
                    self.cancel(task_id)
                self.main.spawn(self._fire(task))
                return

    def cancel(self, task_id: str) -> bool:
        tasks = self._load()
        remaining = []
        target = None
        for task in tasks:
            if task.get("id") == task_id:
                target = task
                continue
            remaining.append(task)
        if target is None:
            return False
        if target.get("managed_by") == "Cron" and target.get("cron_ref"):
            cron = self._cron_module()
            if cron is not None:
                try:
                    cron.cancel(target["cron_ref"])
                except Exception:
                    pass
        self._save(remaining)
        return True

    async def start(self) -> None:
        self.ensure_delegations()
        self.register_cron_handler()
        self.main.spawn(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(max(5, int(getattr(self.main.cfg, "task_check_interval", 20))))
            try:
                await self._tick()
            except Exception as e:
                self.main.logger.warning(f"scheduler tick failed: {e}")

    async def _tick(self) -> None:
        now = utils.now_ts()
        tasks = self._load()
        remaining: list[dict] = []
        to_fire: list[dict] = []
        changed = False
        cron_alive = self._cron_module() is not None
        for task in tasks:
            if task.get("managed_by") == "Cron" and not cron_alive:
                task["managed_by"] = ""
                task["cron_ref"] = ""
                changed = True
            if task.get("managed_by") == "Cron":
                remaining.append(task)
                continue
            if float(task.get("next_run", 0)) > now:
                remaining.append(task)
                continue
            changed = True
            schedule = task.get("schedule") or {}
            if schedule.get("type") == "once":
                to_fire.append(task)
                continue
            try:
                task["next_run"] = schedule_next(schedule, now)
            except ValueError:
                continue
            remaining.append(task)
            to_fire.append(task)
        if changed:
            self._save(remaining)
        for task in to_fire:
            await self._fire(task)

    async def _fire(self, task: dict) -> None:
        try:
            await self.main.run_task(task)
            self._record_run(task, "ok")
            self.main.logger.info(f"task fired: {task.get('id')} {task.get('name')}")
        except Exception as e:
            self._record_run(task, "error", str(e))
            self.main.logger.warning(f"task {task.get('id')} failed: {e}")
