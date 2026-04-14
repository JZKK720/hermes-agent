# Hermes Agent - Development Guide

Instructions for AI coding assistants and developers working on the hermes-agent codebase.

## Development Environment

```bash
source venv/bin/activate  # ALWAYS activate before running Python
```

### Quick Install (dev)

```bash
# Clone and set up with uv (recommended)
git clone --recurse-submodules https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
uv venv venv --python 3.11
export VIRTUAL_ENV="$(pwd)/venv"
uv pip install -e ".[all,dev]"

# Configure
mkdir -p ~/.hermes/{cron,sessions,logs,memories,skills}
cp cli-config.yaml.example ~/.hermes/config.yaml
touch ~/.hermes/.env
echo 'OPENROUTER_API_KEY=sk-or-v1-your-key' >> ~/.hermes/.env

# Verify
hermes doctor
```

### Docker Build

```bash
# Build image (installs Node, Playwright, all Python extras)
docker build -t hermes-agent .

# Run — /opt/data is the HERMES_HOME volume
docker run -it \
  -v "$(pwd)/data:/opt/data" \
  hermes-agent

# With custom HERMES_UID to match host file ownership
docker run -it \
  -e HERMES_UID=$(id -u) \
  -v "$(pwd)/data:/opt/data" \
  hermes-agent

# Expose web UI port (default 9119)
docker run -it \
  -p 9119:9119 \
  -v "$(pwd)/data:/opt/data" \
  hermes-agent web --host 0.0.0.0

# Expose gateway webhook port (default 8644)
docker run -d \
  -p 8644:8644 \
  -v "$(pwd)/data:/opt/data" \
  hermes-agent gateway
```

> **Port reference** — the Dockerfile has NO `EXPOSE` directive:
> | Service | Default Port | Flag/Config |
> |---------|-------------|-------------|
> | Web UI | **9119** | `hermes web --port N` |
> | Gateway webhook | **8644** | `platforms.webhook.extra.port` in config.yaml |
> | BlueBubbles webhook | **8645** | `BLUEBUBBLES_WEBHOOK_PORT` env var |
> | ACP server | stdio (no port) | — |
>
> When running in Docker, always add `-p <host>:<container>` for the ports you need.

### Connecting to a Custom OpenAI-Compatible Endpoint

Set the provider to `custom` and point `base_url` at your endpoint:

```yaml
# ~/.hermes/config.yaml
model:
  provider: "custom"        # aliases: lmstudio, ollama, vllm, llamacpp
  base_url: "http://localhost:7788/v1"   # or any host:port
  default: "your-model-name"
```

Or via env vars:
```bash
export OPENAI_BASE_URL=http://localhost:7788/v1
export HERMES_INFERENCE_PROVIDER=custom
```

In Docker, use `host.docker.internal` to reach host services:
```yaml
model:
  provider: "custom"
  base_url: "http://host.docker.internal:7788/v1"
```

No API key is required for most local servers. If the server requires one, set `OPENAI_API_KEY` in `~/.hermes/.env`.

## Project Structure

