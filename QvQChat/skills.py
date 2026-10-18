from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import texts

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


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

    def list_skills(self) -> list[dict]:
        skills = {s["name"]: s for s in self._stored_skills()}
        for s in self._file_skills():
            skills.setdefault(s["name"], s)
        return sorted(skills.values(), key=lambda s: s["name"])

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
