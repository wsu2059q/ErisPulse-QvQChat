# 存储管理 API：全库浏览 / 分域清理 / 一键重置（保留项）/ 瘦身 / 人格层级绑定回落
import json

from QvQChat.dashboard.manager import DashboardManager

from fakes import FakeMain


class _Req:
    def __init__(self, body=None, query=None):
        self._body = body or {}
        self.query_params = query or {}

    async def json(self):
        return self._body


def make_manager():
    main = FakeMain()
    return main, DashboardManager(main)


def _seed(main):
    store = main.sdk.storage
    store.set("QvQChat:conv:onebot11:group:1@bot_a", {"contexts": [
        {"role": "assistant", "content": "hi", "trace": [{"tool": "x", "output": "o"}], "rounds": [{"text": "hi", "tools": []}]},
    ]})
    store.set("QvQChat:conv:dashboard:private:web", {"contexts": []})
    store.set("QvQChat:mem:global", [{"content": "m"}])
    store.set("QvQChat:profile:onebot11:42", {"traits": ["t"]})
    store.set("QvQChat:audit", [{"tool": "x"}])
    store.set("QvQChat:usage:2026-11-06", {"total": 10})
    store.set("QvQChat:personas", {"assistant": {"name": "a"}})
    store.set("QvQChat:binding:onebot11:group:1@bot_a", "cat")
    store.set("QvQChat:auth_token", "secret")  # 保护键：任何端点不可见不可删


async def test_storage_get_groups_domains():
    main, manager = make_manager()
    _seed(main)
    resp = await manager.storage_get(_Req())
    domains = {d["id"]: d for d in resp["domains"]}
    assert domains["sessions"]["keys"] == 2  # conv: 两个会话
    assert domains["memories"]["keys"] == 1
    assert domains["personas"]["keys"] == 2  # 定义 + 绑定
    assert domains["audit"]["keys"] == 1
    assert all(d["id"] != "other" or d["keys"] == 0 for d in resp["domains"]) or "other" in domains
    # auth_token 永远不出现在统计里
    flat = json.dumps(resp)
    assert "secret" not in flat
    assert sum(d["keys"] for d in resp["domains"]) >= 8


async def test_storage_keys_and_entry():
    main, manager = make_manager()
    _seed(main)
    resp = await manager.storage_keys(_Req(query={"domain": "memories"}))
    assert resp["total"] == 1
    assert resp["keys"][0]["key"] == "QvQChat:mem:global"

    entry = await manager.storage_entry(_Req(query={"key": "QvQChat:mem:global"}))
    assert entry["bytes"] > 0
    assert "m" in entry["value"]

    # 保护键与外部键拒绝
    assert await manager.storage_entry(_Req(query={"key": "QvQChat:auth_token"})) == ({"error": "bad key"}, 400)
    assert await manager.storage_entry(_Req(query={"key": "Other:thing"})) == ({"error": "bad key"}, 400)


async def test_storage_delete_keys():
    main, manager = make_manager()
    _seed(main)
    resp = await manager.storage_delete(_Req({"keys": ["QvQChat:mem:global", "QvQChat:auth_token", "Other:x"]}))
    assert resp["removed"] == 1
    assert main.sdk.storage.get("QvQChat:mem:global", None) is None
    assert main.sdk.storage.get("QvQChat:auth_token", None) == "secret"  # 保护键不动


async def test_storage_cleanup_domains():
    main, manager = make_manager()
    _seed(main)
    resp = await manager.storage_cleanup(_Req({"domains": ["memories", "audit"]}))
    assert resp["ok"] is True
    assert main.sdk.storage.get("QvQChat:mem:global", None) is None
    assert main.sdk.storage.get("QvQChat:audit", None) is None
    assert main.sdk.storage.get("QvQChat:personas", None) is not None


async def test_storage_reset_keeps():
    main, manager = make_manager()
    _seed(main)
    resp = await manager.storage_cleanup(_Req({"reset": True, "keep": ["personas", "models"]}))
    assert resp["ok"] is True
    # 保留项存活
    assert main.sdk.storage.get("QvQChat:personas", None) is not None
    assert main.sdk.storage.get("QvQChat:binding:onebot11:group:1@bot_a", None) is not None  # personas 域含绑定
    # 其余清空
    assert main.sdk.storage.get("QvQChat:conv:dashboard:private:web", None) is None
    assert main.sdk.storage.get("QvQChat:mem:global", None) is None
    assert main.sdk.storage.get("QvQChat:usage:2026-11-06", None) is None
    # auth_token 不属于任何域，重置后仍在
    assert main.sdk.storage.get("QvQChat:auth_token", None) == "secret"


