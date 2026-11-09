import asyncio

from QvQChat.conversation.budget import PRIORITY, _priority
from QvQChat.conversation.todo import TODO_MAX, TodoStore
from QvQChat.tools_builtin import todo as todo_tools

from fakes import FakeMain, make_ctx


def make_store():
    main = FakeMain()
    return main, TodoStore(main.sdk, main.cfg)


async def test_todo_replace_and_render():
    main, store = make_store()
    items = store.replace("chat:1", ["第一步", "第二步", "第三步"])
    assert [i["status"] for i in items] == ["pending", "pending", "pending"]
    assert len({i["id"] for i in items}) == 3
    assert store.render("chat:1") == "[ ] 第一步\n[ ] 第二步\n[ ] 第三步"
    # 空清单 render 为空串（不注入部件）
    assert store.render("chat:none") == ""


async def test_todo_update_status_flow():
    main, store = make_store()
    items = store.replace("chat:1", ["查资料", "写报告"])
    tid = items[0]["id"]
    updated = store.update("chat:1", tid, status="in_progress")
    assert updated["status"] == "in_progress"
    assert store.render("chat:1").startswith("[~] 查资料")
    store.update("chat:1", tid, status="completed")
    assert store.render("chat:1").startswith("[x] 查资料")
    # 非法状态 / 不存在 id
    assert store.update("chat:1", tid, status="bogus") is None
    assert store.update("chat:1", "nope", status="completed") is None


async def test_todo_replace_keeps_in_progress():
    """全量重写保留进行中的条目（不易丢正在做的任务）。"""
    main, store = make_store()
    items = store.replace("chat:1", ["旧任务A", "旧任务B"])
    store.update("chat:1", items[0]["id"], status="in_progress")
    fresh = store.replace("chat:1", ["新计划"])
    contents = [i["content"] for i in fresh]
    assert "新计划" in contents
    assert "旧任务A" in contents and "旧任务B" not in contents
    kept = next(i for i in fresh if i["content"] == "旧任务A")
    assert kept["status"] == "in_progress"


async def test_todo_add_and_cap():
    main, store = make_store()
    for n in range(TODO_MAX + 5):
        store.add("chat:1", f"任务{n}")
    items = store.items("chat:1")
    assert len(items) == TODO_MAX


async def test_todo_clear_on_session_delete():
    main, store = make_store()
    store.replace("chat:del", ["事情"])
    assert store.items("chat:del")
    main.sessions.delete("chat:del")
    assert store.items("chat:del") == []


async def test_todo_tools_end_to_end():
    main = FakeMain()
    ctx = make_ctx(main=main, chat_key="test:group:9")
    out = await todo_tools.todo_write(ctx, ["摸鱼", "干活"])
    assert '"updated": 2' in out or '"updated":2' in out
    items = main.conversations.todos.items("test:group:9")
    tid = items[1]["id"]
    out = await todo_tools.todo_update(ctx, tid, status="in_progress")
    assert '"in_progress"' in out
    out = await todo_tools.todo_list(ctx)
    assert "干活" in out
    # 非法状态工具层报错不抛
    out = await todo_tools.todo_update(ctx, tid, status="nope")
    assert '"ok": false' in out or '"ok":false' in out


async def test_todo_tools_registered():
    from QvQChat.agent.tools import ToolRegistry

    reg = ToolRegistry()
    todo_tools.register(reg, FakeMain())
    for name in ("todo_write", "todo_update", "todo_list"):
        tool = reg.get(name)
        assert tool is not None and tool.access == "safe"


async def test_todo_budget_priority():
    assert PRIORITY["todo"] == 4.2
    assert _priority("todo") == 4.2
    # 预算裁剪顺序（数值越小越重要）：todo 比 kb/技能列表更保命，比 profile 更先被裁
    assert _priority("todo") < _priority("profile")
    assert _priority("kb") > _priority("todo") > _priority("facts")
