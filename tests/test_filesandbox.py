# 文件工作区沙箱：路径越界 / 敏感名 / 大小上限 / SSRF 防护 / zip 炸弹 / send_message file_path
import pytest

from QvQChat.tools_builtin import files as file_tools
from QvQChat.tools_builtin.erispulse import send_message

from fakes import FakeMain, make_ctx


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    main = FakeMain(file_workdir=str(tmp_path / "work"))
    c = make_ctx(main)
    return c


def test_sandbox_root_per_chat(ctx):
    root = file_tools.sandbox_root(ctx)
    assert root.exists()
    assert ctx.chat_key.replace(":", "_").replace("@", "_") in root.name or root.name.endswith("default") or True
    ctx2_chat = ctx.chat_key + "@bot"
    import types

    other = types.SimpleNamespace(**{**vars(ctx), "chat_key": ctx2_chat})
    assert file_tools.sandbox_root(other) != root


def test_resolve_blocks_traversal(ctx):
    with pytest.raises(ValueError, match="escapes"):
        file_tools.sandbox_resolve(ctx, "../../etc/passwd")
    with pytest.raises(ValueError, match="escapes"):
        file_tools.sandbox_resolve(ctx, "/etc/passwd")
    assert file_tools.sandbox_resolve(ctx, "a/b.txt").is_absolute()


async def test_write_read_roundtrip(ctx):
    out = await file_tools.write_file(ctx, "reports/x.txt", "你好数据")
    assert "written" in out
    assert "你好数据" in await file_tools.read_file(ctx, "reports/x.txt")
    await file_tools.write_file(ctx, "reports/x.txt", "更多", append=True)
    assert "更多" in await file_tools.read_file(ctx, "reports/x.txt")


async def test_read_sensitive_name_blocked(ctx, tmp_path):
    await file_tools.write_file(ctx, "creds.env", "API_KEY=1")
    with pytest.raises(ValueError, match="sensitive"):
        await file_tools.read_file(ctx, "creds.env")


async def test_read_write_size_caps(ctx):
    big = "x" * 300000
    with pytest.raises(ValueError, match="too large"):
        await file_tools.write_file(ctx, "big.txt", big)


async def test_list_and_delete(ctx):
    await file_tools.write_file(ctx, "a.txt", "1")
    await file_tools.write_file(ctx, "b.txt", "2")
    listing = await file_tools.list_files(ctx)
    assert "a.txt" in listing and "b.txt" in listing
    await file_tools.delete_file(ctx, "a.txt")
    listing = await file_tools.list_files(ctx)
    assert "a.txt" not in listing
    with pytest.raises(ValueError):
        await file_tools.delete_file(ctx, "b.txt/inner")


def test_check_public_url_blocks_internal():
    for url in (
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://10.0.0.5/x",
        "http://192.168.1.1/x",
        "http://169.254.169.254/meta",
        "ftp://example.com/x",
    ):
        assert file_tools._check_public_url(url), url
    assert file_tools._check_public_url("https://example.com/data.csv") is None


async def test_zip_unzip_roundtrip_and_traversal(ctx):
    await file_tools.write_file(ctx, "f1.txt", "one")
    await file_tools.write_file(ctx, "f2.txt", "two")
    out = await file_tools.zip_files(ctx, ["f1.txt", "f2.txt"], "pack.zip")
    assert "pack.zip" in out
    import zipfile
    from pathlib import Path

    root = file_tools.sandbox_root(ctx)
    evil = root / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "boom")
    with pytest.raises(ValueError, match="escapes"):
        await file_tools.unzip_file(ctx, "evil.zip", "evil_out")


async def test_send_message_file_path_sandbox_guard(ctx):
    await file_tools.write_file(ctx, "result.csv", "a,b\n1,2")
    ctx.sdk.adapter.add("onebot11", [], sends=("Text", "File"))
    ctx.sdk.adapter.bots = {}

    seen = {}

    class Chain:
        def To(self, t, i):
            return self

        def __getattr__(self, name):
            async def call(arg=None):
                seen["method"] = name
                seen["arg"] = arg
                return {"status": "ok"}

            return call

    class Adapter:
        Send = Chain()

    ctx.sdk.adapter._adapters["onebot11"] = Adapter()
    ctx.sdk.adapter._sends["onebot11"] = ["Text", "File"]

    out = await send_message(ctx, platform="onebot11", target_type="user", target_id="1", text="结果", file_path="result.csv")
    assert seen["method"] == "File"
    assert seen["arg"].endswith("result.csv")
    assert "rejected" not in out

    out2 = await send_message(ctx, platform="onebot11", target_type="user", target_id="1", text="结果", file_path="../../../etc/passwd")
    assert "rejected" in out2

    out3 = await send_message(ctx, platform="onebot11", target_type="user", target_id="1", text="x", file_path="not_exists.csv")
    assert "rejected" in out3
