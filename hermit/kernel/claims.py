from __future__ import annotations

from typing import Any

from hermit.kernel.claim_manifest import CLAIM_ROWS, PROFILE_LABELS
from hermit.kernel.store import KernelStore


def repository_claim_status() -> dict[str, Any]:
    rows = [dict(row) for row in CLAIM_ROWS]
    blockers = [row["id"] for row in rows if row["status"] != "implemented"]
    profiles = {
        "core": {"claimable": not blockers, "label": PROFILE_LABELS["core"]},
        "governed": {"claimable": not blockers, "label": PROFILE_LABELS["governed"]},
        "verifiable": {
            "claimable": not blockers,
            "label": PROFILE_LABELS["verifiable"],
        },
    }
    return {
        "rows": rows,
        "profiles": profiles,
        "claimable_profiles": [
            payload["label"] for payload in profiles.values() if payload["claimable"]
        ],
        "blockers": blockers,
    }


def task_claim_status(
    store: KernelStore, task_id: str, *, proof_summary: dict[str, Any]
) -> dict[str, Any]:
    repo = repository_claim_status()
    coverage = dict(proof_summary.get("proof_coverage", {}) or {})
    chain = dict(proof_summary.get("chain_verification", {}) or {})
    receipt_bundle = dict(coverage.get("receipt_bundle_coverage", {}) or {})
    signature_coverage = dict(coverage.get("signature_coverage", {}) or {})
    inclusion_coverage = dict(coverage.get("inclusion_proof_coverage", {}) or {})
    verifiable_ready = bool(chain.get("valid")) and (
        int(receipt_bundle.get("bundled_receipts", 0) or 0)
        == int(receipt_bundle.get("total_receipts", 0) or 0)
    )
    strongest_ready = (
        verifiable_ready
        and (
            int(signature_coverage.get("signed_receipts", 0) or 0)
            == int(signature_coverage.get("total_receipts", 0) or 0)
        )
        and (
            int(inclusion_coverage.get("proved_receipts", 0) or 0)
            == int(inclusion_coverage.get("total_receipts", 0) or 0)
        )
    )
    return {
        "task_id": task_id,
        "repository": repo,
        "task_gate": {
            "chain_valid": bool(chain.get("valid")),
            "verifiable_ready": verifiable_ready,
            "strong_verifiable_ready": strongest_ready,
            "proof_mode": proof_summary.get("proof_mode"),
            "strongest_export_mode": proof_summary.get("strongest_export_mode"),
        },
    }


__all__ = ["repository_claim_status", "task_claim_status"]
