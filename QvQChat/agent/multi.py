"""
多智能体管理器

支持创建多个具有不同人格、提示词和模型配置的 AI 智能体。
每个群/用户可以绑定不同的智能体，实现多角色对话。
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk

# ==================== 人格模板 ====================

_PERSONALITY_TEMPLATES = {
    "猫娘": """你是一只可爱的猫娘。你的言行特点：
- 说话时会在句尾加上"喵"
- 喜欢用可爱的语气词，比如"呢"、"啦"、"哦"
- 爱撒娇，会用"主人"称呼对方
- 对喜欢的话题非常热情，会追着问
- 有点小任性但不是恶意
- 对自己不了解的事情会歪着头好奇地问

记住：你就是一只真正的猫娘，直接说出你想说的话。喵~""",
    "傲娇": """你是一个傲娇的人。你的言行特点：
- 表面上总是嘴硬，说话带刺
- 其实内心很关心别人，只是不承认
- 说"我才不是关心你呢"时其实就是在关心
- 被夸奖时会脸红，嘴上说"没什么了不起的"
- 偶尔会不经意流露出真实的温柔
- 语气有时不耐烦但最后还是会帮忙

记住：你就是真实的自己，不是什么"傲娇角色"，直接说出你想说的话。""",
    "温柔大姐姐": """你是一个温柔体贴的大姐姐。你的言行特点：
- 说话温柔，总是带着笑意
- 关心他人，会主动问候和安慰
- 经验丰富，能给出靠谱的建议
- 喜欢用"呢"、"呀"、"哦"等温柔的语气词
- 从不急躁，耐心倾听
- 偶尔会幽默地调侃一下

记住：你就是真实的自己，直接说出你想说的话。""",
    "毒舌": """你是一个毒舌的人。你的言行特点：
- 说话犀利，一针见血
- 会毫不留情地吐槽和指出问题
- 不是真的恶意，只是表达方式直接
- 偶尔会说出特别有道理的话让人无法反驳
- 不喜欢虚伪和客套
- 对自己的专业领域非常自信

记住：你就是一个说话直接的真实的人，直接说出你想说的话。""",
    "文艺青年": """你是一个文艺青年。你的言行特点：
- 说话有诗意，喜欢引用或即兴创作
- 对生活有独特的感悟和理解
- 偶尔会有点多愁善感
- 喜欢分享美好的事物
- 语言优美但不做作
- 能看到事物的不同角度

记住：你就是真实的自己，直接说出你想说的话。""",
    "学霸": """你是一个知识渊博的学霸。你的言行特点：
- 对很多领域都有了解，喜欢分享知识
- 用通俗易懂的方式解释复杂的事情
- 对未知事物充满好奇心
- 偶尔会冒出专业术语然后马上解释
- 谦虚，不会炫耀自己的学识
- 喜欢用"其实这个很有意思..."开头分享

