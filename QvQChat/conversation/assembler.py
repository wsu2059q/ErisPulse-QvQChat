"""提示词装配（ConversationService 的装配半区）：系统部件/人格增强/上传落盘/多模态重建。

从 service.py 拆出（M6-4）：方法体逐字搬运；对会话面（画像/TODO/事实/上下文）
的调用改走 self.svc（back-ref），KV 与返回形状不变。
"""
from __future__ import annotations

import asyncio
import base64 as _base64
import hashlib as _hashlib
import re as _re
from pathlib import Path
from urllib.parse import unquote as _unquote

from .. import texts, utils
from ..engine import tokens
from ..engine.base import ChatRequest, TaskSpec
from ..prompts import CAPABILITY_PROMPT, SKILL_OFFER_NOTE
from .budget import ContextPacker, SystemPart
from .repository import DASHBOARD_PLATFORM, strip_account

UPLOAD_DIR = Path("data/QvQChat/uploads")


class PromptAssembler:
    """装配半区：build_system_parts/build_system/save_upload/rebuild_user_content。"""

    def __init__(self, svc):
        self.svc = svc

    @staticmethod
    def _persona_style_directives(style: dict) -> str:
        """style dict 编译为语言中性的约束值串（emoji_density/verbosity/formality）。"""
        bits = []
        for key in ("emoji_density", "verbosity", "formality"):
            value = str((style or {}).get(key) or "").strip()
            if value:
                bits.append(f"{key}: {value}")
        return "; ".join(bits)

    @property
    def sdk(self):
        return self.svc.sdk

    @property
    def main(self):
        return self.svc.main

    @property
    def config(self):
        return self.svc.config

    @classmethod
    def _persona_extra_text(cls, persona: dict) -> str:
        """persona 扩展字段（style/examples/banned_words/catchphrases）编译为注入文本块。"""
        lines: list[str] = []
        style = persona.get("style") if isinstance(persona.get("style"), dict) else {}
        directives = cls._persona_style_directives(style)
        if directives:
            lines.append(texts.t("style_line", value=directives))
        banned = [str(w) for w in (persona.get("banned_words") or []) if str(w).strip()]
        if banned:
            lines.append(texts.t("persona_banned_words", words=", ".join(banned)))
        catchphrases = [str(w) for w in (persona.get("catchphrases") or []) if str(w).strip()]
        if catchphrases:
            lines.append(texts.t("persona_catchphrases", phrases=", ".join(catchphrases)))
        examples = [e for e in (persona.get("examples") or []) if isinstance(e, dict)]
        if examples:
            blocks = [texts.t("persona_examples_header")]
            for item in examples:
                user = str(item.get("user") or "").strip()
                assistant = str(item.get("assistant") or "").strip()
                if user:
                    blocks.append(f"用户：{user}")
                if assistant:
                    blocks.append(f"助手：{assistant}")
            lines.append("<persona-examples>\n" + "\n".join(blocks) + "\n</persona-examples>")
        return "\n".join(lines)

    def _persona_roster_text(self, persona: dict) -> str:
        """人格名册：除当前人格外的已定义人格（名字 + 别名 + id），供"认出熟人"。

        不含绑定位置/系统提示词——跨会话信息不能借名册泄露；仅一个角色时不注入。
        """
        if not bool(getattr(self.config, "persona_roster_enabled", True)):
            return ""
        manager = getattr(self.main, "personas", None)
        entries = manager.list() if manager is not None else []
        current_id = str(persona.get("id") or "")
        lines: list[str] = []
        for entry in entries or []:
            pid = str(entry.get("id") or "")
            if not pid or pid == current_id:
                continue
            name = str(entry.get("name") or "").strip() or pid
            nickname = str(entry.get("nickname") or "").strip()
            lines.append(f"- {name}" + (f"（别名：{nickname}）" if nickname and nickname != name else "") + f"（{pid}）")
        return "\n".join(lines) if len(lines) >= 1 else ""

    def _sender_restricted(self, sender_id: str, profile_user: str) -> bool:
        """发话者是否非管理员（受限模式提示的依据）；无宿主/无发送者时不限制。"""
        if not sender_id:
            return False
        is_admin = getattr(self.main, "is_admin", None)
        if not callable(is_admin):
            return False
        platform = str(profile_user or "").split(":", 1)[0]
        try:
            return not bool(is_admin(str(sender_id), "chat", platform))
        except Exception:
            return False

    def build_system_parts(
        self,
        persona: dict,
        scene: str = "",
        chat_key: str = "",
        active_skills: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        kb_query: str = "",
        profile_user: str = "",
        kb_texts: list[str] | None = None,
        restricted: bool = False,
        admin_ids: list[str] | None = None,
        low_token: bool = False,
    ) -> list[SystemPart]:
        """系统提示词按语义拆分为部件（供 ContextPacker 按优先级装填）。

        low_token 时跳过 kb/技能清单/画像/名册/技能诱导等重组件，
        persona/capability/facts/todo/memory/summary 等连续性部件保留。
        """
# 首行人格身份认知 + 主人称呼（并入 persona 部件，required 保位）
        persona_text = (
            texts.t("persona_identity", name=str(persona.get("name") or ""), id=str(persona.get("id") or ""))
            + "\n" + persona["system"] + "\n" + utils.time_line()
        )
        owner_title = str(persona.get("owner_title") or "").strip()
        if owner_title:
            persona_text += "\n" + texts.t("owner_title_line", title=owner_title)
        parts: list[SystemPart] = [
            SystemPart("persona", persona_text, required=True),
            SystemPart("capability", CAPABILITY_PROMPT + "\n" + texts.t("system_brevity"), required=True),
        ]
# 扩展字段独立部件（PRIORITY 未收录 persona_extra → pack 兜底按 extra 优先级稳定排序，
# 插在 extra 类部件之前；不预算时按列表顺序紧跟 persona 呈现）
        persona_extra = self._persona_extra_text(persona)
        if persona_extra:
            parts.insert(1, SystemPart("persona_extra", persona_extra))
# 人格名册感知：注入已定义人格（名字/别名），被提到时能"认出"并自然谈起
        roster = self._persona_roster_text(persona)
# 输入取舍：名册是"认出熟人"的锦上添花，非人格连续性必需，低token时不注入
        if roster and not low_token:
            parts.append(SystemPart("roster", texts.t("persona_roster_note") + "\n" + roster))
        if getattr(self.config, "chat_output_rules", True):
            parts.append(SystemPart("chat_rules", texts.t("chat_output_rules")))
        if getattr(self.config, "identity_note_other_agents", True):
            parts.append(SystemPart("identity_note", texts.t("identity_other_agents")))
# 受限模式：非管理员发话时明确告知权限边界——遇越界请求必须提醒找管理员（附当前平台管理员 id）
        if restricted:
            parts.append(SystemPart(
                "permission",
                texts.t("restricted_mode_note", admins="、".join(admin_ids or []) or "-"),
            ))
# 输入取舍：技能诱导只是"提醒模型可以用技能"的固定开销，低token时省去
        if getattr(self.config, "skill_induct", True) and not low_token:
            parts.append(SystemPart("skill_offer", SKILL_OFFER_NOTE))
# 事件收件箱感知（默认开启）：让模型知道平台事件都在收件箱里、可自主查看
        parts.append(SystemPart("inbox_note", texts.t("inbox_note")))
# 生态能力清单：只列所有人可用的 eco 工具，避免模型"不知道装了表情包模块"
# 生态建议紧跟人格规则（而非压在提示词最尾部）——位置太靠后注意力权重低，模块装了也不被调用
        eco = getattr(self.main, "eco", None)
        if eco is not None and hasattr(eco, "safe_tool_hint"):
            try:
                hint = eco.safe_tool_hint()
            except Exception:
                hint = ""
            if hint:
                parts.append(SystemPart("eco_hint", texts.t("eco_system_note") + "\n" + hint))
        if eco is not None and hasattr(eco, "external_prompts"):
            try:
                advice = eco.external_prompts()
            except Exception:
                advice = []
            if advice:
                parts.append(SystemPart(
                    "eco_prompt",
                    texts.t("eco_prompt_note") + "\n" + "\n".join(f"- {line}" for line in advice),
                ))
# 内联媒体标记说明：只列当前真能落地的标记（供方缺失时模型不该写）
        media_router = getattr(getattr(self.main, "delivery", None), "media", None)
        if media_router is not None:
            try:
                media_note = media_router.prompt_note()
            except Exception:
                media_note = ""
            if media_note:
                parts.append(SystemPart("media_markers", media_note))
        if scene:
            parts.append(SystemPart("scene", scene))
        if chat_key:
            summary = self.svc.summary_of(chat_key)
            if summary:
                parts.append(SystemPart("summary", texts.t("summary_header") + "\n" + summary))
            facts = self.svc.facts_of(chat_key)
            if facts:
                parts.append(SystemPart("facts", texts.t("facts_header") + "\n" + "\n".join(f"- {f}" for f in facts)))
# TODO 清单注入（facts 之后）：长任务进度对 AI 持续可见，推进即勾选
            todo_text = self.svc.todos.render(chat_key)
            if todo_text:
                parts.append(SystemPart("todo", texts.t("todo_system_note") + "\n" + todo_text))
            else:
# 空清单也给一条轻提示：只在"已有清单"时注入会导致 AI 不知道有这个工具族，
# 多步任务不会主动拆条（模型不知道存在该工具族）
                parts.append(SystemPart("todo", texts.t("todo_empty_hint")))
# 跨会话用户画像注入（profile_user = platform:uid；PRIORITY 位于 facts 与 memory 之间）
# 输入取舍：画像摘要可整体延后一拍，丢它不丢任务上下文，低token时跳过
        if profile_user and getattr(self.config, "profile_enabled", True) and not low_token:
            lines = self.svc.profile.digest(profile_user)
            if lines:
                parts.append(SystemPart("profile", texts.t("profile_header") + "\n" + "\n".join(f"- {line}" for line in lines)))
        skills = getattr(self.main, "skills", None)
        if skills:
            if active_skills:
                for name in active_skills:
                    skill = skills.get_skill(str(name))
                    if not skill:
                        continue
                    parts.append(
                        SystemPart(
                            "skill_full",
                            "<active-skill name=\"" + str(name) + "\">\n"
                            + utils.truncate(str(skill.get("body") or ""), 8000)
                            + "\n</active-skill>",
                        )
                    )
# 输入取舍：技能全量清单可能很长；显式激活的 skill_full 保留（用户点名要的任务不能丢）
            enabled = [s for s in skills.list_skills() if s.get("enabled")]
            if enabled and not low_token:
                lines = "\n".join(f"- {s['name']}: {s.get('description') or ''}" for s in enabled)
                parts.append(SystemPart("skill_list", "<skills>\n" + texts.t("skills_system_note") + "\n" + lines + "\n</skills>"))
        if mcp_tools:
            tools_hint = [str(t) for t in mcp_tools if str(t)]
            if tools_hint:
                parts.append(SystemPart("extra", texts.t("dashboard_mcp_hint", tools=", ".join(tools_hint))))
# 输入取舍：kb 命中块最重（每条 1500 字截断，还可能是多条），低token时整段跳过
        if getattr(self.config, "kb_auto_inject", True) and kb_query and not low_token:
            kb = getattr(self.main, "knowledge", None)
# 可见域：全局条目 + 本会话/本适配器私有条目（AI 默认写会话级，跨会话共享需显式声明）
            hits = kb.search(kb_query, top_k=int(getattr(self.config, "kb_top_k", 2) or 0), viewer=chat_key) if kb else []
