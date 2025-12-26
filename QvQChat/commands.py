from typing import Dict, Any


class QvQCommands:
    """
    QvQChat 命令处理器
    
    负责注册和处理 QvQChat 的所有命令。
    """

    def __init__(self, sdk, memory, config, logger):
        self.sdk = sdk
        self.memory = memory
        self.config = config
        self.logger = logger.get_child("QvQCommands")

    def register_all(self) -> None:
        """注册所有命令"""
        from ErisPulse.Core.Event import command

        # ==================== 会话管理 ====================

        @command("清除会话", aliases=["清空会话", "清空对话历史", "清除对话"], help="清除对话历史")
        async def clear_session_cmd(event):
            """清除对话历史"""
            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None
            await self.memory.clear_session(user_id, group_id)
            await self._send_reply(event, "会话已清除（短期对话历史已清空）")

        @command("查看会话", aliases=["对话历史", "历史记录"], help="查看对话历史")
        async def view_history_cmd(event):
            """查看对话历史"""
            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None
            history = await self.memory.get_session_history(user_id, group_id)

            if not history:
                result = "当前没有对话历史。"
            else:
                result_parts = [f"【对话历史】（共{len(history)}条）\n"]
                for i, msg in enumerate(history[-20:], 1):  # 只显示最近20条
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")[:100]  # 限制每条消息100字符
                    if len(msg.get("content", "")) > 100:
                        content += "..."
                    role_name = {"user": "用户", "assistant": "AI"}.get(role, role)
                    result_parts.append(f"{i}. [{role_name}] {content}")
                result = "\n".join(result_parts)
            await self._send_reply(event, result)

        # ==================== 记忆管理 ====================

        @command("查看记忆", aliases=["我的记忆", "记忆列表"], help="查看长期记忆")
        async def view_memory_cmd(event):
            """查看长期记忆"""
            user_id = str(event.get("user_id"))
            user_memory = await self.memory.get_user_memory(user_id)
            long_term = user_memory.get("long_term", [])

            if not long_term:
                result = "当前没有任何长期记忆。"
            else:
                result_parts = [f"【长期记忆】（共{len(long_term)}条）\n"]
                for i, mem in enumerate(long_term[-30:], 1):  # 只显示最近30条
                    content = mem.get("content", "")
                    tags = mem.get("tags", [])
                    timestamp = mem.get("timestamp", "")
                    tag_str = f" [{', '.join(tags)}]" if tags else ""
                    time_str = f" | {timestamp.split('T')[0] if 'T' in timestamp else timestamp}" if timestamp else ""
                    result_parts.append(f"{i}. {content}{tag_str}{time_str}")
                result = "\n".join(result_parts)
            await self._send_reply(event, result)

        @command("删除记忆", aliases=["忘记记忆", "删除"], help="删除指定记忆（格式：删除记忆 1）")
        async def delete_memory_cmd(event):
            """删除指定记忆"""
            user_id = str(event.get("user_id"))

            # 获取索引参数
            args = event.get("args", [])
            if not args:
                result = self._get_memory_list(user_id, "请选择要删除的记忆编号。")
                await self._send_reply(event, result)
                return

            try:
                index = int(args[0]) - 1  # 用户输入从1开始，列表从0开始
                user_memory = await self.memory.get_user_memory(user_id)
                long_term = user_memory.get("long_term", [])

                if 0 <= index < len(long_term):
                    deleted = long_term.pop(index)
                    user_memory["long_term"] = long_term
                    await self.memory.set_user_memory(user_id, user_memory)
                    await self._send_reply(event, f"已删除记忆：{deleted.get('content', '')}")
                else:
                    await self._send_reply(event, f"无效的编号（共{len(long_term)}条记忆）")
            except (ValueError, IndexError):
                result = self._get_memory_list(user_id, "请输入有效的记忆编号。")
                await self._send_reply(event, result)

        @command("清除记忆", aliases=["清空记忆", "删除所有记忆"], help="清除所有长期记忆")
        async def clear_memory_cmd(event):
            """清除长期记忆"""
            user_id = str(event.get("user_id"))
            user_memory = await self.memory.get_user_memory(user_id)
            user_memory["long_term"] = []
            await self.memory.set_user_memory(user_id, user_memory)
            await self._send_reply(event, "记忆已清除（长期记忆已清空）")

        # ==================== 群配置 ====================

        @command("群配置", aliases=["群设定", "群模式", "群提示词"], help="查看群配置")
        async def group_config_cmd(event):
            """查看群配置"""
            group_id = str(event.get("group_id"))
            if not group_id:
                await self._send_reply(event, "此命令只能在群聊中使用")
                return

            group_config = self.config.get_group_config(group_id)
            mode_desc = self.config.get_memory_mode_description(group_config.get("memory_mode", "mixed"))
            result = f"【群配置】\n- 记忆模式：{mode_desc}\n- 群提示词：{group_config.get('system_prompt', '（使用默认）') or '（使用默认）'}"
            await self._send_reply(event, result)

        # ==================== 系统信息 ====================

        @command("状态", aliases=["机器人状态", "系统状态"], help="查看系统状态")
        async def status_cmd(event):
            """查看系统状态"""
            from .ai_client import QvQAIManager
            ai_manager = QvQAIManager(self.config, self.logger)

            result_parts = ["【系统状态】\n"]

            # AI配置状态
            result_parts.append("【AI配置】")
            ai_types = ["dialogue", "memory", "intent", "reply_judge", "vision"]
            for ai_type in ai_types:
                client = ai_manager.get_client(ai_type)
                status = "✓ 已配置" if client else "✗ 未配置"
                model = ai_manager.config.get(f"{ai_type}.model", "未知")
                result_parts.append(f"- {ai_type}: {status} ({model})")

            # 窥屏模式状态
            stalker = self.config.get("stalker_mode", {})
            result_parts.append("\n【窥屏模式】")
            result_parts.append(f"- 启用：{'是' if stalker.get('enabled', True) else '否'}")
            result_parts.append(f"- 每小时回复限制：{stalker.get('max_replies_per_hour', 8)}次")
            result_parts.append(f"- 默认回复概率：{stalker.get('default_probability', 0.03) * 100}%")

            # 记忆统计
            user_id = str(event.get("user_id"))
            user_memory = await self.memory.get_user_memory(user_id)
            long_term_count = len(user_memory.get("long_term", []))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None
            history = await self.memory.get_session_history(user_id, group_id)
            result_parts.append("【当前用户】")
            result_parts.append(f"- 长期记忆：{long_term_count}条")
            result_parts.append(f"- 会话历史：{len(history)}条")

            await self._send_reply(event, "\n".join(result_parts))

        self.logger.info("已注册所有 QvQChat 命令")

    async def _send_reply(self, event: Dict[str, Any], message: str) -> None:
        """
        发送回复消息

        Args:
            event: 事件对象
            message: 回复内容
        """
        platform = event.get("platform")
        detail_type = "group" if event.get("detail_type") == "group" else "user"
        target_id = event.get("group_id") or event.get("user_id")
        adapter_instance = getattr(self.sdk.adapter, platform)
        await adapter_instance.Send.To(detail_type, target_id).Text(message)

    async def _get_memory_list(self, user_id: str, header: str = "【长期记忆】") -> str:
        """
        获取记忆列表

        Args:
            user_id: 用户ID
            header: 列表标题

        Returns:
            str: 格式化的记忆列表
        """
        user_memory = await self.memory.get_user_memory(user_id)
        long_term = user_memory.get("long_term", [])

        if not long_term:
            return f"{header}\n当前没有任何长期记忆。"

        result_parts = [f"{header}（共{len(long_term)}条）\n"]
        for i, mem in enumerate(long_term, 1):
            content = mem.get("content", "")[:80]  # 限制80字符
            if len(mem.get("content", "")) > 80:
                content += "..."
            tags = mem.get("tags", [])
            timestamp = mem.get("timestamp", "")
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            time_str = f" | {timestamp.split('T')[0] if 'T' in timestamp else timestamp}" if timestamp else ""
            result_parts.append(f"{i}. {content}{tag_str}{time_str}")

        return "\n".join(result_parts)
