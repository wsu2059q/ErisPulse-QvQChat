import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

from QvQChat.bridge.docs import (
    DOCS_BRANCH_ZIP,
    ErisPulseDocs,
    GITHUB_ZIP,
    _chunk_markdown,
    framework_version,
)

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

# 隔离 MCP 缓存兜底（真实机器上可能有 epsdk-mcp 的缓存）
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


# ===== 文档下载源：docs-generated 分支优先（小包），tag 兜底 =====


class _Resp:
    def __init__(self, status, data):
        self.status = status
        self._data = data

    async def read(self):
        return self._data


class _SeqClient:
    """按路由表依次应答的假 client：记录请求顺序，供 URL 链断言。"""

    def __init__(self, routes):
        self.routes = list(routes)
        self.requests = []

    async def get(self, url, **kwargs):
        self.requests.append(url)
        status, data = self.routes.pop(0) if self.routes else (404, b"")
        return _Resp(status, data)


def _branch_zip() -> bytes:
    """docs-generated 分支布局：仓库根 README（应过滤）+ docs/<lang> 树 + skills.zip（应过滤）。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("ErisPulse-docs-generated/README.zh-CN.md", "# 分支根 README\n不在 docs/ 下")
        archive.writestr("ErisPulse-docs-generated/docs/zh-CN/README.md", "# 中文文档\n概览")
        archive.writestr("ErisPulse-docs-generated/docs/zh-CN/ai-support/prompts/ModuleDev.md", "# 提示词素材\n内容")
        archive.writestr("ErisPulse-docs-generated/docs/zh-CN/ai-support/skills.zip", "PK-not-a-md")
    return buffer.getvalue()


def test_extract_docs_generated_layout(tmp_path):
    main = FakeMain(docs_dir=str(tmp_path / "cache"))
    docs = ErisPulseDocs(main)
    written = docs._extract(_branch_zip(), "2.12.0")
    assert written == 2  # README.md + prompts/ModuleDev.md；根 README 与 skills.zip 过滤
    root = tmp_path / "cache" / "2.12.0" / "zh-CN"
    assert (root / "README.md").is_file()
    assert (root / "ai-support" / "prompts" / "ModuleDev.md").is_file()
    assert not (root / "ai-support" / "skills.zip").exists()


async def test_download_prefers_branch_then_falls_back_to_tag(tmp_path, monkeypatch):
    import QvQChat.bridge.docs as docs_module

    monkeypatch.setattr(docs_module, "MCP_CACHE", tmp_path / "no-mcp-cache")
    main = FakeMain(docs_dir=str(tmp_path / "cache"))
    main.sdk.client = _SeqClient([
        (404, b""),  # docs-generated 分支失联（演练）
        (200, _branch_zip()),  # tag 兜底包成功
    ])
    docs = ErisPulseDocs(main)
    result = await docs._download("2.12.0")
    assert result["source"] == "github" and result["files"] == 2
    assert main.sdk.client.requests == [
        DOCS_BRANCH_ZIP,
        GITHUB_ZIP.format(tag="v2.12.0"),
    ]
