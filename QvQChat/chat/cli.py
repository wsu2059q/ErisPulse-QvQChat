"""聊天侧命令（拆分自 Main.py）：qvq/agent 命令入口与人格子命令。"""
from __future__ import annotations

import random
import time

from .. import texts, utils
from ..engine.base import ChatRequest
from ..tools_builtin import erispulse


def command_args_text(args) -> str:
    """命令参数归一化：适配器可能返回 str 或 list（拆好的参数表）。

    list 直接 strip 会炸掉整条命令（whoami 等全部不可用）——统一转成单行文本。
    """
    if isinstance(args, (list, tuple)):
        return " ".join(str(a).strip() for a in args).strip()
    return str(args or "").strip()


class CliMixin:
    """Main 的聊天命令 mixin。依赖宿主提供 self.cfg / self.logger / self.sessions /
    self.personas / self.scheduler / self.registry / self.pool / self.is_admin /
    self._chat_key_of / self._chat_ctx。"""

# 交互式菜单数据：(组标题键, [(子命令, 说明键, 是否管理员)])
    MENU_GROUPS = [
        ("cmd_menu_g_session", [
            ("card", "menu_card", False),
            ("todo", "menu_todo", False),
            ("memories", "menu_memories", False),
            ("rewind", "menu_rewind", False),
            ("compact", "menu_compact", True),
            ("reset", "menu_reset", True),
            ("start", "menu_start", True),
            ("persona", "menu_persona", True),
        ]),
        ("cmd_menu_g_run", [
            ("tasks", "menu_tasks", False),
            ("trigger", "menu_trigger", False),
            ("listen", "menu_listen", False),
            ("subjobs", "menu_subjobs", True),
            ("takeover", "menu_takeover", True),
            ("release", "menu_release", True),
        ]),
        ("cmd_menu_g_sys", [
            ("status", "menu_status", False),
            ("whoami", "menu_whoami", False),
            ("health", "menu_health", True),
            ("quota", "menu_quota", False),
            ("memories_clear", "menu_memories_clear", True),
        ]),
    ]

    def _menu_items(self, admin: bool) -> list:
        out = []
        for group_key, items in self.MENU_GROUPS:
            rows = [(cmd, texts.t(desc_key), need_admin)
                    for cmd, desc_key, need_admin in items if admin or not need_admin]
            if rows:
                out.append((texts.t(group_key), rows))
        return out

    def _menu_html(self, admin: bool) -> str:
        """奶油风菜单卡片（Takumi 渲染）：粉白底/圆角/chip，参考 moe 风格。"""
        groups_html = ""
        for group, rows in self._menu_items(admin):
            rows_html = "".join(
                '<div style="display:flex;align-items:center;gap:10px;padding:7px 0;">'
                f'<span style="flex:0 0 auto;background:#ff9ec6;color:#fff;border-radius:999px;'
                f'padding:3px 12px;font-size:13px;font-weight:600;">/qvq {cmd}</span>'
                f'<span style="color:#8f7c87;font-size:13px;">{desc}</span></div>'
                for cmd, desc, _ in rows
            )
            groups_html += (
                '<div style="background:#fff;border-radius:18px;padding:14px 18px;margin-bottom:12px;">'
                f'<div style="font-weight:700;color:#5c4a55;font-size:14px;margin-bottom:4px;">✿ {group}</div>'
                f"{rows_html}</div>"
            )
        admin_chip = (
            f'<span style="background:#fff2f8;color:#ff8fbf;border-radius:999px;padding:2px 10px;'
            f'font-size:12px;">{texts.t("cmd_menu_admin")}</span>' if admin else ""
        )
        return (
            '<div style="background:#ffe9f3;padding:20px;font-family:sans-serif;border-radius:22px;">'
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
            '<div style="font-size:22px;font-weight:800;color:#5c4a55;">QvQChat</div>'
            f'<span style="background:#fff;color:#8f7c87;border-radius:999px;padding:2px 10px;'
            f'font-size:12px;">v{utils.module_version()}</span>{admin_chip}</div>'
            f"{groups_html}"
            f'<div style="text-align:center;color:#b6a2ad;font-size:12px;">{texts.t("cmd_menu_hint")}</div>'
            "</div>"
        )

    def _menu_text(self, admin: bool) -> str:
        lines = ["QvQChat"]
        for group, rows in self._menu_items(admin):
            lines.append(f"✿ {group}")
            lines.extend(f"  /qvq {cmd} - {desc}" for cmd, desc, _ in rows)
        lines.append(texts.t("cmd_menu_hint"))
        return "\n".join(lines)

    async def _send_menu(self, event, admin: bool) -> None:
        """/qvq 交互式菜单：Takumi 可用时渲染奶油风卡片发图，失败/缺失回退文本。"""
        try:
            if "Takumi" in self.sdk.module:
                result = await self.sdk.module.call(
                    "Takumi", "render_card",
                    html=self._menu_html(admin), width=640, height=0, image_format="png",
                )
                path = result.get("path") if isinstance(result, dict) else None
                if path:
                    await event.reply(str(path), method="Image")
                    return
        except Exception as e:
            self.logger.debug(f"menu card render failed, fallback text: {e}")
        await event.reply(self._menu_text(admin))

    async def _cmd_agent(self, event) -> None:
        try:
            event.done()
