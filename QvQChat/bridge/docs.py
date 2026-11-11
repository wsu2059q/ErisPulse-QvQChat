"""内置 ErisPulse 文档检索（不依赖 MCP）。

文档来源就是框架仓库 docs/ 目录（按版本 tag 发布），因此不需要额外协议层：
1. 启动/每日检查：本地缓存版本 vs 已安装框架版本，不一致则按 tag 下载 zip 解压
2. 本地目录源（docs_source）可直接指向框架仓库 docs/，开发环境零网络
3. 离线兜底：复用 epsdk-mcp 的 ~/.cache/erispulse-mcp/docs 缓存（若存在）
4. 检索：markdown 按标题切块 + 词面打分（与知识库同一套 bigram 打分）
"""
from __future__ import annotations

import asyncio
import io
import re
import time
import zipfile
from pathlib import Path

from .. import texts, utils

META_KEY = "QvQChat:docs_meta"
DEFAULT_DOCS_DIR = "data/QvQChat/docs"
GITHUB_ZIP = "https://codeload.github.com/ErisPulse/ErisPulse/zip/refs/tags/{tag}"
MCP_CACHE = Path.home() / ".cache" / "erispulse-mcp" / "docs"
CHUNK_CHARS = 1200
MAX_FILES = 400

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def framework_version() -> str:
    """已安装框架版本：dist metadata 优先，包属性兜底。"""
    try:
        from importlib.metadata import version as _version

        return str(_version("ErisPulse") or "")
    except Exception:
        pass
    try:
        import ErisPulse as _ep

        return str(getattr(_ep, "__version__", "") or "")
    except Exception:
        return ""


def _chunk_markdown(text: str, doc_title: str) -> list[dict]:
    """按标题切块；超长块再按空行切到 CHUNK_CHARS 以内。"""
    chunks: list[dict] = []
    heading = doc_title
    buffer: list[str] = []

    def flush():
        body = "\n".join(buffer).strip()
        buffer.clear()
        if not body:
            return
        if len(body) <= CHUNK_CHARS:
            chunks.append({"title": heading or doc_title, "content": body})
            return
        part: list[str] = []
        size = 0
        for para in re.split(r"\n{2,}", body):
            if size and size + len(para) > CHUNK_CHARS:
                chunks.append({"title": heading or doc_title, "content": "\n\n".join(part)})
                part, size = [], 0
            part.append(para)
            size += len(para) + 2
        if part:
            chunks.append({"title": heading or doc_title, "content": "\n\n".join(part)})

    for line in text.splitlines():
        match = HEADING_RE.match(line.strip())
        if match:
            flush()
            heading = match.group(2).strip() or doc_title
            continue
        buffer.append(line)
    flush()
    return chunks


