from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, Optional

from hermit.core.session import SessionManager, sanitize_session_messages
from hermit.kernel.controller import TaskController
from hermit.provider.runtime import AgentResult, AgentRuntime, ToolCallback, ToolStartCallback

if TYPE_CHECKING:
    from hermit.plugin.manager import PluginManager

CommandHandler = Callable[["AgentRunner", str, str], "DispatchResult"]


@dataclass
class DispatchResult:
    """Unified result returned by AgentRunner.dispatch() for both commands and agent replies."""

    text: str
    is_command: bool = False
    should_exit: bool = False
    agent_result: Optional[AgentResult] = None


class AgentRunner:
    """Unified orchestration layer: session + agent + plugin hooks.

    Both CLI commands and adapter plugins call this instead of
    duplicating the get_session -> run -> save -> hooks flow.
    """

    # Class-level registry for core commands (populated by decorators at import time).
    _core_commands: Dict[str, tuple[CommandHandler, str, bool]] = {}

    @classmethod
    def register_command(
        cls, name: str, help_text: str, cli_only: bool = False
    ) -> Callable[[CommandHandler], CommandHandler]:
        """Decorator to register a core slash command."""
        def decorator(fn: CommandHandler) -> CommandHandler:
            cls._core_commands[name] = (fn, help_text, cli_only)
            return fn
        return decorator

    def __init__(
        self,
        agent: AgentRuntime,
        session_manager: SessionManager,
        plugin_manager: PluginManager,
        serve_mode: bool = False,
        task_controller: TaskController | None = None,
    ) -> None:
        if task_controller is None:
            raise ValueError("AgentRunner requires a TaskController; non-kernel runner mode has been removed.")
        self.agent = agent
        self.session_manager = session_manager
        self.pm = plugin_manager
        self.serve_mode = serve_mode
        self.task_controller = task_controller
        self._session_started: set[str] = set()
        # Instance-level copy: core commands + plugin commands added later via add_command()
        self._commands: Dict[str, tuple[CommandHandler, str, bool]] = dict(self._core_commands)

    def add_command(
        self, name: str, handler: CommandHandler, help_text: str, cli_only: bool = False,
    ) -> None:
        """Register a command on this runner instance (used by plugins)."""
        self._commands[name] = (handler, help_text, cli_only)

    # ------------------------------------------------------------------
    # Public dispatch entry point
    # ------------------------------------------------------------------

    def dispatch(
        self,
        session_id: str,
        text: str,
        on_tool_call: Optional[ToolCallback] = None,
        on_tool_start: Optional[ToolStartCallback] = None,
    ) -> DispatchResult:
        """Route a raw user message: slash commands are handled here; everything
        else is forwarded to the agent.
        """
        stripped = text.strip()
        if self.task_controller is not None:
            resolution = self.task_controller.resolve_text_command(session_id, stripped)
            if resolution is not None:
                action, target_id, reason = resolution
                return self._dispatch_control_action(
                    session_id,
                    action=action,
                    target_id=target_id,
                    reason=reason,
                    on_tool_call=on_tool_call,
                    on_tool_start=on_tool_start,
                )
        if stripped.startswith("/"):
            cmd = stripped.split()[0].lower()
            entry = self._commands.get(cmd)
            if entry:
                handler, _help, _cli = entry
                return handler(self, session_id, stripped)
            return DispatchResult(
                text=f"未知命令：{cmd}。输入 /help 查看可用命令。",
                is_command=True,
            )

        agent_result = self.handle(
            session_id, text,
            on_tool_call=on_tool_call,
            on_tool_start=on_tool_start,
        )
        return DispatchResult(
            text=agent_result.text or "",
            agent_result=agent_result,
        )

    def handle(
        self,
        session_id: str,
        text: str,
        on_tool_call: Optional[ToolCallback] = None,
        on_tool_start: Optional[ToolStartCallback] = None,
    ) -> AgentResult:
        """Process a single user message within a session."""
        session = self.session_manager.get_or_create(session_id)
        sanitized_messages = sanitize_session_messages(session.messages)
        if sanitized_messages != session.messages:
            session.messages = sanitized_messages
            self.session_manager.save(session)
        source_channel = self.task_controller.source_from_session(session_id) if self.task_controller else "chat"

        if session_id not in self._session_started:
            self.pm.on_session_start(session_id)
            self._session_started.add(session_id)

        prompt, run_opts = self.pm.on_pre_run(
            text, session_id=session_id, session=session, messages=list(session.messages),
            runner=self,
        )

        now = datetime.datetime.now()
        session_started = datetime.datetime.fromtimestamp(session.created_at)
        time_ctx = (
            f"<session_time>"
            f"session_started_at={session_started.strftime('%Y-%m-%d %H:%M:%S')} "
            f"message_sent_at={now.strftime('%Y-%m-%d %H:%M:%S')}"
            f"</session_time>\n\n"
        )
        prompt = time_ctx + prompt

        task_ctx = None
        if self.task_controller is not None:
            task_kind = "plan" if run_opts.get("readonly_only", False) else "respond"
            task_ctx = self.task_controller.start_task(
                conversation_id=session_id,
                goal=prompt,
                source_channel=source_channel,
                kind=task_kind,
                policy_profile="readonly" if run_opts.get("readonly_only", False) else "default",
                workspace_root=str(getattr(self.agent, "workspace_root", "") or ""),
            )

        result = self.agent.run(
            prompt,
            message_history=list(session.messages),
            on_tool_call=on_tool_call,
            on_tool_start=on_tool_start,
            disable_tools=run_opts.get("disable_tools", False),
            readonly_only=run_opts.get("readonly_only", False),
            task_context=task_ctx,
        )

        session.total_input_tokens      += result.input_tokens
        session.total_output_tokens     += result.output_tokens
        session.total_cache_read_tokens += result.cache_read_tokens
        session.total_cache_creation_tokens += result.cache_creation_tokens

        session.messages = result.messages
        self.session_manager.save(session)
        if self.task_controller is not None and task_ctx is not None:
            if result.blocked:
                if getattr(result, "status_managed_by_kernel", False):
                    return result
                self.task_controller.mark_blocked(task_ctx)
            else:
                status = self._result_status(result)
                if not getattr(result, "status_managed_by_kernel", False):
                    self.task_controller.finalize_result(task_ctx, status=status)
        if not result.blocked:
            self.pm.on_post_run(result, session_id=session_id, session=session, runner=self)
        return result

    @staticmethod
    def _result_status(result: AgentResult) -> str:
        explicit = str(getattr(result, "execution_status", "") or "").strip()
        if explicit:
            return explicit
        text = result.text or ""
        if text.startswith("[Execution Requires Attention]"):
            return "needs_attention"
        if text.startswith("[API Error]") or text.startswith("[Policy Denied]"):
            return "failed"
        return "succeeded"

    def close_session(self, session_id: str) -> None:
        """End a session, fire hooks, and archive."""
        session = self.session_manager.get_or_create(session_id)
        self.pm.on_session_end(session_id, session.messages)
        self.session_manager.close(session_id)
        self._session_started.discard(session_id)

    def reset_session(self, session_id: str) -> None:
        """Close current session and start a fresh one."""
        self.close_session(session_id)
        self.session_manager.get_or_create(session_id)
        self.pm.on_session_start(session_id)
        self._session_started.add(session_id)

    def _dispatch_control_action(
        self,
        session_id: str,
        *,
        action: str,
        target_id: str,
        reason: str = "",
        on_tool_call: Optional[ToolCallback] = None,
        on_tool_start: Optional[ToolStartCallback] = None,
    ) -> DispatchResult:
        if action in {"approve_once", "approve_always_directory", "deny"}:
            return self._resolve_approval(
                session_id,
                action=action,
                approval_id=target_id,
                reason=reason,
                on_tool_call=on_tool_call,
                on_tool_start=on_tool_start,
            )
        if action == "new_session":
            self.reset_session(session_id)
            return DispatchResult("已开启新会话。", is_command=True)
        if action == "show_history":
            session = self.session_manager.get_or_create(session_id)
            user_turns = sum(1 for m in session.messages if m.get("role") == "user")
            total = len(session.messages)
            return DispatchResult(f"当前会话：{user_turns} 轮用户消息，共 {total} 条记录。", is_command=True)
        if action == "show_help":
            lines = ["**可用命令**"]
            for cmd, (_fn, help_text, cli_only) in sorted(self._commands.items()):
                if self.serve_mode and cli_only:
                    continue
                lines.append(f"- `{cmd}` — {help_text}")
            return DispatchResult("\n".join(lines), is_command=True)

        store = getattr(getattr(self, "agent", None), "kernel_store", None)
        if store is None:
            return DispatchResult(text="Task kernel is not available.", is_command=True)

        if action == "task_list":
            payload = [task.__dict__ for task in store.list_tasks(limit=20)]
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "case":
            from hermit.kernel.supervision import SupervisionService

            payload = SupervisionService(store).build_task_case(target_id)
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "task_events":
            payload = store.list_events(task_id=target_id, limit=100)
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "task_receipts":
            payload = [receipt.__dict__ for receipt in store.list_receipts(task_id=target_id, limit=50)]
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "task_proof":
            from hermit.kernel.proofs import ProofService

            payload = ProofService(store).build_proof_summary(target_id)
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "task_proof_export":
            from hermit.kernel.proofs import ProofService

            payload = ProofService(store).export_task_proof(target_id)
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "rollback":
            from hermit.kernel.rollbacks import RollbackService

            payload = RollbackService(store).execute(target_id)
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "projection_rebuild":
            from hermit.kernel.projections import ProjectionService

            payload = ProjectionService(store).rebuild_task(target_id)
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "projection_rebuild_all":
            from hermit.kernel.projections import ProjectionService

            payload = ProjectionService(store).rebuild_all()
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "grant_list":
            payload = [
                grant.__dict__
                for grant in store.list_path_grants(
                    subject_kind="conversation",
                    subject_ref=session_id,
                    limit=50,
                )
            ]
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "grant_revoke":
            grant = store.get_path_grant(target_id)
            if grant is None:
                return DispatchResult(text=f"Grant not found: {target_id}", is_command=True)
            store.update_path_grant(
                target_id,
                status="revoked",
                actor="user",
                event_type="grant.revoked",
                payload={"status": "revoked"},
            )
            return DispatchResult(text=f"Revoked grant '{target_id}'.", is_command=True)
        if action == "schedule_list":
            payload = [job.to_dict() for job in store.list_schedules()]
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "schedule_history":
            payload = [
                record.to_dict() for record in store.list_schedule_history(job_id=target_id or None, limit=10)
            ]
            return DispatchResult(text=json.dumps(payload, ensure_ascii=False, indent=2), is_command=True)
        if action == "schedule_enable":
            job = store.update_schedule(target_id, enabled=True)
            message = f"Enabled task '{target_id}'." if job is not None else f"Error: no task with id '{target_id}' found."
            return DispatchResult(text=message, is_command=True)
        if action == "schedule_disable":
            job = store.update_schedule(target_id, enabled=False)
            message = f"Disabled task '{target_id}'." if job is not None else f"Error: no task with id '{target_id}' found."
            return DispatchResult(text=message, is_command=True)
        if action == "schedule_remove":
            deleted = store.delete_schedule(target_id)
            message = f"Removed task '{target_id}'." if deleted else f"Error: no task with id '{target_id}' found."
            return DispatchResult(text=message, is_command=True)
        return DispatchResult(text=f"Unsupported control action: {action}", is_command=True)

    def _resolve_approval(
        self,
        session_id: str,
        *,
        action: str,
        approval_id: str,
        reason: str = "",
        on_tool_call: Optional[ToolCallback] = None,
        on_tool_start: Optional[ToolStartCallback] = None,
    ) -> DispatchResult:
        approval = self.task_controller.store.get_approval(approval_id)
        if approval is None:
            return DispatchResult(f"未知 approval：{approval_id}", is_command=True)

        session = self.session_manager.get_or_create(session_id)
        if action == "deny":
            self.task_controller.store.resolve_approval(
                approval_id,
                status="denied",
                resolved_by="user",
                resolution={"status": "denied", "mode": "denied", "reason": reason},
            )
            text = (
                "本次审批已拒绝，当前操作不会继续。"
                "\n如需继续，请重新发起请求；届时你可以对新的审批请求再次进行批准。"
            )
            messages = list(session.messages)
            messages.append({"role": "assistant", "content": [{"type": "text", "text": text}]})
            session.messages = messages
            self.session_manager.save(session)
            return DispatchResult(text=text, is_command=True)

        if action == "approve_always_directory":
            self.task_controller.store.resolve_approval(
                approval_id,
                status="granted",
                resolved_by="user",
                resolution={"status": "granted", "mode": "always_directory"},
            )
        else:
            self.task_controller.store.resolve_approval(
                approval_id,
                status="granted",
                resolved_by="user",
                resolution={"status": "granted", "mode": "once"},
            )
        task_ctx = self.task_controller.context_for_attempt(approval.step_attempt_id)
        result = self.agent.resume(
            step_attempt_id=approval.step_attempt_id,
            task_context=task_ctx,
            on_tool_call=on_tool_call,
            on_tool_start=on_tool_start,
        )
        session.total_input_tokens += result.input_tokens
        session.total_output_tokens += result.output_tokens
        session.total_cache_read_tokens += result.cache_read_tokens
        session.total_cache_creation_tokens += result.cache_creation_tokens
        session.messages = result.messages
        self.session_manager.save(session)
        if result.blocked:
            if not getattr(result, "status_managed_by_kernel", False):
                self.task_controller.mark_blocked(task_ctx)
        else:
            status = self._result_status(result)
            if not getattr(result, "status_managed_by_kernel", False):
                self.task_controller.finalize_result(task_ctx, status=status)
            self.pm.on_post_run(result, session_id=session_id, session=session, runner=self)
        return DispatchResult(
            text=result.text or "",
            is_command=False,
            agent_result=result,
        )


