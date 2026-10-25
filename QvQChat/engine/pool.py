from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

from .. import texts, utils
from ..providers import PROVIDER_PRESETS, get_preset
from .base import ChatRequest, ChatResponse, EngineError, TaskSpec
from .openai import OpenAIEngine
from .router import classify

POOL_KEY = "QvQChat:providers"
LEGACY_KEY = "QvQChat:models"
MODELS_DEV_URL = "https://models.dev/api.json"
MODELS_DEV_CACHE_KEY = "QvQChat:modelsdev"
MODELS_DEV_TTL = 86400


class ModelPool:
    BREAKER_THRESHOLD = 3
    BREAKER_BASE_COOLDOWN = 60.0
    BREAKER_MAX_COOLDOWN = 600.0

    ROUTING_LOG_MAX = 50

    def __init__(self, sdk: Any, config: Any):
        self.sdk = sdk
        self.config = config
        self.engine = OpenAIEngine()
        self._migrate_legacy()
# 模型熔断状态：model_id -> {"fails": 连续失败次数, "until": 冷却截止时间戳}
        self._breaker: dict[str, dict] = {}
# 难度感知路由（默认关闭）：chat_key -> (prefer, reason, ts)
        self.routing_cache: dict[str, tuple] = {}
# 路由统计与最近决策回看（{prefer: 计数} / deque[{chat_key, prefer, reason, ts}]）
        self.routing_stats: dict[str, int] = {}
        self.routing_log: deque = deque(maxlen=self.ROUTING_LOG_MAX)

    def breaker_state(self) -> list[dict]:
        import time as _time

        now = _time.time()
        state = []
        for model_id, info in self.__dict__.setdefault("_breaker", {}).items():
            until = float(info.get("until") or 0)
            if until <= now:
                continue
            state.append({"model": model_id, "fails": info.get("fails", 0), "cooldown_left": int(until - now)})
        return state

    def _record_fail(self, model_id: str) -> None:
        import time as _time

        info = self.__dict__.setdefault("_breaker", {}).setdefault(model_id, {"fails": 0, "until": 0})
        info["fails"] = int(info.get("fails", 0)) + 1
        if info["fails"] >= self.BREAKER_THRESHOLD:
            cooldown = min(self.BREAKER_BASE_COOLDOWN * (2 ** (info["fails"] - self.BREAKER_THRESHOLD)), self.BREAKER_MAX_COOLDOWN)
            info["until"] = _time.time() + cooldown

    def _record_success(self, model_id: str) -> None:
        self.__dict__.setdefault("_breaker", {}).pop(model_id, None)

    def _is_open(self, model_id: str) -> bool:
        import time as _time

        info = self.__dict__.setdefault("_breaker", {}).get(model_id)
        return bool(info and float(info.get("until") or 0) > _time.time())

    def _migrate_legacy(self) -> None:
        try:
            legacy = self.sdk.storage.get(LEGACY_KEY, [])
            if isinstance(legacy, list) and legacy and not self.list_providers():
                models = [m for m in legacy if isinstance(m, dict)]
                base_url = models[0].get("base_url", "") if models else ""
                api_key = models[0].get("api_key", "") if models else ""
                provider = {
                    "id": "custom",
                    "name": "Custom",
                    "base_url": base_url or "https://api.openai.com/v1",
                    "api_key": api_key,
                    "models": [
                        {
                            "id": m.get("model", ""),
                            "enabled": True,
                            "temperature": m.get("temperature"),
                            "max_tokens": m.get("max_tokens"),
                        }
                        for m in models
                    ],
                }
                self.save_provider(provider)
        except Exception:
            pass


    def list_providers(self) -> list[dict]:
        providers = self.sdk.storage.get(POOL_KEY, [])
        return providers if isinstance(providers, list) else []

    def get_provider(self, provider_id: str) -> dict | None:
        for provider in self.list_providers():
            if provider.get("id") == provider_id:
                return provider
        return None

    def save_provider(self, data: dict) -> dict:
        providers = self.list_providers()
        provider_id = str(data.get("id") or utils.new_id())
        entry = {
            "id": provider_id,
            "name": str(data.get("name") or provider_id),
            "base_url": str(data.get("base_url") or "").rstrip("/"),
            "api_key": str(data.get("api_key") or ""),
            "models": data.get("models") if isinstance(data.get("models"), list) else [],
        }
        if not entry["base_url"]:
            raise EngineError(texts.t("provider_base_url_required"))
        for index, existing in enumerate(providers):
            if existing.get("id") == provider_id:
                if not entry["api_key"]:
                    entry["api_key"] = str(existing.get("api_key") or "")
                if "models" not in data:
                    entry["models"] = existing.get("models") or []
                providers[index] = {**existing, **entry}
                break
        else:
            providers.append(entry)
        self.sdk.storage.set(POOL_KEY, providers)
        return entry

    def delete_provider(self, provider_id: str) -> bool:
        providers = self.list_providers()
        remaining = [p for p in providers if p.get("id") != provider_id]
        if len(remaining) == len(providers):
            return False
        self.sdk.storage.set(POOL_KEY, remaining)
        return True

    def presets(self) -> list[dict]:
        return [dict(p) for p in PROVIDER_PRESETS]

    def get_preset(self, preset_id: str) -> dict | None:
        return get_preset(preset_id)


    async def _models_dev_catalog(self) -> dict:
        cached = self.sdk.storage.get(MODELS_DEV_CACHE_KEY, None)
        if isinstance(cached, dict) and time.time() - cached.get("ts", 0) < MODELS_DEV_TTL:
            data = cached.get("data")
            if isinstance(data, dict):
                return data
        try:
            resp = await self.sdk.client.get(MODELS_DEV_URL, timeout=30)
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, dict):
                    self.sdk.storage.set(MODELS_DEV_CACHE_KEY, {"ts": time.time(), "data": data})
                    return data
        except Exception:
            pass
        return {}

    @staticmethod
    def _models_dev_lookup(catalog: dict, base_url: str, model_id: str) -> dict:
        meta: dict = {}
        for provider in catalog.values():
            if not isinstance(provider, dict):
                continue
            models = provider.get("models")
            if not isinstance(models, dict):
                continue
            entry = models.get(model_id)
            if isinstance(entry, dict):
                meta = entry
                break
        info = {
            "context_length": meta.get("context_length"),
            "reasoning": bool(meta.get("reasoning")) if meta.get("reasoning") is not None else None,
            "vision": None,
            "tool_call": None,
        }
        cost = meta.get("cost")
        if isinstance(cost, dict):
            info["cost"] = {
                "input": cost.get("input"),
                "output": cost.get("output"),
            }
        modalities = meta.get("modalities")
        if isinstance(modalities, dict):
            inputs = modalities.get("input") or []
            info["vision"] = "image" in inputs
        elif meta.get("vision") is not None:
            info["vision"] = bool(meta.get("vision"))
        tools = meta.get("tool_call")
        if tools is not None:
            info["tool_call"] = bool(tools)
        return info

    async def fetch_remote_models(self, provider: dict) -> list[dict]:
        base_url = str(provider.get("base_url") or "").rstrip("/")
        if not base_url:
            raise EngineError(texts.t("provider_base_url_required"))
        api_key = str(provider.get("api_key") or "")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            resp = await self.sdk.client.get(f"{base_url}/models", headers=headers, timeout=30)
        except Exception as e:
            raise EngineError(texts.t("fetch_models_failed", error=str(e))) from e
        if resp.status != 200:
            raise EngineError(texts.t("fetch_models_failed", error=f"HTTP {resp.status}"))
        data = await resp.json()
        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        catalog = await self._models_dev_catalog()
        result: list[dict] = []
        for item in items:
            model_id = item.get("id") if isinstance(item, dict) else str(item or "")
            if not model_id:
                continue
            entry = {
                "id": model_id,
                "context_length": item.get("context_length") if isinstance(item, dict) else None,
                "vision": None,
                "files": None,
                "video": None,
                "reasoning": None,
                "tool_call": None,
            }
            if isinstance(item, dict):
                modalities = item.get("modalities")
                if isinstance(modalities, dict):
                    inputs = modalities.get("input") or []
                    entry["vision"] = "image" in inputs
                    entry["files"] = "pdf" in inputs
                    entry["video"] = "video" in inputs
            extra = self._models_dev_lookup(catalog, base_url, model_id)
            for key, value in extra.items():
                if entry.get(key) is None and value is not None:
                    entry[key] = value
            result.append(entry)
        return result


    CAPABILITY_KEYS = ("vision", "files", "video", "tool_call", "reasoning")

    def model_costs(self) -> dict:
# 每百万 token 单价（models.dev 目录），用于 Dashboard 成本换算
        costs: dict[str, dict] = {}
        for model in self.list_models():
            price = model.get("cost")
            if not isinstance(price, dict):
                continue
            try:
                input_price = float(price.get("input") or 0)
                output_price = float(price.get("output") or 0)
            except (TypeError, ValueError):
                continue
            if input_price > 0 or output_price > 0:
                costs[model["id"]] = {"input": input_price, "output": output_price}
        return costs


    def model_capabilities(self, model: dict) -> dict:

        caps = {}
        for key in self.CAPABILITY_KEYS:
            value = model.get(key)
            if value is None and isinstance(model.get("capabilities"), dict):
                value = model["capabilities"].get(key)
            caps[key] = bool(value) if value is not None else None
        return caps

    def _meets_needs(self, model: dict, needs: list | None) -> bool:
        if not needs:
            return True
        caps = self.model_capabilities(model)
        return all(caps.get(n) is True for n in needs)

    def primary_capabilities(self) -> dict:

        try:
            primary = self.resolve_model(None)
        except Exception:
            return {k: None for k in self.CAPABILITY_KEYS}
        return self.model_capabilities(primary)

    def list_models(self) -> list[dict]:
        models: list[dict] = []
        for provider in self.list_providers():
            for model in provider.get("models") or []:
                if not isinstance(model, dict) or not model.get("enabled", True):
                    continue
                models.append(
                    {
                        "id": f"{provider['id']}:{model.get('id', '')}",
                        "provider": provider["id"],
                        "provider_name": provider.get("name", ""),
                        "base_url": provider.get("base_url", ""),
                        "api_key": provider.get("api_key", ""),
                        "model": model.get("id", ""),
                        "temperature": model.get("temperature"),
                        "max_tokens": model.get("max_tokens"),
                        "capabilities": self.model_capabilities(model),
# 透出 models.db 目录数据，否则 context_length/cost 是死数据
                        "context_length": model.get("context_length"),
                        "cost": model.get("cost") if isinstance(model.get("cost"), dict) else None,
                    }
                )
        return models

    def resolve_model(self, model_id: str | None = None, needs: list | None = None) -> dict:
        models = self.list_models()