# 适配器差异：get_command_args 可能返回 str 或 list（拆好的参数表）——
# list 直接 strip 会炸掉整条命令（whoami 等全部不可用）
            raw = command_args_text(event.get_command_args())
            tokens = raw.split() if raw else []
            sub = tokens[0].lower() if tokens else ""
            chat_key = self._chat_key_of(event)
            user_id = str(event.get_user_id() or "")
            if sub in ("", "help", "帮助", "幫助"):
                await self._send_menu(event, self.is_admin(user_id, platform=event.get_platform() or ""))
            elif sub in ("reset", "重置"):
                if not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                self.sessions.reset(chat_key)
                reply = texts.t("reset_done")
# opening_on_reset=True 时连开场白标记一起清，下次对话重新发开场白
                if getattr(self.cfg, "opening_on_reset", False) and self.sessions.get_flag(chat_key, "opening_sent"):
                    self.sessions.set_flags(chat_key, {"opening_sent": False})
                    reply += "\n" + texts.t("opening_sent")
                await event.reply(reply)
            elif sub in ("start", "开场", "開場"):
                await self._cmd_start(event, chat_key, user_id)
            elif sub in ("persona", "人格"):
                if len(tokens) >= 2 and not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                await self._cmd_persona(event, chat_key, tokens)
            elif sub in ("tasks", "任务", "任務"):
# /qvq tasks run <id>：手动触发一次（管理员；不影响下次计划时间）
                if len(tokens) >= 3 and tokens[1] in ("run", "运行", "執行", "跑"):
                    if not self.is_admin(user_id, platform=event.get_platform() or ""):
                        await event.reply(texts.t("needs_admin"))
                        return
                    name = self.scheduler.run_now(str(tokens[2]))
                    if not name:
                        await event.reply(texts.t("task_not_found", id=str(tokens[2])))
                    else:
                        await event.reply(texts.t("task_triggered", name=name, id=str(tokens[2])))
                    return
                tasks = self.scheduler.list()
# 默认只显示本会话的任务（chat_key 匹配；all 参数看全部）
                show_all = len(tokens) >= 2 and tokens[1].lower() in ("all", "全部")
                if not show_all:
                    tasks = [t for t in tasks if str(t.get("chat_key") or "") == chat_key]
                if not tasks:
                    await event.reply(texts.t("task_list_session_empty" if not show_all else "task_list_empty"))
                    return
                if True:
                    lines = [
                        f"[{t.get('id')}] {t.get('name', '')} → {utils.format_ts(float(t.get('next_run', 0)))} :: {str(t.get('prompt', ''))[:40]}"
                        for t in tasks
                    ]
                    await event.reply("\n".join(lines))
            elif sub in ("trigger", "触发", "觸發"):
