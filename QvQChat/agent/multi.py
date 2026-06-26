"""
多智能体管理器

支持创建多个具有不同人格、提示词和模型配置的 AI 智能体。
每个群/用户可以绑定不同的智能体，实现多角色对话。
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk


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

    def create_default_agent(self) -> Dict[str, Any]:
        """创建默认智能体"""
        default_prompt = self.config.get(
            "dialogue.system_prompt", "你是一个友好的AI助手。"
        )
        agent = {
            "id": "default",
            "name": "默认助手",
            "description": "使用全局 dialogue 配置的默认智能体",
            "system_prompt": default_prompt,
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
        """
        获取会话的有效系统提示词

        优先级：会话绑定智能体 > 默认智能体 > dialogue 全局配置

        Args:
            session_key: 会话标识

        Returns:
            系统提示词
        """
        agent = self.get_agent_for_session(session_key)
        prompt = agent.get("system_prompt", "")
        if not prompt:
            prompt = self.config.get("dialogue.system_prompt", "")
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
