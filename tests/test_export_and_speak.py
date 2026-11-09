import asyncio
import io
import json
import zipfile
from types import SimpleNamespace

from QvQChat.Main import Main
from QvQChat.dashboard.api_config import _sanitize_value
from QvQChat.dashboard.manager import DashboardManager

from test_dashboard_auth import FakeJsonRequest, make_manager


class FakeQp:
    def __init__(self, **params):
        self.query_params = params


async def test_export_json_includes_storage_dump():
    main, manager = make_manager(view_token="tok-x")
    main.sdk.storage.set("QvQChat:conv:onebot11:group:1@643319481", {"contexts": [{"role": "user", "content": "hi"}]})
    main.sdk.storage.set("QvQChat:auth_token", "secret-token")  # 受 PROTECTED_KEYS 保护，不得入包
    data = await manager.export_data(FakeQp())
    assert data["version"] == 4
    assert "QvQChat:conv:onebot11:group:1@643319481" in data["storage"]
    assert "QvQChat:auth_token" not in data["storage"]


async def test_export_zip_sanitized_masks_keys(tmp_path):
    import QvQChat.dashboard.api_ops as api_ops

    (tmp_path / "generated.txt").write_text("AI 生成内容", encoding="utf-8")
    original = api_ops.STORAGE_FILE_DOMAINS
    api_ops.STORAGE_FILE_DOMAINS = [("uploads", str(tmp_path))]
    try:
        main, manager = make_manager(view_token="tok-x")
        main.pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://x/v1",
                                 "api_key": "sk-super-secret", "models": [{"id": "m", "enabled": True}]})
        response = await manager.export_data(FakeQp(format="zip", sanitize="1"))
        assert response.media_type == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(response.body))
        names = zf.namelist()
        assert "data.json" in names and "manifest.json" in names
        assert any(n.startswith("uploads/") for n in names)
        data = json.loads(zf.read("data.json").decode("utf-8"))
        assert data["sanitize"] is True
        assert data["providers"][0]["api_key"] == "«removed»"
        assert data["config"]["view_token"] == "«removed»"
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["sanitize"] is True and manifest["files_included"] >= 1
    finally:
        api_ops.STORAGE_FILE_DOMAINS = original


async def test_export_zip_full_keeps_keys():
    main, manager = make_manager(view_token="tok-x")
    main.pool.save_provider({"id": "p1", "name": "P1", "base_url": "https://x/v1",
                             "api_key": "sk-keep-me", "models": [{"id": "m", "enabled": True}]})
    response = await manager.export_data(FakeQp(format="zip"))
    zf = zipfile.ZipFile(io.BytesIO(response.body))
    data = json.loads(zf.read("data.json").decode("utf-8"))
    assert data["sanitize"] is False
    assert data["providers"][0]["api_key"] == "sk-keep-me"


def test_sanitize_value_masks_sensitive_keys_recursively():
    value = {
        "api_key": "sk-1",
        "Authorization": "Bearer x",
        "note": "不敏感",
        "empty_key": "",
        "nested": {"client_secret": "s", "list": [{"token": "t"}]},
    }
    out = _sanitize_value(value)
    assert out["api_key"] == "«removed»"
    assert out["Authorization"] == "«removed»"
    assert out["note"] == "不敏感"
    assert out["empty_key"] == ""  # 空值不掩码
    assert out["nested"]["client_secret"] == "«removed»"
    assert out["nested"]["list"][0]["token"] == "«removed»"


# ---------- 导出内容选择 / 导入策略 ----------


async def test_export_domains_filter():
    main, manager = make_manager(view_token="tok-x")
    main.sdk.storage.set("QvQChat:conv:onebot11:group:1@bot1", {"contexts": []})
    main.sdk.storage.set("QvQChat:audit", [{"tool": "x"}])
    main.sdk.storage.set("QvQChat:mem:onebot11:group:1@bot1", [{"content": "记着"}])
    data = await manager.export_data(FakeQp(domains="sessions,personas"))
    assert data["domains"] == ["personas", "sessions"]
    assert "QvQChat:conv:onebot11:group:1@bot1" in data["storage"]
    assert "QvQChat:audit" not in data["storage"]
    assert "QvQChat:mem:onebot11:group:1@bot1" not in data["storage"]
    assert data["config"] == {} and data["memory"] == {}  # 未选 config/memory 段
    assert data["personas"] == {}  # personas 段保留（结构化），存储键只按域放行