class ErisPulseDocs:
    """文档缓存 + 索引 + 检索（async 同步，sync 检索）。"""

    def __init__(self, main):
        self.main = main
        self.sdk = main.sdk
        self.config = main.cfg
        self._index: list[dict] | None = None
        self._index_version = ""
        self._lock = asyncio.Lock()

    # ==================== 路径与元数据 ====================

    def docs_dir(self) -> Path:
        raw = str(getattr(self.config, "docs_dir", "") or DEFAULT_DOCS_DIR)
        return Path(raw).expanduser()

    def lang(self) -> str:
        return str(getattr(self.config, "docs_lang", "zh-CN") or "zh-CN")

    def _meta(self) -> dict:
        data = self.sdk.storage.get(META_KEY, {})
        return dict(data) if isinstance(data, dict) else {}

    def _set_meta(self, **updates) -> None:
        meta = self._meta()
        meta.update(updates)
        try:
            self.sdk.storage.set(META_KEY, meta)
        except Exception as e:
            self.main.logger.debug(f"docs meta persist failed: {e}")

    def cached_version(self) -> str:
        return str(self._meta().get("version") or "")

    # ==================== 本地源解析 ====================

    def _local_source_root(self) -> Path | None:
        raw = str(getattr(self.config, "docs_source", "") or "").strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_dir():
            return None
        return self._lang_root(path)

    def _lang_root(self, base: Path) -> Path:
        """在候选目录里定位语言子目录：配置的语言优先，base 本身是语言目录则原样返回。"""
        if not base.is_dir():
            return base
        preferred = base / self.lang()
        if preferred.is_dir() and any(preferred.glob("**/*.md")):
            return preferred
        if any(base.glob("*.md")):
            return base
        for candidate in sorted(p for p in base.iterdir() if p.is_dir()):
            if any(candidate.glob("*.md")):
                return candidate
        return base

    def _cache_root(self, version: str) -> Path:
        return self.docs_dir() / (version or "latest") / self.lang()

    def _mcp_cache_root(self) -> Path | None:
        if not MCP_CACHE.is_dir():
            return None
        return self._lang_root(MCP_CACHE)

    def active_root(self) -> Path | None:
        """当前生效的文档根目录（本地源 > 版本缓存 > MCP 缓存）。"""
        local = self._local_source_root()
        if local is not None:
            return local
        cached = self._cache_root(self.cached_version())
        if cached.is_dir() and any(cached.glob("**/*.md")):
            return cached
        return self._mcp_cache_root()

    # ==================== 同步 ====================

    async def ensure_synced(self, force: bool = False) -> dict:
        """文档与已安装框架版本对齐；网络失败时沿用本地缓存，不阻塞启动。"""
        if not bool(getattr(self.config, "docs_builtin", True)):
            return {"enabled": False}
        if self._local_source_root() is not None:
            self._set_meta(version=f"local:{framework_version() or 'dev'}", source="local", synced_at=time.time())
            self._invalidate()
            return {"enabled": True, "source": "local", "root": str(self._local_source_root())}
        version = framework_version() or "latest"
        meta = self._meta()
        last_check = float(meta.get("checked_at") or 0)
        auto = bool(getattr(self.config, "docs_auto_sync", True))
        if not force:
            if self.cached_version() == version and self.active_root() is not None:
                return {"enabled": True, "source": "cache", "version": version, "cached": True}
            if not auto:
                root = self.active_root()
                return {"enabled": True, "source": "stale", "version": self.cached_version(),
                        "root": str(root) if root else ""}
# 非强制时每日最多尝试一次下载，离线环境不会反复撞网
            if last_check and time.time() - last_check < 86400:
                root = self.active_root()
                return {"enabled": True, "source": "stale", "version": self.cached_version(),
                        "root": str(root) if root else "", "throttled": True}
        async with self._lock:
            if not force and self.cached_version() == version and self.active_root() is not None:
                return {"enabled": True, "source": "cache", "version": version, "cached": True}
            result = await self._download(version)
            self._set_meta(checked_at=time.time())
            return result

    async def _download(self, version: str) -> dict:
        custom = str(getattr(self.config, "docs_source", "") or "").strip()
        if custom.startswith(("http://", "https://")):
            urls = [custom]
        else:
            tags = [f"v{version}"] if version and version != "latest" else []
            tags.append(version)
            urls = [GITHUB_ZIP.format(tag=tag) for tag in tags]
        last_error = ""
        for url in urls:
            try:
                data = await self._fetch_bytes(url)
                if not data:
                    continue
                written = self._extract(data, version)
                if written:
                    self._set_meta(version=version, source=url, synced_at=time.time())
                    self._invalidate()
                    self.main.logger.info(f"docs synced for framework {version}: {written} files")
                    return {"enabled": True, "source": "github", "version": version,
                            "root": str(self._cache_root(version)), "files": written}
            except Exception as e:
                last_error = str(e)
                self.main.logger.debug(f"docs download failed ({url}): {e}")
        root = self.active_root()
        if last_error:
            self.main.logger.warning(f"docs sync failed for {version}: {last_error}")
        return {"enabled": True, "source": "stale", "version": self.cached_version(),
                "root": str(root) if root else "", "error": last_error}

    async def _fetch_bytes(self, url: str) -> bytes:
        timeout = float(getattr(self.config, "docs_timeout", 30) or 30)
        client = getattr(self.sdk, "client", None)
        if client is not None and hasattr(client, "get"):
            resp = await client.get(url, timeout=timeout)
            status = getattr(resp, "status", 200)
            if status != 200:
                raise RuntimeError(f"HTTP {status}")
            read = getattr(resp, "read", None)
            if callable(read):
                return await read()
            content = getattr(resp, "content", None)
            if content is not None:
                return await content.read() if hasattr(content, "read") else bytes(content)
        # 退化路径（测试/无 sdk.client）：urllib 在线程里跑
        import urllib.request

        def _blocking() -> bytes:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.read()

        return await asyncio.to_thread(_blocking)

    def _extract(self, data: bytes, version: str) -> int:
        """从 GitHub zip 中只取 docs/<lang>/ 下的 markdown。"""
        target = self._cache_root(version)
        target.mkdir(parents=True, exist_ok=True)
        lang = self.lang()
        written = 0
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".md"):
                    continue
                parts = info.filename.split("/")
                if "docs" not in parts:
                    continue
                idx = parts.index("docs")
                rest = parts[idx + 1:]
                if not rest:
                    continue
                relative = Path(*rest)
                if len(rest) >= 2 and rest[0] == lang:
                    relative = Path(*rest[1:])
                elif len(rest) >= 1 and rest[0] != lang:
# 只收目标语言目录（docs/README.md 除外），避免把多语言全塞进同一索引
                    if len(rest) > 1:
                        continue
                dest = target / relative
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(archive.read(info))
                    written += 1
                except Exception:
                    continue
        return written

    async def maybe_sync_daily(self) -> None:
        """调度器每日调用：与 ensure_synced 同样的节流语义。"""
        try:
            await self.ensure_synced()
        except Exception as e:
            self.main.logger.debug(f"docs daily sync failed: {e}")

    # ==================== 索引与检索 ====================

    def _invalidate(self) -> None:
        self._index = None
        self._index_version = ""

    def _build_index(self) -> list[dict]:
        version = self.cached_version() or "local"
        if self._index is not None and self._index_version == version:
            return self._index
        root = self.active_root()
        index: list[dict] = []
        if root is not None and root.is_dir():
            files = sorted(root.rglob("*.md"))[:MAX_FILES]
            for path in files:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                doc_title = text.splitlines()[0].lstrip("# ").strip() if text.strip() else path.stem
                try:
                    relative = str(path.relative_to(root)).replace("\\", "/")
                except Exception:
                    relative = path.name
                for chunk in _chunk_markdown(text, doc_title):
                    index.append({"file": relative, **chunk})
        self._index = index
        self._index_version = version
        return index

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query = str(query or "").strip()
        if not query:
            return []
        scored: list[tuple[float, dict]] = []
        for chunk in self._build_index():
            title_score = utils.overlap_score(query, chunk["title"]) * 1.5
            body_score = utils.overlap_score(query, chunk["content"])
            score = title_score + body_score
            if score <= 0:
                continue
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, chunk in scored[: max(1, int(top_k or 5))]:
            snippet = chunk["content"][:600]
            results.append({"file": chunk["file"], "title": chunk["title"],
                            "snippet": snippet, "score": round(score, 3)})
        return results

    def read(self, file: str, limit: int = 8000) -> str:
        root = self.active_root()
        if root is None:
            return texts.t("docs_not_ready")
        try:
            resolved = (root / str(file or "")).resolve()
            root_resolved = root.resolve()
        except Exception as e:
            return texts.t("docs_read_failed", error=e)
# 路径穿越防护：只允许读取文档根目录内的文件
        if not str(resolved).startswith(str(root_resolved)):
            return texts.t("docs_path_denied")
        if not resolved.is_file():
            return texts.t("docs_not_found", file=file)
        try:
            text = resolved.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return texts.t("docs_read_failed", error=e)
        return utils.truncate(text, limit)

    def status(self) -> dict:
        root = self.active_root()
        return {
            "framework_version": framework_version(),
            "cached_version": self.cached_version(),
            "root": str(root) if root else "",
            "chunks": len(self._build_index()),
            "lang": self.lang(),
        }
