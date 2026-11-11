from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import texts

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

BUILTIN_SKILLS: list[dict] = [
    {
        "name": "erispulse-dev",
        "description": texts.t("skill.erispulse_dev.desc"),
        "body": """Develop or modify an ErisPulse module, then hot-reload it. Always verify APIs with
search_erispulse_docs / read_erispulse_doc instead of guessing — the docs are synced to the installed framework version.

## 0. Locate the target
- Find the module package (e.g. `Module/ErisPulse-Foo/Foo/Main.py`) and read `pyproject.toml` + the entry module before editing.
- Check how the module currently registers handlers/services: `get_meta()`, `get_load_strategy()`, `on_load`, `on_unload`.

## 1. Package skeleton (new module)
- `pyproject.toml` needs the entry point:
  ```toml
  [project.entry-points."erispulse.module"]
  Foo = "Foo:Main"
  ```
- `Foo/__init__.py` exports `Main`; `Foo/Main.py` defines `class Main(BaseModule)` with `ConfigClass` / `I18nClass`.
- Declare services in `get_meta(services=[{"name","description","signature"}, ...])` — `sdk.module.call` rejects undeclared services.
- Use `get_load_strategy()` priority to control load order (higher priority loads earlier).

## 2. Config & i18n conventions (this repo's style)
- Config is a dataclass (`BaseConfig`) where every field carries `_desc(key, text, group, order, widget...)` metadata for the settings UI.
- Text goes through a `texts.py` dict (zh-CN/zh-TW/en/ja/ru) or `I18nClass`; never hardcode user-facing strings.
- Storage: `sdk.storage.get/set` with a namespaced key like `Foo:state`; don't create your own DB.

## 3. Interop with QvQChat (optional)
- Register `qvq_settings` to appear in the QvQChat settings page.
- Register `qvq_schemas` to give QvQChat's eco bridge parameter-level schemas (otherwise only a weak signature-derived schema is used).
- Register `qvq_personas` to contribute personas; `qvq.observe` / `qvq.replied` lifecycle events to observe chat.
- To let members (not just admins) use your service through QvQChat, the operator must list it in `eco_safe` (`Module:service`).

## 4. Verify
- Syntax: `python -m compileall Foo` (or import the package).
- Unit tests: add `tests/` with pytest; run `python -m pytest tests/ -q`.
- Hot reload: call `reload_module` with the module name, then re-run the failing scenario.
- Check logs for `module reload` / lifecycle events; if reload fails, fix the import error and reload again.

## 5. Common pitfalls
- Service not declared in `get_meta` → call rejected even though the method exists.
- Forgetting `await` on async sdk calls; blocking I/O inside handlers (use `asyncio.to_thread`).
- Catching `Exception` and returning silently — log at least at debug level.
- Holding state on the class instead of the instance → survives reload incorrectly.""",
    },
    {
        "name": "self-config",
        "description": texts.t("skill.self_config.desc"),
        "body": """The manage_* tools are your configuration interface (admin/master only). Use them when the user asks in natural language — no dashboard needed.

## Personas — manage_personas
- action="list": personas, the global default and per-chat bindings (current chat included).
- action="save" with name and/or system (id optional): creates or updates a persona; built-in ids (assistant/concise/detailed) can be overridden.
- action="bind" with persona and optional chat_key (default = current chat); action="unbind" clears it.
- action="set_global" with persona_id makes it the default for unbound chats; action="clear_global" resets.

## Models — manage_models
- action="list": providers with masked keys, enabled models, current default.
- action="presets": preset base URLs (openai, deepseek, zhipu, ollama, custom, ...).
- action="save" with provider={id?, name, base_url, api_key, models:[{id, enabled, temperature?, max_tokens?}]}.
  - An empty api_key keeps the stored key of an existing provider.
  - Pass the FULL list of enabled models — it replaces the provider's list. If unsure which ids exist, fetch_models first.
- action="fetch_models" with provider={base_url, api_key?} (or provider_id to reuse stored credentials): lists the remote /models the user can pick from.
- action="set_default" with model_id="provider:model" (empty clears back to pool order).
- action="delete" with provider_id. Confirm before deleting.

## MCP servers — manage_mcp
- action="list" / "status": configured servers and live clients with their tool names.
- action="save": name plus either stdio (command, args, env) or http (url, headers). Saves and connects immediately; the result reports the tool count or the connection error.
- action="connect" / "disconnect" / "remove" with name. Confirm before removing.
- Newly connected tools register as mcp_<server>_<tool> and follow the normal permission rules.

## Module settings — manage_config
- action="get": all QvQChat settings, or one key.
- action="set" with updates={key: value}: valid QvQChat config keys only (unknown keys are rejected, values are type-checked). Covers every section: triggers, aggregate_window, forward behaviour (forward_external_reply / forward_args_chars / forward_output_chars), reply_quote, tool_select*, web_*, docs_*, eco_*, context_compress_tokens, participation_*, plus the token/effort knobs: budget_mode, budget_auto_on_limit, daily_token_limit, user_daily_budget, reasoning_effort, aux_model, max_context_turns, turn_timeout.
- Examples: turn off auto-forwarding outside the card (`forward_external_reply=false`), widen the process summary (`forward_output_chars=800`), disable quoting (`reply_quote="off"`), let members use a module's service (`eco_safe=["Mod:service"]`) or veto a module's safe self-declaration (`eco_admin=["Mod:*"]`).
- Eco access is normally self-declared by the module via its `qvq_access` service; `eco_safe`/`eco_admin` are operator overrides only.

## Session policy & usage — session_settings
- action="get" (chat_key optional, default = current chat): trigger_mode, listen_off, ui overrides (model/effort/density), muted, low_token, priority, session_budget, plus `low_token_active` (whether low-token mode is really in effect, including auto-on-limit) and `usage_today` (session tokens vs session_budget; global tokens vs daily_token_limit).
- action="set" with settings={...}: trigger_mode, listen_off, model, effort, density, muted (true = that chat goes FULLY silent — confirm before self-muting), low_token (lean prompt + tightened history for token saving), priority (high/normal/low — concurrency slot preference), session_budget (daily token cap for that chat, 0 = unlimited).
- Scope: ONE chat per key; the global equivalents live in manage_config (budget_mode, daily_token_limit).

Rules: never read back or repeat api keys in your replies; sanity-check a changed model pool with a quick ping if the user asks; settings that affect safety (security_level, trust_agent, owner_only, admin lists, eco_admin) deserve an explicit confirmation even from an admin.""",
    },
]


def parse_skill_md(text: str) -> tuple[dict, str]:
    meta: dict = {}
    body = text.strip()
    match = FRONTMATTER_RE.match(body)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip().lower()] = value.strip()
        body = body[match.end():]
    if not meta.get("name"):
        first = body.strip().splitlines()[0].lstrip("# ").strip() if body.strip() else ""
        if first:
            meta["name"] = first[:40]
    return meta, body.strip()


class SkillManager:
# 技能草稿命名时跳过的英文虚词（提议名只取实义词）
    _NAME_STOPWORDS = {
        "the", "and", "for", "with", "this", "that", "then", "from",
        "please", "help", "me", "you", "your", "use", "using", "used",
        "how", "what", "when", "where", "why", "can", "could", "would",
    }

    def __init__(self, sdk: Any, config: Any):
        self.sdk = sdk
        self.config = config
        self._store_key = "QvQChat:skills"
# 生态模块经 qvq_extensions 贡献的只读技能（由 Main 注入 provider）
        self._external_provider = None

    def set_external_provider(self, provider) -> None:
        """注入外部技能来源（返回 [{name, description, body, enabled, source}]）。"""
        self._external_provider = provider

    def _external_skills(self) -> list[dict]:
        if self._external_provider is None:
            return []
        try:
            items = self._external_provider() or []
        except Exception:
            return []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            result.append({
                "name": name,
                "description": str(item.get("description") or ""),
                "body": str(item.get("body") or ""),
                "source": str(item.get("source") or "module"),
                "enabled": bool(item.get("enabled", True)) and name not in self._disabled(),
            })
        return result

    def skills_dir(self) -> Path:
        raw = str(getattr(self.config, "skills_dir", "") or "data/QvQChat/skills")
        return Path(raw).expanduser()

    def _disabled(self) -> list[str]:
        return [str(s) for s in (getattr(self.config, "skills_disabled", []) or [])]

    def _file_skills(self) -> list[dict]:
        result: list[dict] = []
        directory = self.skills_dir()
        if not directory.is_dir():
            return result
        for path in sorted(directory.glob("*.md")):
            try:
                meta, body = parse_skill_md(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            name = str(meta.get("name") or path.stem)
            result.append(
                {
                    "name": name,
                    "description": str(meta.get("description") or ""),
                    "body": body,
                    "source": "file",
                    "path": str(path),
                    "enabled": name not in self._disabled(),
                }
            )
        return result

    def _stored_skills(self) -> list[dict]:
        stored = self.sdk.storage.get(self._store_key, {})
        result: list[dict] = []
        if isinstance(stored, dict):
            for name, data in stored.items():
                if not isinstance(data, dict):
                    continue
                result.append(
                    {
                        "name": name,
                        "description": str(data.get("description") or ""),
                        "body": str(data.get("body") or ""),
                        "source": "dashboard",
                        "enabled": name not in self._disabled(),
                    }
                )
        return sorted(result, key=lambda s: s["name"])

    def _builtin_skills(self) -> list[dict]:
        """内置技能按各自开关过滤：self-config 跟 self_config，erispulse-dev 跟 skill_dev。"""
        gates = {
            "self-config": bool(getattr(self.config, "self_config", True)),
            "erispulse-dev": bool(getattr(self.config, "skill_dev", True)),
        }
        disabled = set(self._disabled())
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "body": s["body"],
                "source": "builtin",
                "enabled": s["name"] not in disabled,
            }
            for s in BUILTIN_SKILLS
            if gates.get(s["name"], True)
        ]

    def list_skills(self) -> list[dict]:
        merged = {s["name"]: s for s in self._builtin_skills()}
