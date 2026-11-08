from __future__ import annotations

from typing import Any

from .. import texts, utils

PERSONAS_KEY = "QvQChat:personas"
BINDING_PREFIX = "QvQChat:binding:"
DEFAULT_PERSONA_KEY = "QvQChat:default_persona"

ASSISTANT_ID = "assistant"
CONCISE_ID = "concise"
DETAILED_ID = "detailed"
BUILTIN_IDS = (ASSISTANT_ID, CONCISE_ID, DETAILED_ID)

# P2style 白名单键（其余键忽略）
STYLE_KEYS = ("emoji_density", "verbosity", "formality")
# P2examples 序列化总长上限（字符）
EXAMPLES_MAX_CHARS = 2000


def _default_personas() -> dict:
    return {
        ASSISTANT_ID: {
            "id": ASSISTANT_ID,
            "name": texts.t("persona_default_name"),
            "system": texts.t("persona_default_system"),
            "opening": [],
            "tools": None,
            "builtin": True,
        },
        CONCISE_ID: {
            "id": CONCISE_ID,
            "name": texts.t("persona_concise_name"),
            "system": texts.t("persona_concise_system"),
            "opening": [],
            "tools": None,
            "builtin": True,
        },
        DETAILED_ID: {
            "id": DETAILED_ID,
            "name": texts.t("persona_detailed_name"),
            "system": texts.t("persona_detailed_system"),
            "opening": [],
            "tools": None,
            "builtin": True,
        },
    }


def _clean_style(style: Any) -> dict:
    if not isinstance(style, dict):
        return {}
    out: dict[str, str] = {}
    for key in STYLE_KEYS:
        value = str(style.get(key) or "").strip().lower()
        if value:
            out[key] = value
    return out


def _clean_examples(examples: Any) -> list[dict]:
    """[{user, assistant}] few-shot；按 user+assistant 合计 2000 字封顶（保序保最前）。"""
    if not isinstance(examples, list):
        return []
    out: list[dict] = []
    used = 0
    for item in examples:
        if not isinstance(item, dict):
            continue
        user = str(item.get("user") or "").strip()
        assistant = str(item.get("assistant") or "").strip()
        if not user and not assistant:
            continue
        if used + len(user) + len(assistant) > EXAMPLES_MAX_CHARS:
            break
        used += len(user) + len(assistant)
        out.append({"user": user, "assistant": assistant})
    return out


def _clean_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v or "").strip()]


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize(entry: dict) -> dict:
    """get/list 缺省兼容：保证 P2 扩展字段在所有人格上存在且类型正确。"""
    data = dict(entry)
    if not isinstance(data.get("opening"), list):
        data["opening"] = []
    if not isinstance(data.get("style"), dict):
        data["style"] = {}
    else:
        data["style"] = _clean_style(data["style"])
    if not isinstance(data.get("examples"), list):
        data["examples"] = []
    if not isinstance(data.get("banned_words"), list):
        data["banned_words"] = []
    if not isinstance(data.get("catchphrases"), list):
        data["catchphrases"] = []
    for key in ("owner_title", "nickname", "avatar", "prefill"):
        if not isinstance(data.get(key), str):
            data[key] = ""
    for key in ("temperature", "max_tokens"):
        value = data.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            data[key] = None
    return data


class PersonaManager:
    def __init__(self, sdk: Any):
        self.sdk = sdk

    def list(self) -> list[dict]:
        stored = self.sdk.storage.get(PERSONAS_KEY, {})
# 内置默认也过 _normalize：保证 P2 扩展字段在所有人格上类型正确
        personas = {pid: _normalize(entry) for pid, entry in _default_personas().items()}
        if isinstance(stored, dict):
            for persona_id, data in stored.items():
                data = _normalize(data if isinstance(data, dict) else {})
                data["id"] = persona_id
                if persona_id in BUILTIN_IDS:
                    data["builtin"] = True
                    data["modified"] = True
                personas[persona_id] = data
        return list(personas.values())

    def get(self, persona_id: str | None) -> dict:
        wanted = persona_id or self.global_default()
        if wanted:
            for persona in self.list():
                if persona["id"] == wanted:
                    return persona
        return _normalize(_default_personas()[ASSISTANT_ID])

    def global_default(self) -> str:
        return str(self.sdk.storage.get(DEFAULT_PERSONA_KEY, "") or "")

    def set_global_default(self, persona_id: str | None) -> None:
        if persona_id:
            self.sdk.storage.set(DEFAULT_PERSONA_KEY, str(persona_id))
        else:
            self.sdk.storage.delete(DEFAULT_PERSONA_KEY)

    def save(self, data: dict) -> dict:
        persona_id = str(data.get("id") or utils.new_id())
        stored = self.sdk.storage.get(PERSONAS_KEY, {})
        if not isinstance(stored, dict):
            stored = {}
