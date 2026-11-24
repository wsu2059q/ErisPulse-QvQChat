"""模型池门面：目录（catalog）× 分派（dispatch）两半的组装层。

目录半区在 catalog.py（ProviderCatalog：提供商 CRUD/全局链/presets/models.dev
富化/成本/能力/模型表解析），分派半区在 dispatch.py（DispatchGate：并发闸门/
熔断/负载分流/难度路由/任务分派/chat 链）。本类只做组装与兼容委托——
公开方法签名与属性面（含测试触碰的 _breaker/_provider_active/_ever_ok/gate）不变。
"""
from __future__ import annotations

from typing import Any

from .base import ChatRequest, ChatResponse, TaskSpec
from .catalog import ProviderCatalog
from .dispatch import DispatchGate
from .openai import OpenAIEngine


class ModelPool:
    def __init__(self, sdk: Any, config: Any):
        self.sdk = sdk
        self.config = config
        self.engine = OpenAIEngine()
        self.catalog = ProviderCatalog(self)
        self._dispatch = DispatchGate(self)

# ---- 兼容属性面：分派状态容器/闸门（测试与外部读这里）----

    @property
    def gate(self):
        return self._dispatch.gate

    @property
    def _breaker(self) -> dict:
        return self._dispatch._breaker

    @property
    def _provider_active(self) -> dict:
        return self._dispatch._provider_active

    @property
    def _ever_ok(self) -> set:
        return self._dispatch._ever_ok

    @property
    def routing_cache(self) -> dict:
        return self._dispatch.routing_cache

    @property
    def routing_stats(self) -> dict:
        return self._dispatch.routing_stats

    @property
    def routing_log(self):
        return self._dispatch.routing_log

    def _is_open(self, model_id: str) -> bool:
        return self._dispatch._is_open(model_id)

    def _record_fail(self, model_id: str) -> None:
        self._dispatch._record_fail(model_id)

    def _record_success(self, model_id: str) -> None:
        self._dispatch._record_success(model_id)

# ---- 目录半区委托（catalog.py）----

    def list_providers(self) -> list[dict]:
        return self.catalog.list_providers()

    def get_provider(self, provider_id: str) -> dict | None:
        return self.catalog.get_provider(provider_id)

    async def save_provider(self, data: dict) -> dict:
        return await self.catalog.save_provider(data)

    async def delete_provider(self, provider_id: str) -> bool:
        return await self.catalog.delete_provider(provider_id)

    def model_chain(self, providers: list[dict] | None = None) -> list[dict]:
        return self.catalog.model_chain(providers)

    async def save_chain(self, entries: list) -> list[dict]:
        return await self.catalog.save_chain(entries)

    async def amigrate_and_refresh(self) -> None:
        return await self.catalog.amigrate_and_refresh()

    def presets(self) -> list[dict]:
        return self.catalog.presets()

    def get_preset(self, preset_id: str) -> dict | None:
        return self.catalog.get_preset(preset_id)

    async def fetch_remote_models(self, provider: dict) -> list[dict]:
        return await self.catalog.fetch_remote_models(provider)

    async def detect_model(self, provider: dict, model_id: str) -> dict:
        return await self.catalog.detect_model(provider, model_id)

    async def enrich_models(self, provider: dict, models: list, catalog: dict | None = None) -> tuple[list, int]:
        return await self.catalog.enrich_models(provider, models, catalog)

    async def enrich_all_providers(self, force: bool = False) -> int:
        return await self.catalog.enrich_all_providers(force)

    def needs_enrichment(self, providers: list[dict] | None = None) -> bool:
        return self.catalog.needs_enrichment(providers)

    def model_costs(self) -> dict:
        return self.catalog.model_costs()

    def model_capabilities(self, model: dict) -> dict:
        return self.catalog.model_capabilities(model)

    def primary_capabilities(self) -> dict:
        return self.catalog.primary_capabilities()

    def list_models(self) -> list[dict]:
        return self.catalog.list_models()

    def resolve_model(self, model_id: str | None = None, needs: list | None = None) -> dict:
        return self.catalog.resolve_model(model_id, needs)

    def has_model(self, needs: list | None = None) -> bool:
        return self.catalog.has_model(needs)

    def capability_status(self, need: str) -> str:
        return self.catalog.capability_status(need)

# ---- 分派半区委托（dispatch.py）----

    def resolve_task_model(self, spec: TaskSpec) -> dict:
        return self._dispatch.resolve_task_model(spec)

    def breaker_state(self) -> list[dict]:
        return self._dispatch.breaker_state()

    def breaker_reset(self, model_id: str = "") -> int:
        return self._dispatch.breaker_reset(model_id)

    async def dispatch(
        self,
        spec: TaskSpec,
        request: ChatRequest,
        on_delta=None,
        on_reset=None,
        on_reasoning=None,
    ) -> ChatResponse:
        return await self._dispatch.dispatch(spec, request, on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning)

    async def chat(self, request: ChatRequest, on_delta=None, on_reset=None, on_reasoning=None, priority: int = 0) -> ChatResponse:
        return await self._dispatch.chat(request, on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning, priority=priority)

    async def describe_images(self, image_urls: list, prompt: str = "", on_error: str = "empty") -> list[str]:
        return await self._dispatch.describe_images(image_urls, prompt, on_error=on_error)

    async def test_model(self, model_id: str) -> ChatResponse:
        return await self._dispatch.test_model(model_id)

    @property
    def saturated(self) -> bool:
        return self._dispatch.saturated

    def background_blocked(self) -> bool:
        return self._dispatch.background_blocked()
