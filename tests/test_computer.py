import os

from QvQChat.tools_builtin import computer

from fakes import make_ctx


async def _granted(ctx, text, timeout=60):
    return True


async def _denied(ctx, text, timeout=60):
    return False


async def test_run_command_denied_in_strict():
    ctx = make_ctx(admins=["1"], security_level="strict")
    out = await computer.run_command(ctx, "echo hi")
    assert "strict" in out


async def test_run_command_blocked_pattern():
    ctx = make_ctx(admins=["1"], blocked_patterns=["shutdown"])
    out = await computer.run_command(ctx, "shutdown /s")
    assert "shutdown" in out


async def test_run_command_danger_requires_confirm_in_standard():
    ctx = make_ctx(admins=["1"])
    ctx.confirmer = _denied
    out = await computer.run_command(ctx, "taskkill /f /pid 999999")
    assert "cancel" in out.lower() or "取消" in out
    ctx.confirmer = _granted
    out = await computer.run_command(ctx, "taskkill /f /pid 999999")
    assert "cancel" not in out.lower() and "取消" not in out


async def test_run_command_safe_executes_without_confirm():
    ctx = make_ctx(admins=["1"])
    out = await computer.run_command(ctx, "echo qvq-ok")
    assert "qvq-ok" in out


async def test_run_command_permissive_skips_confirm():
    ctx = make_ctx(admins=["1"], security_level="permissive")
    out = await computer.run_command(ctx, "taskkill /f /pid 999999")
    assert "cancel" not in out.lower() and "取消" not in out


async def test_run_command_non_admin_denied_by_default():
    ctx = make_ctx()
    out = await computer.run_command(ctx, "echo hi")
    assert "echo hi" not in out


async def test_admin_gate_when_configured():
    ctx = make_ctx(admins=["10001"])
    out = await computer.run_command(ctx, "echo hi")
    assert "echo hi" not in out


async def test_path_confinement(tmp_path):
    inside = tmp_path / "in"
    inside.mkdir()
    (inside / "a.txt").write_text("hello", encoding="utf-8")
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / "b.txt").write_text("secret", encoding="utf-8")
    ctx = make_ctx(work_dirs=[str(inside)])
    out = await computer.read_file(ctx, str(inside / "a.txt"))
    assert "hello" in out
    out = await computer.read_file(ctx, str(outside / "b.txt"))
    assert "secret" not in out
    ctx = make_ctx(work_dirs=[str(inside)], security_level="permissive")
    out = await computer.read_file(ctx, str(outside / "b.txt"))
    assert "secret" in out


async def test_read_file_missing_and_write(tmp_path):
    inside = tmp_path / "w"
    inside.mkdir()
    ctx = make_ctx(admins=["1"], work_dirs=[str(inside)])
    out = await computer.read_file(ctx, str(inside / "nope.txt"))
    assert "nope" in out
    ctx.confirmer = _granted
    out = await computer.write_file(ctx, str(inside / "new.txt"), "data")
    assert "new.txt" in out
    assert (inside / "new.txt").read_text(encoding="utf-8") == "data"


async def test_write_file_non_admin_denied(tmp_path):
    inside = tmp_path / "w2"
    inside.mkdir()
    ctx = make_ctx(work_dirs=[str(inside)])
    out = await computer.write_file(ctx, str(inside / "new.txt"), "data")
    assert "new.txt" not in out


def test_danger_pattern_detection():
    ctx = make_ctx()
    assert computer._is_dangerous(ctx, "rm -rf /data/x")
    assert computer._is_dangerous(ctx, "shutdown -h now")
    assert not computer._is_dangerous(ctx, "echo hello")
    ctx2 = make_ctx(blocked_patterns=["python"])
    assert computer._is_blocked(ctx2, "python run.py")
    assert not computer._is_blocked(ctx, "python run.py")
