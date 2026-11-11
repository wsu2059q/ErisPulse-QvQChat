"""聊天侧命令（拆分自 Main.py）：qvq/agent 命令入口与人格子命令。"""
from __future__ import annotations

import random
import time

from .. import texts, utils
from ..conversation.policy import get_policy, set_policy
from ..engine.base import ChatRequest
from ..tools_builtin import erispulse


def command_args_text(args) -> str:
    """命令参数归一化：适配器可能返回 str 或 list（拆好的参数表）。

    list 直接 strip 会炸掉整条命令（whoami 等全部不可用）——统一转成单行文本。
    """
    if isinstance(args, (list, tuple)):
        return " ".join(str(a).strip() for a in args).strip()
    return str(args or "").strip()


# ===== 拼贴艺术风（Collage Art）视觉词汇：色板 / 硬偏移阴影 / 撕纸 clip-path / 胶带 =====
# 色板唯一：墨/旧纸底/纸片 + 撞色红蓝橙紫；阴影只用硬偏移（模拟纸片厚度），禁平滑渐变/大圆角/毛玻璃
_INK = "#2d2d2d"          # 墨：文字/描边/硬阴影
_PAPER_BG = "#f5f0e8"     # 旧纸底：页面底/进度条轨道色
_PAPER_CHIP = "#fbf7ef"   # 纸片：卡片/标签底（墨字只落在纸片底上，撞色底一律用纸色/白字）
_ACC_RED = "#e74c3c"      # 撞色红：主人档 / 用量警戒
_ACC_BLUE = "#3498db"     # 撞色蓝：管理员档 / 人格卡标签
_ACC_ORANGE = "#f39c12"   # 暖橙：成员档 / 任务卡 / 进度条填充
_ACC_PURPLE = "#9b59b6"   # 异质紫：版本标签 / 人格特征标签
_SHADOW_BIG = "6px 6px 0 rgba(45,45,45,.28)"    # 大件硬阴影（撕纸卡片）
_SHADOW_SMALL = "3px 3px 0 rgba(45,45,45,.22)"  # 小件硬阴影（命令纸条/进度轨道/剪切标签）
_FONT_SERIF = "Georgia,'Songti SC',serif"            # 标题衬线（700-900）
_FONT_SANS = "system-ui,'Segoe UI',sans-serif"       # 正文无衬线（400-700）
_FONT_MONO = "ui-monospace,'Courier New',monospace"  # 标签等宽（全大写 + 0.12em 字距）

# 撕纸边多边形：每张卡一份，顶点 11-13 个、偏移 0.4%-2.6%（约 2-6px），刻意互不相同避免规律感
_CLIP_MENU_1 = "polygon(1.2% 1.6%, 30% 0.4%, 58% 2.2%, 99% 0.6%, 98.2% 34%, 100% 66%, 98.8% 98.4%, 62% 99.6%, 26% 97.8%, 0.8% 99%, 2% 58%, 0.4% 28%)"
_CLIP_MENU_2 = "polygon(0.6% 2.2%, 24% 0.8%, 55% 2.4%, 86% 0.4%, 99.4% 1.8%, 100% 50%, 98.2% 99%, 56% 97.4%, 20% 99.6%, 1% 97.8%, 1.8% 46%)"
_CLIP_MENU_3 = "polygon(1.8% 0.8%, 34% 2%, 66% 0.4%, 98.6% 2.2%, 99.6% 38%, 97.8% 68%, 100% 98%, 70% 99%, 38% 97.6%, 4% 99.2%, 0.4% 96.8%, 2.2% 64%, 0.6% 32%)"
_CLIP_CARD_PERSONA = "polygon(0.8% 1.4%, 26% 2.4%, 54% 0.6%, 82% 2%, 99.2% 0.8%, 98.4% 36%, 100% 72%, 98.6% 98.8%, 66% 97.6%, 30% 99.4%, 2% 98.2%, 1.4% 54%, 0.2% 26%)"
_CLIP_CARD_TASKS = "polygon(1.4% 2.4%, 32% 0.6%, 64% 1.8%, 99% 0.8%, 98% 30%, 100% 60%, 99% 99%, 60% 98%, 24% 99.6%, 0.6% 97.6%, 2.4% 66%, 0.8% 36%)"
_CLIP_CARD_USAGE = "polygon(0.4% 1.8%, 22% 0.6%, 48% 2.2%, 76% 0.4%, 99.6% 1.4%, 98.8% 42%, 100% 78%, 98.2% 98.4%, 72% 99.6%, 44% 97.8%, 14% 99.4%, 0.8% 98%, 1.6% 50%)"
_CLIP_HEADER = "polygon(0.8% 2.4%, 30% 0.6%, 60% 2%, 99.2% 0.8%, 98.4% 48%, 100% 96%, 70% 98.6%, 34% 97.2%, 0.6% 99%, 1.6% 50%)"
# 字号按"手机聊天窗口里看小图"设计：正文 16-18px、标签条 14px、标题 22-28px，不做网页阅读尺寸


