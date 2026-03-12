# Providers and Profiles

This document focuses on the provider modes Hermit currently supports, the available auth sources, and how `config.toml` profiles work.

## Currently Supported Providers

The current code supports three providers:

- `claude`
- `codex`
- `codex-oauth`

The provider entrypoint is [`hermit/provider/services.py`](../hermit/provider/services.py).

## 1. `claude`

This is the default provider.

Typical use cases:

- direct Anthropic API access
- a Claude-compatible enterprise gateway / proxy

### Direct Anthropic Access

Simplest configuration:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

### Via a Compatible Gateway

```bash
HERMIT_PROVIDER=claude
HERMIT_AUTH_TOKEN=your-bearer-token
HERMIT_BASE_URL=https://your-gateway.example.com/llm/claude
HERMIT_CUSTOM_HEADERS=X-Biz-Id: my-team
HERMIT_MODEL=claude-3-7-sonnet-latest
```

Compatible aliases:

- `HERMIT_CLAUDE_AUTH_TOKEN` is equivalent to `HERMIT_AUTH_TOKEN`
- `HERMIT_CLAUDE_BASE_URL` is equivalent to `HERMIT_BASE_URL`
- `HERMIT_CLAUDE_HEADERS` is equivalent to `HERMIT_CUSTOM_HEADERS`

## 2. `codex`

This does not mean “call the local codex CLI.” It goes directly through the OpenAI Responses API.

Most common configuration:

```bash
HERMIT_PROVIDER=codex
HERMIT_OPENAI_API_KEY=sk-...
HERMIT_MODEL=gpt-5.4
```

Optional fields:

```bash
HERMIT_OPENAI_BASE_URL=https://api.openai.com/v1
HERMIT_OPENAI_HEADERS=X-Project: hermit
```

### One Common Misunderstanding

If `~/.codex/auth.json` exists locally but does not contain a usable OpenAI API key, `codex` mode will not automatically “borrow” the desktop login session.

The current implementation fails immediately and tells you:

- `HERMIT_OPENAI_API_KEY` is required
- or local `~/.codex/auth.json` must contain API-key-backed auth state

## 3. `codex-oauth`

This is the mode that actually reads OAuth tokens from `~/.codex/auth.json`.

Typical use cases:

- you are already signed into the local Codex / ChatGPT desktop environment
- you want to reuse the existing access / refresh tokens directly

Example:

```bash
HERMIT_PROVIDER=codex-oauth
HERMIT_MODEL=gpt-5.4
```

Requirements:

- `~/.codex/auth.json` must exist
- it must contain both `access_token` and `refresh_token`

If the file is missing, Hermit fails immediately at startup.

## Model Resolution Logic

After a provider is selected, there is one more detail in model resolution:

- if you are in `codex` / `codex-oauth` mode but still request a model name starting with `claude`
- Hermit will try to read the `model` field from `~/.codex/config.toml`
- if it still cannot resolve one, it falls back to the default `gpt-5.4`

In other words, `codex*` modes are not a good fit for keeping a Claude-style default model name around.

## `config.toml` Profiles

Profile file path:

```text
~/.hermit/config.toml
```

Most common format:

```toml
default_profile = "codex-local"

[profiles.codex-local]
provider = "codex-oauth"
model = "gpt-5.4"
max_turns = 60

[profiles.claude-work]
provider = "claude"
model = "claude-3-7-sonnet-latest"
claude_base_url = "https://example.internal/claude"
claude_headers = "X-Biz-Id: workbench"
```

### How a Profile Is Selected

1. `default_profile`
2. `HERMIT_PROFILE`
3. `profiles resolve --name ...` only inspects; it does not write anything

Environment variables can still override profile values.

## Recommended Configuration Examples

### Personal Machine, Direct Claude Access

```toml
default_profile = "default"

[profiles.default]
provider = "claude"
model = "claude-3-7-sonnet-latest"
```

Then put `ANTHROPIC_API_KEY` in `~/.hermit/.env`.

### Personal Machine, Reusing the Codex Login State

```toml
default_profile = "codex-local"

[profiles.codex-local]
provider = "codex-oauth"
model = "gpt-5.4"
max_turns = 60
```

### Internal Team Network, Using a Claude-Compatible Gateway

```toml
default_profile = "work"

[profiles.work]
provider = "claude"
model = "claude-3-7-sonnet-latest"
claude_base_url = "https://gateway.example.com/claude"
claude_headers = "X-Biz-Id: hermit"
```

Then inject the token through shell env or `~/.hermit/.env`.

## Plugin Variables Also Come from `config.toml`

Besides `[profiles.*]`, the file also supports:

```toml
[plugins.github.variables]
github_pat = "ghp_xxx"
github_mcp_url = "https://api.githubcopilot.com/mcp/"
```

Plugin variables participate in template rendering when `plugin.toml` is loaded, for example:

```toml
[config]
url = "{{ github_mcp_url }}"

[config.headers]
Authorization = "Bearer {{ github_pat }}"
```

## Common Inspection Commands

```bash
hermit profiles list
hermit profiles resolve --name codex-local
hermit auth status
hermit config show
```

The most practical troubleshooting order is usually:

1. `hermit profiles list`
2. `hermit profiles resolve --name ...`
3. `hermit auth status`
4. `hermit config show`

## Facts Confirmed in This Review

- `codex` is currently explicitly bound to the OpenAI Responses API
- `codex-oauth` is the mode that reads tokens from `~/.codex/auth.json`
- the profile + env layering is real supported behavior and should not be inferred only from tests
