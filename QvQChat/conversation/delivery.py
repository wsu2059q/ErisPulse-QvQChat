from __future__ import annotations

import asyncio
import re

from .. import texts, utils
from ..tools_builtin.erispulse import REPLY_PREFERENCE

OUTPUT_TAG_RE = re.compile(r"^\[\[(转发|直发)\]\]\s*")

RECAP_RE = re.compile(r"^(已[经把完成向]|好[的了]|已发送|已发出|done|sent)")


def strip_output_tag(reply: str) -> tuple[str, bool | None]:
    """[[转发]]/[[直发]] 前缀解析；返回 (正文, force)。"""
    tag = OUTPUT_TAG_RE.match(reply)
    if not tag:
        return reply, None
    return reply[tag.end():].strip(), tag.group(1) == "转发"


def split_paragraphs(text: str, min_length: int = 120, max_parts: int = 6) -> list[str]:
    """纯对话分段：按空行切段，过短的相邻段合并，总量不足或只有一段则不分。"""
    parts = [p.strip() for p in re.split(r"\n{2,}", str(text or "")) if p.strip()]
    if len(parts) <= 1:
        return []
    merged: list[str] = []
    for part in parts:
        if merged and len(merged[-1]) < min_length:
            merged[-1] += "\n\n" + part
        else:
            merged.append(part)
    if len(merged) < 2 or sum(len(p) for p in merged) < min_length:
        return []
    if len(merged) > max_parts:
        head = merged[: max_parts - 1]
        head.append("\n\n".join(merged[max_parts - 1:]))
        merged = head
    return merged


class Delivery:
    """回复投递唯一出口：转发打包 / 分段连发 / 直发降级，全在这里决定。"""

    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self.config = main.cfg

    def _reply_methods(self, event) -> list:
        from ..tools_builtin import erispulse

        methods = []
        for name in erispulse.REPLY_PREFERENCE:
            try:
                if event.supports(name):
                    methods.append(name)
            except Exception:
                continue
        if "Text" not in methods:
            methods.append("Text")
        return methods

    @staticmethod
    def _is_recap(reply: str, tool_trace: list) -> bool:
        if not tool_trace or not any(t.get("tool") == "send_message" for t in tool_trace):
            return False
        return bool(len(reply.strip()) <= 150 and RECAP_RE.match(reply.strip()))

    async def _try_forward(self, event, reply: str, tool_trace: list, force: bool | None = None) -> bool:
        if force is False:
            return False
        platform = event.get_platform() or ""
        adapter = self.sdk.adapter.get(platform)
        if adapter is None:
            return False
        try:
            sends = list(self.sdk.adapter.list_sends(platform))
        except Exception:
            sends = []
        if force is not True:
            # 打包与否看运行方式，不看文本长度：用了工具的长任务回复转合并转发，纯对话不转
            if not getattr(self.config, "forward_enabled", True):
                return False
            if not tool_trace:
                return False
        sections: list = []
        if tool_trace:
            lines = []
            for entry in tool_trace[:10]:
                lines.append(f"{entry.get('tool', '')}({utils.truncate(str(entry.get('arguments', '')), 80)})")
                output = utils.truncate(str(entry.get("output", "")), 200).replace("\n", " ")
                lines.append(texts.t("forward_result", output=output))
            if lines:
                sections.append(texts.t("forward_process_title") + "\n" + "\n".join(lines))
        sections += utils.split_reply_sections(reply)
        if not sections:
            return False
        detail_type = "group" if event.is_group_message() else "user"
        if detail_type == "group":
            target_id = str(event.get_group_id() or "")
        else:
            target_id = str(event.get_user_id() or "")
        if not target_id:
            return False
        try:
            used = await utils.deliver_forward(adapter, detail_type, target_id, sections, sends)
        except Exception as e:
            self.main.logger.warning(f"forward send failed, fallback to normal reply: {e}")
            return False
        return bool(used)

    async def _send_plain(self, event, reply: str) -> None:
        last_error: Exception | None = None
        for method in self._reply_methods(event):
            content = utils.markdown_to_text(reply) if method == "Text" else reply
            try:
                await event.reply(content, method=method)
                last_error = None
                break
            except Exception as e:
                last_error = e
        if last_error is not None:
            self.main.logger.warning(f"reply failed: {last_error}")

    async def _send_split(self, event, reply: str) -> None:
        parts = split_paragraphs(
            reply,
            min_length=int(getattr(self.config, "split_min_length", 120) or 0),
        )
        if len(parts) < 2:
            await self._send_plain(event, reply)
            return
        delay = float(getattr(self.config, "split_delay", 1.2) or 0)
        for index, part in enumerate(parts):
            if index and delay:
                await asyncio.sleep(delay)
            await self._send_plain(event, part)

    async def deliver_reply(self, event, reply: str, tool_trace: list, force: bool | None = None) -> None:
        """平台回复投递：recap 抑制 → 合并转发 → 分段/单条直发。"""
        if self._is_recap(reply, tool_trace):
            self.main.logger.info("reply suppressed as send recap")
            return
        if await self._try_forward(event, reply, tool_trace, force=force):
            return
        if force is not True and not tool_trace and str(getattr(self.config, "reply_split", "paragraph")) == "paragraph":
            await self._send_split(event, reply)
            return
        await self._send_plain(event, reply)

    async def send_segments(self, platform: str, detail_type: str, target_id: str, segments,
                            from_tools: bool = False) -> None:
        adapter = self.sdk.adapter.get(platform)
        if adapter is None:
            self.main.logger.warning(texts.t("adapter_not_found", platform=platform))
            return
        target_type = detail_type if detail_type in ("group", "channel") else "user"
        try:
            sends = list(self.sdk.adapter.list_sends(platform))
        except Exception:
            sends = []
        if getattr(self.config, "forward_enabled", True) and from_tools:
            try:
                used = await utils.deliver_forward(
                    adapter,
                    target_type,
                    target_id,
                    [segment for _, segment in segments],
                    sends,
                )
                if used:
                    return
            except Exception as e:
                self.main.logger.warning(f"forward send failed, fallback: {e}")
        for delay, segment in segments:
            if delay > 0:
                await asyncio.sleep(delay)
            methods = ["Markdown", "Html", "Text"]
            methods = [m for m in methods if not sends or m in sends]
            if "Text" not in methods:
                methods.append("Text")
            sent = False
            for name in methods:
                content = utils.markdown_to_text(segment) if name == "Text" else segment
                try:
                    await getattr(adapter.Send.To(target_type, target_id), name)(content)
                    sent = True
                    break
                except Exception as e:
                    self.main.logger.warning(f"send via {name} failed: {e}")
            if not sent:
                self.main.logger.warning(f"send to {platform}/{target_type}/{target_id} failed")
                return
