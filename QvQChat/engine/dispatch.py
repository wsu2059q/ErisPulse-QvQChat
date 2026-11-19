"""分派半区（ModelPool 的调度状态机）：并发闸门/熔断/负载分流/难度路由/任务分派/chat 链。

从 pool.py 拆出（M6-5）：方法体逐字搬运（目录调用点改走 self.catalog），
语义不变。状态容器（_breaker/_provider_active/_ever_ok/routing_*）随类走。
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

from .. import texts, utils
from .base import ChatRequest, ChatResponse, EngineError, TaskSpec
from .gate import PriorityGate
from .router import classify


def _provider_match(provider_id: str, pattern: str) -> bool:
    """提供商匹配：精确或 * 通配（api* 命中 apiprovider）。"""
    name = str(provider_id or "")
    pat = str(pattern or "").strip()
    if not pat:
        return False
    if pat.endswith("*"):
        return name.startswith(pat[:-1])
    return name == pat


class DispatchGate:
    """熔断/闸门/路由/分派：chat 链的执行半区（目录查询走 pool.catalog）。"""

    BREAKER_THRESHOLD = 3
    BREAKER_BASE_COOLDOWN = 60.0
    BREAKER_MAX_COOLDOWN = 600.0

    ROUTING_LOG_MAX = 50

    def __init__(self, pool):
        self.pool = pool
# 全局并发闸门（多人高负载）：limit 随配置实时生效；0 = 不限流
        self.gate = PriorityGate(int(getattr(pool.config, "max_concurrent_requests", 0) or 0))
# 模型熔断状态：model_id -> {"fails": 连续失败次数, "until": 冷却截止时间戳}
        self._breaker: dict[str, dict] = {}
# Provider 负载分流：provider_id -> 在飞请求数（并发时把新请求导向更闲的一家）
        self._provider_active: dict[str, int] = {}
# 至少成功过一次的模型（负载分流抢占链首的门槛，见 _record_success）
        self._ever_ok: set[str] = set()
# 难度感知路由（默认关闭）：chat_key -> (prefer, reason, ts)
        self.routing_cache: dict[str, tuple] = {}
# 路由统计与最近决策回看（{prefer: 计数} / deque[{chat_key, prefer, reason, ts}]）
        self.routing_stats: dict[str, int] = {}
        self.routing_log: deque = deque(maxlen=self.ROUTING_LOG_MAX)

    @property
    def sdk(self):
        return self.pool.sdk

    @property
    def config(self):
        return self.pool.config

    @property
    def engine(self):
        return self.pool.engine

    @property
    def catalog(self):
        return self.pool.catalog

    def breaker_state(self) -> list[dict]:
        import time as _time

        now = _time.time()
        state = []
        for model_id, info in self._breaker.items():
            until = float(info.get("until") or 0)
            if until <= now:
                continue
            state.append({"model": model_id, "fails": info.get("fails", 0), "cooldown_left": int(until - now)})
        return state

    def breaker_reset(self, model_id: str = "") -> int:
        """手动清除熔断状态（编排页健康卡重置按钮）：清全部或指定模型。"""
        breaker = self._breaker
        if model_id:
            removed = 1 if breaker.pop(str(model_id), None) is not None else 0
            return removed
        removed = len(breaker)
        breaker.clear()
        return removed

    def _record_fail(self, model_id: str) -> None:
        import time as _time

        info = self._breaker.setdefault(model_id, {"fails": 0, "until": 0})
        info["fails"] = int(info.get("fails", 0)) + 1
        if info["fails"] >= self.BREAKER_THRESHOLD:
            cooldown = min(self.BREAKER_BASE_COOLDOWN * (2 ** (info["fails"] - self.BREAKER_THRESHOLD)), self.BREAKER_MAX_COOLDOWN)
            info["until"] = _time.time() + cooldown

    def _record_success(self, model_id: str) -> None:
        self._breaker.pop(model_id, None)
# 已验证集：该模型至少真实成功过一次。负载分流只允许"服务过"的 provider
# 抢占链首——新加的 provider active=0 永远最闲，否则并发一来就被导到
# 从未验证的模型上（全局间歇性空回复事故：谁最闲就轮到谁，而它没跑通过）
        self._ever_ok.add(str(model_id))

    def _is_open(self, model_id: str) -> bool:
        import time as _time

        info = self._breaker.get(model_id)
        return bool(info and float(info.get("until") or 0) > _time.time())


# ===== TaskSpec 任务分派 =====

    def resolve_task_model(self, spec: TaskSpec) -> dict:
        """解析任务模型：显式 model > cfg.task_models[kind] > aux_model（非 chat）> needs 过滤 >
        prefer="cheap" 按 cost(input+output) 升序 > 池序。"""
        models = self.catalog.list_models()
        if not models:
            raise EngineError(texts.t("provider_no_models"))
        explicit = str(spec.model or "")
        if not explicit:
            task_models = getattr(self.config, "task_models", None)
            if isinstance(task_models, dict):
                explicit = str(task_models.get(spec.kind) or "")
                if str(spec.kind) == "chat" and str(spec.chat_key or ""):
# 会话类型级默认：群聊/私聊可分别固定模型（chat_group / chat_private），
# 优先于 task_models.chat——群聊走便宜档、私聊走旗舰的成本结构靠这两档实现
# （chat_key 形如 platform:detail:id[@account]，本地拆 detail，避免反向依赖 conversation 层）
                    tail = str(spec.chat_key).rsplit("@", 1)[0]
                    segs = tail.split(":")
                    detail = segs[1] if len(segs) >= 2 else ""
                    tier = str(task_models.get("chat_" + detail) or "")
                    if tier:
                        explicit = tier
# 辅助调用统一模型：判定/播报/压缩等后台任务的 cheap 自动选择会命中"最便宜的池"，
# 运营方未必想让辅助调用落到那家（用量与成本统计按 provider 分池）——配一个即全部归位
        if not explicit and str(spec.kind) != "chat":
            explicit = str(getattr(self.config, "aux_model", "") or "").strip()
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
            capable = [m for m in candidates if self.catalog._meets_needs(m, needs)]
            if capable:
                candidates = capable
            elif "vision" in needs:
# 视觉任务：能力标记缺失/未知时按模型名启发式兜底（池里常有 gpt-4o/glm-4v 等）
                hinted = [m for m in candidates if self._vision_name_hint(m)]
                if hinted:
                    self.sdk.logger.info(
                        f"no model advertises vision; using name-based candidate {hinted[0]['id']!r}"
                    )
                    candidates = hinted
                else:
                    self.sdk.logger.warning(
                        "no vision-capable model found: set task_models.vision in config "
                        "(e.g. {\"vision\": \"provider:model\"}) or use a vision model"
                    )
                    raise EngineError(texts.t("no_vision_model"))
            else:
                self.sdk.logger.warning(f"no model meets needs {needs} for task {spec.kind!r}, falling back to full pool")
        if str(spec.prefer or "").lower() == "cheap" and len(candidates) > 1:
            costs = self.catalog.model_costs()
            priced = [m for m in candidates if m["id"] in costs]
            rest = [m for m in candidates if m["id"] not in costs]
            priced.sort(key=lambda m: costs[m["id"]]["input"] + costs[m["id"]]["output"])
            candidates = priced + rest
        return candidates[0]

# 保守的视觉模型名启发式：宁可漏判也不错配（错配会让描述变成空串/幻觉）
    _VISION_HINTS = (
        "gpt-4o", "gpt-4.1", "gpt-5", "o4-", "gemini", "claude-3", "claude-4",
        "glm-4v", "glm-4.1v", "glm-4.5v", "qwen-vl", "qwen2-vl", "qwen2.5-vl", "qwen3-vl",
        "-vl-", "-vl", "llava", "pixtral", "internvl", "minicpm-v", "vision",
    )

    @classmethod
    def _vision_name_hint(cls, model: dict) -> bool:
        name = f"{model.get('id', '')} {model.get('model', '')}".lower()
        return any(hint in name for hint in cls._VISION_HINTS)

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
        """按 TaskSpec 分派任务模型后走统一 chat 链（failover/熔断照常生效）。

        并发闸门优先级：kind=="chat" 用 spec.priority（用户直答默认 0）；其余
        （compact/title/toolselect 等后台任务）固定 8，满载时让位给真实用户。
        """
        self._route_chat_spec(spec, request)# 难度感知路由（默认关闭，不改显式约束）
        model = self.resolve_task_model(spec)
# 思考强度注入优先级（近端覆盖远端）：
# 调用方显式 > 模型条目 > 提供商默认 > 全局配置；全都为空且 chat+cheap 时
# 才落 effort_smalltalk 自动降档（自动档绝不覆盖任何显式档位）
        effort = (
            str(getattr(request, "reasoning_effort", "") or "")
            or str(model.get("reasoning_effort") or "")
            or str(model.get("provider_reasoning_effort") or "")
            or str(getattr(self.config, "reasoning_effort", "") or "")
        )
        if not effort and str(spec.kind) == "chat" and str(spec.prefer or "") == "cheap":
            effort = str(getattr(self.config, "effort_smalltalk", "") or "")
        scoped = ChatRequest(
            messages=request.messages,
            tools=request.tools,
            model=model["id"],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            needs=request.needs,
            reasoning_effort=effort,
        )
        priority = int(spec.priority or 0) if str(spec.kind) == "chat" else 8
        return await self.chat(scoped, on_delta=on_delta, on_reset=on_reset, on_reasoning=on_reasoning, priority=priority)

    @property
    def saturated(self) -> bool:
        """并发闸门满载：上游可据此跳过插话问询等可选工作。"""
        return self.gate.saturated

    def background_blocked(self) -> bool:
        """后台任务（压缩/标题/画像提炼/工具筛选/中止判定）此时是否应让路。

        满载时这些调用全部可跳过且无副作用：压缩下轮再触发、标题下次生成、
        工具筛选回退全量、中止判定回退排队。把并发槽位全部让给用户直答。"""
        try:
            return self.gate.saturated
        except Exception:
            return False

    async def chat(self, request: ChatRequest, on_delta=None, on_reset=None, on_reasoning=None, priority: int = 0) -> ChatResponse:
        primary = self.catalog.resolve_model(request.model, request.needs)
        chain = [primary]
        if getattr(self.config, "model_failover", True):
            backups: list[dict] = []
            for model in self.catalog.list_models():
                if model["id"] == primary["id"]:
                    continue
                if self.catalog._meets_needs(model, request.needs):
                    chain.append(model)
                elif self.catalog._unknown_needs(model, request.needs):
# 能力未知的模型不参与首选，但保留为后备：首选全挂时仍可继续尝试
                    backups.append(model)
            chain.extend(backups)
# 熔断：冷却中的模型沉底而不是丢弃（全冷却时仍按链尝试）
        chain.sort(key=lambda m: 1 if self._is_open(m["id"]) else 0)
# 质量绑定（steer_keep 同时约束分流转出与熔断回退）：首选 provider 在名单内时，
# 跨提供商的后备全部剔除——模型挂了宁可报错（触发失败告警）也不静默换弱模型答
        keep = [str(x) for x in (getattr(self.config, "provider_steer_keep", []) or [])]
        primary_keep = any(_provider_match(primary["provider"], k) for k in keep)
        if primary_keep:
            same = [m for m in chain if m["provider"] == primary["provider"]]
            if len(same) < len(chain):
                self.sdk.logger.debug(
                    f"breaker fallback guard: {primary['provider']} is steer-keep, "
                    f"dropped {len(chain) - len(same)} cross-provider models"
                )
                chain = same
# 思考强度直连路径兜底：不经 dispatch 的调用（面板聊天/OpenAI 端点等）也要吃到
# 模型条目 > 提供商默认 > 全局配置的档位（调用方显式档位保持最高优先级）
        if not str(getattr(request, "reasoning_effort", "") or ""):
            inherited = (
                str(primary.get("reasoning_effort") or "")
                or str(primary.get("provider_reasoning_effort") or "")
                or str(getattr(self.config, "reasoning_effort", "") or "")
            )
            if inherited:
                request.reasoning_effort = inherited
# 负载分流（并发时转移）：首选 provider 在飞数达到阈值时，把更闲的 provider 稳定提前——
# 不等报错就分流；各 provider 的 base_url 不同也照常工作。
# 门槛：只在"至少成功服务过一次"的 provider 之间重排——新加的 provider
# active=0 永远最闲，不分门槛就等于并发一来请求全被导到未验证模型上
# （全局间歇性空回复事故根因），从未跑通的沉底、不参与抢占
        if bool(getattr(self.config, "provider_load_steering", True)) and chain:
            threshold = max(1, int(getattr(self.config, "provider_steer_active", 2) or 2))
            primary_active = self._provider_active.get(chain[0]["provider"], 0)
            if primary_active >= threshold and not primary_keep:
                before = chain[0]["id"]
                chain.sort(key=lambda m: (
                    1 if self._is_open(m["id"]) else 0,
                    0 if str(m["id"]) in self._ever_ok else 1,
                    self._provider_active.get(m["provider"], 0),
                ))
                if chain[0]["id"] != before:
                    self.sdk.logger.debug(f"load steering: {before} active={primary_active} -> {chain[0]['id']}")
            elif primary_keep and primary_active >= threshold:
                self.sdk.logger.debug(f"load steering skipped: {chain[0]['provider']} is steer-keep (active={primary_active})")
        errors: list[str] = []
        gate = self.gate
        gate.set_limit(int(getattr(self.config, "max_concurrent_requests", 0) or 0))
        await gate.acquire(priority)
        try:
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
                    reasoning_effort=str(getattr(request, "reasoning_effort", "") or ""),
                )
                self._provider_active[model["provider"]] = self._provider_active.get(model["provider"], 0) + 1
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
                    self._provider_active[model["provider"]] = max(0, self._provider_active.get(model["provider"], 0) - 1)
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
                self._provider_active[model["provider"]] = max(0, self._provider_active.get(model["provider"], 0) - 1)
                response.model = model["id"]
# 空响应软失败：HTTP 200 但无正文且无工具调用不是成功——坏配置的备用模型
# （连通但输出空）此前会在这里"成功"返回空，主对话拿到的就是
# "没有可回复的内容"（间歇性空回复事故：取决于哪次请求落到备用链上）。
# 链上还有模型时记 fail 并继续尝试下一个
                if (
                    index + 1 < len(chain)
                    and not (response.content or "").strip()
                    and not response.tool_calls
                ):
                    self._record_fail(model["id"])
                    errors.append(f"{model['id']}: empty content (no text, no tool calls)")
                    if on_reset is not None:
                        try:
                            result = on_reset()
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            pass
                    continue
                self._record_success(model["id"])
                return response
            raise EngineError(texts.t("engine_all_failed", errors=" | ".join(errors)))
        finally:
            self.gate.release()

    async def describe_images(self, image_urls: list, prompt: str = "", on_error: str = "empty") -> list[str]:
        """逐张图片走视觉模型描述。

        on_error="empty"：失败返回空串（打标签路径依赖此语义，空=未分类）
        on_error="text"：失败返回明确占位文本（对话路径用——宁可说看不见，也不要装作看过）
        """

        descriptions: list[str] = []
        for url in image_urls[:3]:
            parts: list = [
                {
                    "type": "text",
                    "text": prompt
                    or "Describe this image in detail in its likely language: subjects, text, layout and anything notable.",
                },
# 本地路径转 base64 data URL：厂商拉不到部署机本地文件（不转 = 静默丢图，
# 打标签全部失败留「未分类」的根因）
                {"type": "image_url", "image_url": {"url": utils.image_data_url(url)}},
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
            if not text and on_error == "text":
                text = texts.t("vision_unavailable")
            descriptions.append(text)
        return descriptions

    async def test_model(self, model_id: str) -> ChatResponse:
        return await self.chat(ChatRequest(messages=[{"role": "user", "content": "ping"}], model=model_id or None))
