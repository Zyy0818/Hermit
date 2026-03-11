from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_headers_str(raw_headers: Optional[str]) -> Dict[str, str]:
    if not raw_headers:
        return {}
    headers: Dict[str, str] = {}
    raw_items = raw_headers.replace("\n", ",").split(",")
    for raw_item in raw_items:
        item = raw_item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(
                "Invalid HERMIT_CUSTOM_HEADERS format. Expected 'Key: Value[, Key2: Value2]'."
            )
        key, value = item.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


class Settings(BaseSettings):
    """Runtime configuration for Hermit."""

    model_config = SettingsConfigDict(
        env_prefix="HERMIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    provider: str = "claude"
    claude_api_key: Optional[str] = Field(default=None, alias="CLAUDE_API_KEY")
    claude_auth_token: Optional[str] = None
    claude_base_url: Optional[str] = None
    claude_headers: Optional[str] = None
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: Optional[str] = None
    openai_headers: Optional[str] = None
    model: str = "claude-3-7-sonnet-latest"
    max_tokens: int = 2048
    max_turns: int = 100
    tool_output_limit: int = 4000
    thinking_budget: int = 0
    image_model: Optional[str] = None
    image_context_limit: int = 3

    @model_validator(mode="before")
    @classmethod
    def _apply_legacy_provider_env(cls, data: object) -> object:
        if not isinstance(data, dict):
            data = {}
        values = dict(data)
        if "anthropic_api_key" in values and "claude_api_key" not in values:
            values["claude_api_key"] = values["anthropic_api_key"]
        if "auth_token" in values and "claude_auth_token" not in values:
            values["claude_auth_token"] = values["auth_token"]
        if "base_url" in values and "claude_base_url" not in values:
            values["claude_base_url"] = values["base_url"]
        if "custom_headers" in values and "claude_headers" not in values:
            values["claude_headers"] = values["custom_headers"]
        if not values.get("provider"):
            values["provider"] = os.environ.get("HERMIT_PROVIDER", "claude")
        values.setdefault("claude_api_key", os.environ.get("HERMIT_CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
        values.setdefault("claude_auth_token", os.environ.get("HERMIT_CLAUDE_AUTH_TOKEN") or os.environ.get("HERMIT_AUTH_TOKEN"))
        values.setdefault("claude_base_url", os.environ.get("HERMIT_CLAUDE_BASE_URL") or os.environ.get("HERMIT_BASE_URL"))
        values.setdefault("claude_headers", os.environ.get("HERMIT_CLAUDE_HEADERS") or os.environ.get("HERMIT_CUSTOM_HEADERS"))
        values.setdefault("openai_api_key", os.environ.get("HERMIT_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
        values.setdefault("openai_base_url", os.environ.get("HERMIT_OPENAI_BASE_URL"))
        values.setdefault("openai_headers", os.environ.get("HERMIT_OPENAI_HEADERS"))
        return values

    def effective_max_tokens(self) -> int:
        if self.thinking_budget > 0 and self.max_tokens <= self.thinking_budget:
            return self.thinking_budget + self.max_tokens
        return self.max_tokens
    prevent_sleep: bool = True
    log_level: str = "INFO"
    sandbox_mode: str = "l0"
    command_timeout_seconds: int = 30
    session_idle_timeout_seconds: int = 1800
    base_dir: Path = Field(default_factory=lambda: Path.home() / ".hermit")

    @property
    def memory_dir(self) -> Path:
        return self.base_dir / "memory"

    @property
    def memory_file(self) -> Path:
        return self.memory_dir / "memories.md"

    @property
    def session_state_file(self) -> Path:
        return self.memory_dir / "session_state.json"

    @property
    def skills_dir(self) -> Path:
        return self.base_dir / "skills"

    @property
    def rules_dir(self) -> Path:
        return self.base_dir / "rules"

    @property
    def hooks_dir(self) -> Path:
        return self.base_dir / "hooks"

    @property
    def plugins_dir(self) -> Path:
        return self.base_dir / "plugins"

    @property
    def sessions_dir(self) -> Path:
        return self.base_dir / "sessions"

    @property
    def image_memory_dir(self) -> Path:
        return self.base_dir / "image-memory"

    @property
    def schedules_dir(self) -> Path:
        return self.base_dir / "schedules"

    @property
    def context_file(self) -> Path:
        return self.base_dir / "context.md"

    @property
    def parsed_claude_headers(self) -> Dict[str, str]:
        return _parse_headers_str(self.claude_headers)

    @property
    def parsed_openai_headers(self) -> Dict[str, str]:
        return _parse_headers_str(self.openai_headers)

    @property
    def has_auth(self) -> bool:
        if self.provider == "claude":
            return bool(self.claude_api_key or self.claude_auth_token)
        if self.provider == "codex":
            return bool(self.openai_api_key)
        return bool(self.claude_api_key or self.claude_auth_token or self.openai_api_key)

    @property
    def anthropic_api_key(self) -> Optional[str]:
        return self.claude_api_key

    @property
    def auth_token(self) -> Optional[str]:
        return self.claude_auth_token

    @property
    def base_url(self) -> Optional[str]:
        return self.claude_base_url

    @property
    def custom_headers(self) -> Optional[str]:
        return self.claude_headers

    @property
    def parsed_custom_headers(self) -> Dict[str, str]:
        return self.parsed_claude_headers


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
