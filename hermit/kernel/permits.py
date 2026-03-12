from __future__ import annotations

import time

from hermit.kernel.store import KernelStore


class ExecutionPermitService:
    def __init__(self, store: KernelStore, *, default_ttl_seconds: int = 300) -> None:
        self.store = store
        self.default_ttl_seconds = default_ttl_seconds

    def issue(
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
        ttl_seconds: int | None = None,
    ) -> str:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        expires_at = time.time() + ttl if ttl > 0 else None
        permit = self.store.create_execution_permit(
            task_id=task_id,
            step_id=step_id,
            step_attempt_id=step_attempt_id,
            decision_ref=decision_ref,
            approval_ref=approval_ref,
            policy_ref=policy_ref,
            action_class=action_class,
            resource_scope=resource_scope,
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        return permit.permit_id

    def consume(self, permit_id: str) -> None:
        self.store.update_execution_permit(permit_id, status="consumed", consumed_at=time.time())

    def mark_uncertain(self, permit_id: str) -> None:
        self.store.update_execution_permit(permit_id, status="uncertain")
