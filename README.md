# Hermit

[![CI](https://github.com/heggria/Hermit/actions/workflows/ci.yml/badge.svg)](https://github.com/heggria/Hermit/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-black)](./LICENSE)

Hermit is a local-first personal AI agent runtime built in Python.

It is designed for people who want an agent they can actually inspect and modify: a short runtime path, file-based state, plugin-driven extensibility, and a long-running service mode that can connect to channels such as Feishu.

## What Hermit Is

Hermit is not a browser app or a heavy platform. The current repository is centered around:

- a Typer-based CLI for one-shot and multi-turn sessions
- a shared runtime used by `chat`, `serve`, scheduler, webhook, and adapters
- file-based session, memory, and task state under `~/.hermit`
- a `plugin.toml` plugin system for tools, hooks, commands, subagents, adapters, and MCP servers
- optional macOS menu bar companion tooling

## Current Capabilities

- Interactive CLI with `hermit run` and `hermit chat`
- Long-running service mode with `hermit serve --adapter feishu`
- Provider support for `claude`, `codex`, and `codex-oauth`
- Built-in memory and image-memory workflows
- Scheduler and webhook integrations
- MCP loading and plugin-managed tool registration
- Subagent delegation via the orchestrator plugin
- macOS autostart and menu bar companion
- Docker and Docker Compose support

## Tech Stack

- Python 3.11+
- `uv` for environment and packaging workflows
- `setuptools` build backend
- Typer for CLI
- FastAPI + Uvicorn for webhook serving
- Pydantic / pydantic-settings for configuration
- structlog for logging
- MCP integration
- croniter for scheduling

## Repository Layout

```text
hermit/
  builtin/      Built-in plugins such as memory, scheduler, webhook, Feishu
  companion/    macOS menu bar companion and app bundle helpers
  core/         Runner, tools, sandbox, and session orchestration
  kernel/       Task, approval, proof, permit, and projection logic
  plugin/       Plugin loading and MCP integration
  provider/     Claude / OpenAI Codex runtime integration
  storage/      Persistence helpers
docs/           Architecture, configuration, operations, and companion docs
scripts/        Environment control, release, watch, and packaging scripts
tests/          Test suite
```

## Quick Start

### Requirements

- Python 3.11+
- `uv` recommended
- macOS only: `rumps` is needed for the menu bar companion

### Install

The simplest local install path is:

```bash
make install
```

This uses [`install.sh`](./install.sh) to:

- install `uv` if needed
- install Hermit as a `uv tool`
- initialize `~/.hermit`
- copy selected credentials from the current shell into `~/.hermit/.env`
- install the macOS menu bar app bundle when available

You can also initialize the workspace manually:

```bash
uv sync
uv run hermit init
```

### First Commands

```bash
hermit chat
hermit run "Summarize the current repository"
hermit serve --adapter feishu
hermit config show
hermit auth status
```

## Configuration

Hermit loads configuration from a few sources, centered around `HERMIT_BASE_DIR` and `~/.hermit`.

Important paths:

- `~/.hermit/.env`: long-lived local environment variables
- `~/.hermit/config.toml`: profiles and plugin variables
- `~/.hermit/memory/`: memory state
- `~/.hermit/sessions/`: active and archived sessions
- `~/.hermit/schedules/`: scheduler jobs and history
- `~/.hermit/plugins/`: installed external plugins

Common environment variables:

```bash
HERMIT_PROVIDER=claude
ANTHROPIC_API_KEY=...

# or
HERMIT_PROVIDER=codex
OPENAI_API_KEY=...
HERMIT_MODEL=gpt-5.4

# optional Feishu service mode
HERMIT_FEISHU_APP_ID=...
HERMIT_FEISHU_APP_SECRET=...
```

Hermit also supports provider profiles in `~/.hermit/config.toml`:

```toml
default_profile = "codex-local"

[profiles.codex-local]
provider = "codex-oauth"
model = "gpt-5.4"
max_turns = 60
```

For the full configuration model, see [`docs/configuration.md`](./docs/configuration.md) and [`docs/providers-and-profiles.md`](./docs/providers-and-profiles.md).

## Development Workflow

This repository already includes a dev environment wrapper. The recommended local flow is:

```bash
make env-up ENV=dev
make env-status ENV=dev
make env-watch ENV=dev
```

Useful commands:

```bash
make env-restart ENV=dev
make env-down ENV=dev
make lint
make test
make test-cov
make build
make package-check
make verify
```

If you want to run Hermit directly inside an isolated environment:

```bash
scripts/hermit-env.sh dev chat
scripts/hermit-env.sh dev serve --adapter feishu
```

The repository uses separate base directories for environment isolation, so development and production state do not get mixed.

## Service and Operations

The main long-running entrypoint is:

```bash
hermit serve --adapter feishu
```

Related operations:

```bash
hermit reload --adapter feishu
hermit schedule list
hermit plugin list
hermit autostart status
```

Current service-mode hooks can activate scheduler and webhook support from the same runtime process.

## Docker

The repository includes both a `Dockerfile` and `docker-compose.yml`.

Build and run with Compose:

```bash
docker compose up --build
```

The default container command is:

```bash
hermit serve --adapter feishu
```

Container state is persisted by mounting `~/.hermit` into the container.

## Testing

Run the main checks with:

```bash
make lint
make test
make verify
```

The current repository contains a substantial automated test suite across CLI, providers, plugins, scheduler, webhook, kernel, and companion behavior.

## Documentation

- [`docs/architecture.md`](./docs/architecture.md)
- [`docs/configuration.md`](./docs/configuration.md)
- [`docs/providers-and-profiles.md`](./docs/providers-and-profiles.md)
- [`docs/cli-and-operations.md`](./docs/cli-and-operations.md)
- [`docs/serve-troubleshooting.md`](./docs/serve-troubleshooting.md)
- [`docs/desktop-companion.md`](./docs/desktop-companion.md)
- [`docs/repository-layout.md`](./docs/repository-layout.md)
- [`docs/i18n.md`](./docs/i18n.md)
- [`docs/openclaw-comparison.md`](./docs/openclaw-comparison.md)
- [`docs/kernel-spec-v0.1.md`](./docs/kernel-spec-v0.1.md)

## License

MIT
