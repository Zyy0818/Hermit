from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from hermit.kernel.permits import CapabilityGrantError, CapabilityGrantService


class _FakeStore:
    def __init__(self) -> None:
        self.created = None
        self.updated: list[tuple[str, dict]] = []
        self.permit = None
        self.path_grant = None

    def create_capability_grant(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(permit_id="permit-1")

    def update_capability_grant(self, permit_id: str, **kwargs) -> None:
        self.updated.append((permit_id, kwargs))

    def get_capability_grant(self, permit_id: str):
        return self.permit

    def get_path_grant(self, grant_ref: str):
        return self.path_grant


def test_capability_grant_service_issue_and_state_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _FakeStore()
    service = CapabilityGrantService(store, default_ttl_seconds=300)
    monkeypatch.setattr("hermit.kernel.permits.time.time", lambda: 1000.0)

    permit_id = service.issue(
        task_id="task",
        step_id="step",
        step_attempt_id="attempt",
        decision_ref="decision",
        approval_ref=None,
        policy_ref=None,
        action_class="write_local",
        resource_scope=["/tmp"],
        idempotency_key="abc",
        constraints={"target_paths": ["/tmp/file.txt"]},
    )
    assert permit_id == "permit-1"
    assert store.created["expires_at"] == 1300.0

    no_ttl = service.issue(
        task_id="task",
        step_id="step",
        step_attempt_id="attempt",
        decision_ref="decision",
        approval_ref=None,
        policy_ref=None,
        action_class="write_local",
        resource_scope=["/tmp"],
        idempotency_key=None,
        ttl_seconds=0,
    )
    assert no_ttl == "permit-1"
    assert store.created["expires_at"] is None

    service.consume("permit-1")
    service.mark_uncertain("permit-1")
    service.mark_invalid("permit-1")
    assert store.updated == [
        ("permit-1", {"status": "consumed", "consumed_at": 1000.0}),
        ("permit-1", {"status": "uncertain"}),
        ("permit-1", {"status": "invalid"}),
    ]


def test_capability_grant_service_enforce_and_constraint_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _FakeStore()
    service = CapabilityGrantService(store)
    monkeypatch.setattr("hermit.kernel.permits.time.time", lambda: 1000.0)

    with pytest.raises(CapabilityGrantError, match="not found") as missing:
        service.enforce("missing", action_class="write_local", resource_scope=["/tmp"])
    assert missing.value.code == "missing"

    store.permit = SimpleNamespace(
        permit_id="permit-1",
        status="consumed",
        expires_at=None,
        action_class="write_local",
        resource_scope=["/tmp"],
        constraints={},
    )
    with pytest.raises(CapabilityGrantError, match="cannot be dispatched") as inactive:
        service.enforce("permit-1", action_class="write_local", resource_scope=["/tmp"])
    assert inactive.value.code == "inactive"

    store.permit = SimpleNamespace(
        permit_id="permit-1",
        status="issued",
        expires_at=999.0,
        action_class="write_local",
        resource_scope=["/tmp"],
        constraints={},
    )
    with pytest.raises(CapabilityGrantError, match="expired before dispatch") as expired:
        service.enforce("permit-1", action_class="write_local", resource_scope=["/tmp"])
    assert expired.value.code == "expired"
    assert store.updated[-1] == ("permit-1", {"status": "invalid"})

    store.permit = SimpleNamespace(
        permit_id="permit-1",
        status="issued",
        expires_at=None,
        action_class="read_local",
        resource_scope=["/tmp"],
        constraints={},
    )
    with pytest.raises(CapabilityGrantError, match="only allows") as mismatch:
        service.enforce("permit-1", action_class="write_local", resource_scope=["/tmp"])
    assert mismatch.value.code == "action_mismatch"

    store.permit = SimpleNamespace(
        permit_id="permit-1",
        status="issued",
        expires_at=None,
        action_class="write_local",
        resource_scope=["/tmp"],
        constraints={},
    )
    with pytest.raises(CapabilityGrantError, match="does not cover resource scope") as scope:
        service.enforce("permit-1", action_class="write_local", resource_scope=["/etc"])
    assert scope.value.code == "scope_mismatch"

    store.permit = SimpleNamespace(
        permit_id="permit-1",
        status="issued",
        expires_at=None,
        action_class="write_local",
        resource_scope=["/tmp"],
        constraints={
            "target_paths": ["/tmp/file.txt"],
            "network_hosts": ["example.com"],
            "command_preview": "ls /tmp",
        },
    )
    with pytest.raises(CapabilityGrantError, match="target paths") as path_mismatch:
        service.enforce(
            "permit-1",
            action_class="write_local",
            resource_scope=["/tmp"],
            constraints={"target_paths": ["/tmp/other.txt"]},
        )
    assert path_mismatch.value.code == "target_path_mismatch"

    with pytest.raises(CapabilityGrantError, match="network hosts") as host_mismatch:
        service._validate_constraints(store.permit, {"network_hosts": ["bad.example.com"]})
    assert host_mismatch.value.code == "network_host_mismatch"

    with pytest.raises(CapabilityGrantError, match="current command") as command_mismatch:
        service._validate_constraints(store.permit, {"command_preview": "pwd"})
    assert command_mismatch.value.code == "command_mismatch"


def test_capability_grant_service_validates_path_grants(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = _FakeStore()
    service = CapabilityGrantService(store)
    monkeypatch.setattr("hermit.kernel.permits.time.time", lambda: 1000.0)

    with pytest.raises(CapabilityGrantError, match="no longer active") as inactive:
        service._validate_path_grant("grant-1", current_paths=[str(tmp_path / "file.txt")])
    assert inactive.value.code == "grant_inactive"

    store.path_grant = SimpleNamespace(status="active", expires_at=999.0, path_prefix=str(tmp_path))
    with pytest.raises(CapabilityGrantError, match="expired before dispatch") as expired:
        service._validate_path_grant("grant-1", current_paths=[str(tmp_path / "file.txt")])
    assert expired.value.code == "grant_expired"

    store.path_grant = SimpleNamespace(status="active", expires_at=None, path_prefix=str(tmp_path))
    original_resolve = Path.resolve

    def _bad_resolve(self, *args, **kwargs):
        if str(self) == str(tmp_path):
            raise OSError("bad path")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr("hermit.kernel.permits.Path.resolve", _bad_resolve)
    with pytest.raises(CapabilityGrantError, match="invalid") as invalid_grant:
        service._validate_path_grant("grant-1", current_paths=[str(tmp_path / "file.txt")])
    assert invalid_grant.value.code == "grant_invalid"
    monkeypatch.setattr("hermit.kernel.permits.Path.resolve", original_resolve)

    store.path_grant = SimpleNamespace(status="active", expires_at=None, path_prefix=str(tmp_path))
    with pytest.raises(CapabilityGrantError, match="does not cover") as scope:
        service._validate_path_grant("grant-1", current_paths=[str(tmp_path.parent / "other.txt")])
    assert scope.value.code == "grant_scope_mismatch"

    allowed_path = tmp_path / "nested" / "file.txt"
    allowed_path.parent.mkdir()
    allowed_path.write_text("ok", encoding="utf-8")
    service._validate_path_grant("grant-1", current_paths=[str(allowed_path)])
