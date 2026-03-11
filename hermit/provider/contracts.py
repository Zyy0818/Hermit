from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol

from hermit.core.tools import ToolSpec


@dataclass(frozen=True)
class ProviderFeatures:
    supports_streaming: bool = False
    supports_thinking: bool = False
    supports_images: bool = False
    supports_prompt_cache: bool = False
    supports_tool_calling: bool = False
    supports_structured_output: bool = False


@dataclass
class UsageMetrics:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    extra: dict[str, int] = field(default_factory=dict)


@dataclass
class ToolCall:
    id: str
    name: str
    payload: dict[str, Any]


@dataclass
class ToolResult:
    tool_use_id: str
    content: Any
    is_error: bool = False


@dataclass
class ProviderRequest:
    model: str
    max_tokens: int
    messages: List[Dict[str, Any]]
    system_prompt: Optional[str] = None
    tools: List[ToolSpec] = field(default_factory=list)
    thinking_budget: int = 0
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResponse:
    content: List[Dict[str, Any]]
    stop_reason: Optional[str] = None
    error: Optional[str] = None
    usage: UsageMetrics = field(default_factory=UsageMetrics)


@dataclass
class ProviderEvent:
    type: str
    text: str = ""
    block: Optional[Dict[str, Any]] = None
    stop_reason: Optional[str] = None
    usage: Optional[UsageMetrics] = None


class Provider(Protocol):
    name: str
    features: ProviderFeatures

    def generate(self, request: ProviderRequest) -> ProviderResponse: ...

    def stream(self, request: ProviderRequest) -> Iterable[ProviderEvent]: ...

    def clone(
        self,
        *,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> "Provider": ...


class ProviderFactory(Protocol):
    def create(self, settings: Any) -> Provider: ...
