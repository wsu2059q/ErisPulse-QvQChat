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
        self._gd_cache: str | None = None
        self._store_cache: dict | None = None
        self._binding_cache: dict[str, str] | None = None

    async def arefresh(self) -> None:
        """预热进程内缓存（人格表 + 绑定表各一次批量读）。
        预热后事件循环内的 list/get/aresolve 全部零存储访问；写路径同步维护缓存。"""
        stored = await self.sdk.storage.aget(PERSONAS_KEY, {})
        self._store_cache = stored if isinstance(stored, dict) else {}
        keys = [
            key for key in await self.sdk.storage.aget_all_keys()
            if isinstance(key, str) and key.startswith(BINDING_PREFIX)
        ]
        values = await self.sdk.storage.aget_multi(keys) if keys else {}
        self._binding_cache = {
            key[len(BINDING_PREFIX):]: str(value)
            for key, value in (values or {}).items()
            if str(value or "")
        }

    def list(self) -> list[dict]:
        stored = self._store_cache
        if stored is None:
# 未预热回退（线程路径/测试环境）：生产事件循环内由 on_load 先行 arefresh
            stored = self.sdk.storage.get(PERSONAS_KEY, {})
            if not isinstance(stored, dict):
                stored = {}
# 内置默认也过 _normalize：保证 P2 扩展字段在所有人格上类型正确
        personas = {pid: _normalize(entry) for pid, entry in _default_personas().items()}
        for persona_id, data in stored.items():
            data = _normalize(data if isinstance(data, dict) else {})
            data["id"] = persona_id
            if persona_id in BUILTIN_IDS:
                data["builtin"] = True
                data["modified"] = True
            personas[persona_id] = data
        return list(personas.values())

    def get(self, persona_id: str | None) -> dict:
        wanted = persona_id or (self._gd_cache or "")
        if wanted:
            for persona in self.list():
                if persona["id"] == wanted:
                    return persona
        return _normalize(_default_personas()[ASSISTANT_ID])

    async def global_default(self) -> str:
        if self._gd_cache is None:
            self._gd_cache = str(await self.sdk.storage.aget(DEFAULT_PERSONA_KEY, "") or "")
        return self._gd_cache

    async def set_global_default(self, persona_id: str | None) -> None:
        if persona_id:
            await self.sdk.storage.aset(DEFAULT_PERSONA_KEY, str(persona_id))
        else:
            await self.sdk.storage.adelete(DEFAULT_PERSONA_KEY)
        self._gd_cache = str(persona_id or "")

    async def save(self, data: dict) -> dict:
        persona_id = str(data.get("id") or utils.new_id())

        def _merge(stored: dict) -> dict:
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
            return stored

# 键级 RMW（面板/工具并发保存同一人格表不再互相覆盖）
        stored = await utils.storage_aupdate(self.sdk, PERSONAS_KEY, _merge, {})
        self._store_cache = stored
        result = dict(stored.get(persona_id) or {})
        result["id"] = persona_id
        if persona_id in BUILTIN_IDS:
            result["builtin"] = True
            result["modified"] = True
        return result

    async def delete(self, persona_id: str) -> bool:
        found: list = []

        def _drop(stored) -> dict:
            if not isinstance(stored, dict):
                return {}
            if persona_id in stored:
                del stored[persona_id]
                found.append(True)
            return stored

        stored = await utils.storage_aupdate(self.sdk, PERSONAS_KEY, _drop, {})
        self._store_cache = stored
        return bool(found)

    async def bind(self, chat_key: str, persona_id: str | None) -> None:
        if persona_id:
            await self.sdk.storage.aset(BINDING_PREFIX + chat_key, persona_id)
        else:
            await self.sdk.storage.adelete(BINDING_PREFIX + chat_key)
        if self._binding_cache is not None:
            if persona_id:
                self._binding_cache[str(chat_key)] = str(persona_id)
            else:
                self._binding_cache.pop(str(chat_key), None)

    async def abindings(self) -> dict[str, str]:
        """chat_key → persona_id 的绑定表（预热后读缓存）。"""
        if self._binding_cache is not None:
            return dict(self._binding_cache)
        keys = [
            key for key in await self.sdk.storage.aget_all_keys()
            if isinstance(key, str) and key.startswith(BINDING_PREFIX)
        ]
        values = await self.sdk.storage.aget_multi(keys) if keys else {}
        out: dict[str, str] = {}
        for key, value in (values or {}).items():
            if str(value or ""):
                out[key[len(BINDING_PREFIX):]] = str(value)
        return out

    def _single_account_keys(self, platform: str) -> list[str]:
        """单账户适配器的账户标识候选（@bot_id + @账户名）。

        适配器只剩一个账户后，事件 chat_key 不再带 @账户 后缀（inbox 的隔离策略：
        在线 bot < 2 不加，为存量会话兼容）；而账户级绑定往往挂在 @账户名 / @bot_id
        上，两边变体对不上就会一路落空到全局默认人格（"以为自己是另一个旧账户"的根因）。

        判定用 adapter.list_bots(platform)（与 inbox 同一数据源：在线 bot 集合）——
        配置里可能残留停用/掉登录的旧账户，以在线集合恰有一个为准；只有唯一在线 bot
        才兜底，避免多账户下张冠李戴。名字变体从 adapter.accounts 的 bot_id 反查补齐。
        """
        if not platform:
            return []
        platform = str(platform)
        bot_ids: list[str] = []
        try:
            bots = self.sdk.adapter.list_bots(platform) or {}
            per_platform = bots.get(platform, bots) if isinstance(bots, dict) else {}
            if isinstance(per_platform, dict) and len(per_platform) == 1:
                bot_ids.append(str(next(iter(per_platform))))
        except Exception:
            bot_ids = []
        if not bot_ids:
            # list_bots 不可用时的回退：配置账户恰好一个也视为唯一
            try:
                adapter = self.sdk.adapter.get(platform)
                accounts = getattr(adapter, "accounts", None) if adapter is not None else None
                if isinstance(accounts, dict) and len(accounts) == 1:
                    name, cfg = next(iter(accounts.items()))
                    cfg_bot = cfg.get("bot_id") if isinstance(cfg, dict) else getattr(cfg, "bot_id", None)
                    bot_ids.append(str(cfg_bot) if cfg_bot else "")
                    if str(name):
                        bot_ids.append("@" + str(name))  # 带 @ 前缀标记账户名候选
            except Exception:
                return []
        keys: list[str] = []
        for item in bot_ids:
            item = str(item)
            if not item:
                continue
            keys.append(item if item.startswith("@") else "@" + item)
