"""向量层：OpenAI 兼容 /v1/embeddings 客户端（可选能力，零破坏）。

设计约束：
- 纯同步（调用方 knowledge.py 的检索路径是同步的）；openai 已是依赖，用其同步客户端。
- 任何异常一律返回 None，调用方（knowledge.search）回退词面打分，零配置时行为与现状完全一致。
- client 注入式：VectorEngine(client=fake) 供测试注入假客户端，跳过 openai 导入检查。
"""
from __future__ import annotations

import math
import threading

BATCH_SIZE = 16

_default_engine: "VectorEngine | None" = None
_default_lock = threading.Lock()


class VectorEngine:
    """封装 OpenAI 兼容 embeddings 端点；_client 可注入（测试）或按 provider 懒构建（生产）。"""

    def __init__(self, client=None):
        self._client = client
        self._key: tuple | None = None if client is not None else ("__unset__",)
        self._lock = threading.Lock()

    @staticmethod
    def provider_of(cfg) -> dict:
        raw = getattr(cfg, "embedding_provider", None) if cfg is not None else None
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def model_of(cfg) -> str:
        provider = VectorEngine.provider_of(cfg)
        explicit = str(getattr(cfg, "embedding_model", "") or "").strip() if cfg is not None else ""
        return explicit or str(provider.get("model") or "").strip()

    def available(self, cfg) -> bool:
        """配置齐全（base_url/api_key/模型名）且网络层可用（openai 可导入，或已注入测试 client）。"""
        provider = self.provider_of(cfg)
        if not (str(provider.get("base_url") or "").strip() and str(provider.get("api_key") or "").strip()):
            return False
        if not self.model_of(cfg):
            return False
        if self._client is not None:
            return True
        try:
            import openai# noqa: F401  网络层可用性探针（openai 已是依赖，通常成功）

            return True
        except Exception:
            return False

    def _client_for(self, cfg):
        if self._client is not None:
            return self._client
        provider = self.provider_of(cfg)
        key = (str(provider.get("base_url") or "").strip(), str(provider.get("api_key") or "").strip())
        with self._lock:
            if self._key != key:
                from openai import OpenAI

                self._client = OpenAI(base_url=key[0] or None, api_key=key[1] or "none")
                self._key = key
        return self._client

    def embed(self, texts: list, cfg=None) -> list[list[float]] | None:
        """批量向量化（每批 BATCH_SIZE 条）；任何异常返回 None 供调用方回退词面检索。"""
        clean = [str(t or "") for t in (texts or [])]
        clean = [t for t in clean if t.strip()]
        if not clean or not self.available(cfg):
            return None
        model = self.model_of(cfg)
        client = self._client_for(cfg)
        out: list[list[float]] = []
        try:
            for start in range(0, len(clean), BATCH_SIZE):
                batch = clean[start:start + BATCH_SIZE]
                resp = client.embeddings.create(model=model, input=batch)
                data = list(getattr(resp, "data", None) or [])
                if len(data) != len(batch):
                    return None
                for item in data:
                    vec = getattr(item, "embedding", None)
                    if vec is None and isinstance(item, dict):
                        vec = item.get("embedding")
                    if not isinstance(vec, (list, tuple)) or not vec:
                        return None
                    out.append([float(x) for x in vec])
            return out
        except Exception:
            return None

    @staticmethod
    def cosine(a, b) -> float:
        """余弦相似度（纯函数）：长度不等/零向量/任何异常 → 0.0"""
        try:
            if a is None or b is None or len(a) != len(b) or not a:
                return 0.0
            norm_a = math.sqrt(sum(float(x) * float(x) for x in a))
            norm_b = math.sqrt(sum(float(x) * float(x) for x in b))
            if norm_a <= 0.0 or norm_b <= 0.0:
                return 0.0
            dot = sum(float(x) * float(y) for x, y in zip(a, b))
            return dot / (norm_a * norm_b)
        except Exception:
            return 0.0


def engine() -> VectorEngine:
    """模块级单例（生产路径；按 provider 记忆化构建客户端）。"""
    global _default_engine
    if _default_engine is None:
        with _default_lock:
            if _default_engine is None:
                _default_engine = VectorEngine()
    return _default_engine


def available(cfg=None, client=None) -> bool:
    return (VectorEngine(client) if client is not None else engine()).available(cfg)


def model_of(cfg=None) -> str:
    return VectorEngine.model_of(cfg)


def embed(texts: list, cfg=None, client=None) -> list[list[float]] | None:
    return (VectorEngine(client) if client is not None else engine()).embed(texts, cfg)


def cosine(a, b) -> float:
    return VectorEngine.cosine(a, b)
