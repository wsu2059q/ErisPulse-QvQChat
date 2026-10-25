from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import texts

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

BUILTIN_SKILLS: list[dict] = [
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
- action="set" with updates={key: value}: valid QvQChat config keys only (unknown keys are rejected). E.g. reply triggers, aggregate_window, forward_platforms, tool_notice_mode.

Rules: never read back or repeat api keys in your replies; sanity-check a changed model pool with a quick ping if the user asks; settings that affect safety (security_level, trust_agent, owner_only, admin lists) deserve an explicit confirmation even from an admin.""",
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
        if not bool(getattr(self.config, "self_config", True)):
            return []
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
        ]

    def list_skills(self) -> list[dict]:
        merged = {s["name"]: s for s in self._builtin_skills()}
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