# 显式指定的模型优先于 needs 过滤——用户点名不被静默换掉
        if model_id:
            for model in models:
                if model["id"] == model_id:
                    return model
            for model in models:
                if model.get("model") == model_id:
                    return model
        if needs:
            capable = [m for m in models if self._meets_needs(m, needs)]
            if capable:
                models = capable
            else:
                self.sdk.logger.warning(f"no model meets needs {needs}, falling back to full pool")
        default = getattr(self.config, "default_model", "") or ""
        if default:
            for model in models:
                if model["id"] == default or model.get("model") == default:
                    return model
        if models:
            return models[0]
        raise EngineError(texts.t("provider_no_models"))

# ===== 无副作用能力查询 =====

    def has_model(self, needs: list | None = None) -> bool:
        """无副作用查询：池中是否存在满足全部 needs 的启用模型（能力未知 None 视为不满足）。"""
        models = self.list_models()
        if not needs:
            return bool(models)
        return any(self._meets_needs(m, needs) for m in models)

    def capability_status(self, need: str) -> str:
        """全池对单一能力的明确判定：yes=至少一个启用模型明确具备；
        no=全部启用模型明确不具备；unknown=无数据或含能力未知的模型。"""
        saw_false = False
        for model in self.list_models():
            value = self.model_capabilities(model).get(need)
            if value is True:
                return "yes"
            if value is False:
                saw_false = True
        return "no" if saw_false else "unknown"