# ------------------------------------------------------------------
# Core slash commands (always available, not from plugins)
# ------------------------------------------------------------------

@AgentRunner.register_command("/new", "开启新会话，清空当前上下文")
def _cmd_new(runner: AgentRunner, session_id: str, _text: str) -> DispatchResult:
    runner.reset_session(session_id)
    return DispatchResult("已开启新会话。", is_command=True)


@AgentRunner.register_command("/history", "显示当前会话的消息轮次统计")
def _cmd_history(runner: AgentRunner, session_id: str, _text: str) -> DispatchResult:
    session = runner.session_manager.get_or_create(session_id)
    user_turns = sum(1 for m in session.messages if m.get("role") == "user")
    total = len(session.messages)
    return DispatchResult(
        f"当前会话：{user_turns} 轮用户消息，共 {total} 条记录。",
        is_command=True,
    )


@AgentRunner.register_command("/quit", "退出（仅 CLI 模式）", cli_only=True)
def _cmd_quit(_runner: AgentRunner, _session_id: str, _text: str) -> DispatchResult:
    return DispatchResult("Bye.", is_command=True, should_exit=True)


@AgentRunner.register_command("/help", "显示所有可用命令")
def _cmd_help(runner: AgentRunner, _session_id: str, _text: str) -> DispatchResult:
    lines = ["**可用命令**"]
    for cmd, (_fn, help_text, cli_only) in sorted(runner._commands.items()):
        if runner.serve_mode and cli_only:
            continue
        lines.append(f"- `{cmd}` — {help_text}")
    return DispatchResult("\n".join(lines), is_command=True)


@AgentRunner.register_command("/task", "任务控制；支持 approve/deny/case/rollback")
def _cmd_task(runner: AgentRunner, session_id: str, text: str) -> DispatchResult:
    parts = text.strip().split(maxsplit=2)
    if len(parts) < 3 or parts[1] not in {"approve", "deny", "case", "rollback"}:
        return DispatchResult(
            "用法：/task approve <approval_id> | /task deny <approval_id> | /task case <task_id> | /task rollback <receipt_id>",
            is_command=True,
        )
    action = parts[1]
    target_id = parts[2].strip()
    mapped_action = {"approve": "approve_once", "deny": "deny", "case": "case", "rollback": "rollback"}[action]
    return runner._dispatch_control_action(session_id, action=mapped_action, target_id=target_id)