```
hermes-agent/
├── run_agent.py          # AIAgent class — core conversation loop
├── model_tools.py        # Tool orchestration, discover_builtin_tools(), handle_function_call()
├── toolsets.py           # Toolset definitions, _HERMES_CORE_TOOLS list
├── cli.py                # HermesCLI class — interactive CLI orchestrator
├── hermes_state.py       # SessionDB — SQLite session store (FTS5 search)
├── hermes_constants.py   # get_hermes_home(), display_hermes_home() — import-safe
├── hermes_logging.py     # Logging helpers
├── hermes_time.py        # Timezone-aware time helpers
├── mcp_serve.py          # Expose Hermes as an MCP server (FastMCP)
├── utils.py              # Shared utilities (atomic_json_write, env_var_enabled)
├── agent/                # Agent internals
│   ├── prompt_builder.py         # System prompt assembly
│   ├── context_compressor.py     # Auto context compression (default context engine)
│   ├── context_engine.py         # Abstract base: pluggable context engines
│   ├── context_references.py     # Cross-session context reference tracking
│   ├── prompt_caching.py         # Anthropic prompt caching
│   ├── auxiliary_client.py       # Auxiliary LLM client (vision, summarization)
│   ├── model_metadata.py         # Model context lengths, token estimation
│   ├── models_dev.py             # models.dev registry integration
│   ├── credential_pool.py        # Multi-credential failover pool
│   ├── smart_model_routing.py    # Cheap-vs-strong model routing
│   ├── memory_manager.py         # Orchestrates built-in + plugin memory providers
│   ├── memory_provider.py        # Abstract base: pluggable memory providers
│   ├── display.py                # KawaiiSpinner, tool preview formatting
│   ├── error_classifier.py       # API error → FailoverReason classification
│   ├── insights.py               # Session analytics + cost estimation (/insights)
│   ├── manual_compression_feedback.py  # /compress before/after stats
│   ├── rate_limit_tracker.py     # Per-model rate limit tracking
│   ├── redact.py                 # Sensitive text redaction from tool results
│   ├── retry_utils.py            # Jittered backoff helpers
│   ├── skill_commands.py         # Skill slash commands (shared CLI/gateway)
│   ├── skill_utils.py            # Shared skill loading helpers
│   ├── subdirectory_hints.py     # Working directory hint injection
│   ├── title_generator.py        # Auto session title generation
│   ├── trajectory.py             # Trajectory saving helpers
│   └── usage_pricing.py          # Token cost estimation per model
├── hermes_cli/           # CLI subcommands and setup
│   ├── main.py           # Entry point — all `hermes` subcommands
│   ├── config.py         # DEFAULT_CONFIG, OPTIONAL_ENV_VARS, migration (_config_version: 16)
│   ├── commands.py       # Central slash command registry (CommandDef) + autocomplete
│   ├── auth.py           # Provider credential resolution + credential pool writes
│   ├── auth_commands.py  # `hermes login/logout` command dispatch
│   ├── callbacks.py      # Terminal callbacks (clarify, sudo, approval)
│   ├── setup.py          # Interactive setup wizard
│   ├── skin_engine.py    # Skin/theme engine — CLI visual customization
│   ├── skills_config.py  # `hermes skills` — enable/disable per platform
│   ├── tools_config.py   # `hermes tools` — enable/disable per platform
│   ├── skills_hub.py     # `/skills` slash command (search, browse, install)
│   ├── models.py         # Model catalog, provider model lists
│   ├── model_switch.py   # Shared /model switch pipeline (CLI + gateway)
│   ├── model_normalize.py # Model name normalization
│   ├── banner.py         # Welcome banner + ASCII art
│   ├── colors.py         # Rich color constants
│   ├── default_soul.py   # Default SOUL.md content for Docker installs
│   ├── doctor.py         # `hermes doctor` diagnostics
│   ├── backup.py         # Config/data backup helpers
│   ├── claw.py           # OpenClaw migration (hermes claw migrate)
│   ├── clipboard.py      # /paste — OS clipboard image capture
│   ├── cli_output.py     # Structured CLI output helpers
│   ├── codex_models.py   # OpenAI Codex model list
│   ├── copilot_auth.py   # GitHub Copilot OAuth flow
│   ├── cron.py           # `hermes cron` subcommand
│   ├── curses_ui.py      # Reusable curses-based interactive menu (replaces simple_term_menu)
│   ├── debug.py          # `hermes debug` — system info + log uploader
│   ├── dump.py           # Session dump / export
│   ├── env_loader.py     # Load ~/.hermes/.env with encoding fallback
│   ├── gateway.py        # `hermes gateway` subcommand
│   ├── logs.py           # `hermes logs` subcommand
│   ├── mcp_config.py     # MCP server config management
│   ├── memory_setup.py   # Memory provider setup
│   ├── nous_subscription.py  # Nous Portal subscription status
│   ├── pairing.py        # Device pairing for OAuth flows
│   ├── platforms.py      # `hermes platforms` — gateway platform status
│   ├── plugins.py        # Plugin discovery + loading
│   ├── plugins_cmd.py    # `hermes plugins` subcommand
│   ├── profiles.py       # `hermes profile` — multi-instance profile management
│   ├── providers.py      # `hermes provider` — provider info + switching
│   ├── runtime_provider.py # Active provider resolution at runtime
│   ├── status.py         # `hermes status` — component status
│   ├── tips.py           # Random usage tips shown at startup
│   ├── uninstall.py      # `hermes uninstall`
│   ├── webhook.py        # `hermes webhook` — webhook subscription management
│   └── web_server.py     # `hermes web` — FastAPI web UI on port 9119
├── tools/                # Tool implementations (self-registering)
│   ├── registry.py           # Central tool registry (schemas, handlers, dispatch)
│   ├── approval.py           # Dangerous command detection + per-session approvals
│   ├── terminal_tool.py      # Terminal orchestration (sudo, env lifecycle, backends)
│   ├── process_registry.py   # Background process management
│   ├── file_tools.py         # File read/write/search/patch (LLM-facing tools)
│   ├── file_operations.py    # Low-level file ops used by file_tools.py
│   ├── web_tools.py          # web_search, web_extract (Parallel + Firecrawl)
│   ├── browser_tool.py       # Browser automation (Browserbase + local CDP)
│   ├── browser_providers/    # Browser backend abstractions
│   ├── code_execution_tool.py # execute_code sandbox
│   ├── delegate_tool.py      # Subagent delegation + parallel tasks
│   ├── mcp_tool.py           # MCP client
│   ├── checkpoint_manager.py # Filesystem snapshots via shadow git repos
│   ├── tool_result_storage.py # 3-layer tool result budget system
│   ├── budget_config.py      # Budget constants (BudgetConfig dataclass)
│   ├── vision_tools.py       # Image analysis via multimodal models
│   ├── image_generation_tool.py  # Image generation (FAL.ai)
│   ├── tts_tool.py           # Text-to-speech (Edge TTS + ElevenLabs)
│   ├── transcription_tools.py # Speech-to-text (Whisper)
│   ├── voice_mode.py         # Voice mode orchestration
│   ├── memory_tool.py        # memory tool (read/write ~/.hermes/memories/)
│   ├── todo_tool.py          # todo tool (agent-level, intercepted before dispatch)
│   ├── session_search_tool.py # FTS5 session history search
│   ├── clarify_tool.py       # Ask user clarifying questions
│   ├── cronjob_tools.py      # Scheduled task management
│   ├── skills_tool.py        # skills_list, skill_view
│   ├── skill_manager_tool.py # skill_manage (install/update/remove)
│   ├── send_message_tool.py  # Cross-platform messaging (Telegram/Discord/Slack/etc)
│   ├── homeassistant_tool.py # Home Assistant smart home control
│   ├── mixture_of_agents_tool.py # Mixture-of-agents reasoning
│   ├── rl_training_tool.py   # RL training integration (Atropos)
│   ├── path_security.py      # Path traversal + deny-list enforcement
│   ├── url_safety.py         # URL validation + allowlist
│   ├── skills_guard.py       # Security scanner for hub-installed skills
│   ├── tirith_security.py    # Tirith policy engine integration
│   ├── osv_check.py          # OSV vulnerability database checks
│   ├── patch_parser.py       # Unified diff patch parsing
│   ├── interrupt.py          # Ctrl-C / interrupt signal handling
│   └── environments/         # Terminal backends (local, docker, ssh, modal, daytona, singularity)
├── plugins/              # Pluggable extensions (loaded at runtime)
│   ├── memory/           # Memory provider plugins
│   │   ├── honcho/       # Honcho AI user modeling
│   │   ├── hindsight/    # Hindsight memory
│   │   ├── holographic/  # Holographic memory
│   │   ├── mem0/         # Mem0 memory
│   │   ├── byterover/    # ByteRover memory
│   │   ├── openviking/   # OpenViking memory
│   │   ├── retaindb/     # RetainDB memory
│   │   └── supermemory/  # SuperMemory
│   └── context_engine/   # Context engine plugins (placeholder for LCM etc.)
├── gateway/              # Messaging platform gateway
│   ├── run.py            # GatewayRunner — platform lifecycle, message routing, cron
│   ├── session.py        # SessionStore — conversation persistence
│   ├── config.py         # Platform config resolution
│   ├── delivery.py       # Reliable message delivery
│   └── platforms/        # Platform adapters (14 platforms):
│       ├── telegram.py, discord.py, slack.py, whatsapp.py
│       ├── signal.py, matrix.py, email.py, sms.py
│       ├── bluebubbles.py, homeassistant.py
│       ├── dingtalk.py, feishu.py, wecom.py, weixin.py
│       ├── mattermost.py, api_server.py, webhook.py
│       └── ADDING_A_PLATFORM.md
├── acp_adapter/          # ACP server (VS Code / Zed / JetBrains integration)
├── cron/                 # Scheduler (jobs.py, scheduler.py)
├── environments/         # RL training environments (Atropos)
├── skills/               # Bundled skills (synced to ~/.hermes/skills/ on install)
├── optional-skills/      # Official optional skills (hub-discoverable, not auto-activated)
├── tests/                # Pytest suite (~3000+ tests)
└── batch_runner.py       # Parallel batch processing
```

