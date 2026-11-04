import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from QvQChat.bridge.docs import ErisPulseDocs, _chunk_markdown, framework_version

from fakes import FakeLogger, FakeSDK, make_config


class FakeMain:
    def __init__(self, **overrides):
        self.cfg = make_config(**overrides)
        self.sdk = FakeSDK()
        self.logger = FakeLogger()


def write_docs(root: Path, lang: str = "zh-CN") -> Path:
    base = root / "docs" / lang
    (base / "developer-guide").mkdir(parents=True)
    (base / "README.md").write_text("# ErisPulse 文档\n\n概览内容。\n", encoding="utf-8")
    (base / "developer-guide" / "module.md").write_text(
        "# 模块开发\n\n## 生命周期\n\nBaseModule 提供 on_load / on_unload 生命周期回调。\n\n"
        "## 服务声明\n\n在 get_meta 的 services 里声明服务名，未声明会被 sdk.module.call 拒绝。\n",
        encoding="utf-8",
    )
    return root / "docs"


def test_chunk_markdown_splits_by_heading():
    chunks = _chunk_markdown("# T\n\n## A\n内容A\n\n## B\n内容B", "T")
    titles = [c["title"] for c in chunks]
    assert "A" in titles and "B" in titles


async def test_local_source_indexing_and_search(tmp_path):
    docs_root = write_docs(tmp_path)
    main = FakeMain(docs_source=str(docs_root))
    docs = ErisPulseDocs(main)
    info = await docs.ensure_synced()
    assert info["source"] == "local"
    results = docs.search("生命周期 on_load")
    assert results and results[0]["file"].endswith("module.md")
    assert "on_load" in results[0]["snippet"]
    full = docs.read(results[0]["file"])
    assert "BaseModule" in full


async def test_search_empty_without_docs(tmp_path, monkeypatch):
    import QvQChat.bridge.docs as docs_module

 
    monkeypatch.setattr(docs_module, "MCP_CACHE", tmp_path / "no-mcp-cache")
    main = FakeMain(docs_source=str(tmp_path / "missing"))
    docs = ErisPulseDocs(main)
    assert docs.search("anything") == []
    assert "文档" in docs.read("a.md") or "docs" in docs.read("a.md").lower()


async def test_read_blocks_path_traversal(tmp_path):
    docs_root = write_docs(tmp_path)
    main = FakeMain(docs_source=str(docs_root))
    docs = ErisPulseDocs(main)
    await docs.ensure_synced()
    assert "拒绝" in docs.read("../../etc/passwd") or "denied" in docs.read("../../etc/passwd").lower()


def test_extract_zip_keeps_language_dir(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("ErisPulse-2.11.2/docs/zh-CN/README.md", "# 中文\n内容")
        archive.writestr("ErisPulse-2.11.2/docs/zh-CN/guide/a.md", "# 指南\n内容")
        archive.writestr("ErisPulse-2.11.2/docs/en/README.md", "# English\ncontent")
    main = FakeMain(docs_dir=str(tmp_path / "cache"))
    docs = ErisPulseDocs(main)
    written = docs._extract(buffer.getvalue(), "2.11.2")
    assert written == 2
    root = tmp_path / "cache" / "2.11.2" / "zh-CN"
    assert (root / "README.md").is_file()
    assert (root / "guide" / "a.md").is_file()
    assert not (root / "en").exists()


def test_framework_version_returns_string():
    assert isinstance(framework_version(), str)