# ===== TaskSpec 任务分派 =====

    def resolve_task_model(self, spec: TaskSpec) -> dict:
        """解析任务模型：显式 model > cfg.task_models[kind] > needs 过滤 >
        prefer="cheap" 按 cost(input+output) 升序 > 池序。"""
        models = self.list_models()
        if not models:
            raise EngineError(texts.t("provider_no_models"))
        explicit = str(spec.model or "")
        if not explicit:
            task_models = getattr(self.config, "task_models", None)
            if isinstance(task_models, dict):
                explicit = str(task_models.get(spec.kind) or "")
        if explicit:
            for model in models:
                if model["id"] == explicit:
                    return model
            for model in models:
                if model.get("model") == explicit:
                    return model
            self.sdk.logger.warning(f"task model {explicit!r} not found for kind {spec.kind!r}, falling back to pool")
        candidates = models
        needs = [str(n) for n in (spec.needs or []) if str(n)]
        if needs:
            capable = [m for m in candidates if self._meets_needs(m, needs)]
            if capable:
                candidates = capable
            else:
                self.sdk.logger.warning(f"no model meets needs {needs} for task {spec.kind!r}, falling back to full pool")
        if str(spec.prefer or "").lower() == "cheap" and len(candidates) > 1:
            costs = self.model_costs()
            priced = [m for m in candidates if m["id"] in costs]
            rest = [m for m in candidates if m["id"] not in costs]
            priced.sort(key=lambda m: costs[m["id"]]["input"] + costs[m["id"]]["output"])
            candidates = priced + rest
        return candidates[0]