**User config:** `~/.hermes/config.yaml` (settings), `~/.hermes/.env` (API keys)

**User data directories:**
```
~/.hermes/
├── config.yaml       # Settings
├── .env              # API keys
├── auth.json         # OAuth credentials
├── skills/           # Active skills
├── memories/         # MEMORY.md, USER.md
├── state.db          # SQLite session database
├── sessions/         # JSON session logs
├── checkpoints/      # Filesystem snapshots (shadow git repos)
├── cron/             # Scheduled job data
├── skins/            # User-installed skin YAML files
└── profiles/         # Additional profile home directories
```

## File Dependency Chain

```
tools/registry.py  (no deps — imported by all tool files)
       ↑
tools/*.py  (each calls registry.register() at import time)
       ↑
model_tools.py  (imports tools/registry + triggers tool discovery)
       ↑                 ↑
run_agent.py          cli.py, batch_runner.py, environments/
       ↑
plugins/memory/*.py    (MemoryProvider ABC — activated via memory.provider config)
plugins/context_engine/*.py  (ContextEngine ABC — activated via context.engine config)
```

Plugin loading order: `_discover_tools()` fires first, then `discover_mcp_tools()`, then plugin tool discovery in `model_tools.py`. Memory/context-engine plugins are initialized in `run_agent.py.__init__()` after tool discovery.

