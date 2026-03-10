from __future__ import annotations

from hermit.config import Settings
from hermit.main import _build_anthropic_client_kwargs


def test_settings_parse_prefixed_env_fields(monkeypatch) -> None:
    monkeypatch.setenv("HERMIT_AUTH_TOKEN", "token-123")
    monkeypatch.setenv("HERMIT_BASE_URL", "https://example.internal/claude")
    monkeypatch.setenv("HERMIT_CUSTOM_HEADERS", "X-Biz-Id: claude-code, X-Test: yes")
    monkeypatch.setenv("HERMIT_MODEL", "claude-sonnet-4-6")

    settings = Settings()

    assert settings.auth_token == "token-123"
    assert settings.base_url == "https://example.internal/claude"
    assert settings.model == "claude-sonnet-4-6"
    assert settings.parsed_custom_headers == {
        "X-Biz-Id": "claude-code",
        "X-Test": "yes",
    }


def test_build_anthropic_client_kwargs_supports_auth_token_and_headers() -> None:
    settings = Settings(
        auth_token="token-123",
        base_url="https://example.internal/claude",
        custom_headers="X-Biz-Id: claude-code",
    )

    kwargs = _build_anthropic_client_kwargs(settings)

    assert kwargs == {
        "auth_token": "token-123",
        "base_url": "https://example.internal/claude",
        "default_headers": {"X-Biz-Id": "claude-code"},
    }


def test_build_anthropic_client_kwargs_keeps_api_key_when_present() -> None:
    settings = Settings(
        anthropic_api_key="api-key",
        auth_token="token-123",
        base_url="https://example.internal/claude",
    )

    kwargs = _build_anthropic_client_kwargs(settings)

    assert kwargs["api_key"] == "api-key"
    assert kwargs["auth_token"] == "token-123"


def test_custom_headers_requires_colon_separator() -> None:
    settings = Settings(custom_headers="broken-header")

    try:
        _ = settings.parsed_custom_headers
    except ValueError as exc:
        assert "Invalid HERMIT_CUSTOM_HEADERS format" in str(exc)
    else:
        raise AssertionError("Expected custom header parsing failure")
