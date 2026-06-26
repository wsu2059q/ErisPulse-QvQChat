"""
配置管理器

只管理基础设置，AI 模型和行为配置由各自的子系统管理。
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
        config = sdk.env.getConfig("QvQChat")
        if not config:
            default = self._get_default_config()
            sdk.env.setConfig("QvQChat", default)
            return default
        return config

    def _get_default_config(self) -> Dict[str, Any]:
        return {
            "max_history_length": 20,
            "min_reply_interval": 10,
            "max_message_length": 1000,
            "rate_limit_tokens": 20000,
            "rate_limit_window": 60,
            "ignore_command_messages": True,
            "bot_nicknames": [],
            "bot_ids": [],
            "admin": {"admins": []},
            "stalker_mode": {
                "enabled": True,
                "default_probability": 0.03,
                "mention_probability": 0.8,
                "keyword_probability": 0.5,
                "min_messages_between_replies": 15,
                "max_replies_per_hour": 8,
                "silence_threshold_minutes": 30,
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
            "multi_agent": {"enabled": True},
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
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        sdk.env.setConfig("QvQChat", self.config)

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