---

## AIAgent Class (run_agent.py)

```python
class AIAgent:
    def __init__(self,
        model: str = "anthropic/claude-opus-4.6",
        max_iterations: int = 90,
        enabled_toolsets: list = None,
        disabled_toolsets: list = None,
        quiet_mode: bool = False,
        save_trajectories: bool = False,
        platform: str = None,           # "cli", "telegram", etc.
        session_id: str = None,
        skip_context_files: bool = False,
        skip_memory: bool = False,
        # ... plus provider, api_mode, callbacks, routing params
    ): ...

    def chat(self, message: str) -> str:
        """Simple interface — returns final response string."""

    def run_conversation(self, user_message: str, system_message: str = None,
                         conversation_history: list = None, task_id: str = None) -> dict:
        """Full interface — returns dict with final_response + messages."""
```

### Agent Loop

The core loop is inside `run_conversation()` — entirely synchronous:

```python
while api_call_count < self.max_iterations and self.iteration_budget.remaining > 0:
    response = client.chat.completions.create(model=model, messages=messages, tools=tool_schemas)
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args, task_id)
            messages.append(tool_result_message(result))
        api_call_count += 1
    else:
        return response.content
```

Messages follow OpenAI format: `{"role": "system/user/assistant/tool", ...}`. Reasoning content is stored in `assistant_msg["reasoning"]`.

---

## CLI Architecture (cli.py)

- **Rich** for banner/panels, **prompt_toolkit** for input with autocomplete
- **KawaiiSpinner** (`agent/display.py`) — animated faces during API calls, `┊` activity feed for tool results
- `load_cli_config()` in cli.py merges hardcoded defaults + user config YAML
- **Skin engine** (`hermes_cli/skin_engine.py`) — data-driven CLI theming; initialized from `display.skin` config key at startup; skins customize banner colors, spinner faces/verbs/wings, tool prefix, response box, branding text
- `process_command()` is a method on `HermesCLI` — dispatches on canonical command name resolved via `resolve_command()` from the central registry
- Skill slash commands: `agent/skill_commands.py` scans `~/.hermes/skills/`, injects as **user message** (not system prompt) to preserve prompt caching

### Slash Command Registry (`hermes_cli/commands.py`)

All slash commands are defined in a central `COMMAND_REGISTRY` list of `CommandDef` objects. Every downstream consumer derives from this registry automatically:

- **CLI** — `process_command()` resolves aliases via `resolve_command()`, dispatches on canonical name
- **Gateway** — `GATEWAY_KNOWN_COMMANDS` frozenset for hook emission, `resolve_command()` for dispatch
- **Gateway help** — `gateway_help_lines()` generates `/help` output
- **Telegram** — `telegram_bot_commands()` generates the BotCommand menu
- **Slack** — `slack_subcommand_map()` generates `/hermes` subcommand routing
- **Autocomplete** — `COMMANDS` flat dict feeds `SlashCommandCompleter`
- **CLI help** — `COMMANDS_BY_CATEGORY` dict feeds `show_help()`

### Adding a Slash Command

1. Add a `CommandDef` entry to `COMMAND_REGISTRY` in `hermes_cli/commands.py`:
```python
CommandDef("mycommand", "Description of what it does", "Session",
           aliases=("mc",), args_hint="[arg]"),
```
2. Add handler in `HermesCLI.process_command()` in `cli.py`:
```python
elif canonical == "mycommand":
    self._handle_mycommand(cmd_original)
```
3. If the command is available in the gateway, add a handler in `gateway/run.py`:
```python
if canonical == "mycommand":
    return await self._handle_mycommand(event)
```
4. For persistent settings, use `save_config_value()` in `cli.py`

