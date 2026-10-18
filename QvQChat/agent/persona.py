from __future__ import annotations

from typing import Any

from .. import texts, utils

PERSONAS_KEY = "QvQChat:personas"
BINDING_PREFIX = "QvQChat:binding:"

ASSISTANT_ID = "assistant"


def _default_personas() -> dict:
    return {
        ASSISTANT_ID: {
            "id": ASSISTANT_ID,
            "name": texts.t("persona_default_name"),
            "system": texts.t("persona_default_system"),
            "opening": [],
            "tools": None,
            "builtin": True,
        }
    }


class PersonaManager:
    def __init__(self, sdk: Any):
        self.sdk = sdk

    def list(self) -> list[dict]:
        stored = self.sdk.storage.get(PERSONAS_KEY, {})
        personas = _default_personas()
        if isinstance(stored, dict):
            for persona_id, data in stored.items():
                data = dict(data)
                data["id"] = persona_id
                if persona_id == ASSISTANT_ID:
                    data["builtin"] = True
                    data["modified"] = True
                personas[persona_id] = data
        return list(personas.values())

    def get(self, persona_id: str | None) -> dict:
        if persona_id:
            for persona in self.list():
                if persona["id"] == persona_id:
                    return persona
        return _default_personas()[ASSISTANT_ID]

    def save(self, data: dict) -> dict:
        persona_id = str(data.get("id") or utils.new_id())
        stored = self.sdk.storage.get(PERSONAS_KEY, {})
        if not isinstance(stored, dict):
            stored = {}
        stored[persona_id] = {
            "name": str(data.get("name") or (texts.t("persona_default_name") if persona_id == ASSISTANT_ID else persona_id)),
            "system": str(data.get("system") or texts.t("persona_default_system")),
            "opening": data.get("opening") if isinstance(data.get("opening"), list) else [],
            "tools": data.get("tools") if isinstance(data.get("tools"), list) and data["tools"] else None,
        }
        self.sdk.storage.set(PERSONAS_KEY, stored)
        result = dict(stored[persona_id])
        result["id"] = persona_id
        if persona_id == ASSISTANT_ID:
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

    def resolve(self, chat_key: str) -> dict:
        bound = self.sdk.storage.get(BINDING_PREFIX + chat_key, "")
        return self.get(bound or None)
