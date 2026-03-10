"""Compact command plugin: compress session context via LLM summarization.

Also provides auto-compact: when the last API call's input_tokens exceeds
AUTO_COMPACT_THRESHOLD, the session history is compacted automatically before
the next user message is processed.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from hermit.plugin.base import CommandSpec, HookEvent

log = logging.getLogger(__name__)

AUTO_COMPACT_THRESHOLD = 150_000  # tokens

_COMPACT_SYSTEM = (
    "你是一个专业的对话摘要助手。"
    "请将以下对话历史压缩为一段简洁的摘要，保留关键信息、已完成的任务、重要决策和待处理事项。"
    "摘要应足够详细，使新对话能够无缝继续。直接输出摘要内容，不需要额外的解释或标题。"
)

_state: dict[str, Any] = {
    "last_input_tokens": 0,
}


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def _serialize_messages(messages: list) -> str:
    """Convert message history into readable text for LLM summarization."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(f"[{role}]: {content}")
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(f"[{role}]: {block.get('text', '')}")
                elif btype == "thinking":
                    pass  # skip — too noisy for summarization
                elif btype == "tool_use":
                    inp = block.get("input", {})
                    inp_str = json.dumps(inp, ensure_ascii=False)[:100]
                    parts.append(f"[{role}]: [调用工具 {block.get('name', '')}({inp_str})]")
                elif btype == "tool_result":
                    result_text = str(block.get("content", ""))[:200]
                    parts.append(f"[tool_result]: {result_text}")
    return "\n\n".join(parts)


def _do_compact(runner: Any, session: Any) -> tuple[bool, str]:
    """Run LLM summarization and replace session.messages.

    Returns (success, message).
    """
    if not session.messages:
        return False, "没有可压缩的内容。"

    original_count = len(session.messages)
    history_text = _serialize_messages(session.messages)

    try:
        response = runner.agent.client.messages.create(
            model=runner.agent.model,
            max_tokens=2048,
            system=_COMPACT_SYSTEM,
            messages=[{"role": "user", "content": history_text}],
        )
        raw = getattr(response, "content", None) or []
        summary = ""
        for block in raw:
            text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if text:
                summary += text
        summary = summary.strip()
        if not summary:
            return False, "LLM 未能生成摘要，压缩取消。"
    except Exception as exc:
        return False, f"压缩失败：{exc}"

    session.messages = [
        {"role": "user", "content": f"<compacted_context>\n{summary}\n</compacted_context>"},
        {"role": "assistant", "content": "好的，我已了解之前的对话内容，可以继续。"},
    ]
    session.total_input_tokens = 0
    session.total_output_tokens = 0
    session.total_cache_read_tokens = 0
    session.total_cache_creation_tokens = 0
    runner.session_manager.save(session)
    _state["last_input_tokens"] = 0

    preview = summary[:200] + ("…" if len(summary) > 200 else "")
    return True, f"已压缩 {original_count} 条消息 → 2 条摘要消息。\n\n**摘要预览**：\n{preview}"


# ------------------------------------------------------------------
# Command handler
# ------------------------------------------------------------------

def _cmd_compact(runner: Any, session_id: str, _text: str) -> Any:
    from hermit.core.runner import DispatchResult

    session = runner.session_manager.get_or_create(session_id)
    success, msg = _do_compact(runner, session)
    return DispatchResult(msg, is_command=True)


# ------------------------------------------------------------------
# Hooks
# ------------------------------------------------------------------

def _post_run_hook(result: Any, **kwargs: Any) -> None:
    """Track last turn's input_tokens — this reflects the actual context size."""
    tokens = getattr(result, "input_tokens", 0)
    if tokens:
        _state["last_input_tokens"] = tokens


def _pre_run_hook(prompt: str, session: Any = None, session_id: str = "",
                  runner: Any = None, **kwargs: Any) -> str | dict[str, Any]:
    """Auto-compact when last input tokens exceeded the threshold."""
    if runner is None or session is None:
        return prompt
    if _state["last_input_tokens"] < AUTO_COMPACT_THRESHOLD:
        return prompt

    log.info(
        "auto_compact_triggered",
        extra={"last_input_tokens": _state["last_input_tokens"], "threshold": AUTO_COMPACT_THRESHOLD},
    )
    success, summary_msg = _do_compact(runner, session)
    if success:
        # Notify via a system note prepended to the prompt so the user knows it happened
        notice = f"[系统] 已自动压缩上下文（上次输入 {_state.get('last_input_tokens', 0):,} tokens 超过阈值 {AUTO_COMPACT_THRESHOLD:,}）。\n\n"
        # _do_compact resets last_input_tokens, so we read before reset above; just notify.
        return {"prompt": notice + prompt}
    return prompt


# ------------------------------------------------------------------
# Plugin registration
# ------------------------------------------------------------------

def register(ctx: Any) -> None:
    ctx.add_hook(HookEvent.POST_RUN, _post_run_hook, priority=10)
    ctx.add_hook(HookEvent.PRE_RUN, _pre_run_hook, priority=90)
    ctx.add_command(CommandSpec(
        name="/compact",
        help_text="压缩当前会话上下文（LLM 摘要）",
        handler=_cmd_compact,
    ))