**CommandDef fields:**
- `name` — canonical name without slash (e.g. `"background"`)
- `description` — human-readable description
- `category` — one of `"Session"`, `"Configuration"`, `"Tools & Skills"`, `"Info"`, `"Exit"`
- `aliases` — tuple of alternative names (e.g. `("bg",)`)
- `args_hint` — argument placeholder shown in help (e.g. `"<prompt>"`, `"[name]"`)
- `cli_only` — only available in the interactive CLI
- `gateway_only` — only available in messaging platforms
- `gateway_config_gate` — config dotpath (e.g. `"display.tool_progress_command"`); when set on a `cli_only` command, the command becomes available in the gateway if the config value is truthy. `GATEWAY_KNOWN_COMMANDS` always includes config-gated commands so the gateway can dispatch them; help/menus only show them when the gate is open.

**Adding an alias** requires only adding it to the `aliases` tuple on the existing `CommandDef`. No other file changes needed — dispatch, help text, Telegram menu, Slack mapping, and autocomplete all update automatically.

---

## Adding New Tools

Requires changes in **2 files**:

**1. Create `tools/your_tool.py`:**
```python
import json, os
from tools.registry import registry

def check_requirements() -> bool:
    return bool(os.getenv("EXAMPLE_API_KEY"))

def example_tool(param: str, task_id: str = None) -> str:
    return json.dumps({"success": True, "data": "..."})

registry.register(
    name="example_tool",
    toolset="example",
    schema={"name": "example_tool", "description": "...", "parameters": {...}},
    handler=lambda args, **kw: example_tool(param=args.get("param", ""), task_id=kw.get("task_id")),
    check_fn=check_requirements,
    requires_env=["EXAMPLE_API_KEY"],
)
```

**2. Add to `toolsets.py`** — either `_HERMES_CORE_TOOLS` (all platforms) or a new toolset.

Auto-discovery: any `tools/*.py` file with a top-level `registry.register()` call is imported automatically — no manual import list to maintain.

The registry handles schema collection, dispatch, availability checking, and error wrapping. All handlers MUST return a JSON string.

**Path references in tool schemas**: If the schema description mentions file paths (e.g. default output directories), use `display_hermes_home()` to make them profile-aware. The schema is generated at import time, which is after `_apply_profile_override()` sets `HERMES_HOME`.

**State files**: If a tool stores persistent state (caches, logs, checkpoints), use `get_hermes_home()` for the base directory — never `Path.home() / ".hermes"`. This ensures each profile gets its own state.

**Agent-level tools** (todo, memory): intercepted by `run_agent.py` before `handle_function_call()`. See `todo_tool.py` for the pattern.

---

## Adding Configuration

### config.yaml options:
1. Add to `DEFAULT_CONFIG` in `hermes_cli/config.py`
2. Bump `_config_version` (currently **16**) to trigger migration for existing users

### .env variables:
1. Add to `OPTIONAL_ENV_VARS` in `hermes_cli/config.py` with metadata:
```python
"NEW_API_KEY": {
    "description": "What it's for",
    "prompt": "Display name",
    "url": "https://...",
    "password": True,
    "category": "tool",  # provider, tool, messaging, setting
},
```

### Config loaders (two separate systems):

| Loader | Used by | Location |
|--------|---------|----------|
| `load_cli_config()` | CLI mode | `cli.py` |
| `load_config()` | `hermes tools`, `hermes setup` | `hermes_cli/config.py` |
| Direct YAML load | Gateway | `gateway/run.py` |

---

## Skin/Theme System

The skin engine (`hermes_cli/skin_engine.py`) provides data-driven CLI visual customization. Skins are **pure data** — no code changes needed to add a new skin.

### Architecture

```
hermes_cli/skin_engine.py    # SkinConfig dataclass, built-in skins, YAML loader
~/.hermes/skins/*.yaml       # User-installed custom skins (drop-in)
```

- `init_skin_from_config()` — called at CLI startup, reads `display.skin` from config
- `get_active_skin()` — returns cached `SkinConfig` for the current skin
- `set_active_skin(name)` — switches skin at runtime (used by `/skin` command)
- `load_skin(name)` — loads from user skins first, then built-ins, then falls back to default
- Missing skin values inherit from the `default` skin automatically

### What skins customize

| Element | Skin Key | Used By |
|---------|----------|---------|
| Banner panel border | `colors.banner_border` | `banner.py` |
| Banner panel title | `colors.banner_title` | `banner.py` |
| Banner section headers | `colors.banner_accent` | `banner.py` |
| Banner dim text | `colors.banner_dim` | `banner.py` |
| Banner body text | `colors.banner_text` | `banner.py` |
| Response box border | `colors.response_border` | `cli.py` |
| Spinner faces (waiting) | `spinner.waiting_faces` | `display.py` |
| Spinner faces (thinking) | `spinner.thinking_faces` | `display.py` |
| Spinner verbs | `spinner.thinking_verbs` | `display.py` |
| Spinner wings (optional) | `spinner.wings` | `display.py` |
| Tool output prefix | `tool_prefix` | `display.py` |
| Per-tool emojis | `tool_emojis` | `display.py` → `get_tool_emoji()` |
| Agent name | `branding.agent_name` | `banner.py`, `cli.py` |
| Welcome message | `branding.welcome` | `cli.py` |
| Response box label | `branding.response_label` | `cli.py` |
| Prompt symbol | `branding.prompt_symbol` | `cli.py` |

