"""拆分与治理的回归测试。"""
import asyncio
import inspect
from dataclasses import MISSING

from QvQChat.Main import CAPABILITY_PROMPT, Main
from QvQChat import prompts, utils
from QvQChat.Config import QvQConfig
from QvQChat.dashboard.manager import DashboardManager

from fakes import FakeChatEvent, FakeMain, make_config

# tests/test_aggregate.py 通过 getattr_static(Main, name) 绑定的方法清单
MAIN_STATIC_NAMES = (
    "_process_locked", "_chat_ctx", "_sender_name", "_resolve_group_name",
    "_seed_history", "_transcript_rows", "_label_seed_rows", "_group_nicknames",
    "is_admin", "check_tool_permission", "_master_checker",
    "record_usage", "_usage_today", "_prune_usage", "_usage_history",
    "_lock_for", "_batch_message", "_flush_later", "_flush_pending",
    "_extract_images", "_to_model_image", "_cleanup_takeovers", "_should_trigger",
    "_chat_key_of", "_chat_confirmer", "_rate_allow", "_rate_notice",
    "_on_message", "_drain_waiting", "_enqueue_waiting", "_announce_queued",
    "_cmd_agent", "_cmd_persona",
)


def test_split_all_main_names_still_resolvable():
    """拆分后 Main 类上仍能解析全部历史方法名（mixin 继承）。"""
    for name in MAIN_STATIC_NAMES:
        assert inspect.getattr_static(Main, name, None) is not None, name
        assert callable(getattr(Main, name)), name


def test_split_capability_prompt_single_source():
    """常量本体在 prompts.py，Main 为兼容再导出，两者一致。"""
    assert prompts.CAPABILITY_PROMPT is CAPABILITY_PROMPT
    assert CAPABILITY_PROMPT.startswith("Sending messages:")


def test_match_pattern_semantics():
    """收编后的前缀通配匹配语义与原实现一致。"""
    assert utils.match_pattern("eco_send", ["eco_*"])
    assert utils.match_pattern("code_exec", ["code_exec"])
    assert not utils.match_pattern("code_exec", ["eco_*", "other"])
    assert utils.match_pattern("anything", ["*"])# 裸 * 匹配一切
    assert not utils.match_pattern("anything", [])# 空规则不匹配
    assert not utils.match_pattern("anything", None)
    assert utils.match_pattern("mcp_foo", ["mcp_*", "memory_*"])
    assert not utils.match_pattern("anything", ["*"], star_all=False)


def test_split_dashboard_handlers_on_manager():
    """DashboardManager 组合三个 mixin 后 handler 仍齐全。"""
    mgr_names = dir(DashboardManager)
    for name in (
        "sessions_get", "session_messages", "session_share", "share_messages", "session_routes",
        "config_get", "config_set", "settings_defaults_get", "personas_get", "models_get",
        "providers_save", "tools_get", "skills_get", "export_data", "import_data",
        "tasks_get", "usage_get", "audit_get", "kb_get", "breakers_get", "costs_get",
        "running_get", "participation_get",
    ):
        assert name in mgr_names, name


def test_config_new_keys_metadata():
    """Config 补键（A2）：分组/控件/默认值/区间正确。"""
    fm = QvQConfig.field_map()
    expected = {
        "tools_fallback": ("tools", "strip"),
        "token_estimator": ("model", ""),
        "task_models": ("model", {}),
        "context_budget_mode": ("chat", "off"),
        "default_context_length": ("chat", 0),
        "context_reserve": ("chat", 0.85),
        "summary_cap": ("chat", 1500),
        "compact_transcript_chars": ("chat", 400),
        "compact_input_chars": ("chat", 12000),
        "facts_extract": ("chat", True),
        "facts_max": ("chat", 100),
    }
    for key, (group, default) in expected.items():
        assert key in fm, key
        f = fm[key]
        ui = (f.metadata or {}).get("ui") or {}
        assert ui.get("group") == group, key
        actual = f.default_factory() if f.default_factory is not MISSING else f.default
        assert actual == default, key
    fm_ui = (fm["tools_fallback"].metadata or {}).get("ui") or {}
    assert fm_ui.get("options") == ["strip", "strict", "off"]
    fm_ui = (fm["token_estimator"].metadata or {}).get("ui") or {}
    assert fm_ui.get("options") == ["", "tiktoken"]
    fm_ui = (fm["context_budget_mode"].metadata or {}).get("ui") or {}
    assert fm_ui.get("options") == ["auto", "tokens", "off"]
    fm_ui = (fm["context_reserve"].metadata or {}).get("ui") or {}
    assert fm_ui.get("min") == 0.5 and fm_ui.get("max") == 0.95


