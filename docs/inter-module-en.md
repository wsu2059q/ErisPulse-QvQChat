# Extension & Inter-module Communication

QvQChat's capabilities come from ErisPulse's modular architecture. Any ErisPulse module can extend QvQChat — no special interface required.

## Quick Start: Make Your Module a Tool

Declare `services` in your module's `get_meta()`. Each service automatically becomes a QvQChat tool:

```python
from ErisPulse.Core.Bases import BaseModule, ModuleMeta

class Main(BaseModule):
    @staticmethod
    def get_meta() -> ModuleMeta:
        return ModuleMeta(name="Draw", services=[
            {"name": "draw", "description": "Generate an image from a text prompt, returns image URL"},
        ])

    async def draw(self, prompt: str, size: str = "1024x1024"):
        """Generate an image"""
        return {"image_url": "https://..."}
```

Install the module and the tool goes live. Uninstall and it disappears. No restart needed.

## Three Optional Deep-Integration Services

Your module can implement any of these services to participate in agent behavior:

### `qvq_prompts()` → Inject System Prompt

Returns `list[str]` or `list[{"text": str, "priority": int}]`. Concatenated to the system prompt in `priority` ascending order.

Use for: usage conventions ("send the image to the user after drawing"), behavior constraints, knowledge notes.

### `qvq_personas()` → Register Persona Presets

Returns `list[{"id", "name", "system", "tools"?}]`. IDs are auto-prefixed with `ext.<module>.` and cleaned up on module uninstall.

Use for: registering specialized personas (translator, code reviewer, etc.). The optional `tools` list restricts which tools that persona can use.

### `qvq_schemas()` → Explicit Parameter Schemas

Returns `dict[service_name, JSON Schema]` to override signature inference. Use when parameters are complex.

## Event Subscription

QvQChat broadcasts two lifecycle events. Subscribe with `sdk.lifecycle.on()`:

| Event | When | Payload |
|---|---|---|
| `qvq.message` | When a user message arrives | `chat_key` `platform` `sender_id` `sender_name` `text` `is_group` |
| `qvq.replied` | After a reply is sent | `chat_key` `reply` `tools` |

```python
async def setup(self):
    sdk.lifecycle.on("qvq.message", self.on_message)

async def on_message(self, data):
    if "help" in data.get("text", ""):
        pass  # Do anything: log, trigger other modules, push notifications
```

## Calling QvQChat from Other Modules

QvQChat declares three services that other modules can call in reverse:

| Service | Signature | Description |
|---|---|---|
| `chat` | `(session_id, prompt, persona="")` | Chat with the agent, returns text; `session_id` is `platform:detail_type:target_id` |
| `run_prompt` | `(chat_key, prompt, ...)` | Run a prompt, optionally send result to target session |
| `get_status` | `()` | Runtime status summary |

## Attachments

Files and images sent by users in conversation:

- **Images**: Auto-converted to base64 and injected into the model request (supports Ctrl+V paste); automatically stripped with retry if the model doesn't support vision
- **Any file** (zip / pdf / code etc.): Deduplicated by SHA-256 hash and saved to `data/QvQChat/uploads/`. The file path is appended to the conversation as `[attachment xxx] saved to: /path/to/file` — the AI can then use tools like `read_file` / `run_command` to read, extract, or analyze it
- **Edit preserves attachments**: When editing a historical message, image and multimodal segments are preserved; only the text segment is replaced

The AI can also proactively send files to users via `send_message` with the `path` parameter.

## Permission Model

| Source | Access | Notes |
|---|---|---|
| Dashboard / local | Owner | All tools available |
| Chat · Admin | Admin | Users in `admins` list; dangerous tools available (with confirmation) |
| Chat · Regular user | Safe set | Send messages, memory, read-only files, scheduled tasks |

Scheduled tasks run with their **creator's permission**: tasks created by an admin execute with admin access; tasks created by regular users cannot use dangerous tools.
