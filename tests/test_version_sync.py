"""版本防呆：pyproject 构建版本与运行时 __version__ 必须一致。"""
import re
from pathlib import Path

from QvQChat.version import __version__


def test_pyproject_version_matches_runtime():
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml 缺少 version 字段"
    assert match.group(1) == __version__, (
        f"pyproject.toml version={match.group(1)} 与 QvQChat/version.py __version__={__version__} 不一致——"
        "发版要同步改两处（或改为 hatch dynamic 从 version.py 读）"
    )