### Built-in skins

- `default` — Classic Hermes gold/kawaii (the current look)
- `ares` — Crimson/bronze war-god theme with custom spinner wings
- `mono` — Clean grayscale monochrome
- `slate` — Cool blue developer-focused theme

### Adding a built-in skin

Add to `_BUILTIN_SKINS` dict in `hermes_cli/skin_engine.py`:

```python
"mytheme": {
    "name": "mytheme",
    "description": "Short description",
    "colors": { ... },
    "spinner": { ... },
    "branding": { ... },
    "tool_prefix": "┊",
},
```

### User skins (YAML)

Users create `~/.hermes/skins/<name>.yaml`:

```yaml
name: cyberpunk
description: Neon-soaked terminal theme

colors:
  banner_border: "#FF00FF"
  banner_title: "#00FFFF"
  banner_accent: "#FF1493"

spinner:
  thinking_verbs: ["jacking in", "decrypting", "uploading"]
  wings:
    - ["⟨⚡", "⚡⟩"]

branding:
  agent_name: "Cyber Agent"
  response_label: " ⚡ Cyber "

tool_prefix: "▏"
```

Activate with `/skin cyberpunk` or `display.skin: cyberpunk` in config.yaml.

---

## Plugin System

Plugins extend Hermes without modifying core code. There are two plugin categories, both loaded in `run_agent.py.__init__()` after tool discovery.

### Memory Providers (`plugins/memory/`)

Abstract base: `agent/memory_provider.py` — `MemoryProvider(ABC)`.

| Hook | Purpose |
|------|---------|
| `system_prompt_block()` | Inject persistent memory into system prompt |
| `prefetch()` | Load memories before agent turn |
| `sync_turn()` | Save turn data to external memory store |
| `on_session_end()` | Flush/summarize on session close |
| `on_pre_compress()` | React to context compression |
| `on_memory_write()` | React to built-in memory writes |
| `on_delegation()` | Pass context to subagent |

**Available plugins:** `honcho`, `hindsight`, `holographic`, `mem0`, `byterover`, `openviking`, `retaindb`, `supermemory`

**Activation:** set `memory.provider: <name>` in `config.yaml`. Only ONE external provider is active at a time; built-in file memory (`~/.hermes/memories/`) is always on.

**Adding a provider:** implement `MemoryProvider` ABC, place in `plugins/memory/<name>/`, add entry point or auto-discovery in `hermes_cli/plugins.py`.

### Context Engine (`plugins/context_engine/`)

Abstract base: `agent/context_engine.py` — `ContextEngine(ABC)`.

Key interface: `should_compress(messages, token_count) -> bool`, `compress(messages) -> list`.

**Default engine:** `"compressor"` (uses `agent/context_compressor.py`).
**Activation:** set `context.engine: <name>` in `config.yaml`.

---

## Checkpoint System

`tools/checkpoint_manager.py` provides transparent filesystem snapshots so the model can recover from bad writes.

- **Storage:** shadow git repos at `~/.hermes/checkpoints/{sha256(abs_dir)[:16]}/`
- **Trigger:** automatically snaps before `write_file` / patch operations (max once per conversation turn per directory)
- **User access:** `/rollback [N]` — list recent checkpoints and restore one
- **Visibility:** NOT a model-visible tool — it is infrastructure, not a callable function
- **Enable:** `checkpoints: true` in `config.yaml` or `--checkpoints` CLI flag

---

## Tool Result Budget System

Three-layer system in `tools/tool_result_storage.py` + `tools/budget_config.py` that prevents context overflow from large tool outputs.

| Layer | Mechanism | Threshold |
|-------|-----------|-----------|
| 1 | Per-tool pre-truncation (inside each tool) | Tool-defined |
| 2 | `maybe_persist_tool_result()` — spill to disk | 100 000 chars |
| 3 | `enforce_turn_budget()` — per-turn aggregate cap | 200 000 chars |

Spilled results land in `/tmp/hermes-results/{tool_use_id}.txt` and are referenced by pointer in the message. `BudgetConfig` in `budget_config.py` holds all thresholds. `PINNED_THRESHOLDS = {"read_file": float("inf")}` keeps file reads exempt.

---

## Credential Pool & Smart Model Routing

### Credential Pool (`agent/credential_pool.py`)

Enables multi-key failover for high-volume or rate-limited deployments.

- **Strategies:** `fill_first` (default), `round_robin`, `random`, `least_used`
- **Cooldown:** 1-hour TTL on 429/402 errors; provider `reset_at` timestamp overrides
- **Config:** `credential_pool` list under `model` in `config.yaml`

### Smart Model Routing (`agent/smart_model_routing.py`)

Optional cheap-vs-strong routing that selects a lighter model for simple turns.

- **Enable:** set `model_routing.enabled: true` and `model_routing.cheap_model: <name>` in `config.yaml`
- **Logic:** `choose_cheap_model_route()` checks `_COMPLEX_KEYWORDS`, tool presence, and URL patterns
- **Override:** strong model is always used if the turn triggers code execution, delegation, or reasoning

---

## Web UI

`hermes web` starts a FastAPI backend + Vite/React frontend.

```bash
hermes web              # http://127.0.0.1:9119
hermes web --port 8080  # custom port
hermes web --host 0.0.0.0  # expose on all interfaces (Docker)
```

- CORS restricted to localhost by default
- Requires `pip install hermes-agent[web]`
- `_SESSION_TOKEN` env var protects sensitive API endpoints
- In Docker: add `-p 9119:9119` and `--host 0.0.0.0`

---

## Voice Mode

`tools/voice_mode.py` orchestrates STT → agent → TTS round-trips.

| Component | File | Backend |
|-----------|------|---------|
| Speech-to-text | `tools/transcription_tools.py` | `faster-whisper` (local), OpenAI Whisper API |
| Text-to-speech | `tools/tts_tool.py` | Edge TTS (free), ElevenLabs, OpenAI TTS |
| Orchestration | `tools/voice_mode.py` | — |

- **Activate:** `/voice on` (or `/voice tts` for TTS-only)
- **Requires:** `pip install hermes-agent[voice]`
- **Toggle mid-session:** `/voice off | tts | status`

---

## Managed Mode

For declarative installs (NixOS, Homebrew, system packages) where config files should not be mutated by runtime commands.

- **Enable:** set env var `HERMES_MANAGED=true` (also: `1`, `yes`, `brew`, `nix`, or any truthy string)
- **Effect:** `hermes config set` and interactive setup skip writes that would overwrite the managed config
- **Use case:** Nix flakes, Homebrew formulae, corp-managed deployments
- **Checked in:** `hermes_cli/config.py` via `is_managed_install()`

---

## Important Policies
### Prompt Caching Must Not Break

Hermes-Agent ensures caching remains valid throughout a conversation. **Do NOT implement changes that would:**
- Alter past context mid-conversation
- Change toolsets mid-conversation
- Reload memories or rebuild system prompts mid-conversation

Cache-breaking forces dramatically higher costs. The ONLY time we alter context is during context compression.

### Working Directory Behavior
- **CLI**: Uses current directory (`.` → `os.getcwd()`)
- **Messaging**: Uses `MESSAGING_CWD` env var (default: home directory)

### Background Process Notifications (Gateway)

When `terminal(background=true, notify_on_complete=true)` is used, the gateway runs a watcher that
detects process completion and triggers a new agent turn. Control verbosity of background process
messages with `display.background_process_notifications`
in config.yaml (or `HERMES_BACKGROUND_NOTIFICATIONS` env var):

- `all` — running-output updates + final message (default)
- `result` — only the final completion message
- `error` — only the final message when exit code != 0
- `off` — no watcher messages at all

---

## Profiles: Multi-Instance Support

Hermes supports **profiles** — multiple fully isolated instances, each with its own
`HERMES_HOME` directory (config, API keys, memory, sessions, skills, gateway, etc.).

The core mechanism: `_apply_profile_override()` in `hermes_cli/main.py` sets
`HERMES_HOME` before any module imports. All 119+ references to `get_hermes_home()`
automatically scope to the active profile.

### Rules for profile-safe code

1. **Use `get_hermes_home()` for all HERMES_HOME paths.** Import from `hermes_constants`.
   NEVER hardcode `~/.hermes` or `Path.home() / ".hermes"` in code that reads/writes state.
   ```python
   # GOOD
   from hermes_constants import get_hermes_home
   config_path = get_hermes_home() / "config.yaml"

   # BAD — breaks profiles
   config_path = Path.home() / ".hermes" / "config.yaml"
   ```

2. **Use `display_hermes_home()` for user-facing messages.** Import from `hermes_constants`.
   This returns `~/.hermes` for default or `~/.hermes/profiles/<name>` for profiles.
   ```python
   # GOOD
   from hermes_constants import display_hermes_home
   print(f"Config saved to {display_hermes_home()}/config.yaml")

   # BAD — shows wrong path for profiles
   print("Config saved to ~/.hermes/config.yaml")
   ```

