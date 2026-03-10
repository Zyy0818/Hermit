"""End-to-end verification for the context7 external plugin.

Tests:
  1. Plugin discovery (loads from ~/.hermit/plugins/context7)
  2. McpServerSpec is registered with correct transport/command
  3. Skill 'context7-docs' is discovered and content is non-empty
  4. MCP Server connects and exposes expected tools
  5. Real tool call: resolve-library-id → query-docs
"""

import pytest
from pathlib import Path


# ── helpers ───────────────────────────────────────────────────────────────

def _make_pm():
    from hermit.plugin.manager import PluginManager
    from hermit.config import Settings

    # Instantiate fresh settings instead of using the lru_cache singleton,
    # which may have been polluted by other tests that set a tmp base_dir.
    settings = Settings()
    pm = PluginManager(settings=settings)
    builtin_dir = Path(__file__).parent.parent / "hermit" / "builtin"
    pm.discover_and_load(builtin_dir, settings.plugins_dir)
    return pm


# ── 1. Plugin discovery ────────────────────────────────────────────────────

def test_context7_plugin_is_discovered():
    pm = _make_pm()
    names = [m.name for m in pm.manifests]
    assert "context7" in names, f"context7 not in discovered plugins: {names}"


def test_context7_plugin_is_not_builtin():
    pm = _make_pm()
    manifest = next(m for m in pm.manifests if m.name == "context7")
    assert manifest.builtin is False


def test_context7_plugin_has_mcp_entry():
    pm = _make_pm()
    manifest = next(m for m in pm.manifests if m.name == "context7")
    assert "mcp" in manifest.entry, f"entry keys: {list(manifest.entry.keys())}"


# ── 2. McpServerSpec registered ───────────────────────────────────────────

def test_context7_mcp_spec_registered():
    pm = _make_pm()
    specs = {s.name: s for s in pm.mcp_specs}
    assert "context7" in specs, f"MCP specs: {list(specs.keys())}"


def test_context7_mcp_spec_transport():
    pm = _make_pm()
    spec = next(s for s in pm.mcp_specs if s.name == "context7")
    assert spec.transport == "http"
    assert spec.url == "https://mcp.context7.com/mcp"
    assert spec.command is None


# ── 3. Skill registered ───────────────────────────────────────────────────

def test_context7_skill_discovered():
    pm = _make_pm()
    names = [s.name for s in pm._all_skills]
    assert "context7-docs" in names, f"Skills: {names}"


def test_context7_skill_has_content():
    pm = _make_pm()
    skill = next(s for s in pm._all_skills if s.name == "context7-docs")
    assert len(skill.content) > 100
    assert "mcp__context7__resolve-library-id" in skill.content
    assert "mcp__context7__query-docs" in skill.content


def test_context7_skill_appears_in_system_prompt():
    pm = _make_pm()
    prompt = pm.build_system_prompt("BASE")
    assert "context7-docs" in prompt
    # Skill should be in available_skills catalog (not preloaded by default)
    assert "<available_skills>" in prompt


# ── 4. MCP Server connects and exposes tools ──────────────────────────────

@pytest.fixture(scope="module")
def mcp_manager():
    from hermit.plugin.mcp_client import McpClientManager
    from hermit.plugin.base import McpServerSpec

    mgr = McpClientManager()
    spec = McpServerSpec(
        name="context7",
        description="Context7 docs",
        transport="http",
        url="https://mcp.context7.com/mcp",
    )
    mgr.connect_all_sync([spec])
    yield mgr
    try:
        mgr.close_all_sync()
    except Exception:
        pass


def test_mcp_server_connects(mcp_manager):
    tools = mcp_manager.get_tool_specs()
    assert len(tools) >= 2, f"Expected >=2 tools, got: {[t.name for t in tools]}"


def test_mcp_tools_have_expected_names(mcp_manager):
    tool_names = {t.name for t in mcp_manager.get_tool_specs()}
    assert "mcp__context7__resolve-library-id" in tool_names
    assert "mcp__context7__query-docs" in tool_names


# ── 5. Real tool calls ────────────────────────────────────────────────────

def test_resolve_library_id(mcp_manager):
    """resolve-library-id should return a Context7-compatible library ID."""
    tools = {t.name: t for t in mcp_manager.get_tool_specs()}
    resolve = tools["mcp__context7__resolve-library-id"]

    result = resolve.handler({
        "libraryName": "pydantic-settings",
        "query": "how to load config from .env file with pydantic-settings",
    })

    # Result should contain a library ID like /pydantic/pydantic-settings
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert len(result) > 10, "Empty or too-short result"
    print(f"\nresolve result (first 300 chars):\n{result[:300]}")


def test_query_docs(mcp_manager):
    """query-docs should return documentation content."""
    tools = {t.name: t for t in mcp_manager.get_tool_specs()}
    query = tools["mcp__context7__query-docs"]

    result = query.handler({
        "libraryId": "/pydantic/pydantic-settings",
        "query": "load configuration from .env file",
    })

    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert len(result) > 50, "Too-short response — likely an error"
    # Should contain something relevant to settings/env
    lower = result.lower()
    has_relevant = any(kw in lower for kw in ["env", "settings", "config", "pydantic"])
    assert has_relevant, f"Response doesn't look like docs:\n{result[:400]}"
    print(f"\nquery-docs result (first 400 chars):\n{result[:400]}")
