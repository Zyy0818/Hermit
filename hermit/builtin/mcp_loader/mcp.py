"""Load MCP server configurations from .mcp.json files.

Searches two locations (later wins on conflict):
  1. ~/.hermit/mcp.json  (global)
  2. <cwd>/.mcp.json         (project-level)

Format is compatible with Claude Code / Cursor:
    {
      "mcpServers": {
        "server-name": {
          "command": "npx",
          "args": ["-y", "pkg-name"],
          "env": {"KEY": "val"}
        },
        "remote": {
          "url": "https://...",
          "headers": {"Authorization": "Bearer ..."}
        }
      }
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from hermit.plugin.base import McpServerSpec, PluginContext

log = structlog.get_logger()


def _load_mcp_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("mcp_config_error", path=str(path), error=str(exc))
        return {}


def _parse_server_entry(name: str, entry: dict[str, Any]) -> McpServerSpec | None:
    if "command" in entry:
        cmd = entry["command"]
        args = entry.get("args", [])
        command = [cmd] + list(args) if isinstance(args, list) else [cmd]
        return McpServerSpec(
            name=name,
            description=entry.get("description", f"MCP server: {name}"),
            transport="stdio",
            command=command,
            env=entry.get("env"),
            allowed_tools=entry.get("allowedTools"),
        )
    elif "url" in entry:
        return McpServerSpec(
            name=name,
            description=entry.get("description", f"MCP server: {name}"),
            transport="http",
            url=entry["url"],
            headers=entry.get("headers"),
            allowed_tools=entry.get("allowedTools"),
        )
    else:
        log.warning("mcp_config_skip", server=name, reason="no 'command' or 'url'")
        return None


def register(ctx: PluginContext) -> None:
    """Discover .mcp.json configs and register MCP servers."""
    search_paths = []

    if ctx.settings is not None:
        base_dir = getattr(ctx.settings, "base_dir", None)
        if base_dir:
            search_paths.append(Path(base_dir) / "mcp.json")

    search_paths.append(Path.cwd() / ".mcp.json")

    servers: dict[str, McpServerSpec] = {}
    for config_path in search_paths:
        data = _load_mcp_json(config_path)
        mcp_servers = data.get("mcpServers", {})
        if not isinstance(mcp_servers, dict):
            continue
        for name, entry in mcp_servers.items():
            if not isinstance(entry, dict):
                continue
            spec = _parse_server_entry(name, entry)
            if spec:
                servers[name] = spec
                log.info("mcp_config_loaded", server=name, source=str(config_path))

    for spec in servers.values():
        ctx.add_mcp(spec)
