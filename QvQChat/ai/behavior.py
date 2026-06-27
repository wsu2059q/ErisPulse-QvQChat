"""
行为管理器（中枢）

管理 AI 行为定义。每个行为代表一种 AI 能力（对话、记忆提取等），
从模型池分配模型，支持多模型冗余备用。

支持触发模式：
- always: 每条消息都经过回复判断
- prediction: 低token模式，每N条消息做一次预测词判断，匹配才进入对话
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk

# ==================== 默认提示词 ====================

_PROMPT_DIALOGUE = """【回复格式规则】
- 你不是AI助手、不是机器人、不是人工智能。永远不说自己是AI/助手/机器人。
- 每次只输出你自己的回复，1-3句话
- 口语化、自然、简短
- 不要用任何格式
- 禁止输出推理过程、括号解释、元概念
- 禁止多行「昵称:内容」格式
- 如果分多条消息，用 <|wait time="N"> 分隔（N=1~5秒，最多3条）"""

_PROMPT_REPLY_JUDGE = """判断是否需要回复这条消息。

必须回复：
1. 有人直接提问
2. 有人@你或叫你名字
3. 话题与你直接相关

不需要回复：
1. 纯打招呼
2. 表情符号、“哈哈”、“233”
3. 简单的“嗯”、“好”、“OK”
4. 与你无关的闲聊

只回复true或false。"""

_PROMPT_MEMORY = "你是一个智能记忆提取助手，负责从对话中提取值得长期记忆的关键信息。"

_PROMPT_INTENT = """你是一个意图识别助手。识别用户意图时，请仔细分析消息内容和上下文。

意图分类：
1. dialogue - 普通对话交流（提问、聊天、日常交流）
2. memory_add - 用户主动要求记住某些信息（明确说"记住"、"记下来"）
3. memory_delete - 用户主动要求删除记忆（明确说"忘记"、"删除"）

判断规则：
- 默认所有普通交流归类为dialogue
- 只有用户明确说"记住"、"记下来"才归类为memory_add
- 只有用户明确说"忘记"、"删除"才归类为memory_delete

