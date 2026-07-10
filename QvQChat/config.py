"""
配置管理器

使用 sdk.config（而非旧版 sdk.env）管理基础设置。
"""

from typing import Any, Dict, List

from ErisPulse import sdk


class QvQConfig:
    """基础配置管理器"""

    def __init__(self):
        self.config = self._load_config()
        self.storage = sdk.storage
        self.logger = sdk.logger.get_child("QvQConfig")

    def _load_config(self) -> Dict[str, Any]:
        config = sdk.config.getConfig("QvQChat")
        if not config:
            default = self._get_default_config()
            sdk.config.setConfig("QvQChat", default)
            return default
        return config

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            "max_history_length": 20,
            "min_reply_interval": 10,
            "max_message_length": 1000,
            "rate_limit_tokens": 20000,
            "rate_limit_window": 60,
            "bot_nicknames": [],
            "bot_ids": [],
            "admin": {"admins": []},
            "stalker_mode": {
                "enabled": True,
                "default_probability": 0.03,
                "min_messages_between_replies": 15,
                "max_replies_per_hour": 8,
                "silence_threshold_minutes": 30,
                "question_probability": 0.6,
                "hot_topic_probability": 0.3,
                "sticker_emoji_probability": 0.15,
                "night_mode": {"enabled": True, "begin": 23, "end": 7},
            },
            "continue_conversation": {
                "enabled": True,
                "max_messages": 3,
                "max_duration": 120,
            },
            "knowledge_base": {
                "enabled": True,
                "max_context_tokens": 2000,
                "auto_search": True,
            },
            "mcp": {"enabled": True, "auto_inject": True},
            "stickers": {
                "enabled": True,
                "probability": 0.3,
                "max_per_session": 2,
            },
            "multi_agent": {"enabled": True},
            "humanize": {
                "typing_delay": True,
                "min_delay": 0.5,
                "max_delay": 5.0,
                "random_at_probability": 0.15,
                "multi_msg_enabled": True,
                "multi_msg_max": 3,
            },
            "voice": {
                "enabled": False,
                "api_url": "https://api.siliconflow.cn/v1/audio/speech",
                "api_key": "",
                "model": "FunAudioLLM/CosyVoice2-0.5B",
                "voice": "",
                "speed": 1.0,
                "gain": 0.0,
                "sample_rate": 44100,
                "platforms": ["qq", "onebot11"],
            },
            "users": {},
            "groups": {},
        }

    def get(self, key: str, default: Any = None) -> Any:
        # 直接从 sdk.config 读取最新值（避免内存缓存过期）
        return sdk.config.getConfig(f"QvQChat.{key}", default)

    def set(self, key: str, value: Any) -> None:
        sdk.config.setConfig(f"QvQChat.{key}", value)

    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        return self.storage.get(
            f"QvQChat.users.{user_id}", {"style": "友好", "preferences": {}}
        )

    def set_user_config(self, user_id: str, config: Dict[str, Any]) -> None:
        self.storage.set(f"QvQChat.users.{user_id}", config)

    def get_group_config(self, group_id: str) -> Dict[str, Any]:
        return self.storage.get(
            f"QvQChat.groups.{group_id}",
            {
                "system_prompt": "",
                "enable_memory": True,
                "memory_mode": "mixed",
                "enable_ai": True,
            },
        )

    def set_group_config(self, group_id: str, config: Dict[str, Any]) -> None:
        self.storage.set(f"QvQChat.groups.{group_id}", config)
        ids = self.storage.get("QvQChat._group_ids", [])
        if group_id not in ids:
            ids.append(group_id)
            self.storage.set("QvQChat._group_ids", ids)

    def list_all_groups(self) -> List[str]:
        return self.storage.get("QvQChat._group_ids", [])
