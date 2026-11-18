"""单账户适配器的账户级人格绑定兜底（无 @账户 后缀的会话键）。"""

from types import SimpleNamespace

from QvQChat.agent.persona import BINDING_PREFIX, PersonaManager


def _sdk(accounts: dict | None, online_bots: dict | None = None):
    storage = SimpleNamespace()

    class _S:
        def __init__(self):
            self._d = {}

        def get(self, key, default=None):
            return self._d.get(key, default)

        def set(self, key, value):
            self._d[key] = value

        def delete(self, key):
            self._d.pop(key, None)

        def keys(self):
            return list(self._d)

    class _Adapters:
        def get(self, name):
            if name != "snowluma" or accounts is None:
                return None
            return SimpleNamespace(accounts=accounts)

        def list_bots(self, name):
            # 与 inbox 同款数据源：返回 {platform: {bot_id: meta}}；未提供时回退由 accounts 推导
            if name != "snowluma" or online_bots is None:
                return {}
            return {"snowluma": online_bots}

    return SimpleNamespace(storage=_S(), adapter=_Adapters())


def _persona(pid: str, name: str) -> dict:
    return {"id": pid, "name": name, "system": f"我是{name}"}


def test_single_account_binding_hit_without_suffix():
    # 在线 bot 恰一个（643319481），绑定挂在 @账户名 / @bot_id
    sdk = _sdk(
        {"Amer": SimpleNamespace(bot_id="643319481")},
        online_bots={"643319481": {"status": "online"}},
    )
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@Amer", "amer")

    # 单账户化之后事件键不再带 @后缀
    persona = mgr.resolve("snowluma:private:2694611137")
    assert persona["id"] == "amer"
    assert persona["name"] == "Amer"


def test_binding_by_bot_id_with_stale_account_in_config():
    # 配置里残留停用/掉登录的旧账户，但在线 bot 只剩一个——以在线集合为准命中 @bot_id
    sdk = _sdk(
        {
            "Amer": SimpleNamespace(bot_id="643319481"),
            "Eris": SimpleNamespace(bot_id="1325859446"),
        },
        online_bots={"643319481": {"status": "online"}},
    )
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@643319481", "amer")

    assert mgr.resolve("snowluma:private:2694611137")["id"] == "amer"


def test_accounts_dict_fallback_without_list_bots():
    # list_bots 未提供在线集合时，配置账户恰好一个也兜底
    sdk = _sdk({"Amer": SimpleNamespace(bot_id="643319481")})
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@Amer", "amer")

    assert mgr.resolve("snowluma:private:2694611137")["id"] == "amer"


def test_multiple_online_bots_do_not_guess():
    # 在线 bot 两个：无法判定归属，不猜（落全局默认）
    sdk = _sdk(
        {
            "Amer": SimpleNamespace(bot_id="643319481"),
            "Eris": SimpleNamespace(bot_id="1325859446"),
        },
        online_bots={"643319481": {"status": "online"}, "1325859446": {"status": "online"}},
    )
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@Amer", "amer")

    assert mgr.resolve("snowluma:private:2694611137")["id"] != "amer"


def test_single_account_binding_hit_by_bot_id():
    sdk = _sdk({"Amer": SimpleNamespace(bot_id="643319481")})
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@643319481", "amer")

    assert mgr.resolve("snowluma:private:2694611137")["id"] == "amer"


def test_multi_account_does_not_guess():
    # 两个账户时不做兜底：避免把 A 账户的绑定错套到 B 账户的会话上
    sdk = _sdk({
        "Amer": SimpleNamespace(bot_id="643319481"),
        "小eris": SimpleNamespace(bot_id="1325859446"),
    })
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@Amer", "amer")

    assert mgr.resolve("snowluma:private:2694611137")["id"] != "amer"


def test_explicit_suffix_still_wins():
    sdk = _sdk({"Amer": SimpleNamespace(bot_id="643319481")})
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@643319481", "amer")

    assert mgr.resolve("snowluma:private:1@643319481")["id"] == "amer"


def test_session_exact_binding_beats_account_level():
    sdk = _sdk({"Amer": SimpleNamespace(bot_id="643319481")})
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer"), "x": _persona("x", "小eris")})
    mgr = PersonaManager(sdk)
    mgr.bind("@Amer", "amer")
    mgr.bind("snowluma:private:2694611137", "x")

    assert mgr.resolve("snowluma:private:2694611137")["id"] == "x"
