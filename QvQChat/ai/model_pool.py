"""
模型池管理器

管理所有可用的 AI 模型，每个模型记录其 API 配置和能力标记。
行为管理器从模型池中选择模型分配给具体行为。
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from ErisPulse import sdk


class ModelPool:
    """
    模型池管理器

    管理所有 AI 模型，每个模型包含：
    - API 连接配置（base_url, api_key, model）
    - 能力标记（chat/vision/tools）
    - 默认参数（temperature, max_tokens）

    模型可被分配给多个行为，实现模型复用和冗余备用。
    """

    STORAGE_KEY = "QvQChat.models"

    # 能力常量
    CAP_CHAT = "chat"
    CAP_VISION = "vision"
    CAP_TOOLS = "tools"

    ALL_CAPABILITIES = [CAP_CHAT, CAP_VISION, CAP_TOOLS]

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger.get_child("ModelPool")
        self.storage = sdk.storage
        self._models: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        """从存储加载模型数据"""
        data = self.storage.get(self.STORAGE_KEY, {})
        self._models = data.get("models", {})

    def _save(self) -> None:
        """保存模型数据到存储"""
        self.storage.set(self.STORAGE_KEY, {"models": self._models})

    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有模型"""
        return list(self._models.values())

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取指定模型"""
        return self._models.get(model_id)

    def get_models_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """
        按能力筛选模型

        Args:
            capability: 能力名称 (chat/vision/tools)

        Returns:
            具备该能力的模型列表
        """
        return [
            m
            for m in self._models.values()
            if m.get("capabilities", {}).get(capability, False)
        ]

    def create_model(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新模型

        Args:
            data: 模型配置

        Returns:
            创建的模型数据
        """
        model_id = f"model_{uuid.uuid4().hex[:8]}"
        now = time.time()
        model = {
            "id": model_id,
            "name": data.get("name", "未命名模型"),
            "base_url": data.get("base_url", "https://api.openai.com/v1"),
            "api_key": data.get("api_key", ""),
            "model": data.get("model", ""),
            "capabilities": {
                self.CAP_CHAT: data.get("capabilities", {}).get(self.CAP_CHAT, True),
                self.CAP_VISION: data.get("capabilities", {}).get(
                    self.CAP_VISION, False
                ),
                self.CAP_TOOLS: data.get("capabilities", {}).get(self.CAP_TOOLS, False),
            },
            "temperature": data.get("temperature", 0.7),
            "max_tokens": data.get("max_tokens", 2000),
            "created_at": now,
            "updated_at": now,
        }
        self._models[model_id] = model
        self._save()
        self.logger.info(f"创建模型: {model['name']} ({model_id})")
        return model

    def update_model(
        self, model_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """更新模型配置"""
        model = self._models.get(model_id)
        if not model:
            return None

        for key in (
            "name",
            "base_url",
            "api_key",
            "model",
            "temperature",
            "max_tokens",
        ):
            if key in data:
                model[key] = data[key]

        if "capabilities" in data:
            for cap in self.ALL_CAPABILITIES:
                if cap in data["capabilities"]:
                    model["capabilities"][cap] = data["capabilities"][cap]

        model["updated_at"] = time.time()
        self._save()
        self.logger.info(f"更新模型: {model.get('name')} ({model_id})")
        return model

    def delete_model(self, model_id: str) -> bool:
        """删除模型"""
        if model_id not in self._models:
            return False
        name = self._models[model_id].get("name", model_id)
        del self._models[model_id]
        self._save()
        self.logger.info(f"删除模型: {name} ({model_id})")
        return True

    def get_client_config(self, model_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用于创建 AI 客户端的配置

        Args:
            model_id: 模型ID

        Returns:
            客户端配置字典（base_url, api_key, model, temperature, max_tokens）
        """
        model = self._models.get(model_id)
        if not model:
            return None
        return {
            "base_url": model.get("base_url", ""),
            "api_key": model.get("api_key", ""),
            "model": model.get("model", ""),
            "temperature": model.get("temperature", 0.7),
            "max_tokens": model.get("max_tokens", 2000),
        }

    def get_stats(self) -> Dict[str, Any]:
        """获取模型池统计"""
        total = len(self._models)
        by_cap = {}
        for cap in self.ALL_CAPABILITIES:
            by_cap[cap] = len(self.get_models_by_capability(cap))
        return {"total": total, "by_capability": by_cap}
