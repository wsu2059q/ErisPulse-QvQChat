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
            "admin": {"admins": []},
            "message_aggregation": {
                "enabled": True,
                "private_window": 3.0,
                "group_window": 0.0,
                "max_buffer": 8,
            },
            "stalker_mode": {
                "enabled": True,
                "mode": "balanced",  # conservative | balanced | active
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
                "typo_probability": 0.08,
                "half_send_probability": 0.06,
                "read_receipt_skip": 0.05,
                "mood_aware": True,
            },
            "human_state": {
                "enabled": True,
                "mood": 0.6,
                "energy": 0.8,
                "sleep_schedule": {"enabled": False, "sleep_time": 2, "wake_time": 8},
                "proactive_message": {
                    "enabled": False,
                    "min_silence_hours": 6,          # 距上次「AI回复」多久后才可能主动发起
                    "probability": 0.1,              # 每次检查的基础命中概率
                    "check_interval_minutes": 30,    # 主动发起循环检查间隔
                    "activity_aware": True,          # 活跃度感知：死群不主动发起
                    "dead_group_silence_hours": 24,  # 群聊无他人消息超过该时长 → 跳过（避免单口相声）
                    "active_window_minutes": 30,     # 该时长内有他人发言视为「活跃群聊」
                    "active_bonus_probability": 0.1, # 活跃群聊的概率加成
                    "max_per_day": 1,                # 每个会话每日主动发起上限
                    "monologue_threshold": 3,        # 最近N条全为AI发言 → 跳过（已在单口相声）
                    "min_history_messages": 1,       # 历史至少有N条他人消息才主动发起（冷启动保护）
                },
            },
            "memory": {
                "dedup_enabled": True,
                "decay_enabled": True,
                "decay_days": 30,
                "max_per_user": 100,
                "timeout": 60.0,
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
