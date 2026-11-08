from __future__ import annotations

import asyncio
import random
import time

from . import texts, utils
from .utils import schedule_next

TASKS_KEY = "QvQChat:tasks"
TASK_RUNS_KEY = "QvQChat:task_runs"
# 单次任务执行状态键前缀（running→done/failed；重启后 running 残留由恢复例程改 interrupted）
TASK_RUN_STATE_PREFIX = "QvQChat:task_runs:"
TASK_RUNS_KEEP = 50

# 用户画像固化内置任务（非对话任务：_fire 走 _fire_profile_consolidate 而非 run_prompt）
PROFILE_TASK_KIND = "profile_consolidate"
PROFILE_TASK_NAME = "qvq:profile_consolidate"

# 存储自动维护内置任务（每日：slim 去重 / trash 过期 / work 沙箱过期）
MAINTAIN_TASK_KIND = "storage_maintain"
MAINTAIN_TASK_NAME = "qvq:storage_maintain"


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
            if status == "error":
                self._alert_if_persistent(task, error)
        except Exception:
            pass

    def _mark_run_state(self, task_id: str, status: str) -> None:
        """单次执行状态标记（执行中断探针）：running 落盘、结束落 done/failed。

        实例在执行中崩溃则残留 running，重启后由恢复例程改 interrupted。
        """
        if not task_id:
            return
        try:
            self.sdk.storage.set(
                TASK_RUN_STATE_PREFIX + task_id, {"status": status, "ts": utils.now_ts()}
            )
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
# 触发账户身份（run_task 据此给 chat_key 加 @后缀，发送绑对 bot）
            "account": str(spec.get("account") or ""),
# 任务分派字段透传（task_models[kind] / 显式模型）
            "task_kind": str(spec.get("task_kind") or "chat"),
            "model": str(spec.get("model") or ""),
            "jitter_minutes": float(spec.get("jitter_minutes") or 0),
            "created_by": str(spec.get("created_by") or ""),
            "created": now,
            "next_run": 0,
            "managed_by": "",
            "cron_ref": "",
        }
        task["next_run"] = self._next_with_jitter(task, now)
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

    def _next_with_jitter(self, task: dict, now: float) -> float:
        """下次触发时间：计划时间 + [0, jitter_minutes] 随机偏移（每次重算都重新掷点）。

        "每天 16:23 左右随机"这类需求——计划仍写 16:23，jitter_minutes=30 则
        实际每天在 16:23~16:53 之间随机；列表里显示的就是本次真实的触发时间。
        """
        nxt = schedule_next(task.get("schedule") or {}, now)
        jitter = float(task.get("jitter_minutes") or 0)
        if jitter > 0:
            nxt += random.uniform(0.0, jitter * 60.0)
        return nxt

    def run_now(self, task_id: str) -> str:
        """手动触发一次：立即执行，不改 next_run 计划。返回任务名；未找到返回空串。"""
        for task in self._load():
            if str(task.get("id")) == str(task_id):
                try:
                    asyncio.get_running_loop().create_task(self._fire(dict(task)))
                    return str(task.get("name") or task_id)
                except RuntimeError:
                    return ""
        return ""

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
        self.ensure_profile_task()
        self.ensure_storage_maintain_task()
        self.main.spawn(self._loop())
# 启动恢复钩子：悬空回复重跑 / 待发队列重放 / 任务中断对账（例程自带延迟避开加载期）
        recover = getattr(self.main, "recover_inflight_routine", None)
        if callable(recover):
            self.main.spawn(recover())

# ===== 用户画像固化定时任务 =====

    def ensure_profile_task(self) -> dict | None:
        """注册画像固化内置任务（幂等）：每 profile_consolidate_hours 小时对近期活跃用户跑 consolidate。

        profile_enabled 关闭或间隔<=0 时不注册；任务表中已存在同 kind 任务则不重复。返回新建任务或 None。"""
        if not bool(getattr(self.main.cfg, "profile_enabled", True)):
            return None
        hours = float(getattr(self.main.cfg, "profile_consolidate_hours", 6) or 0)
        if hours <= 0:
            return None
        for task in self._load():
            if task.get("task_kind") == PROFILE_TASK_KIND:
                return None
        task = self.add(
            {
                "name": PROFILE_TASK_NAME,
                "schedule": {"type": "interval", "seconds": max(60, int(hours * 3600))},
                "schedule_raw": f"every:{int(hours) if hours.is_integer() else hours}h",
                "prompt": "",
                "task_kind": PROFILE_TASK_KIND,
            }
        )
        return task

    def ensure_storage_maintain_task(self) -> dict | None:
        """每日存储自动维护（R7）：slim 去重 / trash 过期 / work 沙箱过期。开关关闭不注册。"""
        if not bool(getattr(self.main.cfg, "storage_auto_maintain", True)):
            return None
        for task in self._load():
            if task.get("task_kind") == MAINTAIN_TASK_KIND:
                return None
        return self.add(
            {
                "name": MAINTAIN_TASK_NAME,
                "schedule": {"type": "interval", "seconds": 24 * 3600},
                "schedule_raw": "every:24h",
                "prompt": "",
                "task_kind": MAINTAIN_TASK_KIND,
            }
        )

    async def _fire_storage_maintain(self) -> dict:
        """回收站/work 沙箱过期清理 + 历史 rounds/trace 双写去重。全部容错。"""
        import time as _time
        from pathlib import Path as _Path

        sdk = self.sdk
        report = {"trash": 0, "work": 0, "slimmed": 0}
        trash_days = int(getattr(self.main.cfg, "trash_retention_days", 14) or 0)
        if trash_days > 0:
            cutoff = _time.time() - trash_days * 86400
            for key in list(sdk.storage.keys()):
                if isinstance(key, str) and key.startswith("QvQChat:trash:"):
                    entry = sdk.storage.get(key, None)
                    ts = float(entry.get("ts") or 0) if isinstance(entry, dict) else 0
                    if ts and ts < cutoff:
                        sdk.storage.delete(key)
                        report["trash"] += 1
        work_days = int(getattr(self.main.cfg, "work_retention_days", 30) or 0)
        if work_days > 0:
            root = _Path(str(getattr(self.main.cfg, "file_workdir", "") or "data/QvQChat/work"))
            if root.exists():
                cutoff = _time.time() - work_days * 86400
                for d in root.iterdir():
                    try:
                        if d.is_dir() and d.stat().st_mtime < cutoff:
                            import shutil

                            shutil.rmtree(d, ignore_errors=True)
                            report["work"] += 1
                    except OSError:
                        continue
        conv_prefix = "QvQChat:conv:"
        for key in list(sdk.storage.keys()):
            if not (isinstance(key, str) and key.startswith(conv_prefix)):
                continue
            state = sdk.storage.get(key, None)
            if not (isinstance(state, dict) and isinstance(state.get("contexts"), list)):
                continue
            dirty = False
            for entry in state["contexts"]:
                if isinstance(entry, dict) and entry.get("rounds") and entry.get("trace"):
                    del entry["trace"]
                    dirty = True
            if dirty:
                sdk.storage.set(key, state)
                report["slimmed"] += 1
        logger = getattr(self.main, "logger", None)
        if logger is not None:
            logger.info(f"storage maintain: {report}")
        return report

    async def _fire_profile_consolidate(self) -> int:
        """对 user_seen 倒排里近 24h 活跃用户跑画像固化；单用户失败跳过（低频容错）。"""
