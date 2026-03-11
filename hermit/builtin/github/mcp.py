from __future__ import annotations

import structlog

from hermit.plugin.base import McpServerSpec, PluginContext

log = structlog.get_logger()
DEFAULT_GITHUB_MCP_URL = "https://api.githubcopilot.com/mcp/"


def _build_github_spec(ctx: PluginContext | None = None) -> McpServerSpec:
    token = ""
    url = DEFAULT_GITHUB_MCP_URL
    headers: dict[str, str] = {}

    if ctx is not None:
        token = str(ctx.get_var("github_pat", "") or "").strip()
        url = str(ctx.config.get("url", "") or "").strip() or DEFAULT_GITHUB_MCP_URL
        raw_headers = ctx.config.get("headers", {})
        if isinstance(raw_headers, dict):
            headers = {str(key): str(value) for key, value in raw_headers.items() if value}
    else:
        import os

        token = (
            os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "").strip()
            or os.getenv("GITHUB_PAT", "").strip()
            or os.getenv("GITHUB_TOKEN", "").strip()
        )
        url = os.getenv("GITHUB_MCP_URL", DEFAULT_GITHUB_MCP_URL).strip() or DEFAULT_GITHUB_MCP_URL
        if token:
            headers["Authorization"] = f"Bearer {token}"

    if not token:
        log.warning(
            "github_mcp_missing_token",
            plugin="github",
            variable="github_pat",
            message="GitHub MCP may fail to authenticate without a PAT",
        )

    return McpServerSpec(
        name="github",
        description="GitHub MCP server for issues, pull requests, repository search, and file reads",
        transport="http",
        url=url,
        headers=headers or None,
    )


def register(ctx: PluginContext) -> None:
    ctx.add_mcp(_build_github_spec(ctx))