# 生态模块贡献的技能：内置同名优先（setdefault），文件/面板可覆盖
        for s in self._external_skills():
            merged.setdefault(s["name"], s)
        for s in self._file_skills():
            merged.setdefault(s["name"], s)
        for s in self._stored_skills():
            merged[s["name"]] = s
        return sorted(merged.values(), key=lambda s: s["name"])

    def get_skill(self, name: str) -> dict | None:
        for skill in self.list_skills():
            if skill["name"] == name:
                return skill
        return None

    def save_skill(self, name: str, description: str, body: str) -> dict:
        name = str(name).strip()
        if not name:
            raise ValueError(texts.t("skills_name_required"))
        stored = self.sdk.storage.get(self._store_key, {})
        if not isinstance(stored, dict):
            stored = {}
        stored[name] = {"description": description, "body": body}
        self.sdk.storage.set(self._store_key, stored)
        return {"name": name, "description": description, "body": body, "source": "dashboard"}

    def delete_skill(self, name: str) -> bool:
        stored = self.sdk.storage.get(self._store_key, {})
        if isinstance(stored, dict) and name in stored:
            del stored[name]
            self.sdk.storage.set(self._store_key, stored)
            return True
        path = self.skills_dir() / f"{name}.md"
        if path.is_file():
            path.unlink()
            return True
        return False

    def set_enabled(self, name: str, enabled: bool) -> None:
        disabled = self._disabled()
        if enabled and name in disabled:
            disabled.remove(name)
        elif not enabled and name not in disabled:
            disabled.append(name)
        self.sdk.config.setConfig("QvQChat.skills_disabled", disabled)

# ===== 技能自动习得：运行结果 → 技能草稿（不落盘）=====

    def propose_from_run(self, user_text: str, result: Any) -> dict | None:
        """从一次完成的运行中提炼技能草稿，返回 {name, description, steps} 或 None。

        启发式（纯本地，不调模型）：需要用户任务文本 + 至少一次工具调用；
        name 取用户文本中第一个实义 ASCII 词（短英文 id），无则回退 "task-{首个工具名}"；
        description 取最终回复首行（空则回退任务文本）；steps 来自连续去重的工具序列。
        同名技能已存在时返回 None（不重复提议）。草稿仅返回给调用方，绝不写存储。
        """
        user_text = str(user_text or "").strip()
        trace = list(getattr(result, "tool_trace", None) or [])
        if not user_text or not trace:
            return None
        sequence: list[str] = []
        for entry in trace:
            name = str(entry.get("tool") or "") if isinstance(entry, dict) else ""
            if name and (not sequence or sequence[-1] != name):
                sequence.append(name)
        if not sequence:
            return None
        words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", user_text)]
        candidates = [w for w in words if w not in self._NAME_STOPWORDS]
        name = (candidates[0] if candidates else "task-" + sequence[0])[:32]
        if self.get_skill(name) is not None:
            return None
        reply_lines = str(getattr(result, "text", "") or "").strip().splitlines()
        description = (reply_lines[0].strip() if reply_lines and reply_lines[0].strip() else user_text)[:120]
        steps: list[str] = []
        for index, entry in enumerate(trace[:12]):
            if not isinstance(entry, dict):
                continue
            tool = str(entry.get("tool") or "")
            if not tool:
                continue
            arguments = str(entry.get("arguments") or "").strip()
            steps.append(f"{len(steps) + 1}. 调用 {tool}" + (f"（参数: {arguments[:80]}）" if arguments else ""))
        if not steps:
            return None
        return {"name": name, "description": description, "steps": steps}