# 会话级触发规则：本群任何人可改（只能收紧不能放宽，全局基线钳制兜底）
                valid = ("all", "at_only", "lurk", "off")
                override = self.sessions.trigger_mode_of(chat_key)
                if len(tokens) >= 2:
                    mode = tokens[1].strip().lower()
                    if mode not in valid:
                        await event.reply("用法：/qvq trigger all|at_only|lurk|off")
                        return
                    self.sessions.set_trigger(chat_key, mode)
                    override = self.sessions.trigger_mode_of(chat_key)
                effective = self._trigger_mode_of(chat_key)
                await event.reply(texts.t(
                    "trigger_show",
                    effective=effective,
                    global_mode=str(getattr(self.cfg, "trigger_mode", "all") or "all"),
                    override=(f"，会话覆盖 {override}" if override else ""),
                ))
            elif sub in ("listen", "监听", "監聽"):
# 隐私开关：关闭后本群消息不再进入旁听/插话/回执事件——本群任何人都可拒绝被监听
                action = tokens[1].strip().lower() if len(tokens) >= 2 else ""
                if action not in ("on", "off", "开", "关"):
                    await event.reply("用法：/qvq listen on|off")
                    return
                listening = action in ("on", "开")
                self.sessions.set_flags(chat_key, {"listen_off": not listening})
                await event.reply(texts.t(
                    "listen_set",
                    state=texts.t("listen_on_state" if listening else "listen_off_state"),
                    effect="",
                ))
            elif sub in ("rewind", "回溯", "回滾"):
# 平台侧回溯：成员限幅 6 条（只动刚发的对话）；更多属会话破坏，管理员限定
                try:
                    count = max(1, int(tokens[1])) if len(tokens) >= 2 else 1
                except ValueError:
                    count = 1
                if count > 6 and not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                count = min(count, 50)  # 硬上限防误操作清空整段
                contexts = self.sessions.get_contexts(chat_key)
                index = max(0, len(contexts) - count)
                if index >= len(contexts):
                    await event.reply(texts.t("rewind_empty"))
                    return
                ok, removed_text = self.sessions.rewind_to(chat_key, index)
                await event.reply(texts.t(
                    "rewind_done",
                    count=count,
                    preview=utils.truncate(removed_text, 120) if ok else "",
                ))
            elif sub in ("todo", "待办", "待辦"):
                await self._cmd_todo(event, chat_key, user_id, tokens)
            elif sub in ("subjobs", "子任务", "後台任務", "后台任务"):
                if not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                await self._cmd_subjobs(event, user_id, tokens)
            elif sub in ("health", "健康"):
                if not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                await self._cmd_health(event)
            elif sub in ("quota", "配额", "配額"):
                await self._cmd_quota(event, user_id)
            elif sub in ("memories", "记忆", "記憶"):
                await self._cmd_memories(event, chat_key, user_id, tokens)
            elif sub in ("card", "卡片", "卡片"):
# 渲染卡片：persona（当前人格详情）/ tasks（本会话定时任务）/ usage（今日用量）
                await self._cmd_card(event, chat_key, user_id, tokens)
            elif sub in ("compact", "压缩", "壓縮"):
                if not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                report = await self.sessions.compact_now(chat_key)
                await event.reply(texts.t("compact_done", actions=", ".join(report.get("actions") or ["noop"])))
            elif sub in ("whoami", "身份", "我是谁", "我是誰"):
                info = self.diagnose_admin(user_id, "chat", event.get_platform() or "")
