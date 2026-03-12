# Hermit Architecture

This document describes only the implementation that exists in the current repository. It does not cover old design drafts or present future ideas as if they were already implemented.

## Overview

Hermit’s main execution path is intentionally short:

```text
CLI / Feishu Adapter / Scheduler / Webhook
                    |
                    v
               AgentRunner
                    |
        +-----------+-----------+
        |                       |
        v                       v
   SessionManager         PluginManager
                                |
                                +--> hooks / tools / commands / subagents / adapters / MCP
                    |
                    v
               AgentRuntime
                    |
                    v
                 Provider
                    |
                    +--> Claude API
                    +--> OpenAI Responses API
                    +--> Codex OAuth flow
```

The goal is not “more platform features at any cost.” The real priorities are:

- keep the runtime path as short as possible
- make plugin extension points explicit
- keep state files easy to inspect and recover

## Startup Path

The main entrypoint is [`hermit/main.py`](../hermit/main.py).

The startup sequence is roughly:

1. Load `~/.hermit/.env` into the process environment
2. Construct `Settings`
3. Create the required `~/.hermit` directories
4. Discover and load builtin / installed plugins
5. Build the tool registry
6. Register plugin tools, commands, subagents, and MCP
7. Build the base system prompt plus rules, skills, and hook-injected fragments
8. Construct the provider and `AgentRuntime`
9. Hand the same runner to the CLI / adapter / scheduler / webhook

## Core Modules

### [`hermit/main.py`](../hermit/main.py)

Responsibilities:

- CLI command definitions
- workspace initialization
- pre-run auth checks and self-checks
- `serve` / `reload` lifecycle
- runtime / runner assembly

### [`hermit/config.py`](../hermit/config.py)

Responsibilities:

- parse `.env`, shell env, and `config.toml` profiles
- handle provider compatibility fields and legacy aliases
- expose all runtime paths
- collect derived properties such as auth status and webhook defaults

### [`hermit/provider/services.py`](../hermit/provider/services.py)

Responsibilities:

- construct a provider from `settings.provider`
- assemble `AgentRuntime`
- build structured extraction and image analysis services

Current provider implementations:

- `claude`
- `codex`
- `codex-oauth`

### [`hermit/provider/runtime.py`](../hermit/provider/runtime.py)

Responsibilities:

- unified model tool loop
- tool result truncation and serialization
- streaming / non-streaming compatibility
- usage metric accumulation

This is Hermit’s model execution center. It is no longer an implementation that “only supports the Anthropic Messages API”; it is now a unified runtime over the provider interface.

### [`hermit/core/runner.py`](../hermit/core/runner.py)

Responsibilities:

- slash command dispatch
- session lifecycle
- `SESSION_START` / `PRE_RUN` / `POST_RUN` / `SESSION_END` hooks
- pass ordinary user messages to `AgentRuntime`

This is the shared orchestration layer used by the CLI, adapter, webhook, and scheduler.

### [`hermit/core/session.py`](../hermit/core/session.py)

Responsibilities:

- single-session, single-JSON-file persistence
- automatic archival after idle timeout
- cumulative token usage accounting

Session files are plain JSON, not JSONL.

### [`hermit/core/tools.py`](../hermit/core/tools.py)

Builtin core tools:

- `read_file`
- `write_file`
- `bash`
- `read_hermit_file`
- `write_hermit_file`
- `list_hermit_files`

Read-only tools can be filtered with `readonly_only=True` for read-only modes such as `/plan`.

### [`hermit/plugin/manager.py`](../hermit/plugin/manager.py)

Responsibilities:

- discover plugins
- load skills / rules / tools / commands / subagents / adapters / MCP
- build the final system prompt
- start and stop MCP servers
- inject subagent delegation tools

This is the central assembly layer for the plugin system.

## Provider Layer

The current provider is selected by `Settings.provider`.

### `claude`

- calls the Anthropic API directly
- or uses a custom Claude-compatible gateway

### `codex`

- uses the OpenAI Responses API
- requires a locally available OpenAI API key

### `codex-oauth`

- reads `~/.codex/auth.json`
- uses access / refresh tokens

`build_provider()` decides whether startup is allowed based on the provider type. If the required credentials are missing, startup fails immediately.

## Plugin Model

Hermit plugins are driven by `plugin.toml`.

The currently supported and actively used entrypoint categories are:

- `tools`
- `hooks`
- `commands`
- `subagents`
- `adapter`
- `mcp`

Example:

```toml
[plugin]
name = "my-plugin"
version = "0.1.0"
description = "Example plugin"

[entry]
tools = "tools:register"
hooks = "hooks:register"
commands = "commands:register"
subagents = "subagents:register"
adapter = "adapter:register"
mcp = "mcp:register"
```

Discovery order:

1. `hermit/builtin/`
2. `~/.hermit/plugins/`

## Plugin Context and Variable Resolution

Each plugin receives a `PluginContext` when loaded and can register:

- hook
- tool
- command
- subagent
- adapter
- MCP server

Plugin variables come from three layers:

1. `[plugins.<name>.variables]` in `~/.hermit/config.toml`
2. mapped fields from `Settings`
3. environment variables and `plugin.toml` defaults

Template rendering uses `{{ variable_name }}`.

## Hook Events

Current active events:

- `SYSTEM_PROMPT`
- `REGISTER_TOOLS`
- `SESSION_START`
- `SESSION_END`
- `PRE_RUN`
- `POST_RUN`
- `SERVE_START`
- `SERVE_STOP`
- `DISPATCH_RESULT`

In particular:

- `PRE_RUN` can return a modified prompt, or control parameters such as `disable_tools`
- `DISPATCH_RESULT` is reused by scheduler, webhook, and reload notifications

## Where Builtin Plugins Fit in the Architecture

### `memory`

- injects static long-term memory at `SYSTEM_PROMPT`
- injects memory relevant to the current prompt at `PRE_RUN`
- performs lightweight checkpoints at `POST_RUN`
- performs full settlement at `SESSION_END`

### `image_memory`

- stores image assets
- extracts semantic image metadata
- injects recent image context into multi-turn conversations or Feishu workflows

### `orchestrator`

- registers researcher / coder subagents
- exposes `delegate_<name>` tools externally