def _cut_tag(text: str, bg: str, fg: str = _PAPER_CHIP, tilt: float = 1.5, size: int = 14) -> str:
    """剪切标签条（cutout tag）：两端各切 8px 斜角的撞色实底纸条，等宽全大写——撞色底上必须纸色/白字保证对比度。"""
    return (
        f'<span style="display:inline-block;height:28px;line-height:28px;padding:0 12px;'
        f"background:{bg};color:{fg};font-family:{_FONT_MONO};font-size:{size}px;font-weight:700;"
        f"letter-spacing:0.12em;text-transform:uppercase;white-space:nowrap;"
        f"clip-path:polygon(8px 0, 100% 0, calc(100% - 8px) 100%, 0 100%);"
        f'filter:drop-shadow({_SHADOW_SMALL});transform:rotate({tilt}deg);">{text}</span>'
    )


def _tape_html(width: int, color: str, tilt: float, pos: str) -> str:
    """胶带（tape strip）：两端锯齿的半透明纸带，压在卡片角上跨边约 8px——每卡至多一条。"""
    # 左右端各两个缺口的锯齿 clip-path，模拟手撕断口
    jag = "polygon(0 0, 100% 0, 96% 30%, 100% 60%, 97% 100%, 0 100%, 3% 70%, 0 40%)"
    return (
        f'<div style="position:absolute;{pos};width:{width}px;height:20px;background:{color};'
        f'transform:rotate({tilt}deg);clip-path:{jag};z-index:2;"></div>'
    )


def _torn_card(inner: str, tilt: float, clip: str, tape: str = "", shadow: str = _SHADOW_BIG) -> str:
    """撕纸卡片：外层旋转 + drop-shadow 硬阴影（阴影跟随 clip-path 撕边走，出纸片厚度），内层纸片沿多边形裁开。"""
    return (
        f'<div style="position:relative;transform:rotate({tilt}deg);filter:drop-shadow({shadow});">'
        f'<div style="background:{_PAPER_CHIP};clip-path:{clip};">{inner}</div>{tape}</div>'
    )