# 完整诊断（主人表形态/直读命中/异常等）只进 debug 日志，聊天回复只留身份视角
                self.logger.debug(f"whoami diagnose: {info}")
                admin = bool(info["is_admin"])
                if info["master_is_master"] or info["framework_master_matched"]:
                    source = texts.t("whoami_source_master")
                elif info["admins_matched"]:
                    source = texts.t("whoami_source_admins")
                else:
                    source = texts.t("whoami_source_none")
                await event.reply(texts.t(
                    "cmd_whoami",
                    identity=texts.t("whoami_admin" if admin else "whoami_member"),
                    source=source,
                    uid=info["user_id"] or "-",
                    platform=info["platform"] or "-",
                    scope=texts.t("whoami_scope_admin" if admin else "whoami_scope_member"),
                ))
            elif sub in ("status", "状态", "狀態"):
                counts = self.registry.count_by_origin()
                info = self.diagnose_admin(user_id, "chat", event.get_platform() or "")
                uptime = max(1, int(time.time() - float(getattr(self, "started_at", time.time()))))
                uptime_text = (f"{uptime // 3600}h{(uptime % 3600) // 60:02d}m" if uptime >= 3600 else f"{uptime // 60}m{uptime % 60:02d}s")
                usage = self._usage_today()
                identity = texts.t("status_admin") if info["is_admin"] else texts.t("status_member")
                await event.reply(texts.t(
                    "status_card",
                    version=utils.module_version(),
                    framework=info["framework_version"],
                    platform=str(event.get_platform() or "-"),
                    uptime=uptime_text,
                    tokens=usage.get("tokens", 0),
                    calls=usage.get("calls", 0),
                    models=len(self.pool.list_models()),
                    tools=sum(counts.values()),
                    eco=counts.get("eco", 0),
                    sessions=len(self.sessions.list_sessions()),
                    tasks=len(self.scheduler.list()),
                    identity=identity,
                ))
            elif sub in ("takeover", "接管"):
                if not self.is_admin(user_id, platform=event.get_platform() or ""):
                    await event.reply(texts.t("needs_admin"))
                    return
                minutes = 10
                if len(tokens) >= 2:
                    try:
                        minutes = max(1, int(tokens[1]))
                    except ValueError:
                        minutes = 10
                result = await erispulse.takeover_session(self._chat_ctx(event, chat_key), duration_minutes=minutes)
                await event.reply(result)
            elif sub in ("release", "释放", "釋放"):
                result = await erispulse.release_takeover(self._chat_ctx(event, chat_key))
                await event.reply(result)
            else:
                await event.reply(texts.t("cmd_unknown"))
        except Exception as e:
            self.logger.warning(f"agent command failed: {e}")

    async def _cmd_start(self, event, chat_key: str, user_id: str) -> None:
        """/qvq start 手动重发当前会话人格开场白（仅管理员）。"""
        if not self.is_admin(user_id, platform=event.get_platform() or ""):
            await event.reply(texts.t("needs_admin"))
            return
        persona = self.personas.resolve(chat_key)
        opening = [str(o).strip() for o in (persona.get("opening") or []) if str(o or "").strip()]
        if not opening:
            await event.reply(texts.t("opening_empty"))
            return
        text = utils.truncate(
            str(random.choice(opening)),
            max(1, int(getattr(self.cfg, "opening_max_len", 200) or 200)),
        )
        await event.reply(text)
        self.sessions.set_flags(chat_key, {"opening_sent": True})

    async def _cmd_persona(self, event, chat_key: str, tokens: list) -> None:
        if len(tokens) >= 2:
            pid = tokens[1]
            persona = self.personas.get(pid)
            if persona.get("id") == pid:
# KV 绑定为唯一事实源，不再镜像写会话 state.persona（已废弃）
                self.personas.bind(chat_key, pid)
                await event.reply(texts.t("persona_set", id=pid))
            else:
                await event.reply(texts.t("persona_unknown", id=pid))
            return
        lines = []
        for persona in self.personas.list():
            mark = " *" if persona.get("builtin") else ""
            lines.append(f"{persona.get('id')}  {persona.get('name', '')}{mark}")
        await event.reply("\n".join(lines))


