"""版本防呆：pyproject 构建版本与运行时 __version__ 必须一致。

只在 version.py bump、漏改 pyproject 会导致构建出的 wheel 仍是旧版本号
（发布事故重现过一次）——用测试把两处锁死。
"""
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
