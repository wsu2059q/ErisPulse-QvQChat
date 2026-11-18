"""单账户适配器的账户级人格绑定兜底（无 @账户 后缀的会话键）。"""

from types import SimpleNamespace

from QvQChat.agent.persona import BINDING_PREFIX, PersonaManager


def _sdk(accounts: dict | None):
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

    return SimpleNamespace(storage=_S(), adapter=_Adapters())


def _persona(pid: str, name: str) -> dict:
    return {"id": pid, "name": name, "system": f"我是{name}"}


def test_single_account_binding_hit_without_suffix():
    # 适配器只剩一个账户（名 Amer，bot_id 643319481），绑定挂在 @Amer / @643319481
    sdk = _sdk({"Amer": SimpleNamespace(bot_id="643319481")})
    sdk.storage.set("QvQChat:personas", {"amer": _persona("amer", "Amer")})
    mgr = PersonaManager(sdk)
    mgr.bind("@Amer", "amer")

    # 单账户化之后事件键不再带 @后缀
    persona = mgr.resolve("snowluma:private:2694611137")
    assert persona["id"] == "amer"
    assert persona["name"] == "Amer"


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