# 高负载降载：满载时整轮跳过（定时任务下轮再跑，画像不急）
        pool = getattr(self.main, "pool", None)
        if pool is not None and callable(getattr(pool, "background_blocked", None)) and pool.background_blocked():
            return 0
        service = getattr(self.main, "conversations", None) or getattr(self.main, "sessions", None)
        profile = getattr(service, "profile", None) if service is not None else None
        if profile is None:
            return 0
        users = profile.active_user_keys(within_hours=24)
        done = 0
        for user_key in users:
            try:
                await profile.consolidate(user_key)
                done += 1
            except Exception as e:
                self.main.logger.warning(f"profile consolidate failed for {user_key}: {e}")
        if users:
            self.main.logger.info(f"profile consolidated: {done}/{len(users)} active users")
        return done

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(max(5, int(getattr(self.main.cfg, "task_check_interval", 20))))
            try:
                await self._tick()
            except Exception as e:
                self.main.logger.warning(f"scheduler tick failed: {e}")

    async def _tick(self) -> None:
        now = utils.now_ts()
# 文档版本检查（内部按 checked_at 节流到每日一次，离线不重复撞网）
        docs = getattr(self.main, "docs", None)
        if docs is not None:
            try:
                await docs.maybe_sync_daily()
            except Exception as e:
                self.main.logger.debug(f"docs daily check failed: {e}")
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
                task["next_run"] = self._next_with_jitter(task, now)
            except ValueError:
                continue
            remaining.append(task)
            to_fire.append(task)
        if changed:
            self._save(remaining)
        for task in to_fire:
            await self._fire(task)


    def _alert_if_persistent(self, task: dict, error: str) -> None:
        """R9B 定时任务连续失败告警：≥3 次时向首个管理员会话每日提醒一次。"""
        try:
            task_id = str(task.get("id") or "")
            marker_day = f"QvQChat:tasks:alerted:{time.strftime('%Y-%m-%d')}"
            recent = [r for r in self.runs(30) if r.get("task_id") == task_id]
            streak = 0
            for r in reversed(recent):
                if r.get("status") != "error":
                    break
                streak += 1
            if streak < 3:
                return
            if self.sdk.storage.get(marker_day, "") == "1":
                return
            self.sdk.storage.set(marker_day, "1")
            admins = [str(a) for a in (getattr(self.main.cfg, "admins", []) or []) if str(a).strip()]
            if not admins:
                return
            admin_id = admins[0]
            from .conversation.service import make_chat_key

            speak = getattr(self.main, "speak", None)
            if not callable(speak):
                return
            import asyncio as _asyncio

            message = texts.t("task_fail_alert", name=str(task.get("name") or task_id), n=streak, error=utils.truncate(error, 120))
            _asyncio.get_event_loop().create_task(
                speak(make_chat_key("dashboard", "private", admin_id), reason=f"任务连续失败 ×{streak}", prompt=message)
            )
        except Exception as e:
            logger = getattr(self.main, "logger", None)
            if logger is not None:
                logger.debug(f"task alert failed: {e}")

    async def _fire(self, task: dict) -> None:
        task_id = str(task.get("id") or "")
        self._mark_run_state(task_id, "running")
        try:
            if task.get("task_kind") == PROFILE_TASK_KIND:
                await self._fire_profile_consolidate()
            elif task.get("task_kind") == MAINTAIN_TASK_KIND:
                await self._fire_storage_maintain()
            else:
                await self.main.run_task(task)
            self._record_run(task, "ok")
            self._mark_run_state(task_id, "done")
            self.main.logger.info(f"task fired: {task.get('id')} {task.get('name')}")
        except Exception as e:
            self._record_run(task, "error", str(e))
            self._mark_run_state(task_id, "failed")
            self.main.logger.warning(f"task {task.get('id')} failed: {e}")