def _perm_tag(level: str) -> str:
    """权限档剪切标签：主人=红 MASTER / 管理员=蓝 ADMIN / 成员=橙 MEMBER（等宽英文+中文并排，取可读性好的写法）。"""
    table = {
        "master": (_ACC_RED, "MASTER 主人"),
        "admin": (_ACC_BLUE, "ADMIN 管理员"),
        "member": (_ACC_ORANGE, "MEMBER 成员"),
    }
    bg, label = table.get(level, table["member"])
    return _cut_tag(label, bg, fg="#ffffff", tilt=1.5)


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
            ("mute", "cmd_desc_mute", True),
            ("unmute", "cmd_desc_unmute", True),
            ("policy", "cmd_desc_policy", True),
            ("lowtoken", "cmd_desc_lowtoken", True),
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
        """拼贴艺术风菜单卡片（Takumi 渲染）：旧纸底 + 撕纸分组卡/剪切标签/胶带/硬阴影。
        承载文字的条状元素（页眉纸条/页脚提示条）一律给实底纸片，任何聊天主题下文字都清晰。"""
        # 三张分组卡角度 -1.5°/+1°/-2°，撕边多边形与胶带各不相同（拼贴风要求块间有偏差，忌整齐划一）
        tilts = (-1.5, 1.0, -2.0)
        clips = (_CLIP_MENU_1, _CLIP_MENU_2, _CLIP_MENU_3)
        tapes = (
            _tape_html(130, "rgba(52,152,219,.6)", -4.0, "top:-9px;left:22px"),       # 蓝胶带压左上角（跨边 8-9px）
            "",                                                                       # 中间卡留白：胶带别滥用
            _tape_html(112, "rgba(255,255,255,.55)", 5.0, "bottom:-9px;right:18px"),  # 白胶带压右下角
        )
        nudges = ("margin:0 16px 18px 4px;", "margin:0 16px 18px 0;", "margin:0 16px 18px 8px;")
        groups_html = ""
        for i, (group, rows) in enumerate(self._menu_items(admin)):
            rows_html = ""
            for j, (cmd, desc, need) in enumerate(rows):
                # 命令纸条：白纸实底剪条 + 等宽墨字 + 小件硬阴影，交替 ±0.7° 歪贴；管理员行补一枚蓝色 ADM 小字（落在纸片底上）
                adm = (
                    f'<span style="flex:0 0 auto;font-family:{_FONT_MONO};font-size:12px;font-weight:700;'
                    f'color:{_ACC_BLUE};letter-spacing:0.12em;">ADM</span>'
                ) if need else ""
                rows_html += (
                    '<div style="display:flex;align-items:center;gap:12px;padding:8px 0;'
                    'border-bottom:1px solid rgba(45,45,45,.10);">'
                    f'<span style="flex:0 0 auto;background:#ffffff;color:{_INK};font-family:{_FONT_MONO};'
                    f'font-size:13px;padding:3px 10px;box-shadow:{_SHADOW_SMALL};'
                    f'transform:rotate({(0.7 if j % 2 == 0 else -0.7):.1f}deg);">/qvq {cmd}</span>'
                    f'<span style="flex:1;color:rgba(45,45,45,.82);font-family:{_FONT_SANS};font-size:16px;">{desc}</span>'
                    f"{adm}</div>"
                )
            head = (
                '<div style="display:flex;align-items:baseline;gap:10px;margin-bottom:8px;">'
                f'<span style="font-family:{_FONT_MONO};font-size:12px;color:rgba(45,45,45,.45);'
                f'letter-spacing:0.12em;">{i + 1:02d}</span>'
                f'<span style="font-family:{_FONT_SERIF};font-weight:700;font-size:20px;color:{_INK};">{group}</span></div>'
            )
            inner = f'<div style="padding:16px 20px 12px;">{head}{rows_html}</div>'
            groups_html += (
                f'<div style="{nudges[i % 3]}">'
                + _torn_card(inner, tilts[i % 3], clips[i % 3], tape=tapes[i % 3])
                + "</div>"
            )
        # 页眉纸条：实底纸片托住标题文字（独立剪纸条贴在旧纸底上），撕边 + 微歪 + 硬阴影；
        # 衬线 900 大标题 + 等宽装饰小字，下面一排剪切标签——版本（异质紫）与权限档（蓝/橙）；
        # 纸条底部一道歪斜墨线把页眉和拼贴区隔开（墨线画在纸片内，深浅主题都可见）
        version_tag = _cut_tag(f"v{utils.module_version()}", _ACC_PURPLE, tilt=2.0)
        perm = _perm_tag("admin" if admin else "member")
        header = (
            f'<div style="background:{_PAPER_CHIP};clip-path:{_CLIP_HEADER};filter:drop-shadow({_SHADOW_SMALL});'
            f'transform:rotate(-0.5deg);padding:14px 20px 12px;margin-bottom:18px;">'
            '<div style="display:flex;align-items:flex-end;gap:12px;">'
            f'<div style="font-family:{_FONT_SERIF};font-weight:900;font-size:28px;color:{_INK};">QvQChat</div>'
            f'<span style="font-family:{_FONT_MONO};font-size:11px;color:rgba(45,45,45,.5);'
            f'letter-spacing:0.14em;padding-bottom:8px;">COMMAND MENU</span></div>'
            '<div style="display:flex;gap:10px;margin-top:10px;">'
            f"{version_tag}{perm}</div>"
            '<div style="height:2px;background:rgba(45,45,45,.22);transform:rotate(-0.4deg);margin-top:12px;"></div></div>'
        )
        # 页脚提示条：同样实底纸片托字，居中窄条微歪
        foot = (
            f'<div style="background:{_PAPER_CHIP};filter:drop-shadow({_SHADOW_SMALL});transform:rotate(0.6deg);'
            f'width:fit-content;margin:2px auto 0;padding:6px 16px;font-family:{_FONT_MONO};font-size:13px;'
            f'color:rgba(45,45,45,.72);letter-spacing:0.08em;">{texts.t("cmd_menu_hint")}</div>'
        )
        # 页面底：旧纸色（风格基准底色），不依赖渲染器 alpha 能力
        return (
            f'<div style="background:{_PAPER_BG};padding:20px 22px 16px;font-family:{_FONT_SANS};border-radius:2px;">'
            f"{header}{groups_html}{foot}</div>"
        )

    def _menu_text(self, admin: bool) -> str:
        lines = ["QvQChat"]
        for group, rows in self._menu_items(admin):
            lines.append(f"✿ {group}")
            lines.extend(f"  /qvq {cmd} - {desc}" for cmd, desc, _ in rows)
        lines.append(texts.t("cmd_menu_hint"))
        return "\n".join(lines)

    async def _send_menu(self, event, admin: bool) -> None:
        """/qvq 交互式菜单：Takumi 可用时渲染拼贴艺术风卡片发图，失败/缺失回退文本。"""
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
# 隐私开关：关闭后本群消息不进入旁听/插话/回执事件，本群成员可拒绝被监听
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
            elif sub in ("mute", "unmute", "屏蔽", "解除屏蔽", "policy", "策略", "lowtoken", "省钱", "省流"):
