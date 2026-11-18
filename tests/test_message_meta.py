"""assistant 条目记录回复出处（model + token 计数）。"""

import asyncio
import time

from fakes import FakeMain

from QvQChat.conversation.service import ConversationService


def test_finalize_stores_model_meta():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta"
    manager.append_user(key, "你好")
    manager.finalize(
        key, "喵～",
        usage={"prompt_tokens": 120, "completion_tokens": 34, "total_tokens": 154, "cost": 0.001},
        model="deepseek-chat",
    )
    entry = manager.get_contexts(key)[-1]
    assert entry["role"] == "assistant"
    assert entry["meta"]["model"] == "deepseek-chat"
    assert entry["meta"]["usage"] == {"prompt_tokens": 120, "completion_tokens": 34, "total_tokens": 154}
    # 聚合记账照旧发生（record_usage 路径不受影响）
    today = main.sdk.storage.get(f"QvQChat:usage:{time.strftime('%Y-%m-%d')}", {})
    assert today.get("by_model", {}).get("deepseek-chat") == {"tokens": 154, "in": 120, "out": 34}


def test_finalize_without_model_has_no_meta():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta0"
    manager.finalize(key, "嗯")
    entry = manager.get_contexts(key)[-1]
    assert "meta" not in entry


def test_append_meta_passthrough():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta1"
    manager.append(key, "assistant", "带出处的回复", meta={"model": "glm-5"})
    entry = manager.get_contexts(key)[-1]
    assert entry["meta"] == {"model": "glm-5"}


def test_prepare_debug_returns_parts_without_persist():
    """提示词调试器：debug=True 回传部件明细；persist=False 不落库。"""
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-dbg"
    manager.append_user(key, "早")
    import asyncio
    prepared = asyncio.run(manager.prepare(key, "调试预览", persist=False, debug=True))
    kinds = [p["kind"] for p in prepared["debug"]["parts"]]
    assert "persona" in kinds and "capability" in kinds
    assert prepared["system"], "system 全文应返回"
    # persist=False：用户消息未落库
    roles = [c["role"] for c in manager.get_contexts(key)]
    assert roles.count("user") == 1, "dry-run 不得追加 user 消息"
    # 非 debug 时无该字段
    prepared2 = asyncio.run(manager.prepare(key, "再次", persist=False))
    assert prepared2["debug"] == {}


def test_profile_edit_replaces_section():
    """画像纠错：整段替换 + 其它段保留 + 审计留痕。"""
    main = FakeMain()
    profile = main.conversations.profile
    profile._save("snowluma:10001", {"traits": [{"text": "夜猫子", "ts": 0}], "facts": [{"text": "在做框架", "ts": 0}]})
    from QvQChat.dashboard.api_sessions import SessionsApiMixin
    import asyncio

    api = SessionsApiMixin.__new__(SessionsApiMixin)
    api.main = main
    api.sdk = main.sdk

    class Req:
        async def json(self):
            return {"user_key": "snowluma:10001", "section": "traits",
                    "items": ["夜猫子（凌晨三点还醒着）", "  ", "咖啡续命"]}

    r = asyncio.run(api.profile_edit(Req()))
    assert r["ok"] and len(r["profile"]["traits"]) == 2
    assert r["profile"]["facts"][0]["text"] == "在做框架", "其它段保留"
    data = profile.get("snowluma:10001")
    assert data["traits"][0]["text"] == "夜猫子（凌晨三点还醒着）"
    assert any(a["tool"] == "profile_edit" for a in main.audits)


def test_task_model_type_tier_group_vs_private():
    """类型级模型：chat_group / chat_private 优先于 task_models.chat。"""
    import sys
    sys.path.insert(0, "tests")
    from test_model_dispatch import make_pool
    from QvQChat.engine.base import TaskSpec

    pool = make_pool()
    pool.config.task_models = {"chat": "p1:plain", "chat_group": "p1:cheap", "chat_private": "p1:smart"}
    got_group = pool.resolve_task_model(TaskSpec(kind="chat", chat_key="snowluma:group:871"))
    got_private = pool.resolve_task_model(TaskSpec(kind="chat", chat_key="snowluma:private:10001"))
    assert got_group["id"] == "p1:cheap"
    assert got_private["id"] == "p1:smart"
    # 无 chat_key 回落 chat 档
    assert pool.resolve_task_model(TaskSpec(kind="chat"))["id"] == "p1:plain"


def test_budget_quiet_hours():
    """时段礼仪：静默窗内参与预算直接拒；窗外不受影响。"""
    import asyncio, time
    main = FakeMain()
    main.cfg.participation_quiet_hours = "23:00-07:00"
    budget = main.conversations and None
    from QvQChat.participation.budget import SpeechBudget
    b = SpeechBudget(main.sdk, main.cfg)
    # 构造 23:30 与 12:00 两个时刻
    t_night = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 23:30", "%Y-%m-%d %H:%M"))
    t_noon = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 12:00", "%Y-%m-%d %H:%M"))
    ok_night, reason = b.allow("s:q:1", "interject", now=t_night)
    ok_noon, _ = b.allow("s:q:1", "interject", now=t_noon)
    assert not ok_night and "静默" in reason or "Quiet" in reason or "silent" in reason.lower() or "quiet" in reason.lower()
    assert ok_noon
    # 跨零点：01:00 仍在窗内
    t_early = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 01:00", "%Y-%m-%d %H:%M"))
    ok_early, _ = b.allow("s:q:2", "interject", now=t_early)
    assert not ok_early
