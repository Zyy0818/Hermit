# CLI and Operations Reference

This document covers the CLI commands that currently exist, the common startup paths, and the operational conventions around long-running processes.

## Top-Level Commands

Commands currently shown by `uv run hermit --help`:

- `setup`
- `init`
- `startup-prompt`
- `run`
- `chat`
- `serve`
- `reload`
- `sessions`
- `plugin`
- `autostart`
- `schedule`
- `config`
- `profiles`
- `auth`

## Basic Commands

### `hermit setup`

Interactive first-run setup wizard:

- writes `~/.hermit/.env`
- optionally configures Feishu
- initializes the workspace automatically

### `hermit init`

Initializes the workspace directories and the default context file.

### `hermit startup-prompt`

Prints the final startup system prompt, useful for debugging:

- base context
- rules
- skills catalog
- hook-injected content

### `hermit run "..."`

Runs a single task without entering an interactive session.

### `hermit chat`

Starts an interactive multi-turn session.

Optional parameters:

- `--session-id`
- `--debug`

## Slash Commands Available in `chat` / `serve`

Core commands:

- `/new`
- `/history`
- `/help`
- `/quit` (CLI only)

Additional builtin plugin commands:

- `/compact`
- `/plan`
- `/usage`

Note: these slash commands are system-level commands handled by `AgentRunner`; they do not go through the LLM.

## `serve` and `reload`

### `hermit serve --adapter feishu`

Long-running mode. The main builtin adapter at the moment is `feishu`.

Startup flow for `serve`:

1. read configuration
2. run environment self-checks
3. discover plugins
4. build the runtime
5. start the adapter
6. activate `SERVE_START` hooks such as scheduler / webhook

### `hermit reload --adapter feishu`

Sends `SIGHUP` to the running service and triggers a graceful reload:

1. stop the current adapter
2. reload configuration
3. rediscover plugins
4. rebuild tools and the system prompt
5. restart the adapter

This is better than a full process restart when you want to keep the same PID or let an external process manager continue owning the process.

## Pre-Start Environment Checks

Before `serve` actually starts, it prints a round of preflight checks.

For the `feishu` adapter, it checks:

- profile source
- provider and model
- whether LLM auth is available
- Feishu App ID / Secret source
- whether Feishu progress cards are enabled
- whether default Feishu notifications for the scheduler are configured

If a critical item is missing, `serve` exits immediately instead of half-starting and failing later.

## `config` / `profiles` / `auth`

### `hermit config show`

Outputs the fully resolved configuration snapshot.

Best used to confirm:

- the currently selected profile
- the effective provider / model
- whether webhook / scheduler are enabled
- whether auth is available

### `hermit profiles list`

Lists all profiles in `~/.hermit/config.toml`.

### `hermit profiles resolve --name <profile>`

Shows the resolved values for a specific profile.

### `hermit auth status`

Shows which auth source the current provider will use.

## `plugin` Subcommands

### `hermit plugin list`

Lists builtin and installed plugins.

### `hermit plugin install <git-url>`

Installs a plugin into `~/.hermit/plugins/<name>` using `git clone --depth 1`.

### `hermit plugin remove <name>`

Deletes an installed plugin directory.

### `hermit plugin info <name>`

Prints the core information from a plugin manifest.

## `schedule` Subcommands

### `hermit schedule list`

Lists all registered jobs and their next run time.

### `hermit schedule add`

Three mutually exclusive scheduling modes:

- `--cron`
- `--once`
- `--interval`

Examples:

```bash
hermit schedule add \
  --name "daily-summary" \
  --prompt "总结今天的 issue 更新" \
  --cron "0 18 * * 1-5"
```

```bash
hermit schedule add \
  --name "one-shot" \
  --prompt "明天下午提醒我检查部署" \
  --once "2026-03-15T14:00"
```

```bash
hermit schedule add \
  --name "polling" \
  --prompt "检查 webhook 错误日志" \
  --interval 300
```

Notes:

- the minimum `interval` is `60`
- after adding a job, it only becomes active the next time `hermit serve` starts

### Other Commands

- `hermit schedule remove <id>`
- `hermit schedule enable <id>`
- `hermit schedule disable <id>`
- `hermit schedule history --job-id ... --limit 20`

## `autostart` Subcommands

Currently only for macOS `launchd`:

- `hermit autostart enable --adapter feishu`
- `hermit autostart disable --adapter feishu`
- `hermit autostart status`

Implementation details:

- each adapter gets its own LaunchAgent plist
- different adapters do not overwrite one another

## `sessions`

`hermit sessions` lists the currently known session filenames.

Session persistence paths:

- active: `~/.hermit/sessions/*.json`
- archived: `~/.hermit/sessions/archive/*.json`

## Docker / Compose

The service command in the current Compose setup is:

```bash
hermit serve --adapter feishu
```

Do not write it as:

```bash
hermit serve feishu
```

Because in the current CLI implementation, `adapter` is an option, not a positional argument.

## Menu Bar Companion

Related menu bar companion commands:

- `hermit-menubar --adapter feishu`
- `hermit-menubar-install-app --adapter feishu --open`

It is not a replacement for `serve`; it is the control layer on macOS.

## Testing and Troubleshooting

Run tests:
