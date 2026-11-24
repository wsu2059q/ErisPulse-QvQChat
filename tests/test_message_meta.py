"""assistant 条目记录回复出处（model + token 计数）。"""

import asyncio
import time

from fakes import FakeMain, FakeSDK, make_config

from QvQChat.conversation.service import ConversationService


async def test_finalize_stores_model_meta():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta"
    await manager.append_user(key, "你好")
    await manager.finalize(
        key, "喵～",
        usage={"prompt_tokens": 120, "completion_tokens": 34, "total_tokens": 154, "cost": 0.001},
        model="deepseek-chat",
    )
    entry = (await manager.get_contexts(key))[-1]
    assert entry["role"] == "assistant"
    assert entry["meta"]["model"] == "deepseek-chat"
    assert entry["meta"]["usage"] == {"prompt_tokens": 120, "completion_tokens": 34, "total_tokens": 154}
    # 聚合记账照旧发生（record_usage 路径不受影响）
    today = main.sdk.storage.get(f"QvQChat:usage:{time.strftime('%Y-%m-%d')}", {})
    assert today.get("by_model", {}).get("deepseek-chat") == {"tokens": 154, "in": 120, "out": 34}


async def test_finalize_without_model_has_no_meta():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta0"
    await manager.finalize(key, "嗯")
    entry = (await manager.get_contexts(key))[-1]
    assert "meta" not in entry


async def test_append_meta_passthrough():
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-meta1"
    await manager.append(key, "assistant", "带出处的回复", meta={"model": "glm-5"})
    entry = (await manager.get_contexts(key))[-1]
    assert entry["meta"] == {"model": "glm-5"}


async def test_prepare_debug_returns_parts_without_persist():
    """提示词调试器：debug=True 回传部件明细；persist=False 不落库。"""
    main = FakeMain()
    manager = ConversationService(main)
    key = "s-dbg"
    await manager.append_user(key, "早")
    prepared = await manager.prepare(key, "调试预览", persist=False, debug=True)
    kinds = [p["kind"] for p in prepared["debug"]["parts"]]
    assert "persona" in kinds and "capability" in kinds
    assert prepared["system"], "system 全文应返回"
    # persist=False：用户消息未落库
    roles = [c["role"] for c in await manager.get_contexts(key)]
    assert roles.count("user") == 1, "dry-run 不得追加 user 消息"
    # 非 debug 时无该字段
    prepared2 = await manager.prepare(key, "再次", persist=False)
    assert prepared2["debug"] == {}


async def test_profile_edit_replaces_section():
    """画像纠错：整段替换 + 其它段保留 + 审计留痕。"""
    main = FakeMain()
    profile = main.conversations.profile
    await profile._save("snowluma:10001", {"traits": [{"text": "夜猫子", "ts": 0}], "facts": [{"text": "在做框架", "ts": 0}]})
    from QvQChat.dashboard.api_sessions import SessionsApiMixin

    api = SessionsApiMixin.__new__(SessionsApiMixin)
    api.main = main
    api.sdk = main.sdk

    class Req:
        async def json(self):
            return {"user_key": "snowluma:10001", "section": "traits",
                    "items": ["夜猫子（凌晨三点还醒着）", "  ", "咖啡续命"]}

    r = await api.profile_edit(Req())
    assert r["ok"] and len(r["profile"]["traits"]) == 2
    assert r["profile"]["facts"][0]["text"] == "在做框架", "其它段保留"
    data = await profile.get("snowluma:10001")
    assert data["traits"][0]["text"] == "夜猫子（凌晨三点还醒着）"
    assert any(a["tool"] == "profile_edit" for a in main.audits)


async def test_task_model_type_tier_group_vs_private():
    """类型级模型：chat_group / chat_private 优先于 task_models.chat。"""
    from QvQChat.engine.base import TaskSpec
    from QvQChat.engine.pool import ModelPool

    pool = ModelPool(FakeSDK(), make_config())
    await pool.save_provider({
        "id": "p1", "name": "P1", "base_url": "https://x/v1", "api_key": "k",
        "models": [
            {"id": "plain", "enabled": True, "tool_call": False, "context_length": 8192,
             "cost": {"input": 10.0, "output": 20.0}},
            {"id": "smart", "enabled": True, "tool_call": True, "vision": True,
             "context_length": 32768, "cost": {"input": 5.0, "output": 5.0}},
            {"id": "cheap", "enabled": True, "tool_call": True,
             "cost": {"input": 0.5, "output": 0.5}},
        ],
    })
    pool.config.task_models = {"chat": "p1:plain", "chat_group": "p1:cheap", "chat_private": "p1:smart"}
    got_group = pool.resolve_task_model(TaskSpec(kind="chat", chat_key="snowluma:group:871"))
    got_private = pool.resolve_task_model(TaskSpec(kind="chat", chat_key="snowluma:private:10001"))
    assert got_group["id"] == "p1:cheap"
    assert got_private["id"] == "p1:smart"
    # 无 chat_key 回落 chat 档
    assert pool.resolve_task_model(TaskSpec(kind="chat"))["id"] == "p1:plain"


async def test_budget_quiet_hours():
    """时段礼仪：静默窗内参与预算直接拒；窗外不受影响。"""
    import time
    main = FakeMain()
    main.cfg.participation_quiet_hours = "23:00-07:00"
    budget = main.conversations and None
    from QvQChat.participation.budget import SpeechBudget
    b = SpeechBudget(main.sdk, main.cfg)
    # 构造 23:30 与 12:00 两个时刻
    t_night = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 23:30", "%Y-%m-%d %H:%M"))
    t_noon = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 12:00", "%Y-%m-%d %H:%M"))
    ok_night, reason = await b.allow("s:q:1", "interject", now=t_night)
    ok_noon, _ = await b.allow("s:q:1", "interject", now=t_noon)
    assert not ok_night and "静默" in reason or "Quiet" in reason or "silent" in reason.lower() or "quiet" in reason.lower()
    assert ok_noon
    # 跨零点：01:00 仍在窗内
    t_early = time.mktime(time.strptime(time.strftime("%Y-%m-%d") + " 01:00", "%Y-%m-%d %H:%M"))
    ok_early, _ = await b.allow("s:q:2", "interject", now=t_early)
    assert not ok_early


def test_notify_admins_tier_and_restricted_single_id():
    """分级管理员：上报只发 notify_admins；受限提示只露负责管理员一个。"""
    main = FakeMain()
    main.cfg.admins = ["挂名A", "决策B", "主人C"]
    main.cfg.notify_admins = ["决策B"]
    # 框架主人表兜底进 _admin_ids_for（fake 里 framework_masters 可能报错，try 内吞）
    assert main.sessions.notify_admin_ids_for("snowluma") == ["决策B"]
    # notify 留空回落第一个（配置原序，不是字典序）
    main.cfg.notify_admins = []
    assert main.sessions.notify_admin_ids_for("snowluma") == ["挂名A"]
    # 受限提示只带一个负责管理员
    ids = main.sessions.notify_admin_ids_for("snowluma")[:1]
    assert ids == ["挂名A"] and len(ids) == 1