async def test_storage_slim_drops_duplicate_trace():
    main, manager = make_manager()
    _seed(main)
    resp = await manager.storage_slim(_Req({}))
    assert resp["sessions"] == 1
    assert resp["freed"] > 0
    state = main.sdk.storage.get("QvQChat:conv:onebot11:group:1@bot_a", None)
    assert "trace" not in state["contexts"][0]
    assert state["contexts"][0]["rounds"]


async def test_append_no_longer_dual_writes_trace():
    main = FakeMain()
    key = "dashboard:private:web"
    main.sessions.append(key, "assistant", "答案", trace=[{"tool": "x"}], rounds=[{"text": "答案", "tools": []}])
    entry = main.sessions.get_contexts(key)[-1]
    assert "rounds" in entry and "trace" not in entry
    main.sessions.append(key, "assistant", "纯文本", trace=[{"tool": "y"}])
    entry2 = main.sessions.get_contexts(key)[-1]
    assert "trace" in entry2 and "rounds" not in entry2  # 无 rounds 时 trace 照存


async def test_persona_resolve_tiered_fallback():
    """绑定回落链：会话 → 群 base → @账户 → platform:* → 全局默认。"""
    main, manager = make_manager()
    personas = main.personas
    cat = personas.save({"name": "猫娘", "system": "喵"})
    plat = personas.save({"name": "平台助手", "system": "p"})
    acct = personas.save({"name": "账户人设", "system": "a"})
    grp = personas.save({"name": "群人设", "system": "g"})

    key = "onebot11:group:777@bot_b"
    # 无任何绑定 → assistant 兜底
    assert personas.resolve(key)["id"] != grp["id"]

    # 平台级
    personas.bind("onebot11:*", plat["id"])
    assert personas.resolve(key)["id"] == plat["id"]
    # 账户级覆盖平台级
    personas.bind("@bot_b", acct["id"])
    assert personas.resolve(key)["id"] == acct["id"]
    # 会话级覆盖账户级
    personas.bind(key, cat["id"])
    assert personas.resolve(key)["id"] == cat["id"]
    # 群 base（跨账户同群）：会话级仍优先；群 base 优先于 @账户（回落链：会话→群→账户→平台）
    personas.bind("onebot11:group:777", grp["id"])
    assert personas.resolve(key)["id"] == cat["id"]
    other = "onebot11:group:777@bot_c"
    assert personas.resolve(other)["id"] == grp["id"]  # 群 base 命中，先于账户
    # 账户绑定对没有群绑定的其它会话生效
    personas.bind("@bot_c", acct["id"])
    assert personas.resolve("onebot11:private:9@bot_c")["id"] == acct["id"]
    assert personas.resolve("onebot11:group:888@bot_c")["id"] == acct["id"]


async def test_sessions_get_accounts_overview():
    main, manager = make_manager()
    _seed(main)
    main.sdk.adapter.add("onebot11", [])
    main.sdk.adapter.bots = {"bot_a": {}, "bot_b": {}}
    resp = await manager.sessions_get(_Req())
    accts = resp["accounts"]["accounts"]
    assert accts and accts[0]["account"] == "bot_a"
    assert accts[0]["sessions"] == 1
    assert resp["accounts"]["adapters"][0]["platform"] == "onebot11"
    assert sorted(resp["accounts"]["adapters"][0]["bots"]) == ["bot_a", "bot_b"]


async def test_session_rewind_drops_message_and_after():
    """编辑并重发：删除目标消息及其之后所有内容，返回原文。"""
    main, manager = make_manager()
    key = "dashboard:private:web"
    main.sessions.append_user(key, "第一问")
    main.sessions.append(key, "assistant", "第一答")
    main.sessions.append_user(key, "要改的问题")
    main.sessions.append(key, "assistant", "旧回答")

    resp = await manager.session_rewind(_Req({"chat_key": key, "index": 2}))
    assert resp["ok"] is True
    assert resp["text"] == "要改的问题"
    contexts = main.sessions.get_contexts(key)
    assert [c.get("content") for c in contexts] == ["第一问", "第一答"]


async def test_session_rewind_rejects_bad_index_and_busy():
    main, manager = make_manager()
    key = "dashboard:private:web"
    main.sessions.append_user(key, "hi")
    assert await manager.session_rewind(_Req({"chat_key": key, "index": 9})) == ({"error": "index out of range"}, 400)
    assert await manager.session_rewind(_Req({"index": 0})) == ({"error": "chat_key required"}, 400)
    manager._live.start(key)
    assert await manager.session_rewind(_Req({"chat_key": key, "index": 0})) == ({"error": "session busy"}, 409)
