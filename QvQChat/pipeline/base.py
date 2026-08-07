"""
提示词注入管线基础设施

提供 Injector 基类、PromptContext、PromptPipeline。
每个注入器是独立的提示词片段生产者，按 priority 排序拼接。
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PromptContext:
    """注入器上下文（传递给每个 Injector.build）"""

    user_id: str = ""
    group_id: Optional[str] = None
    user_input: str = ""
    user_nickname: str = ""
    group_name: str = ""
    platform: str = ""
    is_mentioned: bool = False
    is_group: bool = False

    is_proactive: bool = False
    reply_gap: str = ""
    incoming_gap: str = ""


class Injector:
    """注入器基类

    子类需实现 build(ctx) -> str（同步或异步）。
    priority 越小越靠前。
    """

    id: str = "base"
    priority: int = 100
    enabled: bool = True

    def __init__(self, main_module: Any = None):
        self.main = main_module
        if main_module:
            self.config = main_module.config
            self.logger = main_module.logger

    async def build(self, ctx: PromptContext) -> str:
        raise NotImplementedError


class PromptPipeline:
    """提示词管线

    注册注入器，按 priority 排序依次调用 build，拼接结果。
    """

    def __init__(self, main_module: Any = None):
        self.main = main_module
        from ErisPulse import sdk
        self.logger = sdk.logger.get_child("Pipeline")
        self._injectors: Dict[str, Injector] = {}

    def register(self, injector: Injector) -> None:
        self._injectors[injector.id] = injector
        self.logger.debug(f"注册注入器: {injector.id} (priority={injector.priority})")

    def unregister(self, injector_id: str) -> None:
        self._injectors.pop(injector_id, None)

    def get_injector(self, injector_id: str) -> Optional[Injector]:
        return self._injectors.get(injector_id)

    def list_injectors(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": inj.id,
                "priority": inj.priority,
                "enabled": inj.enabled,
            }
            for inj in sorted(self._injectors.values(), key=lambda i: i.priority)
        ]

    async def build(self, ctx: PromptContext) -> str:
        """构建完整系统提示词"""
        parts = []
        active = []

        for inj in sorted(self._injectors.values(), key=lambda i: i.priority):
            if not inj.enabled:
                continue
            try:
                result = inj.build(ctx)
                if asyncio.iscoroutine(result):
                    result = await result
                if result and result.strip():
                    parts.append(result.strip())
                    active.append(inj.id)
            except Exception as e:
                self.logger.debug(f"注入器 {inj.id} 失败: {e}")

        if active:
            self.logger.info(f"注入器生效: {', '.join(active)}")

        return "\n\n".join(parts)