# 会话治理（屏蔽/优先级/省钱）四个子命令统一入口，见 _cmd_policy
                await self._cmd_policy(event, chat_key, user_id, tokens)
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
# KV 绑定为唯一事实源；会话 state.persona 镜像已废弃
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


# ===== 会话治理：/qvq mute|unmute|policy|lowtoken（全管理员，写 conversation/policy 的会话策略） =====

    @staticmethod
    def _policy_labels(policy: dict) -> dict:
        """策略值 → 回复文案 format 标签（中文短标签固定，与 locale 文案解耦）。"""
        return {
            "priority": {"high": "高", "normal": "常规", "low": "低"}.get(str(policy.get("priority") or ""), "常规"),
            "low_token": "开" if policy.get("low_token") else "关",
        }

    async def _cmd_policy(self, event, chat_key: str, user_id: str, tokens: list) -> None:
        """/qvq mute|unmute：屏蔽开关（消息入口早闸不回复不旁听）。
        /qvq policy [high|normal|low]：资源优先级（无参回用法+当前值）。
        /qvq lowtoken on|off：省钱模式（输入瘦身，配合全局 budget_mode 省更多）。"""
        if not self.is_admin(user_id, platform=event.get_platform() or ""):
            await event.reply(texts.t("needs_admin"))
            return
        sub = tokens[0].lower()
        if sub in ("mute", "屏蔽"):
            set_policy(self.sdk, chat_key, muted=True)
            await event.reply(texts.t("policy_muted_on"))
            return
        if sub in ("unmute", "解除屏蔽"):
            set_policy(self.sdk, chat_key, muted=False)
            await event.reply(texts.t("policy_muted_off"))
            return
        if sub in ("lowtoken", "省钱", "省流"):
            action = tokens[1].lower() if len(tokens) >= 2 else ""
            if action in ("on", "开", "開"):
                policy = set_policy(self.sdk, chat_key, low_token=True)
            elif action in ("off", "关", "關"):
                policy = set_policy(self.sdk, chat_key, low_token=False)
            else:
# 无参/非法参数也回完整用法（附当前值），顺手当状态查询用
                await event.reply(texts.t("policy_usage", **self._policy_labels(get_policy(self.sdk, chat_key))))
                return
            await event.reply(texts.t("policy_set", **self._policy_labels(policy)))
            return
