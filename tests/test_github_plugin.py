from __future__ import annotations

from pathlib import Path

from hermit.config import Settings
from hermit.plugin.manager import PluginManager


def _make_pm() -> PluginManager:
    settings = Settings()
    pm = PluginManager(settings=settings)
    builtin_dir = Path(__file__).parent.parent / "hermit" / "builtin"
    pm.discover_and_load(builtin_dir, settings.plugins_dir)
    return pm


def test_github_builtin_plugin_is_discovered() -> None:
    pm = _make_pm()
    names = [manifest.name for manifest in pm.manifests]
    assert "github" in names


def test_github_plugin_registers_http_mcp_spec(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "test-token")

    from hermit.builtin.github.mcp import DEFAULT_GITHUB_MCP_URL, _build_github_spec

    spec = _build_github_spec()
    assert spec.name == "github"
    assert spec.transport == "http"
    assert spec.url == DEFAULT_GITHUB_MCP_URL
    assert spec.headers == {"Authorization": "Bearer test-token"}


def test_github_plugin_supports_custom_mcp_url(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_MCP_URL", "https://example.enterprise.github/mcp")

    from hermit.builtin.github.mcp import _build_github_spec

    spec = _build_github_spec()
    assert spec.url == "https://example.enterprise.github/mcp"


def test_github_skill_is_discovered() -> None:
    pm = _make_pm()
    names = [skill.name for skill in pm._all_skills]
    assert "github" in names


def test_github_skill_appears_in_system_prompt_catalog() -> None:
    pm = _make_pm()
    prompt = pm.build_system_prompt("BASE")
    assert "<available_skills>" in prompt
    assert '<skill name="github">' in prompt