def _import_manager():
    from fakes import FakeMain

    main = FakeMain(view_token="tok-x")
    return main, DashboardManager(main)


async def test_import_personas_append_keeps_existing():

    main, manager = _import_manager()
    main.sdk.storage.set("QvQChat:personas", {"old": {"name": "旧人格"}})
    res = await manager.import_data(FakeJsonRequest({
        "data": {"personas": {"old": {"name": "导入版"}, "new": {"name": "新人格"}}},
        "strategies": {"personas": "append"},
    }))
    assert res["ok"] and "personas" in res["applied"]
    stored = main.sdk.storage.get("QvQChat:personas")
    assert stored["old"]["name"] == "旧人格"  # 追加：已有人格不动
    assert stored["new"]["name"] == "新人格"


async def test_import_tasks_overwrite_replaces():

    main, manager = _import_manager()
    main.scheduler.add({"id": "old-task", "name": "旧", "schedule": {"type": "interval", "seconds": 60},
                        "prompt": "x", "platform": "p", "target_type": "group", "target_id": "1"})
    res = await manager.import_data(FakeJsonRequest({
        "data": {"tasks": [{"id": "new-task", "name": "新", "schedule": {"type": "interval", "seconds": 60},
                            "prompt": "y", "platform": "p", "target_type": "group", "target_id": "1"}]},
        "strategies": {"tasks": "overwrite"},
    }))
    assert res["ok"] and "tasks" in res["applied"]
    ids = {t["id"] for t in main.scheduler.list()}
    assert ids == {"new-task"}


async def test_import_storage_append_only_missing():

    main, manager = _import_manager()
    main.sdk.storage.set("QvQChat:conv:exists@bot1", {"kept": True})
    res = await manager.import_data(FakeJsonRequest({
        "data": {"storage": {
            "QvQChat:conv:exists@bot1": {"kept": False},
            "QvQChat:conv:missing@bot1": {"added": True},
            "QvQChat:auth_token": "恶意token",  # 受保护键拒写
        }},
        "strategies": {"storage": "append"},
    }))
    assert res["ok"] and "storage" in res["applied"]
    assert main.sdk.storage.get("QvQChat:conv:exists@bot1") == {"kept": True}
    assert main.sdk.storage.get("QvQChat:conv:missing@bot1") == {"added": True}
    assert main.sdk.storage.get("QvQChat:auth_token") != "恶意token"


async def test_import_section_skip_and_select():

    main, manager = _import_manager()
    res = await manager.import_data(FakeJsonRequest({
        "data": {"personas": {"p1": {"name": "A"}}, "tasks": [], "config": {"context_limit": 8}},
        "sections": ["config"],  # 只导 config
    }))
    assert res["ok"] and res["applied"] == ["config"]
    assert main.sdk.storage.get("QvQChat:personas") is None
    res2 = await manager.import_data(FakeJsonRequest({
        "data": {"personas": {"p2": {"name": "B"}}},
        "strategies": {"personas": "skip"},
    }))
    assert "personas" not in res2["applied"]
    assert main.sdk.storage.get("QvQChat:personas") is None