# bot_id → 配置账户名（绑定可能挂在名字变体上，两种都试）
        if keys:
            try:
                adapter = self.sdk.adapter.get(platform)
                accounts = getattr(adapter, "accounts", None) if adapter is not None else None
                if isinstance(accounts, dict):
                    for acct_name, cfg in accounts.items():
                        cfg_bot = cfg.get("bot_id") if isinstance(cfg, dict) else getattr(cfg, "bot_id", None)
                        if cfg_bot and "@" + str(cfg_bot) in keys and str(acct_name):
                            keys.append("@" + str(acct_name))
            except Exception:
                pass
        return list(dict.fromkeys(keys))

    def _binding_candidates(self, chat_key: str) -> list[str]:
        """绑定回落链候选（从具体到宽泛）：

        会话精确 key → 群 base key（跨账户的同一群）→ @账户 级（该 bot 账户全部会话）
        → platform:* 平台级。全局默认与 assistant 兜底由调用方追加。
        层级 key 通过 bind() 直接写入即可（chat_key 填 "@账号" / "平台名:*"）。

        base 层只对群聊生效：群里不同 bot 账号看到的确实是同一场对话，共享绑定合理；
        私聊的 base 键（去 @ 后缀）会把"用户和 A bot 的绑定"串到"用户和 B bot 的私聊"
        上（账户增减后键在有无后缀间切换时尤其如此），故私聊跳过。

        键上没有 @账户 后缀（单账户适配器）时，用该平台唯一账户的标识补齐 @ 层候选。
        """
        from ..conversation.service import account_of, strip_account, strip_isolation

        candidates: list[str] = []
        key = str(chat_key or "")
        if key:
            candidates.append(key)
            if ":group:" in key:
                base = strip_account(strip_isolation(key))
                if base and base != key:
                    candidates.append(base)
            platform = key.split(":", 1)[0]
            account = account_of(key)
            if account:
                candidates.append("@" + account)
            else:
                candidates.extend(self._single_account_keys(platform))
            if platform:
                candidates.append(f"{platform}:*")
        return candidates

    def resolve(self, chat_key: str) -> dict:
        """同步版：仅供无事件循环的路径（线程/测试）使用；事件循环内用 aresolve。
        缓存未预热时同步读存储。"""
        for candidate in self._binding_candidates(chat_key):
            bound = (self._binding_cache or {}).get(candidate)
            if bound is None:
                bound = str(self.sdk.storage.get(BINDING_PREFIX + candidate, "") or "")
            if bound:
                return self.get(bound)
        return self.get(None)

    async def aresolve(self, chat_key: str) -> dict:
        """事件循环内的绑定解析：预热后纯内存回落链查找，零存储访问。"""
        cache = self._binding_cache
        if cache is not None:
            for candidate in self._binding_candidates(chat_key):
                bound = str(cache.get(candidate) or "")
                if bound:
                    return self.get(bound)
            return self.get(None)
        for candidate in self._binding_candidates(chat_key):
            bound = str(await self.sdk.storage.aget(BINDING_PREFIX + candidate, "") or "")
            if bound:
                return self.get(bound)
        return self.get(None)

    async def migrate_state_mirror(self) -> int:
        """启动迁移：KV 绑定为权威源，conv state.persona 指向不同则回填一次。

        仅在 KV binding 存在时回填（反向不迁，避免把过期镜像升格为绑定）。
        在 arefresh 之后调用（绑定走缓存）。
        """
        from ..conversation.service import CONV_PREFIX

        moved = 0
        keys = [
            key for key in await self.sdk.storage.aget_all_keys()
            if isinstance(key, str) and key.startswith(CONV_PREFIX)
        ]
        values = await self.sdk.storage.aget_multi(keys) if keys else {}
        for key, state in (values or {}).items():
            if not isinstance(state, dict):
                continue
            chat_key = key[len(CONV_PREFIX):]
            bound = str((self._binding_cache or {}).get(chat_key) or "")
            if not bound or state.get("persona") == bound:
                continue
            state["persona"] = bound
            await self.sdk.storage.aset(key, state)
            moved += 1
        return moved