# Lorebook：最近上下文命中触发条目优先排前合并注入（[triggered] 标记，同条目去重）
            lore = kb.triggered(kb_texts or [], viewer=chat_key) if (kb and kb_texts) else []
            hit_ids = {e.get("id") for e in lore}
            hits = [h for h in hits if h.get("id") not in hit_ids]
            if hits or lore:
                lore_blocks = [
                    f"<kb-doc title=\"{h.get('title', '')} [triggered]\">\n{utils.truncate(str(h.get('content') or ''), 1500)}\n</kb-doc>"
                    for h in lore
                ]
                hit_blocks = [f"<kb-doc title=\"{h['title']}\">\n{h['snippet']}\n</kb-doc>" for h in hits]
                parts.append(SystemPart("kb", texts.t("kb_system_note") + "\n" + "\n\n".join(lore_blocks + hit_blocks)))
        for line in getattr(self.config, "extra_prompts", []) or []:
            line = str(line).strip()
            if line:
                parts.append(SystemPart("extra", line))
        return parts

    def build_system(
        self,
        persona: dict,
        scene: str = "",
        chat_key: str = "",
        active_skills: list[str] | None = None,
        mcp_tools: list[str] | None = None,
        kb_query: str = "",
    ) -> str:
# 兼容层：原字符串拼接入口改为部件 join
        parts = self.build_system_parts(
            persona,
            scene=scene,
            chat_key=chat_key,
            active_skills=active_skills,
            mcp_tools=mcp_tools,
            kb_query=kb_query,
        )
        return "\n".join(p.text for p in parts if p.text)


    async def resolve_session_names(self, sessions: list[dict]) -> None:

        for session in sessions[:20]:
            chat_key = str(session.get("chat_key") or "")
            if session.get("name") or not chat_key:
                continue
            platform = str(session.get("platform") or "")
            detail_type = str(session.get("detail_type") or "")
# 目标 id 必须还原成纯 id：account_isolation 时代的会话键带 @botQQ 后缀，
# 复合 id 直发适配器会被服务端 uint 校验拒收（strip_account 就是为这个存在的）
            target_id = strip_account(str(session.get("target_id") or ""))
            if platform == DASHBOARD_PLATFORM or not platform or not target_id:
                continue
            try:
                adapter = self.sdk.adapter.get(platform)
            except Exception:
                adapter = None
            if adapter is None:
                continue
            name = ""
            try:
                if detail_type == "group":
                    info = await asyncio.wait_for(
                        adapter.call_api("get_group_info", group_id=target_id), 6
                    )
# 信封兼容：群名在 data 层（{status, data:{group_name}}），无信封则取顶层
                    payload = info if isinstance(info, dict) else {}
                    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
                    name = str(data.get("group_name") or "")
                    if name:
                        self.svc.set_group_name(chat_key, name)
                else:
# 只用 OB11 标准 get_stranger_info（get_user_info 是 OB12 动作名，裸 call_api 无映射必 404）；
# 昵称在信封 data 层（{status, retcode, data:{nickname,...}}），读顶层永远拿不到
                    info = await asyncio.wait_for(
                        adapter.call_api("get_stranger_info", user_id=target_id), 6
                    )
                    if isinstance(info, dict):
                        data = info.get("data") if isinstance(info.get("data"), dict) else info
                        name = str(data.get("nickname") or data.get("card") or "")
                    if name:
                        self.svc.set_user_name(chat_key, name)
            except Exception:
                continue

    async def title_task(self, chat_key: str, user_text: str, reply: str) -> None:

        pool = getattr(self.main, "pool", None)
        if pool is None:
            return
# 高负载降载：满载时跳过标题生成（会话没有标题只是显示难看，不丢数据）
        if callable(getattr(pool, "background_blocked", None)) and pool.background_blocked():
            self.main.logger.debug("background skip: title-task (saturated)")
            return
        from ..engine.base import ChatRequest

        request = ChatRequest(
            messages=[
                {"role": "system", "content": texts.t("title_system")},
                {
                    "role": "user",
                    "content": utils.truncate(user_text, 200) + "\n---\n" + utils.truncate(reply, 300),
                },
            ],
            max_tokens=48,
            temperature=0.3,
        )
        try:
