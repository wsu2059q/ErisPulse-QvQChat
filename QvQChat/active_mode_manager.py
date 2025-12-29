"""
活跃模式管理器

负责管理活跃模式（临时关闭窥屏模式，积极参与聊天）：
- 启用/禁用活跃模式
- 查询活跃模式状态
- 获取所有活跃会话列表
"""
import time
from typing import Optional, Dict, Any


class ActiveModeManager:
    """
    活跃模式管理器

    管理活跃模式，用于临时关闭窥屏模式，积极参与聊天。
    """

    def __init__(self, session_manager, logger):
        self.session_manager = session_manager
        self.logger = logger.get_child("ActiveModeManager")

        # 活跃模式（临时关闭窥屏模式）
        # key: 会话标识, value: {"end_time": float, "duration_minutes": int}
        self._active_mode: Dict[str, Dict[str, Any]] = {}

    def enable_active_mode(
        self,
        user_id: str,
        duration_minutes: int = 10,
        group_id: Optional[str] = None
    ) -> str:
        """
        启用活跃模式（临时关闭窥屏模式，积极参与聊天）

        Args:
            user_id: 用户ID
            duration_minutes: 持续时间（分钟），默认10分钟
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)
        end_time = time.time() + duration_minutes * 60

        self._active_mode[session_key] = {
            "end_time": end_time,
            "duration_minutes": duration_minutes
        }

        # 构建会话描述
        if group_id:
            session_desc = f"群聊 {group_id}"
        else:
            session_desc = f"私聊 {user_id}"

        self.logger.info(f"✓ {session_desc} 已启用活跃模式，持续 {duration_minutes} 分钟")
        return f"活跃模式已启用！我会积极参与聊天，{duration_minutes}分钟后自动切回窥屏模式~"

    def disable_active_mode(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        手动关闭活跃模式

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)

        if session_key in self._active_mode:
            del self._active_mode[session_key]

            # 构建会话描述
            if group_id:
                session_desc = f"群聊 {group_id}"
            else:
                session_desc = f"私聊 {user_id}"

            self.logger.info(f"✓ {session_desc} 已手动关闭活跃模式，切换回窥屏模式")
            return "活跃模式已关闭，切换回窥屏模式~"
        else:
            return "当前没有启用活跃模式哦"

    def get_active_mode_status(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取活跃模式状态

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 状态消息
        """
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)
        active_mode_data = self._active_mode.get(session_key)

        if active_mode_data:
            current_time = time.time()
            remaining_seconds = int(active_mode_data["end_time"] - current_time)

            if remaining_seconds > 0:
                remaining_minutes = remaining_seconds // 60
                remaining_seconds = remaining_seconds % 60
                return f"活跃模式生效中~ 还剩 {remaining_minutes}分{remaining_seconds}秒"
            else:
                # 已过期，清除缓存
                del self._active_mode[session_key]
                return "活跃模式已结束，当前是窥屏模式"

        return "当前是窥屏模式，使用 /活跃模式 命令可以临时切换到活跃模式"

    def is_active_mode(self, user_id: str, group_id: Optional[str] = None) -> bool:
        """
        检查是否处于活跃模式

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            bool: 是否处于活跃模式
        """
        session_key = self.session_manager.get_reply_count_key(user_id, group_id)
        active_mode_data = self._active_mode.get(session_key)

        if active_mode_data:
            current_time = time.time()
            if current_time < active_mode_data["end_time"]:
                remaining_minutes = int((active_mode_data["end_time"] - current_time) / 60)
                self.logger.debug(f"活跃模式生效中，剩余 {remaining_minutes} 分钟")
                return True
            else:
                # 活跃模式已过期，清除缓存
                del self._active_mode[session_key]
                self.logger.info("活跃模式已结束，自动切换回窥屏模式")

        return False

    def get_all_active_modes(self) -> str:
        """
        获取所有处于活跃模式的会话

        Returns:
            str: 所有活跃会话的状态信息
        """
        if not self._active_mode:
            return "当前没有会话处于活跃模式~"

        current_time = time.time()
        active_sessions = []

        for session_key, data in self._active_mode.items():
            remaining_seconds = int(data["end_time"] - current_time)

            if remaining_seconds > 0:
                # 解析会话key
                if session_key.startswith("group:"):
                    group_id = session_key[6:]  # 去掉 "group:" 前缀
                    desc = f"群聊 {group_id}"
                else:
                    user_id = session_key[5:] if session_key.startswith("user:") else session_key
                    desc = f"私聊 {user_id}"

                remaining_minutes = remaining_seconds // 60
                remaining_seconds = remaining_seconds % 60
                active_sessions.append(f"• {desc} - 剩余 {remaining_minutes}分{remaining_seconds}秒")

        if not active_sessions:
            return "当前没有会话处于活跃模式~"

        result = "【活跃模式会话列表】\n" + "\n".join(active_sessions)
        self.logger.info(f"查询活跃模式，共 {len(active_sessions)} 个会话处于活跃状态")
        return result
