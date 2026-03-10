from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for Hermit."""

    model_config = SettingsConfigDict(
        env_prefix="HERMIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    auth_token: Optional[str] = None
    base_url: Optional[str] = None
    custom_headers: Optional[str] = None
    model: str = "claude-3-7-sonnet-latest"
    max_tokens: int = 2048
    max_turns: int = 100
    tool_output_limit: int = 4000
    thinking_budget: int = 0
    image_model: Optional[str] = None
    image_context_limit: int = 3

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
    def parsed_custom_headers(self) -> Dict[str, str]:
        if not self.custom_headers:
            return {}

        headers: Dict[str, str] = {}
        raw_items = self.custom_headers.replace("\n", ",").split(",")
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

    @property
    def has_auth(self) -> bool:
        return bool(self.anthropic_api_key or self.auth_token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
