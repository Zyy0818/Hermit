"""Usage command plugin: show token consumption for the current session."""
from __future__ import annotations

from typing import Any

from hermit.plugin.base import CommandSpec


def _cmd_usage(runner: Any, session_id: str, _text: str) -> Any:
    from hermit.core.runner import DispatchResult

    session = runner.session_manager.get_or_create(session_id)
    user_turns = sum(1 for m in session.messages if m.get("role") == "user")
    lines = [
        "**当前会话 token 用量**",
        f"- 输入：{session.total_input_tokens:,}",
        f"- 输出：{session.total_output_tokens:,}",
        f"- Cache 读取：{session.total_cache_read_tokens:,}",
        f"- Cache 写入：{session.total_cache_creation_tokens:,}",
        f"- 消息轮次：{user_turns}",
    ]
    return DispatchResult("\n".join(lines), is_command=True)


def register(ctx: Any) -> None:
    ctx.add_command(CommandSpec(
        name="/usage",
        help_text="显示当前会话的 token 消耗统计",
        handler=_cmd_usage,
    ))
