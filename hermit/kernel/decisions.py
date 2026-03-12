from __future__ import annotations

from hermit.kernel.store import KernelStore


class DecisionService:
    def __init__(self, store: KernelStore) -> None:
        self.store = store

    def record(
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
    ) -> str:
        decision = self.store.create_decision(
            task_id=task_id,
            step_id=step_id,
            step_attempt_id=step_attempt_id,
            decision_type=decision_type,
            verdict=verdict,
            reason=reason,
            evidence_refs=evidence_refs,
            policy_ref=policy_ref,
            approval_ref=approval_ref,
            action_type=action_type,
            decided_by=decided_by,
        )
        return decision.decision_id
