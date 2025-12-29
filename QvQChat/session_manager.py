"""
会话管理器

负责管理会话相关的逻辑，包括：
- 会话标识管理
- 消息计数和回复时间跟踪
- 每小时回复限制
- 图片缓存
- 群内沉寂跟踪
"""
import time
from typing import Optional, List, Dict, Any


class SessionManager:
    """
    会话管理器

    管理会话状态、回复计数、图片缓存等。
    """

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("SessionManager")

        # 消息计数器和时间戳（用于窥屏模式）
        self._message_count: Dict[str, int] = {}
        self._last_reply_time: Dict[str, float] = {}

        # 每小时回复计数
        self._hourly_reply_count: Dict[str, int] = {}
        self._last_hour_reset: Dict[str, float] = {}

        # 群内沉寂跟踪
        self._group_silence: Dict[str, Dict[str, float]] = {}

        # 图片缓存
        self._image_cache: Dict[str, Dict[str, Any]] = {}
        self._IMAGE_CACHE_EXPIRE = 60  # 图片缓存过期时间（秒）

    def get_session_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取会话唯一标识

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 会话唯一标识
        """
        if group_id:
            return f"group:{group_id}"
        return f"user:{user_id}"

    def get_reply_count_key(self, user_id: str, group_id: Optional[str] = None) -> str:
        """
        获取回复计数器key

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            str: 计数器key
        """
        return self.get_session_key(user_id, group_id)

    def cache_images(self, user_id: str, image_urls: List[str], group_id: Optional[str] = None) -> None:
        """
        缓存图片URL

        Args:
            user_id: 用户ID
            image_urls: 图片URL列表
            group_id: 群ID（可选）
        """
        if not image_urls:
            return

        session_key = self.get_reply_count_key(user_id, group_id)
        self._image_cache[session_key] = {
            "image_urls": image_urls,
            "timestamp": time.time()
        }
        self.logger.debug(f"已缓存 {len(image_urls)} 张图片，过期时间 {self._IMAGE_CACHE_EXPIRE} 秒")

    def get_cached_images(self, user_id: str, group_id: Optional[str] = None) -> List[str]:
        """
        获取会话缓存的图片URL（自动清理过期缓存）

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            List[str]: 图片URL列表
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        current_time = time.time()

        # 清理过期的缓存
        self._image_cache = {
            k: v for k, v in self._image_cache.items()
            if current_time - v["timestamp"] < self._IMAGE_CACHE_EXPIRE
        }

        cached_data = self._image_cache.get(session_key)
        if cached_data:
            return cached_data["image_urls"]
        return []

    def clear_cached_images(self, user_id: str, group_id: Optional[str] = None) -> None:
        """
        清除已使用的图片缓存

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        if session_key in self._image_cache:
            del self._image_cache[session_key]
            self.logger.debug("已清除已使用的图片缓存")

    def increment_message_count(self, user_id: str, group_id: Optional[str] = None) -> int:
        """
        增加消息计数

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            int: 增加后的计数
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        count = self._message_count.get(session_key, 0) + 1
        self._message_count[session_key] = count
        return count

    def get_message_count(self, user_id: str, group_id: Optional[str] = None) -> int:
        """
        获取当前消息计数

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            int: 当前计数
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        return self._message_count.get(session_key, 0)

    def reset_message_count(self, user_id: str, group_id: Optional[str] = None) -> None:
        """
        重置消息计数

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        self._message_count[session_key] = 0

    def get_last_reply_time(self, user_id: str, group_id: Optional[str] = None) -> float:
        """
        获取上次回复时间

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            float: 上次回复时间戳
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        return self._last_reply_time.get(session_key, 0)

    def update_last_reply_time(self, user_id: str, group_id: Optional[str] = None) -> None:
        """
        更新回复时间

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        self._last_reply_time[session_key] = time.time()

    def update_group_silence(self, user_id: str, group_id: Optional[str] = None) -> None:
        """
        更新群内沉寂时间

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
        """
        if not group_id:
            return

        session_key = self.get_reply_count_key(user_id, group_id)
        self._group_silence[session_key] = {"last_message_time": time.time()}

    def get_group_silence_duration(self, user_id: str, group_id: Optional[str] = None) -> float:
        """
        获取群内沉寂持续时间（秒）

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            float: 沉寂持续时间（秒）
        """
        if not group_id:
            return 0

        session_key = self.get_reply_count_key(user_id, group_id)
        silence_data = self._group_silence.get(session_key, {})
        last_message_time = silence_data.get("last_message_time", 0)

        if last_message_time:
            return time.time() - last_message_time
        return 0

    def reset_and_check_hourly_limit(self, user_id: str, group_id: Optional[str] = None, max_replies_per_hour: int = 8) -> bool:
        """
        检查每小时回复限制（自动重置）

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）
            max_replies_per_hour: 每小时最大回复次数

        Returns:
            bool: 是否允许回复（True=允许，False=限制）
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        current_time = time.time()

        # 重置每小时计数器
        last_reset = self._last_hour_reset.get(session_key, 0)
        if current_time - last_reset > 3600:  # 1小时
            self._hourly_reply_count[session_key] = 0
            self._last_hour_reset[session_key] = current_time
            self.logger.debug(f"会话 {session_key} 每小时计数器已重置")

        # 检查每小时回复限制
        hourly_count = self._hourly_reply_count.get(session_key, 0)
        if hourly_count >= max_replies_per_hour:
            self.logger.debug(f"每小时回复次数已达上限 ({max_replies_per_hour})，跳过回复")
            return False

        return True

    def increment_hourly_count(self, user_id: str, group_id: Optional[str] = None) -> int:
        """
        增加每小时回复计数

        Args:
            user_id: 用户ID
            group_id: 群ID（可选）

        Returns:
            int: 增加后的计数
        """
        session_key = self.get_reply_count_key(user_id, group_id)
        count = self._hourly_reply_count.get(session_key, 0) + 1
        self._hourly_reply_count[session_key] = count
        return count
