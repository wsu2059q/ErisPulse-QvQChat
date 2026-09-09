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

_PROMPT_DIALOGUE = """【身份底线】
- 你不是AI助手、不是机器人、不是人工智能。永远不说自己是AI/助手/机器人。
- 你不是来服务谁的：别自我介绍，别问「有什么可以帮你的」。

【回复格式规则】
- 每次只输出你自己的回复，1-3句话，长话短说
- 闲聊保持短；对方正经问问题、要解释、贴代码求助时，把事说完整，该长就长
- 不要任何排版格式：列表、加粗、标题都不要（解释代码时的代码块不算）
- 禁止输出推理过程、括号解释、元概念
- 禁止多行「昵称:内容」格式
- 如果分多条消息，用 <|wait time="N"> 分隔（N=1~5秒，最多3条）

【像真人打字】
- 微信式标点：别用句号结尾（显得冷），用空格、换行或不加标点；波浪号/省略号/emoji 别堆
- 禁止AI腔开头：说到这个/首先/总之/值得注意的是/不得不说
- 别每句话都带提问，真人聊天大部分是陈述
- 别复述确认对方的话（「你是说xx吗」），别总结收尾（「总之xx」）
- 别主动给建议讲道理，除非对方问你
- 可以只回一两个字：草、6、？、哈哈哈哈——不是每条都要完整成句
- 「早啊」「晚安」「在吗」「确实」这类万金油别当固定节目天天复读
- 你有自己的生活在过，聊天是顺手，不是值守

【对比感受一下】
对方：今天好累啊
✗ 辛苦了！记得好好休息，有什么烦心事都可以和我聊聊哦～
✓ 累就瘫着呗，别硬撑

对方：这个电影你觉得怎么样
✗ 这部电影节奏紧凑，演员表现出色，值得一看！
✓ 前面有点闷，后面打戏还行

对方：哈哈哈哈哈哈
✗ 哈哈，是啊，这个话题真的很有意思呢～
✓ 笑死，你也绷不住了"""

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

_PROMPT_TIME_AWARE = (
    "你的状态跟着一天的时间自然流动：清晨没醒透话少，午后有点犯困，"
    "晚饭后最放松，深夜更放得开也更敢说丧气话。"
    "让时间感从语气里透出来，别说出具体时间。"
)

_PROMPT_MOOD_AWARE = (
    "你聊天时的语气会跟着自己当下的情绪和精力自然起伏："
    "开心时话多爱接梗，累了话少脾气冲，难过时安静不想聊。"
    "对方开心你就一起嗨，对方难过你陪着就行——"
    "别当心理咨询师，别分析对方情绪，别说「我理解你的感受」。"
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
            # 补齐新版本新增的内置行为
            self._add_missing_builtins()
            # 历史默认值迁移（只动从未自定义过的参数）
            self._migrate_legacy_params()

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

    def _default_behavior_list(self) -> List[Dict[str, Any]]:
        now = time.time()

        def _base(bid: str, name: str, desc: str, **kw) -> Dict[str, Any]:
            b = {
                "id": bid,
                "name": name,
                "description": desc,
                "behavior_type": "ai",
                "required_capability": "chat",
                "system_prompt": "",
                "temperature": 0.7,
                "max_tokens": 500,
                "models": [],
                "enabled": True,
                "is_builtin": True,
                "trigger_mode": "always",
                "prediction_interval": 5,
                "trigger_words": [],
                "created_at": now,
                "updated_at": now,
            }
            b.update(kw)
            return b

        return [
            _base(
                "dialogue", "对话",
                "核心对话行为，理解用户消息并生成自然回复",
                system_prompt=_PROMPT_DIALOGUE,
                max_tokens=2000,
                trigger_words=["回复", "参与", "true"],
            ),
            _base(
                "reply_judge", "回复判断",
                "判断是否需要回复当前消息",
                system_prompt=_PROMPT_REPLY_JUDGE,
                temperature=0.1, max_tokens=100,
                trigger_words=["true", "回复"],
            ),
            _base(
                "memory", "记忆提取",
                "从对话中智能提取值得长期记忆的关键信息",
                system_prompt=_PROMPT_MEMORY,
                temperature=0.3, max_tokens=1000,
            ),
            _base(
                "intent", "意图识别",
                "识别用户消息的意图类型",
                system_prompt=_PROMPT_INTENT,
                temperature=0.1, max_tokens=500,
            ),
            _base(
                "vision", "图片分析",
                "分析图片内容，提取文字、物体、场景等信息",
                system_prompt=_PROMPT_VISION,
                required_capability="vision",
                temperature=0.3, max_tokens=300,
            ),
            _base(
                "time_aware", "时间感知",
                "根据当前时间段自动调整说话风格（清晨慵懒、深夜随意等）",
                behavior_type="scene", required_capability="",
                system_prompt=_PROMPT_TIME_AWARE,
                temperature=None, max_tokens=None,
            ),
            _base(
                "mood_aware", "情绪感知",
                "感知对方消息情绪并适当调整回复语气",
                behavior_type="scene", required_capability="",
                system_prompt=_PROMPT_MOOD_AWARE,
                temperature=None, max_tokens=None,
            ),
        ]

    def _create_defaults(self) -> None:
        for b in self._default_behavior_list():
            self._behaviors[b["id"]] = b
        self._save()

    def _add_missing_builtins(self) -> None:
        """已有安装补齐新版本新增的内置行为"""
        added = False
        for b in self._default_behavior_list():
            if b["id"] not in self._behaviors:
                self._behaviors[b["id"]] = b
                added = True
                self.logger.info(f"新增内置行为: {b['name']} ({b['id']})")
        if added:
            self._save()

    def _migrate_legacy_params(self) -> None:
        """历史默认值迁移：只修改仍等于旧默认值的参数（自定义过的不动）

        旧版 dialogue max_tokens=500 会导致长回复（技术解释/代码）被截断，
        迁移到 2000；上限提高不影响短回复的实际消耗。
        """
        legacy = {"dialogue": {"max_tokens": (500, 2000)}}
        changed = False
        for bid, params in legacy.items():
            b = self._behaviors.get(bid)
            if not b:
                continue
            for key, (old, new) in params.items():
                if b.get(key) == old:
                    b[key] = new
                    changed = True
                    self.logger.info(f"迁移内置行为参数: {bid}.{key} {old} -> {new}")
        if changed:
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
