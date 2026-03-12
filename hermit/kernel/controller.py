from __future__ import annotations

import re
import time

from hermit.kernel.context import TaskExecutionContext
from hermit.kernel.store import KernelStore

_APPROVE_RE = re.compile(r"^(?:/task\s+approve|批准|approve)\s+([a-z0-9_]+)$", re.IGNORECASE)
_DENY_RE = re.compile(r"^(?:/task\s+deny|拒绝|deny)\s+([a-z0-9_]+)(?:\s+(.+))?$", re.IGNORECASE)
_PENDING_APPROVE_TEXT = {"开始执行", "执行吧", "确认执行", "继续执行", "approve", "通过", "批准", "同意"}
_AUTO_PARENT = object()


class TaskController:
    def __init__(self, store: KernelStore) -> None:
        self.store = store

    def source_from_session(self, session_id: str) -> str:
        if session_id.startswith("webhook-"):
            return "webhook"
        if session_id.startswith("schedule-"):
            return "scheduler"
        if session_id.startswith("cli"):
            return "cli"
        if ":" in session_id or session_id.startswith("oc_"):
            return "feishu"
        return "chat"

    def ensure_conversation(self, conversation_id: str, *, source_channel: str | None = None) -> None:
        self.store.ensure_conversation(
            conversation_id,
            source_channel=source_channel or self.source_from_session(conversation_id),
        )

    def start_task(
        self,
        *,
        conversation_id: str,
        goal: str,
        source_channel: str,
        kind: str,
        policy_profile: str = "default",
        workspace_root: str = "",
        parent_task_id: str | None | object = _AUTO_PARENT,
        requested_by: str | None = None,
    ) -> TaskExecutionContext:
        self.ensure_conversation(conversation_id, source_channel=source_channel)
        parent = self.store.get_last_task_for_conversation(conversation_id)
        if parent_task_id is _AUTO_PARENT:
            resolved_parent = parent.task_id if parent else None
        else:
            resolved_parent = parent_task_id
        task = self.store.create_task(
            conversation_id=conversation_id,
            title=(goal.strip() or "Hermit task")[:120],
            goal=goal,
            source_channel=source_channel,
            parent_task_id=resolved_parent,
            policy_profile=policy_profile,
            requested_by=requested_by,
        )
        step = self.store.create_step(task_id=task.task_id, kind=kind, status="running")
        attempt_context = {"workspace_root": workspace_root} if workspace_root else {}
        attempt = self.store.create_step_attempt(
            task_id=task.task_id,
            step_id=step.step_id,
            status="running",
            context=attempt_context,
        )
        return TaskExecutionContext(
            conversation_id=conversation_id,
            task_id=task.task_id,
            step_id=step.step_id,
            step_attempt_id=attempt.step_attempt_id,
            source_channel=source_channel,
            workspace_root=workspace_root,
        )

    def context_for_attempt(self, step_attempt_id: str) -> TaskExecutionContext:
        attempt = self.store.get_step_attempt(step_attempt_id)
        if attempt is None:
            raise KeyError(f"Unknown step attempt: {step_attempt_id}")
        task = self.store.get_task(attempt.task_id)
        if task is None:
            raise KeyError(f"Unknown task for step attempt: {step_attempt_id}")
        return TaskExecutionContext(
            conversation_id=task.conversation_id,
            task_id=task.task_id,
            step_id=attempt.step_id,
            step_attempt_id=step_attempt_id,
            source_channel=task.source_channel,
            policy_profile=task.policy_profile,
            workspace_root=str(attempt.context.get("workspace_root", "") or ""),
        )

    def finalize_result(
        self,
        ctx: TaskExecutionContext,
        *,
        status: str,
        output_ref: str | None = None,
    ) -> None:
        now = time.time()
        self.store.update_step(ctx.step_id, status=status, output_ref=output_ref, finished_at=now)
        self.store.update_step_attempt(ctx.step_attempt_id, status=status, finished_at=now)
        self.store.update_task_status(ctx.task_id, "completed" if status == "succeeded" else status)

    def mark_blocked(self, ctx: TaskExecutionContext) -> None:
        self.store.update_step(ctx.step_id, status="awaiting_approval")
        self.store.update_step_attempt(ctx.step_attempt_id, status="awaiting_approval")
        self.store.update_task_status(ctx.task_id, "blocked")

    def resolve_text_command(self, conversation_id: str, text: str) -> tuple[str, str, str] | None:
        stripped = text.strip()
        match = _APPROVE_RE.match(stripped)
        if match:
            return ("approve", match.group(1), "")
        match = _DENY_RE.match(stripped)
        if match:
            return ("deny", match.group(1), match.group(2) or "")
        pending = self.store.get_latest_pending_approval(conversation_id)
        if pending and stripped in _PENDING_APPROVE_TEXT:
            return ("approve", pending.approval_id, "")
        return None