# 合并语义：未显式提供的新字段沿用存量（防部分保存误清空）；name/system 仍按原 falsy 回退链
        existing = stored.get(persona_id) if isinstance(stored.get(persona_id), dict) else {}

        def _merged_list(key: str, cleaner) -> list:
            if isinstance(data.get(key), list):
                return cleaner(data[key])
            if isinstance(existing.get(key), list):
                return cleaner(existing[key])
            return []

        opening = _merged_list("opening", _clean_str_list)
        banned = _merged_list("banned_words", _clean_str_list)
        catchphrases = _merged_list("catchphrases", _clean_str_list)
        tools_raw = data.get("tools") if isinstance(data.get("tools"), list) and data["tools"] else None
        if tools_raw is None:
            prior = existing.get("tools")
            tools_raw = prior if isinstance(prior, list) and prior else None
        if isinstance(data.get("examples"), list):
            examples = _clean_examples(data["examples"])
        elif isinstance(existing.get("examples"), list):
            examples = _clean_examples(existing["examples"])
        else:
            examples = []
        if isinstance(data.get("style"), dict):
            style = _clean_style(data["style"])
        elif isinstance(existing.get("style"), dict):
            style = _clean_style(existing["style"])
        else:
            style = {}

        def _merged_str(key: str) -> str:
            if key in data and data[key] is not None:
                return _clean_str(data[key])
            return _clean_str(existing.get(key))

        def _merged_num(key: str):
            """人格级模型参数覆盖：显式提供合法正值优先；显式非法/非正=清除；未提供沿用存量。"""
            if key in data:
                try:
                    value = float(data[key])
                    if value > 0:
                        return value
                except (TypeError, ValueError):
                    pass
                return None
            try:
                value = float(existing.get(key))
                return value if value > 0 else None
            except (TypeError, ValueError):
                return None

        stored[persona_id] = {
            "name": str(data.get("name") or existing.get("name") or (texts.t("persona_default_name") if persona_id == ASSISTANT_ID else persona_id)),
            "system": str(data.get("system") or existing.get("system") or texts.t("persona_default_system")),
            "opening": opening,
            "tools": [str(t) for t in tools_raw] if tools_raw else None,
            "owner_title": _merged_str("owner_title"),
            "style": style,
            "examples": examples,
            "banned_words": banned,
            "catchphrases": catchphrases,
            "nickname": _merged_str("nickname"),
            "avatar": _merged_str("avatar"),
            "prefill": _merged_str("prefill"),
            "temperature": _merged_num("temperature"),
            "max_tokens": _merged_num("max_tokens"),
        }
        self.sdk.storage.set(PERSONAS_KEY, stored)
        result = dict(stored[persona_id])
        result["id"] = persona_id
        if persona_id in BUILTIN_IDS:
            result["builtin"] = True
            result["modified"] = True
        return result

    def delete(self, persona_id: str) -> bool:
        stored = self.sdk.storage.get(PERSONAS_KEY, {})
        if not isinstance(stored, dict):
            return False
        if persona_id not in stored:
            return False
        del stored[persona_id]
        self.sdk.storage.set(PERSONAS_KEY, stored)
        return True

    def bind(self, chat_key: str, persona_id: str | None) -> None:
        if persona_id:
            self.sdk.storage.set(BINDING_PREFIX + chat_key, persona_id)
        else:
            self.sdk.storage.delete(BINDING_PREFIX + chat_key)

    def bindings(self) -> dict[str, str]:
        """P3chat_key → persona_id 的权威绑定表（低频调用，KV 直扫）。"""
        out: dict[str, str] = {}
        for key in self.sdk.storage.keys():
            if not (isinstance(key, str) and key.startswith(BINDING_PREFIX)):
                continue
            value = str(self.sdk.storage.get(key, "") or "")
            if value:
                out[key[len(BINDING_PREFIX):]] = value
        return out

    def resolve(self, chat_key: str) -> dict:
        """绑定回落链（从具体到宽泛，首个命中生效）：

        会话精确 key → 群 base key（跨账户的同一群）→ @账户 级（该 bot 账户全部会话）
        → platform:* 平台级 → 全局默认 → assistant。
        层级 key 通过 bind() 直接写入即可（chat_key 填 "@账号" / "平台名:*"）。
        """
        from ..conversation.service import account_of, strip_account, strip_isolation

        candidates: list[str] = []
        key = str(chat_key or "")
        if key:
            candidates.append(key)
            base = strip_account(strip_isolation(key))
            if base and base != key:
                candidates.append(base)
            account = account_of(key)
            if account:
                candidates.append("@" + account)
            platform = key.split(":", 1)[0]
            if platform:
                candidates.append(f"{platform}:*")
        for candidate in candidates:
            bound = str(self.sdk.storage.get(BINDING_PREFIX + candidate, "") or "")
            if bound:
                return self.get(bound)
        return self.get(None)

    def migrate_state_mirror(self) -> int:
        """启动迁移：KV 绑定为权威源，conv state.persona 指向不同则回填一次。

        仅在 KV binding 存在时回填（反向不迁，避免把过期镜像升格为绑定）。
        """
        from ..conversation.service import CONV_PREFIX

        moved = 0
        for key in list(self.sdk.storage.keys()):
            if not (isinstance(key, str) and key.startswith(CONV_PREFIX)):
                continue
            chat_key = key[len(CONV_PREFIX):]
            bound = str(self.sdk.storage.get(BINDING_PREFIX + chat_key, "") or "")
            if not bound:
                continue
            state = self.sdk.storage.get(key, None)
            if not isinstance(state, dict) or state.get("persona") == bound:
                continue
            state["persona"] = bound
            self.sdk.storage.set(key, state)
            moved += 1
        return moved
