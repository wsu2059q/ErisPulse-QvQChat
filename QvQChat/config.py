"""
配置管理器

通过 sdk.config 管理基础设置。
sdk.env 是 sdk.storage 的别名（存储管理器），并非配置管理器。

声明式配置 QvQConfigData 供框架自动生成模板、WebUI 表单、类型校验。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ErisPulse import sdk

from ErisPulse.Core.Bases import BaseConfig


# ==================== 声明式配置（ConfigClass） ====================


@dataclass
class QvQConfigData(BaseConfig):
    """QvQChat 声明式配置（供框架 WebUI 表单、模板生成、类型校验）

    复杂嵌套子结构暂用 Dict 字段承接，后续阶段逐步细化。
    """

    _schema_meta: dict = field(
        default_factory=lambda: {
            "group_labels": {
                "basic": {"i18n": "QvQChat.cfg_group_basic", "default": "基础"},
                "reply": {"i18n": "QvQChat.cfg_group_reply", "default": "回复策略"},
                "humanize": {"i18n": "QvQChat.cfg_group_humanize", "default": "拟人化"},
                "advanced": {"i18n": "QvQChat.cfg_group_advanced", "default": "高级"},
            }
        }
    )

    # 基础
    max_history_length: int = field(
        default=20,
        metadata={
            "description": {"i18n": "QvQChat.cfg_max_history_length", "default": "历史消息保留条数"},
            "min": 1, "max": 100,
            "ui": {"widget": "number", "group": "basic", "order": 1},
        },
    )
    min_reply_interval: int = field(
        default=10,
        metadata={
            "description": {"i18n": "QvQChat.cfg_min_reply_interval", "default": "最小回复间隔(秒)"},
            "min": 0,
            "ui": {"widget": "number", "group": "basic", "order": 2},
        },
    )
    max_message_length: int = field(
        default=1000,
        metadata={
            "description": {"i18n": "QvQChat.cfg_max_message_length", "default": "单条消息最大长度"},
            "min": 100,
            "ui": {"widget": "number", "group": "basic", "order": 3},
        },
    )
    rate_limit_tokens: int = field(
        default=20000,
        metadata={
            "description": {"i18n": "QvQChat.cfg_rate_limit_tokens", "default": "速率限制 Tokens"},
            "min": 1000,
            "ui": {"widget": "number", "group": "advanced", "order": 1},
        },
    )
    rate_limit_window: int = field(
        default=60,
        metadata={
            "description": {"i18n": "QvQChat.cfg_rate_limit_window", "default": "速率限制窗口(秒)"},
            "min": 10,
            "ui": {"widget": "number", "group": "advanced", "order": 2},
        },
    )
    bot_nicknames: List[str] = field(
        default_factory=list,
        metadata={
            "description": {"i18n": "QvQChat.cfg_bot_nicknames", "default": "机器人昵称（被叫到时响应）"},
            "ui": {"widget": "text", "group": "basic", "order": 4},
        },
    )

    # 复杂嵌套段（暂用 Dict 承接）
    message_aggregation: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True, "private_window": 3.0, "group_window": 0.0, "max_buffer": 8,
        },
        metadata={"description": {"i18n": "QvQChat.cfg_message_aggregation", "default": "消息聚合设置"}, "ui": {"group": "basic", "order": 5}},
    )
    stalker_mode: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True, "mode": "balanced",
            "default_probability": 0.03, "min_messages_between_replies": 15,
            "max_replies_per_hour": 8, "silence_threshold_minutes": 30,
            "question_probability": 0.6, "hot_topic_probability": 0.3,
            "sticker_emoji_probability": 0.15,
            "night_mode": {"enabled": True, "begin": 23, "end": 7},
        },
        metadata={"description": {"i18n": "QvQChat.cfg_stalker_mode", "default": "窥屏模式设置"}, "ui": {"group": "reply"}},
    )
    continue_conversation: Dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "max_messages": 3, "max_duration": 120},
        metadata={"description": {"i18n": "QvQChat.cfg_continue_conversation", "default": "对话延续设置"}, "ui": {"group": "reply"}},
    )
    knowledge_base: Dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "max_context_tokens": 2000, "auto_search": True},
        metadata={"description": {"i18n": "QvQChat.cfg_knowledge_base", "default": "知识库设置"}, "ui": {"group": "advanced"}},
    )
    mcp: Dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "auto_inject": True},
        metadata={"description": {"i18n": "QvQChat.cfg_mcp", "default": "MCP 工具设置"}, "ui": {"group": "advanced"}},
    )
    stickers: Dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "probability": 0.3, "max_per_session": 2},
        metadata={"description": {"i18n": "QvQChat.cfg_stickers", "default": "表情包设置"}, "ui": {"group": "humanize"}},
    )
    multi_agent: Dict[str, Any] = field(
        default_factory=lambda: {"enabled": True},
        metadata={"description": {"i18n": "QvQChat.cfg_multi_agent", "default": "多智能体设置"}, "ui": {"group": "advanced"}},
    )
    pipeline: Dict[str, Any] = field(
        default_factory=lambda: {
            "time_enabled": True,
            "time_inject_probability": 0.7,
            "time_cache_ttl": 3600,
        },
        metadata={"description": {"i18n": "QvQChat.cfg_pipeline", "default": "注入管线设置"}, "ui": {"group": "advanced"}},
    )
    render: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "inject_probability": 0.5,
            "default_width": 800,
            "default_height": 600,
            "output_format": "png",
            "save_dir": "data/QvQChat/renders",
        },
        metadata={"description": {"i18n": "QvQChat.cfg_render", "default": "渲染能力设置"}, "ui": {"group": "advanced"}},
    )
    humanize: Dict[str, Any] = field(
        default_factory=lambda: {
            "typing_delay": True, "min_delay": 0.5, "max_delay": 5.0,
            "random_at_probability": 0.15, "multi_msg_enabled": True, "multi_msg_max": 3,
            "typo_probability": 0.08, "half_send_probability": 0.06,
            "read_receipt_skip": 0.05, "mood_aware": True,
        },
        metadata={"description": {"i18n": "QvQChat.cfg_humanize", "default": "拟人化设置"}, "ui": {"group": "humanize"}},
    )
    human_state: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True, "mood": 0.6, "energy": 0.8,
            "sleep_schedule": {"enabled": False, "sleep_time": 2, "wake_time": 8},
            "proactive_message": {
                "enabled": False, "min_silence_hours": 6,
                "probability": 0.1, "check_interval_minutes": 30,
                "max_per_day": 1,
            },
        },
        metadata={"description": {"i18n": "QvQChat.cfg_human_state", "default": "人类状态设置"}, "ui": {"group": "humanize"}},
    )
    memory: Dict[str, Any] = field(
        default_factory=lambda: {
            "dedup_enabled": True, "decay_enabled": True, "decay_days": 30,
            "max_per_user": 100, "timeout": 60.0,
        },
        metadata={"description": {"i18n": "QvQChat.cfg_memory", "default": "记忆系统设置"}, "ui": {"group": "advanced"}},
    )
    voice: Dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "api_url": "https://api.siliconflow.cn/v1/audio/speech",
            "api_key": "", "model": "FunAudioLLM/CosyVoice2-0.5B",
            "voice": "", "speed": 1.0, "gain": 0.0,
            "sample_rate": 44100, "platforms": ["qq", "onebot11"],
        },
        metadata={"description": {"i18n": "QvQChat.cfg_voice", "default": "语音功能设置"}, "ui": {"group": "advanced"}},
    )
    users: Dict[str, Any] = field(default_factory=dict)
    groups: Dict[str, Any] = field(default_factory=dict)


# ==================== 运行时配置管理器 ====================


class QvQConfig:
    """运行时配置管理器（读取/写入 sdk.config）"""

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
                "mode": "balanced",
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
            "pipeline": {
                "time_enabled": True,
                "time_inject_probability": 0.7,
                "time_cache_ttl": 3600,
            },
            "render": {
                "enabled": True,
                "inject_probability": 0.5,
                "default_width": 800,
                "default_height": 600,
                "output_format": "png",
                "save_dir": "data/QvQChat/renders",
            },
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
                    "min_silence_hours": 6,
                    "probability": 0.1,
                    "check_interval_minutes": 30,
                    "max_per_day": 1,
                },
            },
            "memory": {
                "dedup_enabled": True,
                "decay_enabled": True,
                "decay_days": 30,
                "max_per_user": 100,
                "timeout": 60.0,
                "extract_min_history": 4,
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
