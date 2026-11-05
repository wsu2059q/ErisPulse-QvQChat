import json
import shutil
from pathlib import Path

from QvQChat.dashboard.manager import DashboardManager
from QvQChat.tools_builtin import computer, takumi

from fakes import FakeMain, make_ctx

TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


# ── view_image 看图工具 ──


async def test_view_image_returns_image_path():
    ctx = make_ctx()
    target = Path("data/QvQChat/uploads/_test_view.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"png")
    try:
        out = json.loads(await computer.view_image(ctx, str(target)))
        assert out["image_path"].endswith("_test_view.png")
    finally:
        target.unlink(missing_ok=True)


async def test_view_image_rejects_non_image():
    ctx = make_ctx()
    target = Path("data/QvQChat/uploads/_test_view.txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello")
    try:
        out = await computer.view_image(ctx, str(target))
        assert "png/jpg" in out or "image" in out
    finally:
        target.unlink(missing_ok=True)


async def test_view_image_missing_file():
    ctx = make_ctx()
    out = await computer.view_image(ctx, "no/such/image.png")
    assert "no/such/image.png" in out


# ── Takumi render_image ──


def _takumi_main():
    main = FakeMain(catalog={"Takumi": object()})
    main.sdk.module.handlers[("Takumi", "render_card")] = lambda **kw: {
        "path": "/tmp/rendered.png", "bytes": len(kw.get("html", "")),
    }
    return main


async def test_render_image_calls_takumi_and_returns_path():
    ctx = make_ctx(main=_takumi_main())
    out = json.loads(await takumi.render_image(ctx, html="<h1>日报</h1>", width=600))
    assert out["image_path"] == "/tmp/rendered.png"


async def test_render_image_without_takumi_reports():
    ctx = make_ctx()
    out = await takumi.render_image(ctx, html="<h1>x</h1>")
    assert "Takumi" in out


def test_render_image_registered_only_with_takumi():
    registry = takumi.__dict__ and __import__("QvQChat.agent.tools", fromlist=["ToolRegistry"]).ToolRegistry()
    takumi.register(registry, _takumi_main())
    assert any(t.name == "render_image" for t in registry.list())
    empty = __import__("QvQChat.agent.tools", fromlist=["ToolRegistry"]).ToolRegistry()
    takumi.register(empty, FakeMain())
    assert not any(t.name == "render_image" for t in empty.list())


# ── 图片附件落盘 + 编辑带附件 ──


def _manager():
    return DashboardManager(FakeMain())


async def test_parse_chat_body_saves_image_upload():
    mgr = _manager()
    text, images, session, skills, mcp, persona, model, temp = mgr._parse_chat_body({
        "text": "看看这张图",
        "attachments": [{"name": "shot.png", "mime": "image/png", "data": TINY_PNG}],
    })
    try:
        assert len(images) == 1 and images[0].startswith("data:image/png")
        assert "[attachment shot.png]" in text and "uploads" in text and "shot.png" in text
    finally:
        shutil.rmtree("data/QvQChat/uploads", ignore_errors=True)


async def test_rebuild_user_content_with_attachments():
    mgr = _manager()
    try:
        content = mgr.main.conversations.rebuild_user_content("改过的文字", [
            {"name": "pic.png", "mime": "image/png", "data": TINY_PNG},
        ])
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": "改过的文字"}
        assert content[1]["type"] == "image_url"

        content2 = mgr.main.conversations.rebuild_user_content("带文件", [
            {"name": "doc.zip", "mime": "application/zip", "data": TINY_PNG},
        ])
# 只有文件没有图片时回落为纯文本（说明文字并入文本段）
        body_text = content2 if isinstance(content2, str) else content2[0]["text"]
        assert "doc.zip" in body_text and "uploads" in body_text

# 清空附件：只余文本
        assert mgr.main.conversations.rebuild_user_content("纯文本", []) == "纯文本"
    finally:
        shutil.rmtree("data/QvQChat/uploads", ignore_errors=True)


async def test_session_context_edit_replaces_attachments():
    mgr = _manager()
    main = mgr.main
    key = "dashboard:private:web"
    main.sessions.append_user(key, "旧消息", sender_id="dashboard")
    contexts = main.sessions.get_contexts(key)
    index = len(contexts) - 1
    try:
        body = {"chat_key": key, "index": index, "content": "新文字",
                "attachments": [{"name": "pic.png", "mime": "image/png", "data": TINY_PNG}]}

        class FakeRequest:
            async def json(self):
                return body

        resp = await mgr.session_context_edit(FakeRequest())
        assert resp == {"ok": True}
        updated = main.sessions.get_contexts(key)[index]
        assert updated["content"][0]["text"] == "新文字"
        assert updated["content"][1]["type"] == "image_url"
    finally:
        shutil.rmtree("data/QvQChat/uploads", ignore_errors=True)