# ===== 难度感知路由（V1 启发式，cfg.routing_enabled 默认关闭） =====

    @staticmethod
    def _first_user_text(request: ChatRequest) -> str:
        """本轮首条 user 消息的文本（多模态分片取 text 部分），无则空串。"""
        for message in request.messages or []:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    str(part.get("text") or "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                ]
                return "\n".join(part for part in parts if part)
            return ""
        return ""

    def _route_chat_spec(self, spec: TaskSpec, request: ChatRequest) -> None:
        """开关打开时，对无显式约束的 chat 任务按首条用户消息难度改写 spec.prefer。

        命中条件：kind=="chat" 且 prefer/model/needs 均未指定（显式指定与能力过滤优先于路由）。
        结果按 chat_key 缓存 routing_ttl 秒（无 chat_key 则每条独立分级）；统计入
        routing_stats / routing_log，决策走 logger.debug。routing_enabled=False 时零行为。
        """
        if not getattr(self.config, "routing_enabled", False):
            return
        if spec.kind != "chat" or spec.prefer or spec.model or spec.needs:
            return
        text = self._first_user_text(request)
        if not text:
            return
        chat_key = str(spec.chat_key or "")
        now = time.time()
        try:
            ttl = float(getattr(self.config, "routing_ttl", 300) or 0)
        except (TypeError, ValueError):
            ttl = 300.0
        prefer = reason = ""
        cached = False
        if chat_key and ttl > 0:
            hit = self.routing_cache.get(chat_key)
            if hit and now - float(hit[2]) < ttl:
                prefer, reason = str(hit[0]), str(hit[1])
                cached = True
        if not prefer:
            prefer, reason = classify(text)
            if chat_key and ttl > 0:
# 简单防膨胀：超 256 条时先剔除过期项再写入
                if len(self.routing_cache) > 256:
                    self.routing_cache = {
                        k: v for k, v in self.routing_cache.items() if now - float(v[2]) < ttl
                    }
                self.routing_cache[chat_key] = (prefer, reason, now)
        spec.prefer = prefer
        self.routing_stats[prefer] = self.routing_stats.get(prefer, 0) + 1
        self.routing_log.append({"chat_key": chat_key, "prefer": prefer, "reason": reason, "ts": now})
        scope = f"[{chat_key}] " if chat_key else ""
        suffix = "; cache hit" if cached else ""
        self.sdk.logger.debug(f"model routing {scope}-> {prefer} ({reason}){suffix}")

    async def dispatch(
        self,
        spec: TaskSpec,
        request: ChatRequest,
        on_delta=None,
        on_reset=None,
        on_reasoning=None,
    ) -> ChatResponse:
        """按 TaskSpec 分派任务模型后走统一 chat 链（failover/熔断照常生效）。"""
        self._route_chat_spec(spec, request)# 难度感知路由（默认关闭，不改显式约束）
        model = self.resolve_task_model(spec)
        scoped = ChatRequest(
            messages=request.messages,
            tools=request.tools,
            model=model["id"],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            needs=request.needs,
        )
        return await self.chat(scoped, on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning)

    async def chat(self, request: ChatRequest, on_delta=None, on_reset=None, on_reasoning=None) -> ChatResponse:
        primary = self.resolve_model(request.model, request.needs)
        chain = [primary]
        if getattr(self.config, "model_failover", True):
            for model in self.list_models():
                if model["id"] != primary["id"] and self._meets_needs(model, request.needs):
                    chain.append(model)
# 熔断：冷却中的模型沉底而不是丢弃（全冷却时仍按链尝试）
        chain.sort(key=lambda m: 1 if self._is_open(m["id"]) else 0)
        errors: list[str] = []
        for index, model in enumerate(chain):
            temperature = request.temperature
            if temperature is None:
                temperature = model.get("temperature")
            if temperature is None:
                temperature = getattr(self.config, "temperature", 0.7)
            max_tokens = request.max_tokens or model.get("max_tokens") or getattr(self.config, "max_tokens", 2048)
            scoped = ChatRequest(
                messages=request.messages,
                tools=request.tools,
                model=model["model"],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            try:
                extra = {"on_reasoning": on_reasoning} if on_reasoning is not None else {}
                response = await self.engine.chat(
                    model.get("base_url", ""),
                    model.get("api_key", ""),
                    scoped,
                    on_delta=on_delta,
                    on_reset=on_reset,
                    **extra,
                )
            except EngineError as e:
                self._record_fail(model["id"])
                errors.append(f"{model['id']}: {e}")
                if index + 1 < len(chain) and on_reset is not None:
                    try:
                        result = on_reset()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass
                continue
            response.model = model["id"]
            self._record_success(model["id"])
            return response
        raise EngineError(texts.t("engine_all_failed", errors=" | ".join(errors)))

    async def describe_images(self, image_urls: list, prompt: str = "") -> list[str]:

        descriptions: list[str] = []
        for url in image_urls[:3]:
            parts: list = [
                {
                    "type": "text",
                    "text": prompt
                    or "Describe this image in detail in its likely language: subjects, text, layout and anything notable.",
                },
                {"type": "image_url", "image_url": {"url": url}},
            ]
            try:
                response = await self.dispatch(
                    TaskSpec(kind="vision", needs=["vision"]),
                    ChatRequest(messages=[{"role": "user", "content": parts}], max_tokens=800),
                )
                text = (response.content or "").strip()
            except Exception as e:
                self.sdk.logger.warning(f"vision delegate failed: {e}")
                text = ""
            descriptions.append(text)
        return descriptions

    async def test_model(self, model_id: str) -> ChatResponse:
        return await self.chat(ChatRequest(messages=[{"role": "user", "content": "ping"}], model=model_id or None))
