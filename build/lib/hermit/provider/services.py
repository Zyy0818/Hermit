from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

import structlog

from hermit.context import build_base_context
from hermit.core.sandbox import CommandSandbox
from hermit.core.tools import ToolRegistry, create_builtin_tool_registry
from hermit.plugin.manager import PluginManager
from hermit.provider.contracts import Provider, ProviderResponse
from hermit.provider.messages import extract_text
from hermit.provider.providers import CodexProvider, build_claude_provider
from hermit.provider.runtime import AgentRuntime

log = structlog.get_logger()


def build_provider(settings: Any, *, model: str, system_prompt: str | None = None) -> Provider:
    provider_name = getattr(settings, "provider", "claude")
    if provider_name == "claude":
        return build_claude_provider(settings, model=model, system_prompt=system_prompt)
    if provider_name == "codex":
        return CodexProvider(model=model, system_prompt=system_prompt)
    raise RuntimeError(f"Unsupported provider: {provider_name}")


def build_provider_client_kwargs(settings: Any, provider: Optional[str] = None) -> dict[str, Any]:
    selected = provider or getattr(settings, "provider", "claude")
    if selected == "claude":
        kwargs: dict[str, Any] = {}
        if settings.claude_api_key:
            kwargs["api_key"] = settings.claude_api_key
        if settings.claude_auth_token:
            kwargs["auth_token"] = settings.claude_auth_token
        if settings.claude_base_url:
            kwargs["base_url"] = settings.claude_base_url
        if settings.parsed_claude_headers:
            kwargs["default_headers"] = settings.parsed_claude_headers
        return kwargs
    if selected == "codex":
        kwargs = {}
        if settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        if settings.parsed_openai_headers:
            kwargs["default_headers"] = settings.parsed_openai_headers
        return kwargs
    return {}


def build_runtime(
    settings: Any,
    *,
    preloaded_skills: list[str] | None = None,
    pm: PluginManager | None = None,
    serve_mode: bool = False,
    cwd: Path | None = None,
) -> tuple[AgentRuntime, PluginManager]:
    if pm is None:
        pm = PluginManager(settings=settings)
        builtin_dir = Path(__file__).resolve().parents[1] / "builtin"
        pm.discover_and_load(builtin_dir, settings.plugins_dir)

    workdir = (cwd or Path.cwd()).resolve()
    sandbox = CommandSandbox(
        mode=settings.sandbox_mode,
        timeout_seconds=settings.command_timeout_seconds,
        cwd=workdir,
    )
    registry = create_builtin_tool_registry(
        workdir, sandbox, config_root_dir=settings.base_dir,
    )
    pm.setup_tools(registry)
    pm.start_mcp_servers(registry)

    from hermit.core.runner import AgentRunner

    base_prompt = build_base_context(settings, workdir)
    visible_commands: list[tuple[str, str]] = [
        (cmd, help_text)
        for cmd, (_fn, help_text, cli_only) in sorted(AgentRunner._core_commands.items())
        if not (serve_mode and cli_only)
    ]
    for spec in pm._all_commands:
        if not (serve_mode and spec.cli_only):
            visible_commands.append((spec.name, spec.help_text))
    visible_commands.sort()
    if visible_commands:
        cmd_lines = ["<available_commands>"]
        cmd_lines.append("以下斜杠命令由系统层处理（不经过 LLM），用户可直接输入使用。当用户询问有哪些命令时，请告知：")
        for cmd, help_text in visible_commands:
            cmd_lines.append(f"- `{cmd}` — {help_text}")
        cmd_lines.append("</available_commands>")
        base_prompt = base_prompt + "\n\n" + "\n".join(cmd_lines)

    system_prompt = pm.build_system_prompt(base_prompt, preloaded_skills=preloaded_skills)
    provider = build_provider(settings, model=settings.model, system_prompt=system_prompt)
    runtime = AgentRuntime(
        provider=provider,
        registry=registry,
        model=settings.model,
        max_tokens=settings.effective_max_tokens(),
        max_turns=settings.max_turns,
        tool_output_limit=settings.tool_output_limit,
        thinking_budget=settings.thinking_budget,
        system_prompt=system_prompt,
    )
    pm.configure_subagent_runtime(runtime)
    return runtime, pm


class StructuredExtractionService:
    def __init__(self, provider: Provider, *, model: str) -> None:
        self.provider = provider
        self.model = model

    def extract_json(self, *, system_prompt: str, user_content: str, max_tokens: int = 2048) -> dict[str, Any] | None:
        response = self.provider.generate(
            request=self._request(system_prompt=system_prompt, user_content=user_content, max_tokens=max_tokens)
        )
        return _parse_json_response(response)

    def _request(self, *, system_prompt: str, user_content: str, max_tokens: int) -> Any:
        from hermit.provider.contracts import ProviderRequest

        return ProviderRequest(
            model=self.model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )


class VisionAnalysisService:
    def __init__(self, provider: Provider, *, model: str) -> None:
        self.provider = provider
        self.model = model

    def analyze_image(self, *, system_prompt: str, text: str, image_block: dict[str, Any], max_tokens: int = 512) -> dict[str, Any] | None:
        if not self.provider.features.supports_images:
            raise RuntimeError(f"Provider '{self.provider.name}' does not support image analysis")
        from hermit.provider.contracts import ProviderRequest

        response = self.provider.generate(
            ProviderRequest(
                model=self.model,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": [image_block, {"type": "text", "text": text}]}],
            )
        )
        return _parse_json_response(response)


def build_background_runtime(settings: Any, *, cwd: Path) -> tuple[AgentRuntime, PluginManager]:
    return build_runtime(settings, cwd=cwd)


def _parse_json_response(response: ProviderResponse) -> dict[str, Any] | None:
    raw = extract_text(response.content)
    if not raw:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    for candidate in (cleaned, raw):
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            continue
    brace_start = cleaned.find("{")
    if brace_start >= 0:
        fragment = cleaned[brace_start:]
        for suffix in ("", "}", "]}", "\"}", "\"]}", "\"]}"):
            try:
                parsed = json.loads(fragment + suffix)
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                continue
    log.warning("provider_json_parse_failed", preview=raw[:200])
    return None