def test_config_coerce_new_keys():
    ok, v, err = QvQConfig.coerce("tools_fallback", "strict")
    assert ok and v == "strict"
    ok, v, err = QvQConfig.coerce("tools_fallback", "bogus")
    assert not ok and err
    ok, v, err = QvQConfig.coerce("context_reserve", "0.99")
    assert not ok# 超出 max 0.95
    ok, v, err = QvQConfig.coerce("task_models", '{"compact": "a:b"}')
    assert not ok# dict 不收 JSON 字符串
    ok, v, err = QvQConfig.coerce("task_models", {"compact": "a:b"})
    assert ok and v == {"compact": "a:b"}
    ok, v, err = QvQConfig.coerce("facts_extract", True)
    assert ok and v is True


def _make_lock_main():
    main = FakeMain()
    main.cfg = make_config(aggregate_window=0.05)
    main.cfg.context_compress_tokens = 0
    main._pending = {}
    main._chat_locks = {}
    main._rate_window = {}
    main._rate_notice_shown = {}
    main.live_registry = None
    for name in (
        "_process_locked", "_chat_ctx", "_sender_name", "_resolve_group_name",
        "_seed_history", "_transcript_rows", "_label_seed_rows", "_group_nicknames",
        "is_admin", "check_tool_permission", "_master_checker",
        "_lock_for", "_batch_message", "_flush_later", "_flush_pending",
        "_extract_images", "_to_model_image", "_cleanup_takeovers", "_should_trigger",
        "_chat_key_of", "_chat_confirmer", "_rate_allow", "_rate_notice",
    ):
        static_attr = inspect.getattr_static(Main, name)
        if isinstance(static_attr, staticmethod):
            setattr(main, name, static_attr.__func__)
        else:
            setattr(main, name, getattr(Main, name).__get__(main))

    class Runner:
        def __init__(self):
            self.in_run = 0
            self.max_overlap = 0

        async def run(self, **kwargs):
            self.in_run += 1
            self.max_overlap = max(self.max_overlap, self.in_run)
            await asyncio.sleep(0.05)
            self.in_run -= 1
            return type("R", (), {"text": "ok", "usage": {}, "tool_trace": [], "rounds": []})()

    main.runner = Runner()

    def spawn(coro):
        return asyncio.get_running_loop().create_task(coro)

    main.spawn = spawn
    return main


async def test_lock_serializes_chat_paths():
    """同 chat_key 的 _flush_pending 与 run_prompt 互斥（无并发交错）。"""
    main = _make_lock_main()
    chat_key = "onebot11:private:u1"# 与 FakeChatEvent 生成的 chat_key 一致

    async def fake_run_prompt(key, prompt, **kwargs):
        async with Main._lock_for(main, key):
            main.runner.in_run += 1
            main.runner.max_overlap = max(main.runner.max_overlap, main.runner.in_run)
            await asyncio.sleep(0.05)
            main.runner.in_run -= 1
        return "ok"

    main.run_prompt = fake_run_prompt
    tasks = []
    for _ in range(3):
        tasks.append(asyncio.get_running_loop().create_task(Main._on_message(main, FakeChatEvent(text="hi", group=False))))
        tasks.append(asyncio.get_running_loop().create_task(fake_run_prompt(chat_key, "p")))
    await asyncio.gather(*tasks)
    await asyncio.sleep(0.2)
    assert main.runner.max_overlap == 1


async def test_rate_window_and_locks_recycled():
    """窗口过期的限频键与空闲 per-chat 锁被顺带回收。"""
    main = FakeMain()
    setattr(main, "_cleanup_takeovers", getattr(Main, "_cleanup_takeovers").__get__(main))
    main._rate_window = {"rate:g:u1": [1000.0], "rate:g:u2": []}
    main._rate_notice_shown = {"rate:g:u1": True, "rate:g:u2": True}
    main._chat_locks = {"a": asyncio.Lock(), "b": asyncio.Lock()}
    await main._chat_locks["b"].acquire()# 持有中的锁不回收
    main._cleanup_takeovers()
    assert "rate:g:u1" not in main._rate_window# 窗口早已过期
    assert "rate:g:u1" not in main._rate_notice_shown
    assert "rate:g:u2" not in main._rate_window# 空窗口
    assert "a" not in main._chat_locks# 空闲锁被回收
    assert "b" in main._chat_locks# 持有中的锁保留
    main._chat_locks["b"].release()


def test_session_module_removed():
    """死代码 session 包已删除。"""
    import importlib

    try:
        importlib.import_module("QvQChat.session.manager")
    except ModuleNotFoundError:
        return
    raise AssertionError("QvQChat.session should be removed")
