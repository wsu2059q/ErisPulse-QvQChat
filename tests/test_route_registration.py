"""路由注册防呆：SDK 对重复注册抛 ValueError，manager.register 必须免疫，
并且 /view（面板唯一入口）最后兜底注册成功——真机曾因 logo 双注册 404。"""
from types import SimpleNamespace

from QvQChat.dashboard.manager import DashboardManager

from fakes import FakeMain


class StrictRouter:
    """模拟 ErisPulse RouterManager：重复的 (路径, 方法) 抛 ValueError。"""

    def __init__(self):
        self.registered = []

    def register_http_route(self, module_name, path, handler, methods=None):
        methods = methods or ["POST"]
        for m in methods:
            if any(p == path and m in ms for _, p, ms in self.registered):
                raise ValueError(f"method_conflict: {path} {m}")
        self.registered.append((path, handler, list(methods)))

    def paths(self):
        return {(p, tuple(ms)) for p, _, ms in self.registered}


def make_registered_manager():
    main = FakeMain()
    router = StrictRouter()
    main.sdk.router = router
    main.sdk.Dashboard = SimpleNamespace(
        register_view=lambda **kw: None, unregister_view=lambda **kw: None
    )
    manager = DashboardManager(main)
    manager.register()
    return main, router


def test_register_no_duplicate_routes():
    # logo 曾同时出现在 guarded 与 public 两条表里 → 真机 SDK ValueError → /view 丢失
    _main, router = make_registered_manager()
    seen = set()
    for path, _handler, methods in router.registered:
        for m in methods:
            key = (m, path)
            assert key not in seen, f"重复注册的路由: {key}"
            seen.add(key)


def test_view_route_registered_last_and_present():
    _main, router = make_registered_manager()
    paths = router.paths()
    assert ("/view", ("GET",)) in paths, "/view 必须注册成功（面板唯一入口）"


def test_register_survives_router_conflicts():
    # 即使 SDK 层拒绝某条路由（毒药注入 router），其余路由与 /view 仍全部落位
    main = FakeMain()

    class PoisonedRouter(StrictRouter):
        def register_http_route(self, module_name, path, handler, methods=None):
            if path == "/api/qvq/status":
                raise ValueError("method_conflict: injected")
            return super().register_http_route(module_name, path, handler, methods)

    router = PoisonedRouter()
    main.sdk.router = router
    main.sdk.Dashboard = SimpleNamespace(
        register_view=lambda **kw: None, unregister_view=lambda **kw: None
    )
    manager = DashboardManager(main)
    manager.register()
    assert ("/view", ("GET",)) in router.paths()
    assert ("/api/qvq/auth", ("GET",)) in router.paths()
    assert any("warning" == r[0] for r in main.logger.records)


def test_view_registered_after_api_routes():
    # /view 在注册序列末尾：API 列表再长、即使尾部条目冲突也不影响它
    _main, router = make_registered_manager()
    order = [p for p, _, _ in router.registered]
    assert order[-1] == "/view"
