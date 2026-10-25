<div align="center">

[简体中文](README.md) | [繁體中文](README.zh-TW.md) | **English** | [日本語](README.ja.md) | [Русский](README.ru.md)

<img src="https://raw.githubusercontent.com/ErisPulse/ErisPulse/main/.github/assets/ErisPulseLogo.png" width="180" alt="QvQChat" />

</div>

# QvQChat

**A general-purpose agent module for ErisPulse: it chats on your bot's platforms, calls tools, writes and runs code, schedules its own tasks and keeps long-term memory.**

QvQChat is built around a tool loop. The model you point it at can send and receive messages through any ErisPulse adapter, call the services of other installed modules, read and write files, run shell commands and Python code, create scheduled tasks, and store memories worth keeping. Which tools exist at any moment simply depends on what you have installed; modules are picked up without a restart.

It is written for people who already run an ErisPulse bot and want it to get things done instead of only replying. You fill the model pool with any OpenAI-compatible endpoints, decide who is allowed to use which tools, and the agent grows capabilities as you install more modules from the ecosystem.

The module needs ErisPulse 2.8.0 or newer and at least one platform adapter. It ships with a web console that also works on its own, and the chat side and the web side run through the same pipeline: a task started from QQ is visible live in the browser and can be stopped from there.

<p>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/pypi/v/ErisPulse-QvQChat?style=for-the-badge&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://pypi.org/project/ErisPulse-QvQChat/"><img src="https://img.shields.io/badge/Python-3.10+-FFD43B?style=for-the-badge&logo=python&logoColor=blue" alt="Python"></a>
  <a href="https://github.com/wsu2059q/ErisPulse-QvQChat/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/wsu2059q/ErisPulse-QvQChat/ci.yml?style=for-the-badge&label=CI" alt="CI"></a>
  <a href="https://github.com/wsu2059q/ErisPulse-QvQChat/pkgs/container/erispulse-qvqchat"><img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"></a>
</p>

<img src=".github/assets/overview.png" width="860" alt="QvQChat web console" />

---

## Installation

With the ErisPulse CLI:

```bash
epsdk install ErisPulse-QvQChat
```

or with pip. Python 3.10+, ErisPulse >= 2.8.0 and at least one platform adapter are required:

```bash
pip install ErisPulse-QvQChat
```

or Docker. The image is built on the official ErisPulse image and already contains the module:

```bash
docker run -d --name qvqchat -p 8000:8000 --restart unless-stopped ghcr.io/wsu2059q/erispulse-qvqchat:latest
```

## Quick start

1. Install the module and at least one adapter, for example `epsdk install ErisPulse-OneBotAdapter`.
2. Open the Dashboard and find the QvQChat view. On the model pool page, add an OpenAI-compatible model: a name, a base URL, an API key and the model id are enough.
3. Tell the agent who its admins are. While `admins` is empty, nobody on the chat side has admin rights, so tools such as running commands stay unavailable there:

```toml
[QvQChat]
admins = ["123456"]   # your user id on the chat platform
```

4. Open `http://<host>:8000/QvQChat/view` for the standalone console, or use the QvQChat entry in the Dashboard sidebar. When the Dashboard is installed, its login token is reused. Without it, QvQChat generates an access token on first start and prints it to the log; you can also set `QvQChat.view_token` yourself.
5. Write to the bot in a private chat, or mention it in a group. It answers where your users already are.

Chat commands use `/qvq` (`/agent` still works as an alias; each subcommand also accepts its Chinese name):

| Command | What it does |
|---|---|
| `/qvq` | show command help |
| `/qvq reset` | clear this session's conversation |
| `/qvq persona [id]` | list or switch persona |
| `/qvq start` | resend the persona opening (admin) |
| `/qvq tasks` | list scheduled tasks |
| `/qvq memories` | inspect memories, facts and profile; admins can clear them by category |
| `/qvq compact` | compact this session's context now |
| `/qvq status` | models, tools and sessions at a glance |
| `/qvq takeover [minutes]` | take over this session (admin), defaults to 10 minutes |
| `/qvq release` | release the takeover |

---

## What the agent can do

### A tool loop with practical tools

The built-in tools cover messaging (`send_message`, `send_dsl`), platform APIs, file access, shell and Python execution, long-term memory, the knowledge base, scheduled tasks and personas. `run_python_sdk` executes Python inside the main process, so scripts can use the sdk, adapters and storage directly. `spawn_agent` starts a sub-agent in its own session when a task deserves separate exploration, and only the conclusion comes back to the main conversation. When the same tool fails twice in a row, a short correction hint with the error summary is injected so the model can fix its arguments itself (`tool_self_heal`, on by default).