# ===== 渲染卡片：/qvq card persona|tasks|usage（takumi 优先，文本回退） =====

    async def _render_card(self, html: str) -> bytes | None:
        try:
            if "Takumi" not in self.sdk.module:
                return None
            result = await self.sdk.module.call(
                "Takumi", "render_card", html=html, width=640, height=0, image_format="png",
            )
            path = result.get("path") if isinstance(result, dict) else None
            if not path:
                return None
            from pathlib import Path as _Path

            data = _Path(str(path)).read_bytes()
            return data if data else None
        except Exception as e:
            self.logger.debug(f"card render failed, fallback text: {e}")
            return None

    async def _cmd_card(self, event, chat_key: str, user_id: str, tokens: list) -> None:
        which = tokens[1].lower() if len(tokens) >= 2 else "persona"
        if which in ("persona", "人格", "人格"):
            persona = self.personas.resolve(chat_key)
            html = self._persona_card_html(persona)
            text = self._persona_card_text(persona)
        elif which in ("tasks", "任务", "任務"):
            tasks = [t for t in self.scheduler.list() if str(t.get("chat_key") or "") == chat_key]
            html = self._tasks_card_html(tasks)
            text = self._tasks_card_text(tasks)
        elif which in ("usage", "用量", "用量"):
            usage = self._usage_today()
            counts = self.registry.count_by_origin()
            info = self.diagnose_admin(user_id, "chat", event.get_platform() or "")
            uptime = max(1, int(time.time() - float(getattr(self, "started_at", time.time()))))
            html = self._usage_card_html(usage, uptime, counts, info["is_admin"])
            text = self._usage_card_text(usage, uptime)
        else:
            await event.reply(texts.t("card_usage"))
            return
        image = await self._render_card(html)
        if image is not None:
            await event.reply(image, method="Image")
            return
        await event.reply(text)

    def _card_shell(self, title: str, body_rows: list, accent: str = "#ec6d9d") -> str:
        rows = "".join(
            '<div style="display:flex;gap:14px;padding:7px 0;border-bottom:1px dashed #f0e2ea;">'
            '<span style="flex:0 0 96px;color:#8a7a85;font-size:13px;">' + k + "</span>"
            '<span style="flex:1;color:#4a3d47;font-size:13.5px;font-weight:500;word-break:break-all;">' + v + "</span></div>"
            for k, v in body_rows
        )
        return (
            '<div style="background:#faf6f8;padding:22px;font-family:sans-serif;border-radius:20px;">'
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">'
            '<div style="width:8px;height:26px;border-radius:4px;background:' + accent + ';"></div>'
            '<div style="font-size:19px;font-weight:700;color:#4a3d47;">' + title + "</div></div>"
            '<div style="background:#fff;border-radius:14px;padding:6px 18px;">' + rows + "</div>"
            '<div style="text-align:center;color:#b3a5b0;font-size:11px;margin-top:12px;">QvQChat</div>'
            "</div>"
        )

    @staticmethod
    def _esc(value) -> str:
        import html as _html

        return _html.escape(str(value or ""))

    def _persona_card_html(self, persona: dict) -> str:
        flags = []
        if persona.get("builtin"):
            flags.append("builtin")
        flags.append(("temp " + str(persona.get("temperature"))) if persona.get("temperature") is not None else "temp auto")
        chips = " ".join(
            '<span style="background:#fff2f8;color:#ec6d9d;border-radius:999px;padding:2px 10px;font-size:11px;">' + f + "</span>"
            for f in flags
        )
        rows = [
            ("ID", self._esc(persona.get("id"))),
            ("Name", self._esc(persona.get("name") or persona.get("id"))),
            ("Nickname", self._esc(persona.get("nickname") or "-")),
            ("Owner", self._esc(persona.get("owner_title") or "-")),
            ("Prefill", self._esc(persona.get("prefill") or "-")),
            ("Catchphrases", self._esc("、".join(persona.get("catchphrases") or []) or "-")),
            ("Examples", str(len(persona.get("examples") or []))),
            ("System", self._esc(utils.truncate(str(persona.get("system") or ""), 120))),
        ]
        html = self._card_shell(self._esc(persona.get("name") or persona.get("id") or "Persona"), rows)
        chip_row = '<div style="display:flex;gap:6px;margin-bottom:10px;">' + chips + "</div>"
        return html.replace('<div style="background:#fff;border-radius:14px;padding:6px 18px;">',
                            chip_row + '<div style="background:#fff;border-radius:14px;padding:6px 18px;">', 1)

    def _persona_card_text(self, persona: dict) -> str:
        return "\n".join([
            f"人格：{persona.get('name') or persona.get('id')}（{persona.get('id')}）",
            f"昵称：{persona.get('nickname') or '-'} · 称呼主人：{persona.get('owner_title') or '-'}",
            f"口头禅：{'、'.join(persona.get('catchphrases') or []) or '-'}",
            f"语气样例：{len(persona.get('examples') or [])} 条 · 温度：{persona.get('temperature') if persona.get('temperature') is not None else 'auto'}",
            f"设定摘要：{utils.truncate(str(persona.get('system') or ''), 120)}",
        ])

    def _tasks_card_html(self, tasks: list) -> str:
        if not tasks:
            return self._card_shell("定时任务 · 本会话", [("状态", "本会话没有定时任务")])
        rows = [
            (self._esc(t.get("name") or t.get("id")),
             self._esc(utils.format_ts(float(t.get("next_run", 0)))) + "<br>" +
             '<span style="color:#b3a5b0;font-size:11.5px;">' + self._esc(utils.truncate(str(t.get("prompt") or ""), 60)) + "</span>")
            for t in tasks[:10]
        ]
        return self._card_shell(f"定时任务 · 本会话（{len(tasks)}）", rows)

    def _tasks_card_text(self, tasks: list) -> str:
        if not tasks:
            return "本会话没有定时任务。"
        return "\n".join(
            f"[{t.get('id')}] {t.get('name', '')} → {utils.format_ts(float(t.get('next_run', 0)))} :: {utils.truncate(str(t.get('prompt', '')), 40)}"
            for t in tasks[:10]
        )

    def _usage_card_html(self, usage: dict, uptime: int, counts: dict, admin: bool) -> str:
        tokens = int(usage.get("tokens", 0) or 0)
        limit = int(usage.get("limit", 0) or 0)
        pct = min(100, tokens * 100 // limit) if limit else 0
        rows = [
            ("今日 Token", f"{tokens:,}" + (f" / {limit:,}（{pct}%）" if limit else "")),
            ("今日调用", f"{int(usage.get('calls', 0) or 0):,}"),
            ("运行时长", (f"{uptime // 3600}h{(uptime % 3600) // 60:02d}m" if uptime >= 3600 else f"{uptime // 60}m{uptime % 60:02d}s")),
            ("工具", f"{sum(counts.values())}（生态 {counts.get('eco', 0)}）"),
            ("身份", "管理员" if admin else "成员"),
        ]
        html = self._card_shell("用量 · 今日", rows)
        if limit:
            bar = ('<div style="background:#f4ecf1;border-radius:999px;height:10px;margin-top:8px;overflow:hidden;">'
                   '<div style="width:' + str(pct) + '%;height:100%;background:' + ("#ec6d9d" if pct < 80 else "#e04f7c") + ';border-radius:999px;"></div></div>')
            html = html.replace('<div style="text-align:center;color:#b3a5b0;font-size:11px;margin-top:12px;">',
                                bar + '<div style="text-align:center;color:#b3a5b0;font-size:11px;margin-top:12px;">', 1)
        return html

    def _usage_card_text(self, usage: dict, uptime: int) -> str:
        tokens = int(usage.get("tokens", 0) or 0)
        limit = int(usage.get("limit", 0) or 0)
        lines = [
            f"今日 Token：{tokens:,}" + (f" / {limit:,}" if limit else ""),
            f"今日调用：{int(usage.get('calls', 0) or 0):,}",
            (f"运行时长：{uptime // 3600}h{(uptime % 3600) // 60:02d}m" if uptime >= 3600 else f"运行时长：{uptime // 60}m{uptime % 60:02d}s"),
        ]
        return "\n".join(lines)

# ===== 记忆透明可控：查看 + 分级清空（管理员 + confirm 词） =====

    # ===== 新子命令：todo / subjobs / health / quota =====

    async def _cmd_todo(self, event, chat_key: str, user_id: str, tokens: list) -> None:
        """/qvq todo [all]：查看 TODO 清单（默认本会话）。
        /qvq todo done <id>：改状态（人人——只推进自己看到的执行面）。
        /qvq todo clear confirm：整表清空（主人）。"""
        store = self.sessions.todos
        action = tokens[1].lower() if len(tokens) >= 2 else ""
        if action in ("clear", "清空"):
            from ..Main import is_framework_master

            if not is_framework_master(user_id, event.get_platform() or ""):
                await event.reply(texts.t("needs_master"))
                return
            confirm = tokens[2].lower() if len(tokens) >= 3 else ""
            if confirm not in ("confirm", "确认", "確認"):
                await event.reply(texts.t("memories_clear_need_confirm"))
                return
            todos = store.items(chat_key)
            store.replace(chat_key, [])
            await event.reply(texts.t("memories_cleared", target="todo", count=len(todos)))
            return
        if action in ("done", "完成", "done") and len(tokens) >= 3:
            todo = store.update(chat_key, str(tokens[2]), status="completed")
            if todo is None:
                await event.reply(texts.t("task_not_found", id=str(tokens[2])))
                return
        scope_all = action in ("all", "全部")
        key = self._all_todo_key(chat_key) if scope_all else chat_key
        todos = store.items(key) if not scope_all else []
        if scope_all:
            # all：扫同平台全部会话键的 TODO（限 20 个会话防拖库）
            platform = chat_key.split(":", 1)[0]
            count = 0
            todos = []
            for session in self.sessions.list_sessions():
                if count >= 20:
                    break
                k = str(session.get("chat_key") or "")
                if not k.startswith(platform + ":"):
                    continue
                count += 1
                for item in store.items(k):
                    todos.append({**item, "_key": k})
        mark = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}
        if not todos:
            await event.reply(texts.t("todo_empty"))
            return
        lines = [
            f"{mark.get(t.get('status'), '[ ]')} {t.get('content', '')[:60]}（{t.get('id')}）"
            + (f" @{t.get('_key')}" if scope_all else "")
            for t in todos[:15]
        ]
        await event.reply(texts.t("todo_list_header", count=len(todos)) + "\n" + "\n".join(lines))

    @staticmethod
    def _all_todo_key(chat_key: str) -> str:
        return chat_key

    async def _cmd_subjobs(self, event, user_id: str, tokens: list) -> None:
        """/qvq subjobs：后台子智能体列表（管理员）。
        /qvq subjobs cancel <sub_key>：取消运行中的子智能体。"""
        from ..tools_builtin.agent import list_subjobs, cancel_subjob

        if len(tokens) >= 2 and tokens[1].lower() in ("cancel", "取消") and len(tokens) >= 3:
            ok = cancel_subjob(self, str(tokens[2]))
            await event.reply(texts.t("subjob_cancel_ok" if ok else "subjob_cancel_miss"))
            return
        jobs = list_subjobs(self, limit=15)
        if not jobs:
            await event.reply(texts.t("subjob_none"))
            return
        lines = []
        for j in jobs:
            status = str(j.get("status") or "?")
            mark = {"running": "▶", "done": "✓", "error": "✗", "cancelled": "⊘", "interrupted": "⏸"}.get(status, "·")
            line = f"{mark} [{status}] {utils.truncate(str(j.get('task') or ''), 40)}（{j.get('sub_key', '')[:28]}…）"
            if j.get("error"):
                line += f"\n   ⚠ {utils.truncate(str(j.get('error')), 80)}"
            lines.append(line)
        await event.reply(texts.t("subjob_list_header", count=len(jobs)) + "\n" + "\n".join(lines))

    async def _cmd_health(self, event) -> None:
        """/qvq health：手动触发一次健康检查并回报告（管理员）。"""
        problems: list[str] = []
        try:
            await self.pool.chat(ChatRequest(messages=[{"role": "user", "content": "ping"}], max_tokens=1))
        except Exception as e:
            problems.append(texts.t("probe_models_down", error=utils.truncate(str(e), 100)))
        try:
            for name in self.sdk.adapter.list_registered():
                try:
                    bots = self.sdk.adapter.list_bots(str(name)) or {}
                    per = bots.get(name, bots) if isinstance(bots, dict) else {}
                    if isinstance(per, dict) and not per:
                        problems.append(texts.t("probe_adapter_offline", platform=str(name)))
                except Exception:
                    pass
        except Exception:
            pass
        if not problems:
            await event.reply(texts.t("health_ok"))
            return
        await event.reply(texts.t("probe_report", problems="\n".join(f"- {p}" for p in problems)))

    async def _cmd_quota(self, event, user_id: str) -> None:
        """/qvq quota：查自己今日用量与配额（人人；管理员额外看到配额配置值）。"""
        today = time.strftime("%Y-%m-%d")
        data = self.sdk.storage.get(f"QvQChat:usage:{today}", {})
        data = data if isinstance(data, dict) else {}
        by_user = data.get("by_user") if isinstance(data, dict) else {}
        used = int((by_user or {}).get(user_id, 0) or 0)
        personal = int(getattr(self.cfg, "user_daily_budget", 0) or 0)
        global_usage = self._usage_today()
        lines = [
            texts.t("quota_self_line", used=used,
                    limit=(f"{personal:,}" if personal else texts.t("quota_no_limit"))),
            texts.t("quota_global_line",
                    tokens=int(global_usage.get("tokens", 0) or 0),
                    calls=int(global_usage.get("calls", 0) or 0)),
        ]
        if self.is_admin(user_id, platform=""):
            lines.append(texts.t("quota_admin_hint"))
        await event.reply("\n".join(lines))

    @staticmethod
    def _profile_user_of(event, chat_key: str, user_id: str) -> str:
        """画像维度 = platform:uid；私聊无 sender 时回落到会话 target_id。"""
        platform = str(event.get_platform() or "")
        uid = str(user_id or "")
        if not uid:
            parts = chat_key.split(":")
            if len(parts) == 3 and parts[1] == "private":
                uid = parts[2]
        return f"{platform}:{uid}" if (platform and uid) else ""

    async def _cmd_memories(self, event, chat_key: str, user_id: str, tokens: list) -> None:
        action = tokens[1].lower() if len(tokens) > 1 else ""
        if action in ("clear", "清空"):
            await self._cmd_memories_clear(event, chat_key, user_id, tokens)
            return
        entries = self.memory.entries(chat_key)
        facts = self.sessions.facts_of(chat_key)
        profile_user = self._profile_user_of(event, chat_key, user_id)
        lines = [texts.t("memories_title"),
                 texts.t("memories_memory_count", count=len(entries)),
                 texts.t("memories_facts_count", count=len(facts))]
        for entry in entries[:3]:
            content = str(entry.get("content") or "")
            if content:
                lines.append(f"- {content[:80]}")
        if profile_user:
            lines.append(texts.t("memories_profile_title", user=profile_user))
            lines.append(self.sessions.profile.describe(profile_user))
        else:
            lines.append(texts.t("profile_empty"))
        await event.reply("\n".join(lines))

    async def _cmd_memories_clear(self, event, chat_key: str, user_id: str, tokens: list) -> None:
        if not self.is_admin(user_id, platform=event.get_platform() or ""):
            await event.reply(texts.t("needs_admin"))
            return
        target = (tokens[2].lower() if len(tokens) > 2 else "")
        aliases = {"profile": "profile", "画像": "profile", "facts": "facts", "事实": "facts",
                   "memory": "memory", "记忆": "memory", "記憶": "memory"}
        kind = aliases.get(target)
        if kind is None:
            await event.reply(texts.t("memories_clear_usage"))
            return
