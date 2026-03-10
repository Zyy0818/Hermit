"""Planner plugin: plan mode with file persistence and confirm-to-execute."""
from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Any

from hermit.plugin.base import CommandSpec, HookEvent

# Natural-language phrases that signal "I want to execute the plan now".
# Only matched when a plan file already exists to avoid false positives on task descriptions.
_EXECUTE_INTENT_RE = re.compile(
    r"(开始执行|执行吧|按计划执行|确认执行|执行计划|没问题.{0,6}执行|就这样执行"
    r"|go\s+ahead|run\s+the\s+plan|execute\s+the\s+plan|execute\s+it\b|confirm\s+and\s+(run|execute))",
    re.IGNORECASE,
)

_PLAN_MODE_PROMPT = (
    "\n\n<plan_mode>\n"
    "你当前处于规划模式。只读工具（搜索、读取文件等）可正常使用，以便收集制定计划所需的信息；"
    "有副作用的工具（写文件、执行命令、创建定时任务等）已禁用。\n"
    "请输出结构化的执行计划（Markdown 格式），包含：\n"
    "1. 任务概述\n"
    "2. 分步计划（每步说明操作和依据）\n"
    "3. 风险与注意事项\n"
    "可以先用只读工具调研，再输出最终计划；但不要执行任何有副作用的操作。\n"
    "</plan_mode>"
)

_state: dict[str, Any] = {
    "plan_mode": False,
    "plan_file": None,
}


def _pre_run_hook(prompt: str, **kwargs: Any) -> str | dict[str, Any]:
    if not _state["plan_mode"]:
        return prompt

    # Natural-language execution intent: if the user says "开始执行" etc. and a plan
    # already exists, switch transparently to execution mode without needing /plan confirm.
    plan_file: Path | None = _state["plan_file"]
    if plan_file and plan_file.exists() and _EXECUTE_INTENT_RE.search(prompt):
        plan_content = plan_file.read_text(encoding="utf-8")
        _state["plan_mode"] = False
        _state["plan_file"] = None
        return (
            f"<execution_plan>\n{plan_content}\n</execution_plan>\n\n"
            "用户已确认执行。请严格按照以上计划逐步执行。每完成一步，简要报告结果后继续下一步。"
        )

    return {"prompt": prompt + _PLAN_MODE_PROMPT, "readonly_only": True}


def _post_run_hook(result: Any, **kwargs: Any) -> None:
    if not _state["plan_mode"]:
        return
    text = getattr(result, "text", None)
    if not text:
        return
    plans_dir = Path.home() / ".hermit" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_path = plans_dir / f"{ts}.md"
    plan_path.write_text(text, encoding="utf-8")
    _state["plan_file"] = plan_path


def _cmd_plan(runner: Any, session_id: str, text: str) -> Any:
    from hermit.core.runner import DispatchResult

    parts = text.strip().split()
    subcommand = parts[1].lower() if len(parts) > 1 else ""

    if subcommand == "off":
        _state["plan_mode"] = False
        _state["plan_file"] = None
        return DispatchResult("规划模式已关闭，所有工具已恢复。", is_command=True)

    if subcommand == "confirm":
        plan_file: Path | None = _state["plan_file"]
        if not plan_file or not plan_file.exists():
            return DispatchResult(
                "没有可执行的计划文件。请先在规划模式下发送任务生成计划，再使用 /plan confirm。",
                is_command=True,
            )
        plan_content = plan_file.read_text(encoding="utf-8")
        _state["plan_mode"] = False
        _state["plan_file"] = None

        execution_prompt = (
            f"<execution_plan>\n{plan_content}\n</execution_plan>\n\n"
            "请严格按照以上计划逐步执行。每完成一步，简要报告结果后继续下一步。"
        )
        result = runner.handle(session_id, execution_prompt)
        return DispatchResult(
            text=result.text or "",
            is_command=False,
            agent_result=result,
        )

    if _state["plan_mode"]:
        plan_path_str = str(_state["plan_file"]) if _state["plan_file"] else "（尚未生成）"
        return DispatchResult(
            f"规划模式已开启。\n计划文件：{plan_path_str}\n\n"
            '发送任务即可生成计划；计划生成后，说"开始执行"或 /plan confirm 均可启动执行，/plan off 退出。',
            is_command=True,
        )

    _state["plan_mode"] = True
    _state["plan_file"] = None
    plans_dir = Path.home() / ".hermit" / "plans"
    return DispatchResult(
        f"已进入规划模式。只读工具（搜索、读文件等）仍可使用，有副作用的操作已禁用。\n"
        f"计划将保存至 {plans_dir}/\n\n"
        "发送你的任务，我将调研后输出结构化计划但不执行任何写操作。\n"
        '计划生成后，直接说"开始执行"或使用 /plan confirm 均可启动执行，/plan off 退出规划模式。',
        is_command=True,
    )


def register(ctx: Any) -> None:
    ctx.add_hook(HookEvent.PRE_RUN, _pre_run_hook, priority=100)
    ctx.add_hook(HookEvent.POST_RUN, _post_run_hook, priority=100)
    ctx.add_command(CommandSpec(
        name="/plan",
        help_text="进入/退出规划模式；/plan off 退出；/plan confirm 按计划执行",
        handler=_cmd_plan,
    ))
