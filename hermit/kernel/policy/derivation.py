from __future__ import annotations

import shlex
from pathlib import Path

from hermit.kernel.policy.models import ActionRequest

_SENSITIVE_PREFIXES = (
    ".env",
    ".ssh",
    ".gnupg",
    "Library/",
)
_SENSITIVE_ABS_PREFIXES = (
    "/etc",
    "/usr",
    "/Library",
    "/System",
)


def derive_request(request: ActionRequest) -> ActionRequest:
    derived = dict(request.derived)
    tool_input = request.tool_input if isinstance(request.tool_input, dict) else {}
    workspace_root = str(request.context.get("workspace_root", "") or "")
    if request.tool_name in {"read_file", "write_file", "write_hermit_file", "read_hermit_file", "list_hermit_files"}:
        target = str(tool_input.get("path", "")).strip()
        if target:
            target_path = _resolve_target(target, workspace_root)
            derived["target_paths"] = [target_path]
            derived["sensitive_paths"] = [target_path] if _is_sensitive_path(target_path, workspace_root) else []
            outside_workspace = bool(workspace_root and not _inside_workspace(target_path, workspace_root))
            derived["outside_workspace"] = outside_workspace
            if outside_workspace:
                derived["outside_workspace_roots"] = [_outside_workspace_root(target_path)]
                derived["grant_candidate_prefix"] = _grant_candidate_prefix(target_path)
    if request.tool_name == "bash" or request.action_class == "execute_command":
        command = str(tool_input.get("command", "")).strip()
        if command:
            lower = command.lower()
            derived["command_preview"] = command
            derived["command_flags"] = {
                "writes_disk": any(token in command for token in (">", ">>", "tee ", "mv ", "cp ", "touch ", "mkdir ")),
                "deletes_files": "rm " in command or "trash " in lower,
                "sudo": "sudo " in lower,
                "curl_pipe_sh": "curl" in lower and "| sh" in lower,
                "git_push": "git push" in lower,
                "network_access": any(token in lower for token in ("curl ", "wget ", "http://", "https://")),
            }
            derived["network_hosts"] = _extract_hosts(command)
    request.derived = derived
    return request


def _resolve_target(target: str, workspace_root: str) -> str:
    try:
        if workspace_root:
            return str((Path(workspace_root) / target).expanduser().resolve())
        return str(Path(target).expanduser().resolve())
    except OSError:
        return target


def _inside_workspace(path: str, workspace_root: str) -> bool:
    try:
        candidate = Path(path).resolve()
        root = Path(workspace_root).resolve()
    except OSError:
        return False
    return candidate == root or root in candidate.parents


def _is_sensitive_path(path: str, workspace_root: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(_SENSITIVE_ABS_PREFIXES):
        return True
    if workspace_root and normalized.startswith(workspace_root.replace("\\", "/")):
        rel = normalized[len(workspace_root.replace("\\", "/")) :].lstrip("/")
        return any(rel == prefix or rel.startswith(prefix) for prefix in _SENSITIVE_PREFIXES)
    return any(part in normalized for part in ("/.ssh/", "/.gnupg/", "/.aws/"))


def _outside_workspace_root(path: str) -> str:
    candidate = Path(path).expanduser()
    home = Path.home().resolve()
    try:
        resolved = candidate.resolve()
    except OSError:
        return str(candidate)
    if resolved == home or home in resolved.parents:
        parts = resolved.parts
        home_parts = home.parts
        if len(parts) > len(home_parts):
            return str(Path(*parts[: len(home_parts) + 1]))
        return str(home)
    return resolved.anchor or str(resolved)


def _grant_candidate_prefix(path: str) -> str:
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve()
    except OSError:
        resolved = candidate
    return str(resolved.parent)


def _extract_hosts(command: str) -> list[str]:
    hosts: list[str] = []
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        if token.startswith(("http://", "https://")):
            host = token.split("://", 1)[1].split("/", 1)[0]
            hosts.append(host)
    return list(dict.fromkeys(hosts))
