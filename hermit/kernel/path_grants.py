from __future__ import annotations

import time
from pathlib import Path

from hermit.kernel.models import PathGrantRecord
from hermit.kernel.store import KernelStore


class PathGrantService:
    def __init__(self, store: KernelStore) -> None:
        self.store = store

    def create(
        self,
        *,
        conversation_id: str,
        action_class: str,
        path_prefix: str,
        path_display: str,
        created_by: str,
        approval_ref: str | None,
        decision_ref: str | None,
        policy_ref: str | None,
    ) -> str:
        grant = self.store.create_path_grant(
            subject_kind="conversation",
            subject_ref=conversation_id,
            action_class=action_class,
            path_prefix=path_prefix,
            path_display=path_display,
            created_by=created_by,
            approval_ref=approval_ref,
            decision_ref=decision_ref,
            policy_ref=policy_ref,
        )
        return grant.grant_id

    def match(
        self,
        *,
        conversation_id: str,
        action_class: str,
        target_path: str,
    ) -> PathGrantRecord | None:
        try:
            candidate = Path(target_path).expanduser().resolve()
        except OSError:
            return None
        grants = self.store.list_path_grants(
            subject_kind="conversation",
            subject_ref=conversation_id,
            status="active",
            action_class=action_class,
            limit=200,
        )
        for grant in grants:
            if self._matches(candidate, grant):
                return grant
        return None

    def mark_used(self, grant_id: str) -> None:
        self.store.update_path_grant(
            grant_id,
            last_used_at=time.time(),
            actor="kernel",
            event_type="grant.used",
        )

    def revoke(self, grant_id: str, *, revoked_by: str = "user") -> None:
        self.store.update_path_grant(
            grant_id,
            status="revoked",
            actor=revoked_by,
            event_type="grant.revoked",
            payload={"status": "revoked"},
        )

    def _matches(self, candidate: Path, grant: PathGrantRecord) -> bool:
        if grant.expires_at is not None and grant.expires_at < time.time():
            return False
        try:
            prefix = Path(grant.path_prefix).expanduser().resolve()
        except OSError:
            return False
        return candidate == prefix or prefix in candidate.parents
