"""Dashboard API 公共脚手架：统一的 JSON body 读取、字段取值与 ApiError 错误形状。

新端点一律走 ``read_json`` / ``sget`` / ``raise ApiError(...)``；旧 handler 的
``({"error": ...}, code)`` 字面量随重构逐步收敛到同一形状（HTTP JSON 不变）。
"""

from __future__ import annotations

import functools


class ApiError(Exception):
    """携带 HTTP 状态的业务错误：api_handler 捕获后转 ``({"error": msg}, status)``。"""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = int(status)


async def read_json(request) -> dict:
    """读 JSON body；缺失/非法一律返回空 dict（字段取值再兜底）。"""
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def sget(body: dict, key: str, default: str = "") -> str:
    """字符串字段：None 回落默认值。"""
    v = (body or {}).get(key, default)
    return default if v is None else str(v)


def bget(body: dict, key: str, default: bool = False) -> bool:
    """布尔字段。"""
    return bool((body or {}).get(key, default))


def nget(body: dict, key: str, default: float = 0) -> float:
    """数值字段：非法回落默认值，不抛异常。"""
    try:
        v = (body or {}).get(key, default)
        return default if v is None else float(v)
    except (TypeError, ValueError):
        return default


def api_handler(fn):
    """ApiError → ({"error": msg}, status)；其余异常照常向上抛（guard 层统一 500）。

    注意 *args 透传：装饰器返回的函数在类体里就是普通方法，绑定后首参是 self。
    """

    @functools.wraps(fn)
    async def inner(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ApiError as e:
            return ({"error": str(e)}, e.status)

    return inner
