from __future__ import annotations

from pathlib import Path

from hermit.kernel.proofs import ProofService
from hermit.kernel.store import KernelStore
from hermit.kernel.store_support import _UNSET, _json_loads


def test_store_support_json_loads_handles_empty_and_invalid() -> None:
    assert _json_loads(None) == {}
    assert _json_loads("") == {}
    assert _json_loads("{bad") == {}
    assert _json_loads('{"ok": true}') == {"ok": True}
    assert _UNSET is not None


def test_kernel_store_task_flow_covers_conversations_tasks_steps_attempts_and_events(tmp_path: Path) -> None:
    store = KernelStore(tmp_path / "state.db")

    conversation = store.ensure_conversation("conv-1", source_channel="chat", source_ref="thread-1")
    same_conversation = store.ensure_conversation("conv-1", source_channel="chat")
    assert conversation.conversation_id == "conv-1"
    assert same_conversation.conversation_id == "conv-1"
    assert store.get_conversation("conv-1") is not None
    assert store.list_conversations() == ["conv-1"]

    store.update_conversation_metadata("conv-1", {"topic": "testing"})
    store.update_conversation_usage(
        "conv-1",
        input_tokens=10,
        output_tokens=20,
        cache_read_tokens=3,
        cache_creation_tokens=4,
        last_task_id=None,
    )
    updated_conversation = store.get_conversation("conv-1")
    assert updated_conversation is not None
    assert updated_conversation.metadata["topic"] == "testing"
    assert updated_conversation.total_output_tokens == 20

    task_one = store.create_task(
        conversation_id="conv-1",
        title="Task One",
        goal="First goal",
        source_channel="chat",
        requested_by="tester",
    )
    task_two = store.create_task(
        conversation_id="conv-1",
        title="Task Two",
        goal="Second goal",
        source_channel="chat",
    )
    fetched_task = store.get_task(task_one.task_id)
    assert fetched_task is not None
    assert fetched_task.title == "Task One"
    assert store.get_last_task_for_conversation("conv-1").task_id == task_two.task_id
    assert [task.task_id for task in store.list_tasks(conversation_id="conv-1", limit=10)][0] == task_two.task_id

    store.update_task_status(task_one.task_id, "blocked")
    blocked_tasks = store.list_tasks(status="blocked", limit=10)
    assert [task.task_id for task in blocked_tasks] == [task_one.task_id]

    step = store.create_step(task_id=task_one.task_id, kind="respond")
    assert store.get_step(step.step_id) is not None
    store.update_step(step.step_id, status="completed", output_ref="artifact-1", finished_at=123.0)
    updated_step = store.get_step(step.step_id)
    assert updated_step is not None
    assert updated_step.status == "completed"
    assert updated_step.output_ref == "artifact-1"
    store.update_step("missing-step", status="ignored")

    attempt = store.create_step_attempt(
        task_id=task_one.task_id,
        step_id=step.step_id,
        attempt=2,
        context={"phase": "draft"},
    )
    assert store.get_step_attempt(attempt.step_attempt_id) is not None
    store.update_step_attempt(
        attempt.step_attempt_id,
        status="blocked",
        context={"phase": "review"},
        waiting_reason="approval",
        approval_id="approval-1",
        decision_id="decision-1",
        permit_id="permit-1",
        state_witness_ref="witness-1",
        finished_at=456.0,
    )
    updated_attempt = store.get_step_attempt(attempt.step_attempt_id)
    assert updated_attempt is not None
    assert updated_attempt.status == "blocked"
    assert updated_attempt.context == {"phase": "review"}
    assert updated_attempt.waiting_reason == "approval"
    assert updated_attempt.permit_id == "permit-1"

    store.update_step_attempt(
        attempt.step_attempt_id,
        status="running",
        context=updated_attempt.context,
        waiting_reason=updated_attempt.waiting_reason,
        approval_id=updated_attempt.approval_id,
        decision_id=updated_attempt.decision_id,
        permit_id=updated_attempt.permit_id,
        state_witness_ref=updated_attempt.state_witness_ref,
        finished_at=updated_attempt.finished_at,
    )
    unchanged_attempt = store.get_step_attempt(attempt.step_attempt_id)
    assert unchanged_attempt is not None
    assert unchanged_attempt.context == {"phase": "review"}
    assert unchanged_attempt.waiting_reason == "approval"
    store.update_step_attempt("missing-attempt", status="ignored")

    custom_event_id = store.append_event(
        event_type="custom.event",
        entity_type="task",
        entity_id=task_one.task_id,
        task_id=task_one.task_id,
        step_id=step.step_id,
        actor="tester",
        payload={"extra": True},
        causation_id="cause-1",
        correlation_id="corr-1",
    )
    assert custom_event_id.startswith("event_")

    all_events = store.list_events(limit=20)
    task_events = store.list_events(task_id=task_one.task_id, limit=20)
    assert all_events
    assert any(event["event_type"] == "custom.event" for event in all_events)
    assert all(event["task_id"] == task_one.task_id for event in task_events)
    assert any(event["payload"].get("status") == "blocked" for event in task_events)
    assert all(event["event_hash"] for event in task_events)
    assert task_events[0]["prev_event_hash"] in {None, ""}
    assert all(event["hash_chain_algo"] == "sha256-v1" for event in task_events)

    projection = store.build_task_projection(task_one.task_id)
    assert projection["task"]["task_id"] == task_one.task_id
    assert projection["task"]["status"] == "blocked"
    assert projection["steps"][step.step_id]["status"] == "completed"
    assert projection["step_attempts"][attempt.step_attempt_id]["status"] == "running"
    assert projection["step_attempts"][attempt.step_attempt_id]["permit_id"] == "permit-1"
    assert projection["events_processed"] >= len(task_events)


