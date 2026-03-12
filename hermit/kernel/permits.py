from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from hermit.kernel.models import CapabilityGrantRecord
from hermit.kernel.store import KernelStore


class CapabilityGrantError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CapabilityGrantService:
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
        constraints: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> str:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        expires_at = time.time() + ttl if ttl > 0 else None
        permit = self.store.create_capability_grant(
            task_id=task_id,
            step_id=step_id,
            step_attempt_id=step_attempt_id,
            decision_ref=decision_ref,
            approval_ref=approval_ref,
            policy_ref=policy_ref,
            action_class=action_class,
            resource_scope=resource_scope,
            constraints=constraints or {},
            idempotency_key=idempotency_key,
            expires_at=expires_at,
        )
        return permit.permit_id

    def consume(self, permit_id: str) -> None:
        self.store.update_capability_grant(permit_id, status="consumed", consumed_at=time.time())

    def mark_uncertain(self, permit_id: str) -> None:
        self.store.update_capability_grant(permit_id, status="uncertain")

    def mark_invalid(self, permit_id: str) -> None:
        self.store.update_capability_grant(permit_id, status="invalid")

    def enforce(
        self,
        permit_id: str,
        *,
        action_class: str,
        resource_scope: list[str],
        constraints: dict[str, Any] | None = None,
    ) -> CapabilityGrantRecord:
        permit = self.store.get_capability_grant(permit_id)
        if permit is None:
            raise CapabilityGrantError("missing", f"Capability grant not found: {permit_id}")
        if permit.status != "issued":
            raise CapabilityGrantError(
                "inactive",
                f"Capability grant {permit_id} is {permit.status} and cannot be dispatched.",
            )
        if permit.expires_at is not None and permit.expires_at <= time.time():
            self.mark_invalid(permit_id)
            raise CapabilityGrantError("expired", f"Capability grant {permit_id} expired before dispatch.")
        if permit.action_class != action_class:
            self.mark_invalid(permit_id)
            raise CapabilityGrantError(
                "action_mismatch",
                f"Capability grant {permit_id} only allows {permit.action_class}, not {action_class}.",
            )
        if not set(resource_scope).issubset(set(permit.resource_scope)):
            self.mark_invalid(permit_id)
            raise CapabilityGrantError(
                "scope_mismatch",
                f"Capability grant {permit_id} does not cover resource scope {sorted(resource_scope)}.",
            )
        self._validate_constraints(permit, constraints or {})
        return permit

    def _validate_constraints(
        self,
        permit: CapabilityGrantRecord,
        current: dict[str, Any],
    ) -> None:
        stored = dict(permit.constraints or {})
        if not stored:
            return

        stored_paths = [str(path) for path in stored.get("target_paths", [])]
        current_paths = [str(path) for path in current.get("target_paths", [])]
        if stored_paths and current_paths and current_paths != stored_paths:
            self.mark_invalid(permit.permit_id)
            raise CapabilityGrantError(
                "target_path_mismatch",
                f"Capability grant {permit.permit_id} does not cover the current target paths.",
            )

        stored_hosts = set(str(host) for host in stored.get("network_hosts", []))
        current_hosts = set(str(host) for host in current.get("network_hosts", []))
        if stored_hosts and current_hosts and not current_hosts.issubset(stored_hosts):
            self.mark_invalid(permit.permit_id)
            raise CapabilityGrantError(
                "network_host_mismatch",
                f"Capability grant {permit.permit_id} does not cover the current network hosts.",
            )

        stored_command = str(stored.get("command_preview", "") or "").strip()
        current_command = str(current.get("command_preview", "") or "").strip()
        if stored_command and current_command and stored_command != current_command:
            self.mark_invalid(permit.permit_id)
            raise CapabilityGrantError(
                "command_mismatch",
                f"Capability grant {permit.permit_id} does not cover the current command.",
            )

        grant_ref = str(stored.get("grant_ref", "") or "").strip()
        if grant_ref:
            self._validate_path_grant(grant_ref, current_paths=current_paths)

    def _validate_path_grant(self, grant_ref: str, *, current_paths: list[str]) -> None:
        grant = self.store.get_path_grant(grant_ref)
        if grant is None or grant.status != "active":
            raise CapabilityGrantError("grant_inactive", f"Path grant {grant_ref} is no longer active.")
        if grant.expires_at is not None and grant.expires_at <= time.time():
            raise CapabilityGrantError("grant_expired", f"Path grant {grant_ref} expired before dispatch.")
        try:
            prefix = Path(grant.path_prefix).expanduser().resolve()
        except OSError as exc:
            raise CapabilityGrantError("grant_invalid", f"Path grant {grant_ref} is invalid: {exc}") from exc
        for target in current_paths:
            try:
                candidate = Path(target).expanduser().resolve()
            except OSError as exc:
                raise CapabilityGrantError("grant_invalid", f"Target path is invalid: {exc}") from exc
            if candidate != prefix and prefix not in candidate.parents:
                raise CapabilityGrantError(
                    "grant_scope_mismatch",
                    f"Path grant {grant_ref} does not cover {candidate}.",
                )


ExecutionPermitService = CapabilityGrantService
