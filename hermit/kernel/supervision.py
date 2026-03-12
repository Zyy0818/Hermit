from __future__ import annotations

from typing import Any

from hermit.kernel.projections import ProjectionService
from hermit.kernel.rollbacks import RollbackService
from hermit.kernel.store import KernelStore


class SupervisionService:
    def __init__(self, store: KernelStore) -> None:
        self.store = store
        self.projections = ProjectionService(store)
        self.rollbacks = RollbackService(store)

    def build_task_case(self, task_id: str) -> dict[str, Any]:
        cached = self.projections.ensure_task_projection(task_id)
        proof = cached["proof"]
        latest_receipt = proof.get("latest_receipt")
        latest_decision = proof.get("latest_decision")
        latest_permit = proof.get("latest_permit")
        approvals = list(cached["projection"]["approvals"].values())
        approvals.sort(key=lambda item: float(item.get("last_event_at") or 0), reverse=True)
        latest_approval = approvals[0] if approvals else None
        latest_grant = None
        if latest_receipt and latest_receipt.get("grant_ref"):
            grant = self.store.get_path_grant(str(latest_receipt["grant_ref"]))
            latest_grant = grant.__dict__ if grant is not None else None
        target_paths = list((latest_permit or {}).get("constraints", {}).get("target_paths", []))
        latest_memory = cached["knowledge"][0] if cached["knowledge"] else None
        rollback = None
        if latest_receipt and latest_receipt.get("receipt_id"):
            record = self.store.get_rollback_for_receipt(str(latest_receipt["receipt_id"]))
            rollback = record.__dict__ if record is not None else None
        return {
            "task": cached["task"],
            "projection": {
                "events_processed": cached["projection"]["events_processed"],
                "last_event_seq": cached["projection"]["last_event_seq"],
                "step_count": len(cached["projection"]["steps"]),
                "step_attempt_count": len(cached["projection"]["step_attempts"]),
                "approval_count": len(cached["projection"]["approvals"]),
                "decision_count": len(cached["projection"]["decisions"]),
                "permit_count": len(cached["projection"]["permits"]),
                "receipt_count": len(cached["projection"]["receipts"]),
                "belief_count": len(cached["projection"]["beliefs"]),
                "memory_count": len(cached["projection"]["memory_records"]),
            },
            "operator_answers": {
                "why_execute": latest_decision["reason"] if latest_decision else None,
                "evidence_refs": list((latest_decision or {}).get("evidence_refs", [])),
                "approval": latest_approval,
                "authority": {
                    "permit": latest_permit,
                    "grant": latest_grant,
                    "target_paths": target_paths,
                    "rollback_available": bool((latest_receipt or {}).get("rollback_supported")),
                    "rollback_strategy": (latest_receipt or {}).get("rollback_strategy"),
                },
                "outcome": latest_receipt,
                "proof": proof["chain_verification"],
                "knowledge": {
                    "latest_memory": latest_memory,
                    "recent_beliefs": cached["beliefs"][:5],
                },
                "rollback": rollback,
            },
        }

    def rollback_receipt(self, receipt_id: str) -> dict[str, Any]:
        return self.rollbacks.execute(receipt_id)