# policy [high|normal|low]：带参改优先级，无参/非法回用法（附当前值）
        arg = tokens[1].lower() if len(tokens) >= 2 else ""
        if arg in ("high", "normal", "low"):
            policy = set_policy(self.sdk, chat_key, priority=arg)
            await event.reply(texts.t("policy_set", **self._policy_labels(policy)))
            return
        await event.reply(texts.t("policy_usage", **self._policy_labels(get_policy(self.sdk, chat_key))))


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

    def _card_shell(self, title: str, body_rows: list, accent: str = _ACC_BLUE,
                    tag_text: str = "", head_extra: str = "", foot_extra: str = "",
                    tilt: float = 0.8, clip: str = _CLIP_CARD_PERSONA, tape: str = "") -> str:
        """拼贴风卡片底壳：一张撕纸纸片——衬线大标题 + 旁边的剪切标签条（accent 决定撞色），行间细墨线。
        tag_text/head_extra/foot_extra/tilt/clip/tape 由各卡自行传入：三张卡的撕边多边形、角度、标签色互不相同。"""
        rows = "".join(
            '<div style="display:flex;gap:14px;padding:9px 0;border-bottom:1px solid rgba(45,45,45,.10);">'
            f'<span style="flex:0 0 112px;font-family:{_FONT_MONO};font-size:12.5px;color:rgba(45,45,45,.55);'
            f'letter-spacing:0.12em;text-transform:uppercase;padding-top:3px;">' + k + "</span>"
            f'<span style="flex:1;color:{_INK};font-family:{_FONT_SANS};font-size:16px;font-weight:500;'
            f'word-break:break-all;">' + v + "</span></div>"
            for k, v in body_rows
        )
        tag = _cut_tag(tag_text, accent, tilt=2.0) if tag_text else ""
        inner = (
            '<div style="padding:20px 22px 16px;">'
            '<div style="display:flex;align-items:center;gap:14px;margin-bottom:14px;">'
            f'<div style="font-family:{_FONT_SERIF};font-weight:800;font-size:24px;color:{_INK};">{title}</div>{tag}</div>'
            f"{head_extra}{rows}{foot_extra}"
            f'<div style="text-align:center;margin-top:16px;font-family:{_FONT_MONO};font-size:12px;'
            f'color:rgba(45,45,45,.4);letter-spacing:0.14em;">QVQCHAT</div></div>'
        )
        # 页面底：旧纸色包住撕纸卡片，内边距给 6px 硬阴影留出投影空间
        return (
            f'<div style="background:{_PAPER_BG};padding:18px 20px;font-family:{_FONT_SANS};border-radius:2px;">'
            + _torn_card(inner, tilt, clip, tape=tape) + "</div>"
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
        # 特征标签：异质紫实底剪纸条（撞色底上放纸色字保对比度），交替 ±1.2° 歪贴
        chips = "".join(
            _cut_tag(f, _ACC_PURPLE, tilt=(1.2 if i % 2 == 0 else -1.2))
            for i, f in enumerate(flags)
        )
        chip_row = ('<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">' + chips + "</div>") if flags else ""
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
        # 人格卡：标签条撞色蓝 + 紫色半透明胶带压右上角，整卡歪 +0.8°
        tape = _tape_html(150, "rgba(155,91,182,.6)", -4.5, "top:-9px;right:24px")
        return self._card_shell(
            self._esc(persona.get("name") or persona.get("id") or "Persona"), rows,
            accent=_ACC_BLUE, tag_text="PERSONA", head_extra=chip_row,
            tilt=0.8, clip=_CLIP_CARD_PERSONA, tape=tape,
        )

    def _persona_card_text(self, persona: dict) -> str:
        return "\n".join([
            f"人格：{persona.get('name') or persona.get('id')}（{persona.get('id')}）",
            f"昵称：{persona.get('nickname') or '-'} · 称呼主人：{persona.get('owner_title') or '-'}",
            f"口头禅：{'、'.join(persona.get('catchphrases') or []) or '-'}",
            f"语气样例：{len(persona.get('examples') or [])} 条 · 温度：{persona.get('temperature') if persona.get('temperature') is not None else 'auto'}",
            f"设定摘要：{utils.truncate(str(persona.get('system') or ''), 120)}",
        ])

    def _tasks_card_html(self, tasks: list) -> str:
        # 任务卡：标签条撞色暖橙 + 橙色半透明胶带压左上角，整卡歪 -1.1°
        tape = _tape_html(118, "rgba(243,156,18,.6)", 4.0, "top:-9px;left:26px")
        if not tasks:
            return self._card_shell("定时任务 · 本会话", [("状态", "本会话没有定时任务")],
                                    accent=_ACC_ORANGE, tag_text="TASKS", tilt=-1.1,
                                    clip=_CLIP_CARD_TASKS, tape=tape)
        rows = []
        for i, t in enumerate(tasks[:10]):
            # 左列等宽序号（剪报页码感），右列无衬线 700 名称（16px 继承壳行）+ 等宽时间 + 小字提示
            value = (
                f'<span style="font-family:{_FONT_SANS};font-weight:700;color:{_INK};">'
                + self._esc(t.get("name") or t.get("id")) + "</span><br>"
                f'<span style="font-family:{_FONT_MONO};font-size:14px;color:rgba(45,45,45,.8);">'
                + self._esc(utils.format_ts(float(t.get("next_run", 0)))) + "</span><br>"
                f'<span style="font-family:{_FONT_SANS};font-size:13.5px;color:rgba(45,45,45,.6);">'
                + self._esc(utils.truncate(str(t.get("prompt") or ""), 60)) + "</span>"
            )
            rows.append((f"{i + 1:02d}", value))
        return self._card_shell(f"定时任务 · 本会话（{len(tasks)}）", rows,
                                accent=_ACC_ORANGE, tag_text="TASKS", tilt=-1.1,
                                clip=_CLIP_CARD_TASKS, tape=tape)

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
        # 进度条 = 剪出来的条：轨道旧纸实底 + 小件硬阴影，填充撞色（≥80% 转红示警），右端三道短墨线刻度（像尺子）
        fill = _ACC_ORANGE if pct < 80 else _ACC_RED
        ticks = (
            f'<div style="position:absolute;top:2px;right:0;width:9px;height:2px;background:{_INK};"></div>'
            f'<div style="position:absolute;top:7px;right:0;width:6px;height:2px;background:{_INK};opacity:.55;"></div>'
            f'<div style="position:absolute;bottom:2px;right:0;width:9px;height:2px;background:{_INK};"></div>'
        )
        bar = (
            f'<div style="position:relative;background:{_PAPER_BG};height:16px;margin-top:12px;box-shadow:{_SHADOW_SMALL};">'
            f'<div style="width:{pct}%;height:100%;background:{fill};"></div>{ticks}</div>'
        )
        pct_label = (
            f'<span style="font-family:{_FONT_MONO};font-size:16px;font-weight:700;color:{fill};">{pct}%</span>'
            if limit else ""
        )
        limit_label = f' <span style="font-size:15px;color:rgba(45,45,45,.55);">/ {limit:,}</span>' if limit else ""
        # "今日"块：白纸实底剪片压在纸片卡上（浅色数字靠白底托清晰），剪切痕迹虚线边框全卡唯一，是这张卡的强调元素
        today = (
            '<div style="border:2px dashed rgba(45,45,45,.4);background:#ffffff;padding:14px 16px;margin-bottom:14px;">'
            '<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<span style="font-family:{_FONT_SANS};font-weight:900;font-size:15px;color:{_INK};letter-spacing:0.06em;">今日 TOKEN</span>'
            f"{pct_label}</div>"
            f'<div style="font-family:{_FONT_MONO};font-size:24px;font-weight:700;color:{_INK};margin-top:6px;">{tokens:,}{limit_label}</div>'
            f"{bar}</div>"
        )
        # 数字一律等宽字体且放大（手机小图可读）；身份行直接贴权限档剪切标签
        rows = [
            ("今日调用", f'<span style="font-family:{_FONT_MONO};font-size:16px;color:{_INK};">{int(usage.get("calls", 0) or 0):,}</span>'),
            ("运行时长", f'<span style="font-family:{_FONT_MONO};font-size:16px;color:{_INK};">'
             + (f"{uptime // 3600}h{(uptime % 3600) // 60:02d}m" if uptime >= 3600 else f"{uptime // 60}m{uptime % 60:02d}s") + "</span>"),
            ("工具", f'<span style="font-family:{_FONT_MONO};font-size:16px;color:{_INK};">{sum(counts.values())}</span>'
             f'<span style="font-family:{_FONT_SANS};font-size:14px;color:rgba(45,45,45,.6);">（生态 {counts.get("eco", 0)}）</span>'),
            ("身份", _perm_tag("admin" if admin else "member")),
        ]
        # 用量卡不贴胶带：虚线"今日"块 + 剪出来的进度条已是焦点（每卡至多一条原则下刻意留白）
        return self._card_shell("用量 · 今日", rows, accent=_ACC_RED, tag_text="USAGE",
                                head_extra=today, tilt=0.6, clip=_CLIP_CARD_USAGE)

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
