from __future__ import annotations

from typing import Iterable, Optional

from hermit.provider.contracts import Provider, ProviderEvent, ProviderFeatures, ProviderRequest, ProviderResponse


class CodexProvider(Provider):
    """Scaffold for a future OpenAI/Codex-backed provider."""

    name = "codex"
    features = ProviderFeatures(
        supports_streaming=True,
        supports_thinking=False,
        supports_images=True,
        supports_prompt_cache=False,
        supports_tool_calling=True,
        supports_structured_output=True,
    )

    def __init__(self, *, model: str, system_prompt: Optional[str] = None) -> None:
        self.model = model
        self.system_prompt = system_prompt

    def clone(
        self,
        *,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> "CodexProvider":
        return CodexProvider(
            model=model or self.model,
            system_prompt=self.system_prompt if system_prompt is None else system_prompt,
        )

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise RuntimeError("Codex provider scaffold exists, but API integration is not implemented yet.")

    def stream(self, request: ProviderRequest) -> Iterable[ProviderEvent]:
        raise RuntimeError("Codex provider scaffold exists, but streaming integration is not implemented yet.")