Tools also come from two other places. Every MCP server you connect contributes its own tools, over stdio or Streamable HTTP, and every installed ErisPulse module that declares services becomes callable as well. See [Extending QvQChat](#extending-qvqchat) below.

After a novel multi-step task you can ask the model to save its approach as a skill. Skills are plain Markdown files under `data/QvQChat/skills`, injected into the system prompt on demand, and `skill_induct` switches the whole mechanism off if you do not want it.

### The web console

<img src=".github/assets/chat.png" width="49%" alt="Chat page" /> <img src=".github/assets/models.png" width="49%" alt="Model pool page" />

The console at `/QvQChat/view` streams replies as they are generated, gives each tool call its own step on the timeline, and shows the model's thinking process in a collapsed block. There is a staging queue for messages you want to hold back, and a stop button for running tasks. Refresh the page or come back later: running tasks pick up where they were. Sessions can be pinned, archived and renamed, and new ones are named by the model automatically. Any session can be shared through a temporary read-only link with an expiry and a token budget, or exported as Markdown.

The console also hosts the management pages: model pool, personas, knowledge base, audit log, task runs and cost estimates. The settings page renders every configuration item with proper widgets, validation and a dirty check. For programmatic access there is an OpenAI-compatible endpoint, `GET /v1/models` and `POST /v1/chat/completions` with streaming, authenticated with the same access token.

Because both sides share one pipeline, a task the agent started from a chat platform shows up live in the browser, tool call by tool call, and can be stopped from there.

### Group chats and personas

In groups the agent wakes up when mentioned; you can add wake prefixes, and private chats trigger it by default. Plain conversational replies are split into paragraphs and sent one by one with configurable, human-like pacing, while the result of a tool task is packed into a merged-forward card when the platform supports it. With `reply_narrate` enabled, the agent narrates tool tasks as it works: one sentence about what it is going to do, a short report after each result, and a brief conclusion at the end, each sent as its own message.

Personas carry a system prompt, opening messages, tone parameters and example dialogue, and can restrict which tools they may use. Group members can get member-level personas with fallback to a group-level and then a global persona. `group_isolation` gives each member of a group a separate context, persona and memory, if that fits the group better. Speaking up in groups without being mentioned is deliberately not a core feature: it is left to a participation plugin and stays off until you enable `participation_enabled` (see QvQStalker below).

<img src=".github/assets/qq.png" width="680" alt="Agent working in a QQ group" />

### Memory, profiles and the knowledge base

The agent keeps long-term memories per session plus a global scope, recalls the relevant ones into each request, and can be told to remember or forget things through tools. Facts such as preferences and agreements are extracted from conversations automatically and injected afterwards. On top of that, facts and memories from all sessions of the same user are consolidated into a cross-session profile every six hours by default; profile entries that nothing reinforces for 30 days fade out. `/qvq memories` and the memory page in the console show what is stored and can clear it by category.

The knowledge base holds longer documents. Entries are chunked and retrieved by keyword scoring, and relevant chunks are injected into the system prompt automatically. Entries can also carry trigger keywords in the style of a SillyTavern world book, so a piece of lore is only injected when it actually comes up in conversation. If you configure an OpenAI-compatible embedding endpoint, retrieval switches to cosine similarity and falls back to keyword scoring whenever any part of that chain is unavailable.

### A model pool that looks after itself

Models live in a pool of providers; any OpenAI-compatible endpoint works, and provider presets keep the form short. Model entries are enriched from the models.dev catalog with capability flags (vision, files, tool calling, reasoning) and prices, both overridable by hand. Requests fail over to the next model in the pool, a model that fails three times in a row gets a cooling break with exponential backoff, and a failover chain skips models that lack a capability the request needs. When the main model cannot see images, a vision model describes them and hands the text over. Difficulty-aware routing can send small talk to a cheap model and code or long analysis to a strong one; it is experimental and off by default. Usage is recorded per model and per day with cost estimates, and background work such as summarizing or titling can be assigned to cheaper models via `task_models`. If you allow it (`self_config`, on by default), the agent can even manage its own model pool, MCP servers and settings through admin-only tools.

### Context that survives long tasks

Old tool output is slimmed down continuously. When the estimated context size crosses the threshold (CJK-aware estimation, 128000 by default), older turns are summarized into an early-context digest instead of being dropped; compression can also run every N turns preventively, or on demand via `/qvq compact`. An optional budget mode packs the system prompt components and the history by priority against the selected model's context window and triggers compression on overflow, and while compacting it also extracts entities, preferences and to-dos as facts. Tool budgets are generous (50 rounds and 150 calls by default), and near the limit the model gets a convergence reminder rather than a hard cutoff.

### Scheduled tasks that survive a restart

The agent creates scheduled tasks itself through tools, described in natural language. Four schedule formats are supported: `cron:0 9 * * 1-5`, `at:2026-10-17 09:00`, `in:30m` and `every:2h`. A task marked as deep runs in three phases: plan, execute, review, with one bounded correction round if the review finds gaps. Task runs are recorded and visible in the console. When ErisPulse-Cron is installed, cron tasks are handed over to it. If the process restarts mid-generation, interrupted replies are detected and rerun, the failed-send queue is replayed, and interrupted task runs are marked (`recovery_enabled` and related settings).

### Safety model

Computer access has three levels. `strict` runs no commands or code and allows only read-only access to whitelisted directories. `standard`, the default, executes dangerous commands only after you confirm them in chat, showing the full command text, and keeps file access inside `work_dirs`. `permissive` lifts the restrictions and records everything in the audit log instead. Tools are split into a basic safe set available to everyone (messaging, memory, read-only file access, scheduled tasks) and admin-only tools (execution, writing files, sub-agents, adapter and module calls). Scheduled tasks run with the permissions of whoever created them. `admins` decides who the admins are, `safe_tools` can open specific tools to everyone, `owner_only` limits the whole agent to the owner, and `trust_agent` skips confirmations while still auditing everything.

---

## Companion plugins

Two standalone modules extend QvQChat and show what the extension points can do:

- [ErisPulse-QvQStalker](https://github.com/wsu2059q/ErisPulse-QvQStalker) lets the agent follow group conversations through the observe channel and decide on its own when to chip in: heat tracking, a five-layer judgment and an impulse value decide when it speaks. Its fifteen behavior parameters are registered through `qvq_settings` and editable directly in the settings page.
- [ErisPulse-QvQMemes](https://github.com/wsu2059q/ErisPulse-QvQMemes) gives the agent a sticker habit. A `send_sticker` tool lets the model pick which sticker fits the moment, group images are collected automatically through the observe channel and tagged by a vision model, and freshness weighting keeps it from repeating the same few pictures.

Group participation stays off until you enable `participation_enabled`; installing a plugin does not open the gate by itself.

## Extending QvQChat

Extensions are ordinary ErisPulse modules; no dedicated interface is needed. A module that declares services in `get_meta()` automatically exposes each service as an agent tool, available right after install and gone after uninstall:

```python
from ErisPulse.Core.Bases import BaseModule, ModuleMeta

class Main(BaseModule):
    @staticmethod
    def get_meta() -> ModuleMeta:
        return ModuleMeta(name="Draw", services=[
            {"name": "draw", "description": "Generate an image from a text prompt"},
        ])

    async def draw(self, prompt: str, size: str = "1024x1024"):
        return {"image_url": "https://..."}
```

For deeper integration, a module can implement any of the convention services. QvQChat discovers them through the ecosystem bridge and refreshes on module load and unload:

- `qvq_personas()` returns persona presets (id, name, system prompt, optional tool subset);
- `qvq_schemas()` returns explicit JSON Schemas for the module's own services, replacing signature inference;
- `qvq_settings()` declares configuration descriptors that appear in the settings page and flow back to the module through the `plugin_config` service and the `qvq.plugin_config` event.

Modules can also subscribe to lifecycle events such as `qvq.message` and `qvq.replied`. In the other direction, QvQChat itself offers `chat`, `run_prompt` and `get_status` services for other modules to call. The full contract, including attachments and the permission model, is described in [docs/inter-module-en.md](docs/inter-module-en.md).

## Configuration

All settings live in the `QvQChat` section and can be edited in the Dashboard settings page, grouped into models, triggers, conversation, tools, ecosystem, MCP, memory, knowledge base, skills, tasks, usage, security, participation and access. Everything mentioned on this page, from `wake_prefixes` and `user_rate_limit` to `daily_token_limit` and `delivery_profiles`, is a plain config key with a description there. See [CHANGELOG.md](CHANGELOG.md) for what changed recently and [ARCHITECTURE.md](ARCHITECTURE.md) for how the module is put together.

## Development

```bash
git clone https://github.com/wsu2059q/ErisPulse-QvQChat
cd ErisPulse-QvQChat
pip install -e .[test]
pytest
```

## License

[MIT](LICENSE)