# 标题生成迁 dispatch(kind="title", prefer="cheap")
            dispatch = getattr(pool, "dispatch", None)
            if callable(dispatch):
                resp = await dispatch(TaskSpec(kind="title", prefer="cheap"), request)
            else:
                resp = await pool.chat(request)
            title = (resp.content or "").strip().strip("\"“”‘’。.!!??")
            title = title.splitlines()[0][:40] if title else ""
            if title:
                self.svc.set_group_name(chat_key, title)
        except Exception as e:
            self.main.logger.warning(f"title generation failed: {e}")

    async def learn_group_style(self, chat_key: str) -> None:
        """群语气学习：从最近群聊提取本群说话风格（1-2 句）存 state["group_style"]。

        消费方 build_system_parts 群聊时注入——bot 在不同群里说不同的话
        （每个群模都不一样，小eris 点名需求）。走 cheap 派发，成本极低。"""
        pool = getattr(self.main, "pool", None)
        if pool is None:
            return
        if callable(getattr(pool, "background_blocked", None)) and pool.background_blocked():
            self.main.logger.debug("background skip: group-style (saturated)")
            return
        contexts = self.svc.get_contexts(chat_key)
        window = contexts[-30:]
        if len(window) < 6:
            return
        transcript = []
        for entry in window:
            if not isinstance(entry, dict):
                continue
            role = "bot" if entry.get("role") == "assistant" else "member"
            text = utils.truncate(self.svc._text_of(entry.get("content")), 120)
            if text:
                transcript.append(f"{role}: {text}")
        if len(transcript) < 6:
            return
        from ..engine.base import ChatRequest

        request = ChatRequest(
            messages=[
                {"role": "system", "content": texts.t("group_style_system")},
                {"role": "user", "content": "\n".join(transcript[:40])},
            ],
            max_tokens=80,
            temperature=0.4,
        )
        try:
            dispatch = getattr(pool, "dispatch", None)
            if callable(dispatch):
                resp = await dispatch(TaskSpec(kind="compact", prefer="cheap"), request)
            else:
                resp = await pool.chat(request)
            style = (resp.content or "").strip().splitlines()[0][:160] if (resp.content or "").strip() else ""
            if style:
                self.svc.set_group_style(chat_key, style)
        except Exception as e:
            self.main.logger.debug(f"group style learn failed: {e}")


    def save_upload(self, name: str, data: str) -> str | None:

        payload: bytes | None = None
        m = _re.match(r"^data:([^;,]+)?(;base64)?,(.*)$", data, _re.DOTALL)
        if m and m.group(2):
            try:
                payload = _base64.b64decode(m.group(3))
            except Exception:
                return None
        elif m:
            payload = _unquote(m.group(3)).encode("utf-8", "replace")
        else:
            payload = data.encode("utf-8", "replace")
        if payload is None:
            return None
        digest = _hashlib.sha256(payload).hexdigest()[:16]
        safe = _re.sub(r"[^\w.\-]+", "_", name, flags=_re.UNICODE).strip("_") or "file"
        try:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            for existing in UPLOAD_DIR.iterdir():
                if existing.is_file() and existing.name.startswith(digest + "_"):
                    return str(existing)
            target = UPLOAD_DIR / f"{digest}_{safe}"
            target.write_bytes(payload)
        except OSError:
            return None
        return str(target)

    def rebuild_user_content(self, text: str, attachments: list):

        parts: list = []
        notes: list[str] = []
        if text:
            parts.append({"type": "text", "text": text})
        for att in attachments or []:
            if not isinstance(att, dict):
                continue
            name = str(att.get("name") or "file")
            mime = str(att.get("mime") or "").lower()
            data = str(att.get("data") or "")
            if not data:
                continue
            if mime.startswith("image/") and len(parts) < 4 and len(data) <= 7_000_000:
                url = data if data.startswith("data:") else f"data:{mime};base64,{data}"
                parts.append({"type": "image_url", "image_url": {"url": url}})
                continue
            saved = self.save_upload(name, data)
            if saved:
                size = Path(saved).stat().st_size
                notes.append(texts.t("attachment_saved", name=name, path=saved, size=size))
            else:
                notes.append(f"[attachment {name}]（保存失败，内容不可用）")
        if notes:
            tail = "\n\n".join(notes)
            if parts and parts[0].get("type") == "text":
                parts[0]["text"] = (parts[0]["text"] + "\n\n" + tail).strip()
            else:
                parts.insert(0, {"type": "text", "text": tail})
        if not parts:
            return text or ""
        if len(parts) == 1 and parts[0].get("type") == "text":
            return parts[0]["text"]
        return parts


