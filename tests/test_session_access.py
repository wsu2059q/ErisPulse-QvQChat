import asyncio
from QvQChat.conversation.service import make_chat_key, strip_isolation
from QvQChat.conversation.knowledge import KnowledgeBase, chunk_text
from QvQChat.Main import Main
from fakes import FakeChatEvent, FakeMain


def make_kb(cfg=None):
    import sys
    sys.path.insert(0, "tests")
    from fakes import FakeSDK
    return KnowledgeBase(FakeSDK(), cfg)


class Cfg:
    kb_chunk_size = 100
    kb_chunk_overlap = 10


def test_strip_isolation_only_group():
    assert strip_isolation("onebot11:group:1:u9") == "onebot11:group:1"
    assert strip_isolation("onebot11:private:u1") == "onebot11:private:u1"
    assert strip_isolation("onebot11:group:1") == "onebot11:group:1"


def test_route_resolution_direct_and_base():
    main = FakeMain()
    svc = main.sessions
    svc.save_routes({"onebot11:group:1": "dashboard:private:web2"})
    assert svc.resolve_route("onebot11:group:1") == "dashboard:private:web2"
    assert svc.resolve_route("onebot11:group:1:u9") == "dashboard:private:web2"
    assert svc.resolve_route("onebot11:group:2") == ""
    assert svc.routes_into("dashboard:private:web2") == ["onebot11:group:1"]


def test_member_allowlist():
    main = FakeMain()
    svc = main.sessions
    key = make_chat_key("onebot11", "group", "1")
    assert svc.member_allowed(key, "9") is True
    svc.set_members(key, ["9", "onebot11:11"])
    assert svc.members_of(key) == ["9", "onebot11:11"]
    assert svc.member_allowed(key, "9", "onebot11") is True
    assert svc.member_allowed(key, "11", "onebot11") is True
    assert svc.member_allowed(key, "77", "onebot11") is False
    svc.set_members(key, [])
    assert svc.members_of(key) == ["*"]


async def test_on_message_respects_route_and_members():
    from test_aggregate import make_main

    main = make_main(aggregate_window=0.01)
    main.sessions.save_routes({"onebot11:group:1": "dashboard:private:web2"})
    main.sessions.set_members("dashboard:private:web2", ["9"])

    class Ev(FakeChatEvent):
        pass

    ev1 = Ev(text="在吗", group=True, group_id="1", user_id="9", at=True)
    await Main._on_message(main, ev1)
    ev2 = Ev(text="我也在", group=True, group_id="1", user_id="77", at=True)
    await Main._on_message(main, ev2)
    await asyncio.sleep(0.1)
    assert len(main.captured) == 1


def test_kb_chunk_params_from_config():
    kb = make_kb(Cfg())
    text = "字" * 250
    kb.add("doc", text)
    chunks = kb.chunk(text)
    assert all(len(c) <= 100 for c in chunks)
    assert kb.stats()["chunks"] >= 3
    default_kb = make_kb()
    assert len(default_kb.chunk("字" * 250)[0]) <= 400


def test_kb_export_import():
    kb = make_kb()
    kb.add("规则", "每周五发周报", source="hr")
    entries = kb.export()
    kb2 = make_kb()
    added = kb2.import_entries(entries)
    assert added == 1
    assert kb2.list()[0]["title"] == "规则"
    assert kb2.import_entries([{"title": "", "content": ""}]) == 0