# 画像/事实清空是跨会话破坏（不止本会话）：主人限定；记忆清空（本会话）管理员即可
        from ..Main import is_framework_master

        if kind in ("profile", "facts") and not is_framework_master(user_id, event.get_platform() or ""):
            await event.reply(texts.t("needs_master"))
            return
        confirm = (tokens[3].lower() if len(tokens) > 3 else "")
        if confirm not in ("confirm", "yes", "y", "确认", "確認", "确定", "確定"):
            await event.reply(texts.t("memories_clear_need_confirm"))
            return
        if kind == "profile":
            profile_user = self._profile_user_of(event, chat_key, user_id)
            if not profile_user:
                await event.reply(texts.t("profile_empty"))
                return
            removed = self.sessions.profile.clear(profile_user)
            await event.reply(texts.t("memories_cleared", target=kind, count=removed))
            return
        if kind == "facts":
# 直接清会话 state.facts（service 未暴露公开清空方法；_state/_save_no_touch 为包内既有内部 seam）
            state = self.sessions._state(chat_key)
            count = len(state.get("facts") or [])
            state["facts"] = []
            self.sessions._save_no_touch(chat_key, state)
            await event.reply(texts.t("memories_cleared", target=kind, count=count))
            return
        removed = self.memory.clear(chat_key)
        await event.reply(texts.t("memories_cleared", target=kind, count=removed))
