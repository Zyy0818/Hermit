from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from hermit.builtin.scheduler.models import JobExecutionRecord, ScheduledJob
from hermit.kernel.models import (
    ApprovalRecord,
    ArtifactRecord,
    ConversationRecord,
    DecisionRecord,
    PathGrantRecord,
    ExecutionPermitRecord,
    ReceiptRecord,
    StepAttemptRecord,
    StepRecord,
    TaskRecord,
)

_UNSET = object()
_SCHEMA_VERSION = "3"
_KNOWN_KERNEL_TABLES = {
    "conversations",
    "tasks",
    "steps",
    "step_attempts",
    "events",
    "artifacts",
    "approvals",
    "receipts",
    "decisions",
    "execution_permits",
    "path_grants",
    "schedule_specs",
    "schedule_history",
}


def _json_loads(raw: str | None) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class KernelSchemaError(RuntimeError):
    """Raised when an existing kernel database does not match the hard-cut schema."""


class KernelStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._validate_existing_schema()
        self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def schema_version(self) -> str:
        with self._lock:
            row = self._row("SELECT value FROM kernel_meta WHERE key = 'schema_version'")
        return str(row["value"]) if row is not None else ""

    def _existing_tables(self) -> set[str]:
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
        return {str(row[0]) for row in cursor.fetchall()}

    def _validate_existing_schema(self) -> None:
        tables = self._existing_tables()
        if not tables:
            return
        if "kernel_meta" not in tables:
            if tables & _KNOWN_KERNEL_TABLES:
                raise KernelSchemaError(
                    f"Existing kernel database at {self.db_path} uses an unsupported pre-v3 schema. "
                    "This is a hard cut release: archive or delete kernel/state.db before restarting Hermit."
                )
            return
        row = self._conn.execute(
            "SELECT value FROM kernel_meta WHERE key = 'schema_version'"
        ).fetchone()
        version = str(row[0]) if row is not None else ""
        if version != _SCHEMA_VERSION:
            raise KernelSchemaError(
                f"Existing kernel database at {self.db_path} has schema_version={version or 'unknown'}, "
                f"but Hermit requires schema_version={_SCHEMA_VERSION}. "
                "Archive or delete kernel/state.db before restarting Hermit."
            )

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS kernel_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    source_channel TEXT NOT NULL,
                    source_ref TEXT,
                    last_task_id TEXT,
                    status TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    total_input_tokens INTEGER NOT NULL DEFAULT 0,
                    total_output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                    total_cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    policy_profile TEXT NOT NULL,
                    source_channel TEXT NOT NULL,
                    parent_task_id TEXT,
                    requested_by TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS steps (
                    step_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    input_ref TEXT,
                    output_ref TEXT,
                    started_at REAL,
                    finished_at REAL
                );
                CREATE TABLE IF NOT EXISTS step_attempts (
                    step_attempt_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    waiting_reason TEXT,
                    approval_id TEXT,
                    decision_id TEXT,
                    permit_id TEXT,
                    state_witness_ref TEXT,
                    started_at REAL,
                    finished_at REAL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    task_id TEXT,
                    step_id TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    occurred_at REAL NOT NULL,
                    causation_id TEXT,
                    correlation_id TEXT
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    step_id TEXT,
                    kind TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    producer TEXT NOT NULL,
                    retention_class TEXT NOT NULL,
                    trust_tier TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    step_attempt_id TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    evidence_refs_json TEXT NOT NULL,
                    policy_ref TEXT,
                    approval_ref TEXT,
                    action_type TEXT,
                    decided_by TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS execution_permits (
                    permit_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    step_attempt_id TEXT NOT NULL,
                    decision_ref TEXT NOT NULL,
                    approval_ref TEXT,
                    policy_ref TEXT,
                    action_class TEXT NOT NULL,
                    resource_scope_json TEXT NOT NULL,
                    idempotency_key TEXT,
                    status TEXT NOT NULL,
                    issued_at REAL NOT NULL,
                    expires_at REAL,
                    consumed_at REAL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    step_attempt_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approval_type TEXT NOT NULL,
                    requested_action_json TEXT NOT NULL,
                    request_packet_ref TEXT,
                    decision_ref TEXT,
                    state_witness_ref TEXT,
                    requested_at REAL NOT NULL,
                    resolved_at REAL,
                    resolved_by TEXT,
                    resolution_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    step_attempt_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    input_refs_json TEXT NOT NULL,
                    environment_ref TEXT,
                    policy_result_json TEXT NOT NULL,
                    approval_ref TEXT,
                    output_refs_json TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    result_code TEXT NOT NULL,
                    decision_ref TEXT,
                    permit_ref TEXT,
                    grant_ref TEXT,
                    policy_ref TEXT,
                    witness_ref TEXT,
                    idempotency_key TEXT,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS path_grants (
                    grant_id TEXT PRIMARY KEY,
                    subject_kind TEXT NOT NULL,
                    subject_ref TEXT NOT NULL,
                    action_class TEXT NOT NULL,
                    path_prefix TEXT NOT NULL,
                    path_display TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    approval_ref TEXT,
                    decision_ref TEXT,
                    policy_ref TEXT,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    last_used_at REAL
                );
                CREATE TABLE IF NOT EXISTS schedule_specs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    cron_expr TEXT,
                    once_at REAL,
                    interval_seconds INTEGER,
                    enabled INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    last_run_at REAL,
                    next_run_at REAL,
                    max_retries INTEGER NOT NULL,
                    feishu_chat_id TEXT
                );
                CREATE TABLE IF NOT EXISTS schedule_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    job_name TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL NOT NULL,
                    success INTEGER NOT NULL,
                    result_text TEXT NOT NULL,
                    error TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_conversation ON tasks(conversation_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id, event_seq);
                CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status, requested_at);
                CREATE INDEX IF NOT EXISTS idx_receipts_task ON receipts(task_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_decisions_task ON decisions(task_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_permits_task ON execution_permits(task_id, issued_at);
                CREATE INDEX IF NOT EXISTS idx_path_grants_subject ON path_grants(subject_kind, subject_ref, status, action_class);
                CREATE INDEX IF NOT EXISTS idx_path_grants_prefix ON path_grants(path_prefix);
                """
            )
            self._ensure_column("receipts", "grant_ref", "TEXT")
            self._conn.execute(
                """
                INSERT INTO kernel_meta(key, value) VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (_SCHEMA_VERSION,),
            )

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        existing = {
            str(row["name"])
            for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column in existing:
            return
        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def _row(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        cursor = self._conn.execute(query, tuple(params))
        return cursor.fetchone()

    def _rows(self, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        cursor = self._conn.execute(query, tuple(params))
        return list(cursor.fetchall())

    def _append_event_tx(
        self,
        *,
        event_id: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        task_id: str | None,
        step_id: str | None = None,
        actor: str = "kernel",
        payload: dict[str, Any] | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> str:
        self._conn.execute(
            """
            INSERT INTO events (
                event_id, task_id, step_id, entity_type, entity_id, event_type,
                actor, payload_json, occurred_at, causation_id, correlation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                task_id,
                step_id,
                entity_type,
                entity_id,
                event_type,
                actor,
                json.dumps(payload or {}, ensure_ascii=False),
                time.time(),
                causation_id,
                correlation_id,
            ),
        )
        return event_id

    def ensure_conversation(
        self,
        conversation_id: str,
        *,
        source_channel: str,
        source_ref: str | None = None,
    ) -> ConversationRecord:
        now = time.time()
        with self._lock, self._conn:
            row = self._row(
                "SELECT * FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            if row is None:
                self._conn.execute(
                    """
                    INSERT INTO conversations (
                        conversation_id, source_channel, source_ref, last_task_id, status,
                        metadata_json, total_input_tokens, total_output_tokens,
                        total_cache_read_tokens, total_cache_creation_tokens,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, NULL, 'open', '{}', 0, 0, 0, 0, ?, ?)
                    """,
                    (conversation_id, source_channel, source_ref, now, now),
                )
                row = self._row(
                    "SELECT * FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                )
            else:
                self._conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE conversation_id = ?",
                    (now, conversation_id),
                )
                row = self._row(
                    "SELECT * FROM conversations WHERE conversation_id = ?",
                    (conversation_id,),
                )
        assert row is not None
        return self._conversation_from_row(row)

    def get_conversation(self, conversation_id: str) -> ConversationRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,))
        return self._conversation_from_row(row) if row is not None else None

    def list_conversations(self) -> list[str]:
        with self._lock:
            rows = self._rows("SELECT conversation_id FROM conversations ORDER BY updated_at DESC")
        return [str(row["conversation_id"]) for row in rows]

    def update_conversation_metadata(self, conversation_id: str, metadata: dict[str, Any]) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE conversations SET metadata_json = ?, updated_at = ? WHERE conversation_id = ?",
                (json.dumps(metadata, ensure_ascii=False), now, conversation_id),
            )

    def update_conversation_usage(
        self,
        conversation_id: str,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int,
        cache_creation_tokens: int,
        last_task_id: str | None,
    ) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE conversations
                SET total_input_tokens = ?,
                    total_output_tokens = ?,
                    total_cache_read_tokens = ?,
                    total_cache_creation_tokens = ?,
                    last_task_id = COALESCE(?, last_task_id),
                    updated_at = ?
                WHERE conversation_id = ?
                """,
                (
                    input_tokens,
                    output_tokens,
                    cache_read_tokens,
                    cache_creation_tokens,
                    last_task_id,
                    now,
                    conversation_id,
                ),
            )

    def create_task(
        self,
        *,
        conversation_id: str,
        title: str,
        goal: str,
        source_channel: str,
        owner: str = "hermit",
        priority: str = "normal",
        policy_profile: str = "default",
        parent_task_id: str | None = None,
        requested_by: str | None = None,
    ) -> TaskRecord:
        now = time.time()
        task_id = self._id("task")
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO tasks (
                    task_id, conversation_id, title, goal, status, priority, owner,
                    policy_profile, source_channel, parent_task_id, requested_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    conversation_id,
                    title,
                    goal,
                    priority,
                    owner,
                    policy_profile,
                    source_channel,
                    parent_task_id,
                    requested_by,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                "UPDATE conversations SET last_task_id = ?, updated_at = ? WHERE conversation_id = ?",
                (task_id, now, conversation_id),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="task.created",
                entity_type="task",
                entity_id=task_id,
                task_id=task_id,
                actor=requested_by or owner,
                payload={"conversation_id": conversation_id, "goal": goal, "source_channel": source_channel},
            )
        task = self.get_task(task_id)
        assert task is not None
        return task

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        return self._task_from_row(row) if row is not None else None

    def list_tasks(self, *, conversation_id: str | None = None, status: str | None = None, limit: int = 50) -> list[TaskRecord]:
        clauses = []
        params: list[Any] = []
        if conversation_id:
            clauses.append("conversation_id = ?")
            params.append(conversation_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._rows(query, params)
        return [self._task_from_row(row) for row in rows]

    def update_task_status(self, task_id: str, status: str) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status, now, task_id),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type=f"task.{status}",
                entity_type="task",
                entity_id=task_id,
                task_id=task_id,
                actor="kernel",
                payload={"status": status},
            )

    def get_last_task_for_conversation(self, conversation_id: str) -> TaskRecord | None:
        with self._lock:
            row = self._row(
                "SELECT * FROM tasks WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1",
                (conversation_id,),
            )
        return self._task_from_row(row) if row is not None else None

    def create_step(self, *, task_id: str, kind: str, status: str = "running") -> StepRecord:
        now = time.time()
        step_id = self._id("step")
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO steps (step_id, task_id, kind, status, attempt, started_at)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (step_id, task_id, kind, status, now),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="step.started",
                entity_type="step",
                entity_id=step_id,
                task_id=task_id,
                step_id=step_id,
                actor="kernel",
                payload={"kind": kind, "status": status},
            )
        step = self.get_step(step_id)
        assert step is not None
        return step

    def get_step(self, step_id: str) -> StepRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM steps WHERE step_id = ?", (step_id,))
        return self._step_from_row(row) if row is not None else None

    def update_step(
        self,
        step_id: str,
        *,
        status: str | None = None,
        output_ref: str | None = None,
        finished_at: float | None = None,
    ) -> None:
        now = time.time()
        step = self.get_step(step_id)
        if step is None:
            return
        values = {
            "status": status or step.status,
            "output_ref": output_ref if output_ref is not None else step.output_ref,
            "finished_at": finished_at if finished_at is not None else step.finished_at,
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE steps
                SET status = ?, output_ref = ?, finished_at = ?
                WHERE step_id = ?
                """,
                (values["status"], values["output_ref"], values["finished_at"], step_id),
            )
            self._conn.execute(
                "UPDATE tasks SET updated_at = ? WHERE task_id = ?",
                (now, step.task_id),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="step.updated",
                entity_type="step",
                entity_id=step_id,
                task_id=step.task_id,
                step_id=step_id,
                actor="kernel",
                payload=values,
            )

    def create_step_attempt(
        self,
        *,
        task_id: str,
        step_id: str,
        attempt: int = 1,
        status: str = "running",
        context: dict[str, Any] | None = None,
    ) -> StepAttemptRecord:
        now = time.time()
        step_attempt_id = self._id("attempt")
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO step_attempts (
                    step_attempt_id, task_id, step_id, attempt, status, context_json, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_attempt_id,
                    task_id,
                    step_id,
                    attempt,
                    status,
                    json.dumps(context or {}, ensure_ascii=False),
                    now,
                ),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="step_attempt.started",
                entity_type="step_attempt",
                entity_id=step_attempt_id,
                task_id=task_id,
                step_id=step_id,
                actor="kernel",
                payload={"attempt": attempt, "status": status},
            )
        return self.get_step_attempt(step_attempt_id)  # type: ignore[return-value]

    def get_step_attempt(self, step_attempt_id: str) -> StepAttemptRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM step_attempts WHERE step_attempt_id = ?", (step_attempt_id,))
        return self._step_attempt_from_row(row) if row is not None else None

    def update_step_attempt(
        self,
        step_attempt_id: str,
        *,
        status: str | None = None,
        context: dict[str, Any] | object = _UNSET,
        waiting_reason: str | None | object = _UNSET,
        approval_id: str | None | object = _UNSET,
        decision_id: str | None | object = _UNSET,
        permit_id: str | None | object = _UNSET,
        state_witness_ref: str | None | object = _UNSET,
        finished_at: float | None | object = _UNSET,
    ) -> None:
        attempt = self.get_step_attempt(step_attempt_id)
        if attempt is None:
            return
        payload = {
            "status": status or attempt.status,
            "waiting_reason": attempt.waiting_reason if waiting_reason is _UNSET else waiting_reason,
            "approval_id": attempt.approval_id if approval_id is _UNSET else approval_id,
            "decision_id": attempt.decision_id if decision_id is _UNSET else decision_id,
            "permit_id": attempt.permit_id if permit_id is _UNSET else permit_id,
            "state_witness_ref": attempt.state_witness_ref if state_witness_ref is _UNSET else state_witness_ref,
            "finished_at": attempt.finished_at if finished_at is _UNSET else finished_at,
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE step_attempts
                SET status = ?, context_json = ?, waiting_reason = ?, approval_id = ?, decision_id = ?, permit_id = ?, state_witness_ref = ?, finished_at = ?
                WHERE step_attempt_id = ?
                """,
                (
                    payload["status"],
                    json.dumps(attempt.context if context is _UNSET else context, ensure_ascii=False),
                    payload["waiting_reason"],
                    payload["approval_id"],
                    payload["decision_id"],
                    payload["permit_id"],
                    payload["state_witness_ref"],
                    payload["finished_at"],
                    step_attempt_id,
                ),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="step_attempt.updated",
                entity_type="step_attempt",
                entity_id=step_attempt_id,
                task_id=attempt.task_id,
                step_id=attempt.step_id,
                actor="kernel",
                payload=payload,
            )

    def append_event(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        task_id: str | None,
        step_id: str | None = None,
        actor: str = "kernel",
        payload: dict[str, Any] | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> str:
        event_id = self._id("event")
        with self._lock, self._conn:
            self._append_event_tx(
                event_id=event_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                task_id=task_id,
                step_id=step_id,
                actor=actor,
                payload=payload,
                causation_id=causation_id,
                correlation_id=correlation_id,
            )
        return event_id

    def list_events(self, *, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if task_id:
            query = "SELECT * FROM events WHERE task_id = ? ORDER BY event_seq ASC LIMIT ?"
            params: tuple[Any, ...] = (task_id, limit)
        else:
            query = "SELECT * FROM events ORDER BY event_seq DESC LIMIT ?"
            params = (limit,)
        with self._lock:
            rows = self._rows(query, params)
        return [
            {
                "event_seq": int(row["event_seq"]),
                "event_id": str(row["event_id"]),
                "task_id": row["task_id"],
                "step_id": row["step_id"],
                "entity_type": str(row["entity_type"]),
                "entity_id": str(row["entity_id"]),
                "event_type": str(row["event_type"]),
                "actor": str(row["actor"]),
                "payload": _json_loads(row["payload_json"]),
                "occurred_at": float(row["occurred_at"]),
            }
            for row in rows
        ]

    def create_artifact(
        self,
        *,
        task_id: str | None,
        step_id: str | None,
        kind: str,
        uri: str,
        content_hash: str,
        producer: str,
        retention_class: str = "default",
        trust_tier: str = "observed",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRecord:
        artifact_id = self._id("artifact")
        created_at = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, task_id, step_id, kind, uri, content_hash, producer,
                    retention_class, trust_tier, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    task_id,
                    step_id,
                    kind,
                    uri,
                    content_hash,
                    producer,
                    retention_class,
                    trust_tier,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    created_at,
                ),
            )
        return ArtifactRecord(
            artifact_id=artifact_id,
            task_id=task_id,
            step_id=step_id,
            kind=kind,
            uri=uri,
            content_hash=content_hash,
            producer=producer,
            retention_class=retention_class,
            trust_tier=trust_tier,
            metadata=metadata or {},
            created_at=created_at,
        )

    def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,))
        return self._artifact_from_row(row) if row is not None else None

    def create_decision(
        self,
        *,
        task_id: str,
        step_id: str,
        step_attempt_id: str,
        decision_type: str,
        verdict: str,
        reason: str,
        evidence_refs: list[str] | None = None,
        policy_ref: str | None = None,
        approval_ref: str | None = None,
        action_type: str | None = None,
        decided_by: str = "kernel",
    ) -> DecisionRecord:
        decision_id = self._id("decision")
        created_at = time.time()
        payload = {
            "decision_type": decision_type,
            "verdict": verdict,
            "reason": reason,
            "evidence_refs": list(evidence_refs or []),
            "policy_ref": policy_ref,
            "approval_ref": approval_ref,
            "action_type": action_type,
            "decided_by": decided_by,
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO decisions (
                    decision_id, task_id, step_id, step_attempt_id, decision_type, verdict, reason,
                    evidence_refs_json, policy_ref, approval_ref, action_type, decided_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    task_id,
                    step_id,
                    step_attempt_id,
                    decision_type,
                    verdict,
                    reason,
                    json.dumps(list(evidence_refs or []), ensure_ascii=False),
                    policy_ref,
                    approval_ref,
                    action_type,
                    decided_by,
                    created_at,
                ),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="decision.recorded",
                entity_type="decision",
                entity_id=decision_id,
                task_id=task_id,
                step_id=step_id,
                actor=decided_by,
                payload=payload,
            )
        decision = self.get_decision(decision_id)
        assert decision is not None
        return decision

    def get_decision(self, decision_id: str) -> DecisionRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,))
        return self._decision_from_row(row) if row is not None else None

    def list_decisions(self, *, task_id: str | None = None, limit: int = 50) -> list[DecisionRecord]:
        if task_id:
            query = "SELECT * FROM decisions WHERE task_id = ? ORDER BY created_at DESC LIMIT ?"
            params: tuple[Any, ...] = (task_id, limit)
        else:
            query = "SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?"
            params = (limit,)
        with self._lock:
            rows = self._rows(query, params)
        return [self._decision_from_row(row) for row in rows]

    def create_execution_permit(
        self,
        *,
        task_id: str,
        step_id: str,
        step_attempt_id: str,
        decision_ref: str,
        approval_ref: str | None,
        policy_ref: str | None,
        action_class: str,
        resource_scope: list[str],
        idempotency_key: str | None,
        expires_at: float | None,
        status: str = "issued",
    ) -> ExecutionPermitRecord:
        permit_id = self._id("permit")
        issued_at = time.time()
        payload = {
            "decision_ref": decision_ref,
            "approval_ref": approval_ref,
            "policy_ref": policy_ref,
            "action_class": action_class,
            "resource_scope": list(resource_scope),
            "idempotency_key": idempotency_key,
            "status": status,
            "expires_at": expires_at,
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO execution_permits (
                    permit_id, task_id, step_id, step_attempt_id, decision_ref, approval_ref, policy_ref,
                    action_class, resource_scope_json, idempotency_key, status, issued_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    permit_id,
                    task_id,
                    step_id,
                    step_attempt_id,
                    decision_ref,
                    approval_ref,
                    policy_ref,
                    action_class,
                    json.dumps(list(resource_scope), ensure_ascii=False),
                    idempotency_key,
                    status,
                    issued_at,
                    expires_at,
                ),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="permit.issued",
                entity_type="execution_permit",
                entity_id=permit_id,
                task_id=task_id,
                step_id=step_id,
                actor="kernel",
                payload=payload,
            )
        permit = self.get_execution_permit(permit_id)
        assert permit is not None
        return permit

    def get_execution_permit(self, permit_id: str) -> ExecutionPermitRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM execution_permits WHERE permit_id = ?", (permit_id,))
        return self._execution_permit_from_row(row) if row is not None else None

    def update_execution_permit(
        self,
        permit_id: str,
        *,
        status: str,
        consumed_at: float | None | object = _UNSET,
    ) -> None:
        permit = self.get_execution_permit(permit_id)
        if permit is None:
            return
        updated_consumed_at = permit.consumed_at if consumed_at is _UNSET else consumed_at
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE execution_permits
                SET status = ?, consumed_at = ?
                WHERE permit_id = ?
                """,
                (status, updated_consumed_at, permit_id),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type=f"permit.{status}",
                entity_type="execution_permit",
                entity_id=permit_id,
                task_id=permit.task_id,
                step_id=permit.step_id,
                actor="kernel",
                payload={"status": status, "consumed_at": updated_consumed_at},
            )

    def list_execution_permits(self, *, task_id: str | None = None, limit: int = 50) -> list[ExecutionPermitRecord]:
        if task_id:
            query = "SELECT * FROM execution_permits WHERE task_id = ? ORDER BY issued_at DESC LIMIT ?"
            params: tuple[Any, ...] = (task_id, limit)
        else:
            query = "SELECT * FROM execution_permits ORDER BY issued_at DESC LIMIT ?"
            params = (limit,)
        with self._lock:
            rows = self._rows(query, params)
        return [self._execution_permit_from_row(row) for row in rows]

    def create_path_grant(
        self,
        *,
        subject_kind: str,
        subject_ref: str,
        action_class: str,
        path_prefix: str,
        path_display: str,
        created_by: str,
        approval_ref: str | None,
        decision_ref: str | None,
        policy_ref: str | None,
        status: str = "active",
        expires_at: float | None = None,
    ) -> PathGrantRecord:
        grant_id = self._id("grant")
        created_at = time.time()
        payload = {
            "subject_kind": subject_kind,
            "subject_ref": subject_ref,
            "action_class": action_class,
            "path_prefix": path_prefix,
            "path_display": path_display,
            "created_by": created_by,
            "approval_ref": approval_ref,
            "decision_ref": decision_ref,
            "policy_ref": policy_ref,
            "status": status,
            "expires_at": expires_at,
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO path_grants (
                    grant_id, subject_kind, subject_ref, action_class, path_prefix, path_display,
                    created_by, approval_ref, decision_ref, policy_ref, status, created_at, expires_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    grant_id,
                    subject_kind,
                    subject_ref,
                    action_class,
                    path_prefix,
                    path_display,
                    created_by,
                    approval_ref,
                    decision_ref,
                    policy_ref,
                    status,
                    created_at,
                    expires_at,
                ),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="grant.created",
                entity_type="path_grant",
                entity_id=grant_id,
                task_id=None,
                step_id=None,
                actor=created_by,
                payload=payload,
            )
        grant = self.get_path_grant(grant_id)
        assert grant is not None
        return grant

    def get_path_grant(self, grant_id: str) -> PathGrantRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM path_grants WHERE grant_id = ?", (grant_id,))
        return self._path_grant_from_row(row) if row is not None else None

    def list_path_grants(
        self,
        *,
        subject_kind: str | None = None,
        subject_ref: str | None = None,
        status: str | None = None,
        action_class: str | None = None,
        limit: int = 50,
    ) -> list[PathGrantRecord]:
        clauses: list[str] = []
        params: list[Any] = []
        if subject_kind:
            clauses.append("subject_kind = ?")
            params.append(subject_kind)
        if subject_ref:
            clauses.append("subject_ref = ?")
            params.append(subject_ref)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if action_class:
            clauses.append("action_class = ?")
            params.append(action_class)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._rows(
                f"SELECT * FROM path_grants {where} ORDER BY created_at DESC LIMIT ?",
                tuple(params),
            )
        return [self._path_grant_from_row(row) for row in rows]

    def update_path_grant(
        self,
        grant_id: str,
        *,
        status: str | object = _UNSET,
        expires_at: float | None | object = _UNSET,
        last_used_at: float | None | object = _UNSET,
        actor: str = "kernel",
        event_type: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        grant = self.get_path_grant(grant_id)
        if grant is None:
            return
        updated_status = grant.status if status is _UNSET else str(status)
        updated_expires_at = grant.expires_at if expires_at is _UNSET else expires_at
        updated_last_used_at = grant.last_used_at if last_used_at is _UNSET else last_used_at
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE path_grants
                SET status = ?, expires_at = ?, last_used_at = ?
                WHERE grant_id = ?
                """,
                (updated_status, updated_expires_at, updated_last_used_at, grant_id),
            )
            if event_type:
                self._append_event_tx(
                    event_id=self._id("event"),
                    event_type=event_type,
                    entity_type="path_grant",
                    entity_id=grant_id,
                    task_id=None,
                    step_id=None,
                    actor=actor,
                    payload=payload or {},
                )

    def create_approval(
        self,
        *,
        task_id: str,
        step_id: str,
        step_attempt_id: str,
        approval_type: str,
        requested_action: dict[str, Any],
        request_packet_ref: str | None,
        decision_ref: str | None = None,
        state_witness_ref: str | None = None,
    ) -> ApprovalRecord:
        approval_id = self._id("approval")
        requested_at = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, task_id, step_id, step_attempt_id, status,
                    approval_type, requested_action_json, request_packet_ref, decision_ref, state_witness_ref,
                    requested_at, resolution_json
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    approval_id,
                    task_id,
                    step_id,
                    step_attempt_id,
                    approval_type,
                    json.dumps(requested_action, ensure_ascii=False),
                    request_packet_ref,
                    decision_ref,
                    state_witness_ref,
                    requested_at,
                ),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="approval.requested",
                entity_type="approval",
                entity_id=approval_id,
                task_id=task_id,
                step_id=step_id,
                actor="kernel",
                payload={
                    **requested_action,
                    "decision_ref": decision_ref,
                    "state_witness_ref": state_witness_ref,
                },
            )
        approval = self.get_approval(approval_id)
        assert approval is not None
        return approval

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        with self._lock:
            row = self._row("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,))
        return self._approval_from_row(row) if row is not None else None

    def list_approvals(
        self,
        *,
        conversation_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ApprovalRecord]:
        clauses = []
        params: list[Any] = []
        if conversation_id:
            clauses.append("task_id IN (SELECT task_id FROM tasks WHERE conversation_id = ?)")
            params.append(conversation_id)
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._lock:
            rows = self._rows(f"SELECT * FROM approvals {where} ORDER BY requested_at DESC LIMIT ?", params)
        return [self._approval_from_row(row) for row in rows]

    def get_latest_pending_approval(self, conversation_id: str) -> ApprovalRecord | None:
        approvals = self.list_approvals(conversation_id=conversation_id, status="pending", limit=1)
        return approvals[0] if approvals else None

    def resolve_approval(
        self,
        approval_id: str,
        *,
        status: str,
        resolved_by: str,
        resolution: dict[str, Any],
    ) -> None:
        now = time.time()
        approval = self.get_approval(approval_id)
        if approval is None:
            return
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE approvals
                SET status = ?, resolved_at = ?, resolved_by = ?, resolution_json = ?
                WHERE approval_id = ?
                """,
                (status, now, resolved_by, json.dumps(resolution, ensure_ascii=False), approval_id),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type=f"approval.{status}",
                entity_type="approval",
                entity_id=approval_id,
                task_id=approval.task_id,
                step_id=approval.step_id,
                actor=resolved_by,
                payload=resolution,
            )

    def update_approval_resolution(self, approval_id: str, resolution: dict[str, Any]) -> None:
        approval = self.get_approval(approval_id)
        if approval is None:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE approvals SET resolution_json = ? WHERE approval_id = ?",
                (json.dumps(resolution, ensure_ascii=False), approval_id),
            )

    def consume_approval(self, approval_id: str, *, actor: str = "kernel") -> None:
        approval = self.get_approval(approval_id)
        if approval is None:
            return
        resolution = dict(approval.resolution or {})
        resolution["status"] = "consumed"
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE approvals
                SET status = ?, resolution_json = ?
                WHERE approval_id = ?
                """,
                ("consumed", json.dumps(resolution, ensure_ascii=False), approval_id),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="approval.consumed",
                entity_type="approval",
                entity_id=approval_id,
                task_id=approval.task_id,
                step_id=approval.step_id,
                actor=actor,
                payload=resolution,
            )

    def create_receipt(
        self,
        *,
        task_id: str,
        step_id: str,
        step_attempt_id: str,
        action_type: str,
        input_refs: list[str],
        environment_ref: str | None,
        policy_result: dict[str, Any],
        approval_ref: str | None,
        output_refs: list[str],
        result_summary: str,
        result_code: str = "succeeded",
        decision_ref: str | None = None,
        permit_ref: str | None = None,
        grant_ref: str | None = None,
        policy_ref: str | None = None,
        witness_ref: str | None = None,
        idempotency_key: str | None = None,
    ) -> ReceiptRecord:
        receipt_id = self._id("receipt")
        created_at = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO receipts (
                    receipt_id, task_id, step_id, step_attempt_id, action_type,
                    input_refs_json, environment_ref, policy_result_json,
                    approval_ref, output_refs_json, result_summary, result_code,
                    decision_ref, permit_ref, grant_ref, policy_ref, witness_ref, idempotency_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    task_id,
                    step_id,
                    step_attempt_id,
                    action_type,
                    json.dumps(input_refs, ensure_ascii=False),
                    environment_ref,
                    json.dumps(policy_result, ensure_ascii=False),
                    approval_ref,
                    json.dumps(output_refs, ensure_ascii=False),
                    result_summary,
                    result_code,
                    decision_ref,
                    permit_ref,
                    grant_ref,
                    policy_ref,
                    witness_ref,
                    idempotency_key,
                    created_at,
                ),
            )
            self._append_event_tx(
                event_id=self._id("event"),
                event_type="receipt.issued",
                entity_type="receipt",
                entity_id=receipt_id,
                task_id=task_id,
                step_id=step_id,
                actor="kernel",
                payload={
                    "action_type": action_type,
                    "result_summary": result_summary,
                    "result_code": result_code,
                    "decision_ref": decision_ref,
                    "permit_ref": permit_ref,
                    "grant_ref": grant_ref,
                    "policy_ref": policy_ref,
                    "witness_ref": witness_ref,
                    "idempotency_key": idempotency_key,
                },
            )
        return ReceiptRecord(
            receipt_id=receipt_id,
            task_id=task_id,
            step_id=step_id,
            step_attempt_id=step_attempt_id,
            action_type=action_type,
            input_refs=input_refs,
            environment_ref=environment_ref,
            policy_result=policy_result,
            approval_ref=approval_ref,
            output_refs=output_refs,
            result_summary=result_summary,
            result_code=result_code,
            decision_ref=decision_ref,
            permit_ref=permit_ref,
            grant_ref=grant_ref,
            policy_ref=policy_ref,
            witness_ref=witness_ref,
            idempotency_key=idempotency_key,
            created_at=created_at,
        )

    def list_receipts(self, *, task_id: str | None = None, limit: int = 50) -> list[ReceiptRecord]:
        if task_id:
            query = "SELECT * FROM receipts WHERE task_id = ? ORDER BY created_at DESC LIMIT ?"
            params: tuple[Any, ...] = (task_id, limit)
        else:
            query = "SELECT * FROM receipts ORDER BY created_at DESC LIMIT ?"
            params = (limit,)
        with self._lock:
            rows = self._rows(query, params)
        return [self._receipt_from_row(row) for row in rows]

    def create_schedule(self, job: ScheduledJob) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO schedule_specs (
                    id, name, prompt, schedule_type, cron_expr, once_at, interval_seconds,
                    enabled, created_at, last_run_at, next_run_at, max_retries, feishu_chat_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.name,
                    job.prompt,
                    job.schedule_type,
                    job.cron_expr,
                    job.once_at,
                    job.interval_seconds,
                    1 if job.enabled else 0,
                    job.created_at,
                    job.last_run_at,
                    job.next_run_at,
                    job.max_retries,
                    job.feishu_chat_id,
                ),
            )

    def update_schedule(self, job_id: str, **updates: Any) -> ScheduledJob | None:
        job = self.get_schedule(job_id)
        if job is None:
            return None
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)
        self.create_schedule(job)
        return job

    def delete_schedule(self, job_id: str) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute("DELETE FROM schedule_specs WHERE id = ?", (job_id,))
        return cursor.rowcount > 0

    def get_schedule(self, job_id: str) -> ScheduledJob | None:
        with self._lock:
            row = self._row("SELECT * FROM schedule_specs WHERE id = ?", (job_id,))
        return self._schedule_from_row(row) if row is not None else None

    def list_schedules(self) -> list[ScheduledJob]:
        with self._lock:
            rows = self._rows("SELECT * FROM schedule_specs ORDER BY created_at DESC")
        return [self._schedule_from_row(row) for row in rows]

    def append_schedule_history(self, record: JobExecutionRecord) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO schedule_history (job_id, job_name, started_at, finished_at, success, result_text, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.job_name,
                    record.started_at,
                    record.finished_at,
                    1 if record.success else 0,
                    record.result_text,
                    record.error,
                ),
            )

    def list_schedule_history(self, *, job_id: str | None = None, limit: int = 20) -> list[JobExecutionRecord]:
        if job_id:
            query = """
                SELECT job_id, job_name, started_at, finished_at, success, result_text, error
                FROM schedule_history WHERE job_id = ? ORDER BY started_at DESC LIMIT ?
            """
            params: tuple[Any, ...] = (job_id, limit)
        else:
            query = """
                SELECT job_id, job_name, started_at, finished_at, success, result_text, error
                FROM schedule_history ORDER BY started_at DESC LIMIT ?
            """
            params = (limit,)
        with self._lock:
            rows = self._rows(query, params)
        return [
            JobExecutionRecord(
                job_id=str(row["job_id"]),
                job_name=str(row["job_name"]),
                started_at=float(row["started_at"]),
                finished_at=float(row["finished_at"]),
                success=bool(row["success"]),
                result_text=str(row["result_text"]),
                error=row["error"],
            )
            for row in rows
        ]

    def _conversation_from_row(self, row: sqlite3.Row) -> ConversationRecord:
        return ConversationRecord(
            conversation_id=str(row["conversation_id"]),
            source_channel=str(row["source_channel"]),
            source_ref=row["source_ref"],
            last_task_id=row["last_task_id"],
            status=str(row["status"]),
            metadata=_json_loads(row["metadata_json"]),
            total_input_tokens=int(row["total_input_tokens"]),
            total_output_tokens=int(row["total_output_tokens"]),
            total_cache_read_tokens=int(row["total_cache_read_tokens"]),
            total_cache_creation_tokens=int(row["total_cache_creation_tokens"]),
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
        )

    def _task_from_row(self, row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=str(row["task_id"]),
            conversation_id=str(row["conversation_id"]),
            title=str(row["title"]),
            goal=str(row["goal"]),
            status=str(row["status"]),
            priority=str(row["priority"]),
            owner=str(row["owner"]),
            policy_profile=str(row["policy_profile"]),
            source_channel=str(row["source_channel"]),
            parent_task_id=row["parent_task_id"],
            created_at=float(row["created_at"]),
            updated_at=float(row["updated_at"]),
            requested_by=row["requested_by"],
        )

    def _step_from_row(self, row: sqlite3.Row) -> StepRecord:
        return StepRecord(
            step_id=str(row["step_id"]),
            task_id=str(row["task_id"]),
            kind=str(row["kind"]),
            status=str(row["status"]),
            attempt=int(row["attempt"]),
            input_ref=row["input_ref"],
            output_ref=row["output_ref"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def _step_attempt_from_row(self, row: sqlite3.Row) -> StepAttemptRecord:
        return StepAttemptRecord(
            step_attempt_id=str(row["step_attempt_id"]),
            task_id=str(row["task_id"]),
            step_id=str(row["step_id"]),
            attempt=int(row["attempt"]),
            status=str(row["status"]),
            context=_json_loads(row["context_json"]),
            waiting_reason=row["waiting_reason"],
            approval_id=row["approval_id"],
            decision_id=row["decision_id"],
            permit_id=row["permit_id"],
            state_witness_ref=row["state_witness_ref"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    def _artifact_from_row(self, row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=str(row["artifact_id"]),
            task_id=row["task_id"],
            step_id=row["step_id"],
            kind=str(row["kind"]),
            uri=str(row["uri"]),
            content_hash=str(row["content_hash"]),
            producer=str(row["producer"]),
            retention_class=str(row["retention_class"]),
            trust_tier=str(row["trust_tier"]),
            metadata=_json_loads(row["metadata_json"]),
            created_at=float(row["created_at"]),
        )

    def _approval_from_row(self, row: sqlite3.Row) -> ApprovalRecord:
        return ApprovalRecord(
            approval_id=str(row["approval_id"]),
            task_id=str(row["task_id"]),
            step_id=str(row["step_id"]),
            step_attempt_id=str(row["step_attempt_id"]),
            status=str(row["status"]),
            approval_type=str(row["approval_type"]),
            requested_action=_json_loads(row["requested_action_json"]),
            request_packet_ref=row["request_packet_ref"],
            decision_ref=row["decision_ref"],
            state_witness_ref=row["state_witness_ref"],
            requested_at=float(row["requested_at"]),
            resolved_at=row["resolved_at"],
            resolved_by=row["resolved_by"],
            resolution=_json_loads(row["resolution_json"]),
        )

    def _decision_from_row(self, row: sqlite3.Row) -> DecisionRecord:
        return DecisionRecord(
            decision_id=str(row["decision_id"]),
            task_id=str(row["task_id"]),
            step_id=str(row["step_id"]),
            step_attempt_id=str(row["step_attempt_id"]),
            decision_type=str(row["decision_type"]),
            verdict=str(row["verdict"]),
            reason=str(row["reason"]),
            evidence_refs=list(_json_loads(row["evidence_refs_json"])),
            policy_ref=row["policy_ref"],
            approval_ref=row["approval_ref"],
            action_type=row["action_type"],
            decided_by=str(row["decided_by"]),
            created_at=float(row["created_at"]),
        )

    def _execution_permit_from_row(self, row: sqlite3.Row) -> ExecutionPermitRecord:
        return ExecutionPermitRecord(
            permit_id=str(row["permit_id"]),
            task_id=str(row["task_id"]),
            step_id=str(row["step_id"]),
            step_attempt_id=str(row["step_attempt_id"]),
            decision_ref=str(row["decision_ref"]),
            approval_ref=row["approval_ref"],
            policy_ref=row["policy_ref"],
            action_class=str(row["action_class"]),
            resource_scope=list(_json_loads(row["resource_scope_json"])),
            idempotency_key=row["idempotency_key"],
            status=str(row["status"]),
            issued_at=float(row["issued_at"]),
            expires_at=row["expires_at"],
            consumed_at=row["consumed_at"],
        )

    def _receipt_from_row(self, row: sqlite3.Row) -> ReceiptRecord:
        return ReceiptRecord(
            receipt_id=str(row["receipt_id"]),
            task_id=str(row["task_id"]),
            step_id=str(row["step_id"]),
            step_attempt_id=str(row["step_attempt_id"]),
            action_type=str(row["action_type"]),
            input_refs=list(_json_loads(row["input_refs_json"])),
            environment_ref=row["environment_ref"],
            policy_result=_json_loads(row["policy_result_json"]),
            approval_ref=row["approval_ref"],
            output_refs=list(_json_loads(row["output_refs_json"])),
            result_summary=str(row["result_summary"]),
            result_code=str(row["result_code"]),
            decision_ref=row["decision_ref"],
            permit_ref=row["permit_ref"],
            grant_ref=row["grant_ref"],
            policy_ref=row["policy_ref"],
            witness_ref=row["witness_ref"],
            idempotency_key=row["idempotency_key"],
            created_at=float(row["created_at"]),
        )

    def _path_grant_from_row(self, row: sqlite3.Row) -> PathGrantRecord:
        return PathGrantRecord(
            grant_id=str(row["grant_id"]),
            subject_kind=str(row["subject_kind"]),
            subject_ref=str(row["subject_ref"]),
            action_class=str(row["action_class"]),
            path_prefix=str(row["path_prefix"]),
            path_display=str(row["path_display"]),
            created_by=str(row["created_by"]),
            approval_ref=row["approval_ref"],
            decision_ref=row["decision_ref"],
            policy_ref=row["policy_ref"],
            status=str(row["status"]),
            created_at=float(row["created_at"]),
            expires_at=row["expires_at"],
            last_used_at=row["last_used_at"],
        )

    def _schedule_from_row(self, row: sqlite3.Row) -> ScheduledJob:
        return ScheduledJob(
            id=str(row["id"]),
            name=str(row["name"]),
            prompt=str(row["prompt"]),
            schedule_type=str(row["schedule_type"]),
            cron_expr=row["cron_expr"],
            once_at=row["once_at"],
            interval_seconds=row["interval_seconds"],
            enabled=bool(row["enabled"]),
            created_at=float(row["created_at"]),
            last_run_at=row["last_run_at"],
            next_run_at=row["next_run_at"],
            max_retries=int(row["max_retries"]),
            feishu_chat_id=row["feishu_chat_id"],
        )
