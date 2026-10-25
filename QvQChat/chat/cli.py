"""聊天侧命令（拆分自 Main.py）：qvq/agent 命令入口与人格子命令。"""
from __future__ import annotations

import random

from .. import texts, utils
from ..tools_builtin import erispulse


class CliMixin:
    """Main 的聊天命令 mixin。依赖宿主提供 self.cfg / self.logger / self.sessions /
    self.personas / self.scheduler / self.registry / self.pool / self.is_admin /
    self._chat_key_of / self._chat_ctx。"""

    async def _cmd_agent(self, event) -> None:
        try:
            event.done()
            raw = (event.get_command_args() or "").strip()
            tokens = raw.split() if raw else []
            sub = tokens[0].lower() if tokens else ""
            chat_key = self._chat_key_of(event)
            user_id = str(event.get_user_id() or "")
            if sub in ("", "help", "帮助", "幫助"):
                await event.reply(texts.t("cmd_help"))
            elif sub in ("reset", "重置"):
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
                await self._cmd_persona(event, chat_key, tokens)
            elif sub in ("tasks", "任务", "任務"):
                tasks = self.scheduler.list()
                if not tasks:
                    await event.reply(texts.t("task_list_empty"))
                else:
                    lines = [
                        f"[{t.get('id')}] {t.get('name', '')} → {utils.format_ts(float(t.get('next_run', 0)))} :: {str(t.get('prompt', ''))[:40]}"
                        for t in tasks
                    ]
                    await event.reply("\n".join(lines))
            elif sub in ("memories", "记忆", "記憶"):
                await self._cmd_memories(event, chat_key, user_id, tokens)
            elif sub in ("compact", "压缩", "壓縮"):
                report = await self.sessions.compact_now(chat_key)
                await event.reply(texts.t("compact_done", actions=", ".join(report.get("actions") or ["noop"])))
            elif sub in ("status", "状态", "狀態"):
                counts = self.registry.count_by_origin()
                await event.reply(
                    texts.t(
                        "status_line",
                        models=len(self.pool.list_models()),
                        tools=sum(counts.values()),
                        eco=counts.get("eco", 0),
                        sessions=len(self.sessions.list_sessions()),
                        tasks=len(self.scheduler.list()),
                    )
                )
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

# ===== 记忆透明可控：查看 + 分级清空（管理员 + confirm 词） =====

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