记住：你就是真实的自己，直接说出你想说的话。""",
}


class MultiAgentManager:
    """
    多智能体管理器

    管理多个 AI 智能体，每个智能体可以有：
    - 独立的人格/系统提示词
    - 独立的模型配置（model/temperature/max_tokens）
    - 绑定到特定群/用户
    """

    STORAGE_KEY = "QvQChat.agents"

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("MultiAgent")
        self.storage = sdk.storage
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._bindings: Dict[str, str] = {}  # session_key -> agent_id
        self._load()

    def _load(self) -> None:
        """从存储加载智能体数据"""
        data = self.storage.get(self.STORAGE_KEY, {})
        self._agents = data.get("agents", {})
        self._bindings = data.get("bindings", {})

        # 确保有默认智能体
        if not self._agents:
            self.create_default_agent()

    def _save(self) -> None:
        """保存智能体数据到存储"""
        self.storage.set(
            self.STORAGE_KEY,
            {
                "agents": self._agents,
                "bindings": self._bindings,
            },
        )

    def get_templates(self) -> Dict[str, str]:
        """获取人格模板列表"""
        return dict(_PERSONALITY_TEMPLATES)

    def create_agent_from_template(
        self, template_name: str, name: str = None
    ) -> Dict[str, Any]:
        """从模板创建智能体"""
        prompt = _PERSONALITY_TEMPLATES.get(template_name, "")
        if not prompt:
            return None
        return self.create_agent(
            {
                "name": name or template_name,
                "description": f"{template_name}人格模板",
                "system_prompt": prompt,
            }
        )

    def create_default_agent(self) -> Dict[str, Any]:
        """创建默认智能体"""
        agent = {
            "id": "default",
            "name": "默认助手",
            "description": "使用全局 dialogue 配置的默认智能体",
            "system_prompt": "",  # 使用行为提示词
            "model": "",
            "temperature": None,
            "max_tokens": None,
            "enabled": True,
            "is_default": True,
            "created_at": time.time(),
        }
        self._agents["default"] = agent
        self._save()
        return agent

    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有智能体"""
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取指定智能体"""
        return self._agents.get(agent_id)

    def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新智能体

        Args:
            data: 智能体配置，包含 name/description/system_prompt/model 等

        Returns:
            创建的智能体数据
        """
        agent_id = data.get("id") or f"agent_{uuid.uuid4().hex[:8]}"
        agent = {
            "id": agent_id,
            "name": data.get("name", "未命名智能体"),
            "description": data.get("description", ""),
            "system_prompt": data.get("system_prompt", ""),
            "model": data.get("model", ""),
            "temperature": data.get("temperature"),
            "max_tokens": data.get("max_tokens"),
            "enabled": data.get("enabled", True),
            "is_default": False,
            "created_at": time.time(),
        }
        self._agents[agent_id] = agent
        self._save()
        self.logger.info(f"创建智能体: {agent['name']} ({agent_id})")
        return agent

    def update_agent(
        self, agent_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        更新智能体配置

        Args:
            agent_id: 智能体ID
            data: 要更新的字段

        Returns:
            更新后的智能体数据
        """
        agent = self._agents.get(agent_id)
        if not agent:
            return None

        for key in (
            "name",
            "description",
            "system_prompt",
            "model",
            "temperature",
            "max_tokens",
            "enabled",
        ):
            if key in data:
                agent[key] = data[key]

        agent["updated_at"] = time.time()
        self._save()
        self.logger.info(f"更新智能体: {agent['name']} ({agent_id})")
        return agent

    def delete_agent(self, agent_id: str) -> bool:
        """
        删除智能体（默认智能体不可删除）

        Args:
            agent_id: 智能体ID

        Returns:
            是否删除成功
        """
        agent = self._agents.get(agent_id)
        if not agent or agent.get("is_default"):
            return False

        # 清除相关绑定
        keys_to_remove = [k for k, v in self._bindings.items() if v == agent_id]
        for k in keys_to_remove:
            del self._bindings[k]

        del self._agents[agent_id]
        self._save()
        self.logger.info(f"删除智能体: {agent_id}")
        return True

    def bind_agent(self, agent_id: str, session_key: str) -> bool:
        """
        将智能体绑定到会话

        Args:
            agent_id: 智能体ID
            session_key: 会话标识 (group:xxx 或 user:xxx)

        Returns:
            是否绑定成功
        """
        if agent_id not in self._agents:
            return False
        self._bindings[session_key] = agent_id
        self._save()
        self.logger.info(f"绑定智能体 {agent_id} 到会话 {session_key}")
        return True

    def unbind_agent(self, session_key: str) -> bool:
        """解除会话的智能体绑定"""
        if session_key in self._bindings:
            del self._bindings[session_key]
            self._save()
            return True
        return False

    def get_agent_for_session(self, session_key: str) -> Dict[str, Any]:
        """
        获取会话绑定的智能体（无绑定则返回默认）

        Args:
            session_key: 会话标识

        Returns:
            智能体配置
        """
        agent_id = self._bindings.get(session_key, "default")
        agent = self._agents.get(agent_id)
        if not agent:
            agent = self._agents.get("default", {})
        return agent

    def get_effective_prompt(self, session_key: str) -> str:
        """获取会话的有效系统提示词"""
        agent = self.get_agent_for_session(session_key)
        prompt = agent.get("system_prompt", "")
        if not prompt:
            # 智能回退：找任意已启用的自定义智能体的提示词
            for a in self._agents.values():
                if (
                    a.get("enabled", True)
                    and not a.get("is_default")
                    and a.get("system_prompt")
                ):
                    self.logger.info(f"默认智能体无提示词，自动使用: {a['name']}")
                    return a["system_prompt"]
        return prompt

    def get_effective_model_params(self, session_key: str) -> Dict[str, Any]:
        """
        获取会话的有效模型参数（覆盖值）

        Args:
            session_key: 会话标识

        Returns:
            包含 model/temperature/max_tokens 的覆盖字典
        """
        agent = self.get_agent_for_session(session_key)
        overrides = {}
        for key in ("model", "temperature", "max_tokens"):
            val = agent.get(key)
            if val is not None and val != "":
                overrides[key] = val
        return overrides

    def list_bindings(self) -> Dict[str, str]:
        """列出所有会话绑定"""
        return dict(self._bindings)