async def test_import_zip_roundtrip_with_files(tmp_path):
    import base64

    import QvQChat.dashboard.api_ops as api_ops

    uploads_dir = tmp_path / "uploads"
    work_dir = tmp_path / "work"
    (uploads_dir / "sub").mkdir(parents=True)
    (work_dir / "sub").mkdir(parents=True)
    (uploads_dir / "sub" / "pic.txt").write_text("AI 生成图", encoding="utf-8")
    (work_dir / "sub" / "report.txt").write_text("导出时的工作区内容", encoding="utf-8")
    original = api_ops.STORAGE_FILE_DOMAINS
    api_ops.STORAGE_FILE_DOMAINS = [("uploads", str(uploads_dir)), ("work", str(work_dir))]
    try:
        main, manager = make_manager(view_token="tok-x")
        main.sdk.storage.set("QvQChat:conv:c1@bot1", {"contexts": []})
        export = await manager.export_data(FakeQp(format="zip"))
        b64 = base64.b64encode(export.body).decode()
        # peek：只探测
        peek = await manager.import_zip(FakeJsonRequest({"data_b64": b64, "peek": True}))
        assert "storage" in peek["sections"]
        assert set(peek["files"]) == {"uploads", "work"}
        # 导出后现场被改动：append 保住现场，overwrite 还原导出内容
        (uploads_dir / "sub" / "pic.txt").write_text("被改过", encoding="utf-8")
        (work_dir / "sub" / "report.txt").write_text("被改过", encoding="utf-8")
        res = await manager.import_zip(FakeJsonRequest({
            "data_b64": b64, "sections": ["storage", "files"],
            "strategies": {"storage": "overwrite", "files": "append"},
        }))
        assert res["ok"] and "storage" in res["applied"]
        assert res["files_restored"] == 0  # append：已存在不覆盖
        assert (uploads_dir / "sub" / "pic.txt").read_text(encoding="utf-8") == "被改过"
        # overwrite：覆盖
        res2 = await manager.import_zip(FakeJsonRequest({
            "data_b64": b64, "sections": ["files"],
            "strategies": {"files": "overwrite"},
        }))
        assert res2["files_restored"] == 2
        assert (uploads_dir / "sub" / "pic.txt").read_text(encoding="utf-8") == "AI 生成图"
        assert (work_dir / "sub" / "report.txt").read_text(encoding="utf-8") == "导出时的工作区内容"
        assert main.sdk.storage.get("QvQChat:conv:c1@bot1") == {"contexts": []}
    finally:
        api_ops.STORAGE_FILE_DOMAINS = original


async def test_import_zip_rejects_path_escape(tmp_path):
    import base64

    import QvQChat.dashboard.api_ops as api_ops

    src = tmp_path / "src"
    src.mkdir()
    original = api_ops.STORAGE_FILE_DOMAINS
    api_ops.STORAGE_FILE_DOMAINS = [("uploads", str(src))]
    try:
        main, manager = make_manager(view_token="tok-x")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("data.json", json.dumps({"version": 4}))
            zf.writestr("uploads/../../evil.txt", "越界")
        res = await manager.import_zip(FakeJsonRequest({
            "data_b64": base64.b64encode(buf.getvalue()).decode(),
            "strategies": {"files": "overwrite"},
        }))
        assert res["ok"] and res["files_restored"] == 0
    finally:
        api_ops.STORAGE_FILE_DOMAINS = original


# ---------- 主动发言防复读 ----------


def _speakable_main():
    from fakes import FakeMain

    main = FakeMain()
    main.participation = SimpleNamespace(
        budget=SimpleNamespace(
            allow=lambda chat_key, kind: (True, ""),
            record=lambda chat_key, kind: None,
        ),
        log_decision=lambda entry: None,
    )
    main.prompts = []
    main.logger = main.sdk.logger

    async def fake_run_prompt(chat_key, prompt, **kwargs):
        main.prompts.append((chat_key, prompt, kwargs))
        return "聊聊雪lico的日常"

    main.run_prompt = fake_run_prompt
    return main


async def test_speak_injects_recent_proactive_and_blocks_repeat():
    main = _speakable_main()
    scene1 = (await Main.speak(main, "onebot11:group:1", reason="测试")) or ""
    assert len(main.prompts) == 1
    kwargs = main.prompts[0][2]
    assert "防复读" not in kwargs["scene"], "首次主动发言无历史，不注入防复读"
    # 第二次：场景必须列出最近说过的话并明令不再谈（文案随 locale，取锚点断言）
    await Main.speak(main, "onebot11:group:1", reason="测试")
    kwargs2 = main.prompts[1][2]
    assert ("防复读" in kwargs2["scene"]) or ("anti-repeat" in kwargs2["scene"])
    assert "聊聊雪lico的日常" in kwargs2["scene"]


async def test_speak_period_reply_not_tracked():
    """句号（沉默标记）不计入最近发言，避免自我锁死。"""
    main = _speakable_main()

    async def silent_prompt(chat_key, prompt, **kwargs):
        return "。"

    main.run_prompt = silent_prompt
    await Main.speak(main, "onebot11:group:1", reason="测试")
    assert not main._proactive_recent.get("onebot11:group:1")