def test_kernel_store_backfills_event_hash_chain_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "state.db"
    store = KernelStore(db_path)
    store.ensure_conversation("conv-proof", source_channel="chat")
    task = store.create_task(
        conversation_id="conv-proof",
        title="Proof Task",
        goal="Backfill event hash chain",
        source_channel="chat",
    )
    step = store.create_step(task_id=task.task_id, kind="respond")
    store.create_step_attempt(task_id=task.task_id, step_id=step.step_id)
    with store._lock, store._conn:  # type: ignore[attr-defined]
        store._conn.execute(  # type: ignore[attr-defined]
            "UPDATE events SET event_hash = NULL, prev_event_hash = NULL, hash_chain_algo = NULL"
        )
    store.close()

    reopened = KernelStore(db_path)
    try:
        proof = ProofService(reopened).verify_task_chain(task.task_id)
        events = reopened.list_events(task_id=task.task_id, limit=20)
        assert proof["valid"] is True
        assert all(event["event_hash"] for event in events)
        assert all(event["hash_chain_algo"] == "sha256-v1" for event in events)
    finally:
        reopened.close()


def test_proof_service_detects_tampered_event_chain(tmp_path: Path) -> None:
    store = KernelStore(tmp_path / "state.db")
    store.ensure_conversation("conv-tamper", source_channel="chat")
    task = store.create_task(
        conversation_id="conv-tamper",
        title="Tampered Task",
        goal="Detect event tampering",
        source_channel="chat",
    )
    step = store.create_step(task_id=task.task_id, kind="respond")
    store.create_step_attempt(task_id=task.task_id, step_id=step.step_id)

    events = store.list_events(task_id=task.task_id, limit=20)
    assert events
    tampered_event_id = events[-1]["event_id"]
    with store._lock, store._conn:  # type: ignore[attr-defined]
        store._conn.execute(  # type: ignore[attr-defined]
            "UPDATE events SET payload_json = ? WHERE event_id = ?",
            ('{"tampered":true}', tampered_event_id),
        )
    proof = ProofService(store).verify_task_chain(task.task_id)
    assert proof["valid"] is False
    assert proof["broken_at_event_id"] == tampered_event_id
