from typing import Dict, Any


class QvQCommands:
    """
    QvQChat 命令处理器

    负责注册和处理 QvQChat 的所有命令。

    命令组划分：
    - 会话管理: 会话管理命令
    - 记忆管理: 记忆管理命令
    - 配置查看: 配置查看命令
    - 活跃模式: 活跃模式命令
    - AI控制: AI启用/禁用命令
    - 群管理: 群管理命令（仅管理员或群主）
    - 管理员: 管理员命令（需要管理员权限）
    """

    def __init__(self, sdk, memory, config, logger, main=None):
        self.sdk = sdk
        self.memory = memory
        self.config = config
        self.logger = logger.get_child("QvQCommands")
        self.main = main  # 保存 Main 实例引用

    def _is_admin(self, event: Dict[str, Any]) -> bool:
        """
        检查用户是否为管理员

        Args:
            event: 事件对象

        Returns:
            bool: 是否为管理员
        """
        user_id = str(event.get("user_id"))
        admins = self.config.get("admin.admins", [])
        return user_id in admins

    def _is_group_admin(self, event: Dict[str, Any]) -> bool:
        """
        检查用户是否为群管理员或系统管理员

        Args:
            event: 事件对象

        Returns:
            bool: 是否为群管理员或系统管理员
        """
        # 如果是系统管理员，直接通过
        if self._is_admin(event):
            return True

        group_id = event.get("group_id")
        if not group_id:
            return False

        user_id = event.get("user_id")
        platform = event.get("platform", "")

        # 根据不同平台使用不同策略
        if platform == "onebot11":
            # OneBot11: 从原始数据中获取 sender.role
            raw_event = event.get("onebot11_raw", {})
            sender = raw_event.get("sender", {})
            role = sender.get("role", "member")
            return role in ["admin", "owner"]
        elif platform == "yunhu":
            # Yunhu: 从原始数据中获取 sender.senderUserLevel
            raw_event = event.get("yunhu_raw", {})
            yunhu_event = raw_event.get("event", {})
            sender = yunhu_event.get("sender", {})
            user_level = sender.get("senderUserLevel", "member")
            # owner: 群主, administrator: 管理员
            return user_level in ["owner", "administrator"]
        else:
            # 其他平台: 目前仅支持系统管理员
            return False

    def register_all(self) -> None:
        """注册所有命令"""
        from ErisPulse.Core.Event import command

        # ==================== 会话管理命令 ====================

        @command("清除会话", aliases=["清空会话", "清空对话历史", "清除对话"], group="会话管理", help="清除对话历史")
        async def clear_session_cmd(event):
            """清除对话历史"""
            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None
            await self.memory.clear_session(user_id, group_id)
            await self._send_reply(event, "会话已清除（短期对话历史已清空）")

        @command("查看会话", aliases=["对话历史", "历史记录"], group="会话管理", help="查看对话历史")
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

        # ==================== 记忆管理命令 ====================

        @command("查看记忆", aliases=["我的记忆", "记忆列表"], group="记忆管理", help="查看长期记忆")
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

        @command("清除记忆", aliases=["清空记忆", "删除所有记忆"], group="记忆管理", help="清除所有长期记忆")
        async def clear_memory_cmd(event):
            """清除长期记忆"""
            user_id = str(event.get("user_id"))
            user_memory = await self.memory.get_user_memory(user_id)
            user_memory["long_term"] = []
            await self.memory.set_user_memory(user_id, user_memory)
            await self._send_reply(event, "记忆已清除（长期记忆已清空）")

        # ==================== 配置查看命令 ====================

        @command("群配置", aliases=["群设定", "群模式", "群提示词"], group="配置查看", help="查看群配置")
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

        @command("状态", aliases=["机器人状态", "系统状态"], group="配置查看", help="查看系统状态")
        async def status_cmd(event):
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

        # ==================== 活跃模式命令 ====================

        @command("活跃模式", aliases=["开启活跃", "活跃起来", "取消窥屏"], group="活跃模式", help="启用活跃模式（格式：活跃模式 10）")
        async def active_mode_cmd(event):
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None

            # 获取持续时间参数
            args = event.get("args", [])
            duration = 10  # 默认10分钟

            if args:
                try:
                    duration = int(args[0])
                    if duration < 1 or duration > 120:
                        await self._send_reply(event, "持续时间请在 1-120 分钟之间~")
                        return
                except ValueError:
                    await self._send_reply(event, "请输入有效的分钟数，例如：/活跃模式 10")
                    return

            result = self.main.enable_active_mode(user_id, duration, group_id)
            await self._send_reply(event, result)

        @command("关闭活跃", aliases=["结束活跃", "恢复窥屏"], group="活跃模式", help="关闭活跃模式")
        async def disable_active_mode_cmd(event):
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None

            result = self.main.disable_active_mode(user_id, group_id)
            await self._send_reply(event, result)

        @command("活跃状态", aliases=["当前模式", "是否活跃"], group="活跃模式", help="查看当前模式状态")
        async def active_status_cmd(event):
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None

            result = self.main.get_active_mode_status(user_id, group_id)
            await self._send_reply(event, result)

        # ==================== 管理员命令 ====================

        @command("admin.add", aliases=["添加管理员"], group="管理员", permission=lambda e: self._is_admin(e), help="添加管理员")
        async def add_admin_cmd(event):
            args = event.get("args", [])
            if not args:
                await self._send_reply(event, "请提供用户ID，例如：/admin.add 123456789")
                return

            target_user_id = args[0]
            admins = self.config.get("admin.admins", [])

            if target_user_id in admins:
                await self._send_reply(event, f"用户 {target_user_id} 已经是管理员了~")
                return

            admins.append(target_user_id)
            self.config.set("admin.admins", admins)
            await self._send_reply(event, f"已添加管理员：{target_user_id}")

        @command("admin.remove", aliases=["移除管理员"], group="管理员", permission=lambda e: self._is_admin(e), help="移除管理员")
        async def remove_admin_cmd(event):
            args = event.get("args", [])
            if not args:
                await self._send_reply(event, "请提供用户ID，例如：/admin.remove 123456789")
                return

            target_user_id = args[0]
            admins = self.config.get("admin.admins", [])

            if target_user_id not in admins:
                await self._send_reply(event, f"用户 {target_user_id} 不是管理员~")
                return

            admins.remove(target_user_id)
            self.config.set("admin.admins", admins)
            await self._send_reply(event, f"已移除管理员：{target_user_id}")

        @command("admin.list", aliases=["管理员列表", "查看管理员"], group="管理员", permission=lambda e: self._is_admin(e), help="查看管理员列表")
        async def list_admin_cmd(event):
            admins = self.config.get("admin.admins", [])

            if not admins:
                result = "当前没有设置管理员。"
            else:
                result_parts = ["【管理员列表】\n"]
                for i, admin_id in enumerate(admins, 1):
                    result_parts.append(f"{i}. {admin_id}")
                result = "\n".join(result_parts)

            await self._send_reply(event, result)

        @command("admin.reload", aliases=["重载配置", "重新加载配置"], group="管理员", permission=lambda e: self._is_admin(e), help="重新加载配置")
        async def reload_config_cmd(event):
            self.config.config = self.config._load_config()
            await self._send_reply(event, "配置已重新加载")

        @command("admin.clear_all_memory", aliases=["清空所有记忆", "清除全部记忆"], group="管理员", permission=lambda e: self._is_admin(e), help="清除所有用户记忆")
        async def clear_all_memory_cmd(event):
            """清除所有用户记忆"""
            from ErisPulse.Core.Event import command

            # 定义验证函数
            def validate_confirm(reply_event):
                text = ""
                for segment in reply_event.get("message", []):
                    if segment.get("type") == "text":
                        text = segment.get("data", {}).get("text", "").strip().lower()
                        break
                return text in ["是", "yes", "y", "确认"]

            # 定义回调函数
            async def handle_confirmation(reply_event):
                text = ""
                for segment in reply_event.get("message", []):
                    if segment.get("type") == "text":
                        text = segment.get("data", {}).get("text", "").strip().lower()
                        break

                if text in ["是", "yes", "y", "确认"]:
                    # 执行清除
                    from ErisPulse import sdk
                    await sdk.storage.delete_prefix("qvc:user:")
                    await self._send_reply(event, "所有用户记忆已清除")
                else:
                    await self._send_reply(event, "操作已取消。")

            # 等待用户确认
            await command.wait_reply(
                event,
                prompt="⚠️ 此操作将清除所有用户的长期记忆！\n请输入 '是' 确认，或输入其他内容取消",
                timeout=30.0,
                callback=handle_confirmation,
                validator=validate_confirm
            )
        
        @command("admin.clear_all_sessions", aliases=["清空所有会话", "清除全部会话"], group="管理员", permission=lambda e: self._is_admin(e), help="清除所有用户会话历史")
        async def clear_all_sessions_cmd(event):
            """清除所有用户会话历史"""
            from ErisPulse.Core.Event import command

            # 定义验证函数
            def validate_confirm(reply_event):
                text = ""
                for segment in reply_event.get("message", []):
                    if segment.get("type") == "text":
                        text = segment.get("data", {}).get("text", "").strip().lower()
                        break
                return text in ["是", "yes", "y", "确认"]

            # 定义回调函数
            async def handle_confirmation(reply_event):
                text = ""
                for segment in reply_event.get("message", []):
                    if segment.get("type") == "text":
                        text = segment.get("data", {}).get("text", "").strip().lower()
                        break

                if text in ["是", "yes", "y", "确认"]:
                    # 执行清除
                    from ErisPulse import sdk
                    await sdk.storage.delete_prefix("qvc:session:")
                    await self._send_reply(event, "所有用户会话历史已清除")
                else:
                    await self._send_reply(event, "操作已取消。")

            # 等待用户确认
            await command.wait_reply(
                event,
                prompt="⚠️ 此操作将清除所有用户的会话历史！\n请输入 '是' 确认，或输入其他内容取消",
                timeout=30.0,
                callback=handle_confirmation,
                validator=validate_confirm
            )

        @command("admin.clear_all_groups", aliases=["清空所有群聊", "清除全部群"], group="管理员", permission=lambda e: self._is_admin(e), help="清除所有群记忆和上下文")
        async def clear_all_groups_cmd(event):
            """清除所有群记忆和上下文"""
            from ErisPulse.Core.Event import command

            # 定义验证函数
            def validate_confirm(reply_event):
                text = ""
                for segment in reply_event.get("message", []):
                    if segment.get("type") == "text":
                        text = segment.get("data", {}).get("text", "").strip().lower()
                        break
                return text in ["是", "yes", "y", "确认"]

            # 定义回调函数
            async def handle_confirmation(reply_event):
                text = ""
                for segment in reply_event.get("message", []):
                    if segment.get("type") == "text":
                        text = segment.get("data", {}).get("text", "").strip().lower()
                        break

                if text in ["是", "yes", "y", "确认"]:
                    # 执行清除
                    from ErisPulse import sdk
                    await sdk.storage.delete_prefix("qvc:group:")
                    await self._send_reply(event, "所有群记忆和上下文已清除")
                else:
                    await self._send_reply(event, "操作已取消。")

            # 等待用户确认
            await command.wait_reply(
                event,
                prompt="⚠️ 此操作将清除所有群的记忆和上下文！\n请输入 '是' 确认，或输入其他内容取消",
                timeout=30.0,
                callback=handle_confirmation,
                validator=validate_confirm
            )

        # ==================== AI控制命令 ====================

        @command("启用AI", aliases=["开启AI", "激活AI"], group="AI控制", help="启用AI回复功能")
        async def enable_ai_cmd(event):
            """启用AI回复功能"""
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None

            result = self.main.enable_ai(user_id, group_id)
            await self._send_reply(event, result)

        @command("禁用AI", aliases=["关闭AI", "停用AI"], group="AI控制", help="禁用AI回复功能（命令仍可用）")
        async def disable_ai_cmd(event):
            """禁用AI回复功能"""
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None

            result = self.main.disable_ai(user_id, group_id)
            await self._send_reply(event, result)

        @command("AI状态", aliases=["查看AI", "AI开关"], group="AI控制", help="查看AI启用状态")
        async def ai_status_cmd(event):
            """查看AI启用状态"""
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            user_id = str(event.get("user_id"))
            group_id = str(event.get("group_id")) if event.get("detail_type") == "group" else None

            result = self.main.get_ai_status(user_id, group_id)
            await self._send_reply(event, result)

        # ==================== 群管理命令 ====================

        @command("清除群上下文", aliases=["清空群上下文", "删除群上下文"], group="群管理", help="清除群公共上下文（仅管理员或群主）")
        async def clear_group_context_cmd(event):
            """清除群公共上下文"""
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            group_id = str(event.get("group_id"))
            if not group_id:
                await self._send_reply(event, "此命令只能在群聊中使用")
                return

            # 检查权限（管理员或群主）
            if not self._is_group_admin(event):
                await self._send_reply(event, "只有管理员或群主可以使用此命令")
                return

            from ErisPulse import sdk
            key = f"qvc:group:{group_id}:memory"
            group_memory = sdk.storage.get(key, {})
            group_memory["shared_context"] = []
            sdk.storage.set(key, group_memory)

            await self._send_reply(event, f"群 {group_id} 的公共上下文已清除")

        @command("清除群记忆", aliases=["清空群记忆", "删除群记忆"], group="群管理", help="清除群记忆（仅管理员或群主）")
        async def clear_group_memory_cmd(event):
            """清除群记忆"""
            if not self.main:
                await self._send_reply(event, "功能不可用")
                return

            group_id = str(event.get("group_id"))
            if not group_id:
                await self._send_reply(event, "此命令只能在群聊中使用")
                return

            # 检查权限（管理员或群主）
            if not self._is_group_admin(event):
                await self._send_reply(event, "只有管理员或群主可以使用此命令")
                return

            from ErisPulse import sdk
            key = f"qvc:group:{group_id}:memory"
            sdk.storage.set(key, {
                "sender_memory": {},
                "shared_context": [],
                "last_updated": None
            })

            await self._send_reply(event, f"群 {group_id} 的记忆已清除")

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
