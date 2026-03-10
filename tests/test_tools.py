from __future__ import annotations

from hermit.core.sandbox import CommandSandbox
from hermit.core.tools import create_builtin_tool_registry


def test_builtin_tools_can_read_and_write_workspace_files(tmp_path) -> None:
    registry = create_builtin_tool_registry(tmp_path, CommandSandbox(mode="l0", cwd=tmp_path))

    registry.call("write_file", {"path": "notes/test.txt", "content": "hello"})
    content = registry.call("read_file", {"path": "notes/test.txt"})

    assert content == "hello"


def test_builtin_tools_block_workspace_escape(tmp_path) -> None:
    registry = create_builtin_tool_registry(tmp_path, CommandSandbox(mode="l0", cwd=tmp_path))

    try:
        registry.call("read_file", {"path": "../secret.txt"})
    except ValueError as exc:
        assert "escapes workspace" in str(exc)
    else:
        raise AssertionError("Expected workspace escape error")


def test_builtin_bash_tool_returns_command_result(tmp_path) -> None:
    registry = create_builtin_tool_registry(tmp_path, CommandSandbox(mode="l0", cwd=tmp_path))

    result = registry.call("bash", {"command": "printf 'ok'"})

    assert result["returncode"] == 0
    assert result["stdout"] == "ok"


def test_builtin_config_tools_can_manage_hermit_directory(tmp_path) -> None:
    config_dir = tmp_path / ".hermit"
    registry = create_builtin_tool_registry(
        tmp_path,
        CommandSandbox(mode="l0", cwd=tmp_path),
        config_root_dir=config_dir,
    )

    registry.call("write_hermit_file", {"path": "rules/a.md", "content": "rule"})
    content = registry.call("read_hermit_file", {"path": "rules/a.md"})
    listing = registry.call("list_hermit_files", {"path": "rules"})

    assert content == "rule"
    assert listing == ["rules/a.md"]


def test_builtin_config_tools_block_escape(tmp_path) -> None:
    registry = create_builtin_tool_registry(
        tmp_path,
        CommandSandbox(mode="l0", cwd=tmp_path),
        config_root_dir=tmp_path / ".hermit",
    )

    try:
        registry.call("read_hermit_file", {"path": "../secret.txt"})
    except ValueError as exc:
        assert "escapes workspace" in str(exc)
    else:
        raise AssertionError("Expected Hermit config escape error")


def test_read_hermit_file_returns_message_for_missing_file(tmp_path) -> None:
    registry = create_builtin_tool_registry(
        tmp_path,
        CommandSandbox(mode="l0", cwd=tmp_path),
        config_root_dir=tmp_path / ".hermit",
    )

    content = registry.call("read_hermit_file", {"path": "memory/session_state.json"})

    assert content == "File not found: memory/session_state.json"