只返回意图类型名称（如dialogue），不要包含其他内容。"""

_PROMPT_VISION = "你是一个图片分析助手。请详细描述图片的内容，包括图片中的物体、文字、场景、人物表情等。"

# ==================== 默认场景行为提示词 ====================

_PROMPT_TIME_AWARE = "你会根据当前时间段调整说话风格。现在是%s。"

_PROMPT_MOOD_AWARE = (
    "你会感知对方消息中的情绪并适当调整回复语气。"
    "如果对方开心你也轻松愉快，如果对方难过你会安慰。"
)


class BehaviorManager:
    """
    行为管理器（中枢）

    管理所有 AI 行为，每个行为包含：
    - 名称、描述
    - 系统提示词
    - 参数覆盖（temperature, max_tokens）
    - 分配的模型列表（按优先级，支持冗余备用）
    - 所需能力标记
    - 触发模式（always / prediction）
    """

    STORAGE_KEY = "QvQChat.behaviors"

    # 核心AI行为（需要模型分配）
    BUILTIN_AI = ["dialogue", "reply_judge", "memory", "intent", "vision"]
    # 内置场景行为（不需要模型，提供上下文提示）
    BUILTIN_SCENE = ["time_aware", "mood_aware"]
    BUILTIN_BEHAVIORS = BUILTIN_AI + BUILTIN_SCENE

    def __init__(self, config, model_pool, logger):
        self.config = config
        self.model_pool = model_pool
        self.logger = logger.get_child("Behavior")
        self.storage = sdk.storage
        self._behaviors: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        data = self.storage.get(self.STORAGE_KEY, {})
        self._behaviors = data.get("behaviors", {})
        if not self._behaviors:
            self._create_defaults()
        else:
            # 升级旧版提示词到最新版本
            self._upgrade_prompts()

    def _save(self) -> None:
        self.storage.set(self.STORAGE_KEY, {"behaviors": self._behaviors})

    def _upgrade_prompts(self) -> bool:
        """升级内置行为到最新代码定义（提示词+类型+能力）"""
        builtin_defaults = {
            "dialogue": {
                "system_prompt": _PROMPT_DIALOGUE,
                "behavior_type": "ai",
                "required_capability": "chat",
            },
            "reply_judge": {
                "system_prompt": _PROMPT_REPLY_JUDGE,
                "behavior_type": "ai",
                "required_capability": "chat",
            },
            "memory": {
                "system_prompt": _PROMPT_MEMORY,
                "behavior_type": "ai",
                "required_capability": "chat",
            },
            "intent": {
                "system_prompt": _PROMPT_INTENT,
                "behavior_type": "ai",
                "required_capability": "chat",
            },
            "vision": {
                "system_prompt": _PROMPT_VISION,
                "behavior_type": "ai",
                "required_capability": "vision",
            },
            "time_aware": {
                "system_prompt": _PROMPT_TIME_AWARE,
                "behavior_type": "scene",
                "required_capability": "",
            },
            "mood_aware": {
                "system_prompt": _PROMPT_MOOD_AWARE,
                "behavior_type": "scene",
                "required_capability": "",
            },
        }
        changed = False
        for bid, defaults in builtin_defaults.items():
            b = self._behaviors.get(bid)
            if not b:
                continue
            for key, val in defaults.items():
                if b.get(key) != val:
                    b[key] = val
                    changed = True
            if changed:
                b["updated_at"] = time.time()
            if changed:
                self.logger.info(f"升级内置行为: {bid}")
        if changed:
            self._save()
        return changed

    def _create_defaults(self) -> None:
        now = time.time()
        defaults = [
            {
                "id": "dialogue",
                "name": "对话",
                "description": "核心对话行为，理解用户消息并生成自然回复",
                "behavior_type": "ai",
                "required_capability": "chat",
                "system_prompt": _PROMPT_DIALOGUE,
                "temperature": 0.7,
                "max_tokens": 500,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": ["回复", "参与", "true"],
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "reply_judge",
                "name": "回复判断",
                "description": "判断是否需要回复当前消息",
                "behavior_type": "ai",
                "required_capability": "chat",
                "system_prompt": _PROMPT_REPLY_JUDGE,
                "temperature": 0.1,
                "max_tokens": 100,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": ["true", "回复"],
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "memory",
                "name": "记忆提取",
                "description": "从对话中智能提取值得长期记忆的关键信息",
                "behavior_type": "ai",
                "required_capability": "chat",
                "system_prompt": _PROMPT_MEMORY,
                "temperature": 0.3,
                "max_tokens": 1000,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": [],
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "intent",
                "name": "意图识别",
                "description": "识别用户消息的意图类型",
                "behavior_type": "ai",
                "required_capability": "chat",
                "system_prompt": _PROMPT_INTENT,
                "temperature": 0.1,
                "max_tokens": 500,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": [],
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "vision",
                "name": "图片分析",
                "description": "分析图片内容，提取文字、物体、场景等信息",
                "behavior_type": "ai",
                "required_capability": "vision",
                "system_prompt": _PROMPT_VISION,
                "temperature": 0.3,
                "max_tokens": 300,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": [],
                "created_at": now,
                "updated_at": now,
            },
        ]
        # 场景行为（不需要模型分配）
        scene_defaults = [
            {
                "id": "time_aware",
                "name": "时间感知",
                "description": "根据当前时间段自动调整说话风格（清晨慵懒、深夜随意等）",
                "behavior_type": "scene",
                "required_capability": "",
                "system_prompt": _PROMPT_TIME_AWARE,
                "temperature": None,
                "max_tokens": None,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": [],
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "mood_aware",
                "name": "情绪感知",
                "description": "感知对方消息情绪并适当调整回复语气",
                "behavior_type": "scene",
                "required_capability": "",
                "system_prompt": _PROMPT_MOOD_AWARE,
                "temperature": None,
                "max_tokens": None,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": [],
                "created_at": now,
                "updated_at": now,
            },
        ]
        for b in defaults + scene_defaults:
            self._behaviors[b["id"]] = b
        self._save()

    def list_behaviors(self) -> List[Dict[str, Any]]:
        return list(self._behaviors.values())

    def get_behavior(self, behavior_id: str) -> Optional[Dict[str, Any]]:
        return self._behaviors.get(behavior_id)

    def create_behavior(self, data: Dict[str, Any]) -> Dict[str, Any]:
        behavior_id = data.get("id") or f"behavior_{uuid.uuid4().hex[:8]}"
        now = time.time()
        behavior = {
            "id": behavior_id,
            "name": data.get("name", "未命名行为"),
            "description": data.get("description", ""),
            "behavior_type": data.get("behavior_type", "ai"),
            "required_capability": data.get("required_capability", "chat"),
            "system_prompt": data.get("system_prompt", ""),
            "temperature": data.get("temperature"),
            "max_tokens": data.get("max_tokens"),
            "models": data.get("models", []),
            "enabled": data.get("enabled", True),
            "is_builtin": False,
            "trigger_mode": data.get("trigger_mode", "always"),
            "prediction_interval": data.get("prediction_interval", 5),
            "trigger_words": data.get("trigger_words", []),
            "response_template": data.get("response_template", ""),
            "trigger_probability": data.get("trigger_probability", 0),
            "created_at": now,
            "updated_at": now,
        }
        self._behaviors[behavior_id] = behavior
        self._save()
        self.logger.info(f"创建行为: {behavior['name']} ({behavior_id})")
        return behavior

    def update_behavior(
        self, behavior_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        behavior = self._behaviors.get(behavior_id)
        if not behavior:
            return None
        for key in (
            "name",
            "description",
            "behavior_type",
            "required_capability",
            "system_prompt",
            "temperature",
            "max_tokens",
            "models",
            "enabled",
            "trigger_mode",
            "prediction_interval",
            "trigger_words",
            "response_template",
            "trigger_probability",
        ):
            if key in data:
                behavior[key] = data[key]
        behavior["updated_at"] = time.time()
        self._save()
        self.logger.info(f"更新行为: {behavior.get('name')} ({behavior_id})")
        return behavior

    def delete_behavior(self, behavior_id: str) -> bool:
        behavior = self._behaviors.get(behavior_id)
        if not behavior or behavior.get("is_builtin"):
            return False
        del self._behaviors[behavior_id]
        self._save()
        self.logger.info(f"删除行为: {behavior_id}")
        return True

    def get_behavior_models(self, behavior_id: str) -> List[Dict[str, Any]]:
        behavior = self._behaviors.get(behavior_id)
        if not behavior:
            return []
        models = []
        for mid in behavior.get("models", []):
            config = self.model_pool.get_client_config(mid)
            if config:
                model = self.model_pool.get_model(mid)
                config["_model_id"] = mid
                config["_model_name"] = (
                    model.get("name", mid) if isinstance(model, dict) else mid
                )
                models.append(config)
        return models

    def get_behavior_prompt(self, behavior_id: str) -> str:
        behavior = self._behaviors.get(behavior_id)
        return behavior.get("system_prompt", "") if behavior else ""

    def get_behavior_params(self, behavior_id: str) -> Dict[str, Any]:
        behavior = self._behaviors.get(behavior_id)
        if not behavior:
            return {}
        params = {}
        if behavior.get("temperature") is not None:
            params["temperature"] = behavior["temperature"]
        if behavior.get("max_tokens") is not None:
            params["max_tokens"] = behavior["max_tokens"]
        return params

    def is_behavior_available(self, behavior_id: str) -> bool:
        behavior = self._behaviors.get(behavior_id)
        if not behavior or not behavior.get("enabled", True):
            return False
        # 场景行为不需要模型分配
        if behavior.get("behavior_type") == "scene":
            return True
        return len(behavior.get("models", [])) > 0

    def get_trigger_mode(self, behavior_id: str) -> str:
        behavior = self._behaviors.get(behavior_id)
        return behavior.get("trigger_mode", "always") if behavior else "always"

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._behaviors)
        enabled = sum(1 for b in self._behaviors.values() if b.get("enabled", True))
        with_models = sum(1 for b in self._behaviors.values() if b.get("models"))
        builtin = sum(1 for b in self._behaviors.values() if b.get("is_builtin"))
        return {
            "total": total,
            "enabled": enabled,
            "with_models": with_models,
            "builtin": builtin,
            "custom": total - builtin,
        }

    def auto_assign_models(self) -> None:
        if not self.model_pool.list_models():
            return
        changed = False
        for bid in self.BUILTIN_AI:
            behavior = self._behaviors.get(bid)
            if not behavior or behavior.get("models"):
                continue
            if behavior.get("behavior_type") != "ai":
                continue
            cap = behavior.get("required_capability", "chat")
            compatible = self.model_pool.get_models_by_capability(cap)
            if compatible:
                behavior["models"] = [compatible[0]["id"]]
                changed = True
                self.logger.info(f"自动分配模型: {bid} -> {compatible[0]['name']}")
        if changed:
            self._save()