3. **Module-level constants are fine** — they cache `get_hermes_home()` at import time,
   which is AFTER `_apply_profile_override()` sets the env var. Just use `get_hermes_home()`,
   not `Path.home() / ".hermes"`.

4. **Tests that mock `Path.home()` must also set `HERMES_HOME`** — since code now uses
   `get_hermes_home()` (reads env var), not `Path.home() / ".hermes"`:
   ```python
   with patch.object(Path, "home", return_value=tmp_path), \
        patch.dict(os.environ, {"HERMES_HOME": str(tmp_path / ".hermes")}):
       ...
   ```

5. **Gateway platform adapters should use token locks** — if the adapter connects with
   a unique credential (bot token, API key), call `acquire_scoped_lock()` from
   `gateway.status` in the `connect()`/`start()` method and `release_scoped_lock()` in
   `disconnect()`/`stop()`. This prevents two profiles from using the same credential.
   See `gateway/platforms/telegram.py` for the canonical pattern.

6. **Profile operations are HOME-anchored, not HERMES_HOME-anchored** — `_get_profiles_root()`
   returns `Path.home() / ".hermes" / "profiles"`, NOT `get_hermes_home() / "profiles"`.
   This is intentional — it lets `hermes -p coder profile list` see all profiles regardless
   of which one is active.

## Known Pitfalls

### DO NOT hardcode `~/.hermes` paths
Use `get_hermes_home()` from `hermes_constants` for code paths. Use `display_hermes_home()`
for user-facing print/log messages. Hardcoding `~/.hermes` breaks profiles — each profile
has its own `HERMES_HOME` directory. This was the source of 5 bugs fixed in PR #3575.

### DO NOT use `simple_term_menu` for interactive menus
Rendering bugs in tmux/iTerm2 — ghosting on scroll. Use `curses` (stdlib) instead. See `hermes_cli/tools_config.py` for the pattern.

### DO NOT use `\033[K` (ANSI erase-to-EOL) in spinner/display code
Leaks as literal `?[K` text under `prompt_toolkit`'s `patch_stdout`. Use space-padding: `f"\r{line}{' ' * pad}"`.

### `_last_resolved_tool_names` is a process-global in `model_tools.py`
`_run_single_child()` in `delegate_tool.py` saves and restores this global around subagent execution. If you add new code that reads this global, be aware it may be temporarily stale during child agent runs.

### DO NOT hardcode cross-tool references in schema descriptions
Tool schema descriptions must not mention tools from other toolsets by name (e.g., `browser_navigate` saying "prefer web_search"). Those tools may be unavailable (missing API keys, disabled toolset), causing the model to hallucinate calls to non-existent tools. If a cross-reference is needed, add it dynamically in `get_tool_definitions()` in `model_tools.py` — see the `browser_navigate` / `execute_code` post-processing blocks for the pattern.

### Tests must not write to `~/.hermes/`
The `_isolate_hermes_home` autouse fixture in `tests/conftest.py` redirects `HERMES_HOME` to a temp dir. Never hardcode `~/.hermes/` paths in tests.

**Profile tests**: When testing profile features, also mock `Path.home()` so that
`_get_profiles_root()` and `_get_default_hermes_home()` resolve within the temp dir.
Use the pattern from `tests/hermes_cli/test_profiles.py`:
```python
@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home
```

### DO NOT bypass the tool result budget system
Returning large raw strings (e.g., hundreds of KB of file content) directly from a tool handler bypasses Layer 2 truncation. Always return your result through the normal handler path so `maybe_persist_tool_result()` can spill to disk when needed. If a tool genuinely needs unbounded output (like `read_file`), add it to `PINNED_THRESHOLDS` in `budget_config.py` explicitly.

### Plugin providers must NOT reload mid-conversation
Memory provider `prefetch()` and `sync_turn()` are called per agent turn. Do NOT reconstruct the provider object or re-initialize its client inside these hooks — that breaks prompt caching and can cause duplicate memory writes. Initialize once in `__init__()`.

### Managed-mode installs: do not write config unconditionally
Any code path that writes to `config.yaml` must check `is_managed_install()` from `hermes_cli/config.py` first. Bypassing this check silently corrupts declarative (Nix/Homebrew) installs.

---

## Testing

```bash
source venv/bin/activate
python -m pytest tests/ -q          # Full suite (~3000+ tests, ~3 min)
python -m pytest tests/test_model_tools.py -q   # Toolset resolution
python -m pytest tests/test_cli_init.py -q       # CLI config loading
python -m pytest tests/gateway/ -q               # Gateway tests
python -m pytest tests/tools/ -q                 # Tool-level tests
```

Always run the full suite before pushing changes.
