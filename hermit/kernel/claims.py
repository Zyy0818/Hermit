from __future__ import annotations

from typing import Any

from hermit.kernel.store import KernelStore

_ROWS: list[dict[str, Any]] = [
    {
        "id": "ingress_task_first",
        "label": "Every ingress is task-first and durable",
        "status": "implemented",
    },
    {
        "id": "event_backed_truth",
        "label": "Durable truth is event-backed and append-only",
        "status": "implemented",
    },
    {
        "id": "no_tool_bypass",
        "label": "No direct model-to-tool execution bypass",
        "status": "implemented",
    },
    {
        "id": "scoped_authority",
        "label": "Effectful execution uses scoped authority and approval packets",
        "status": "implemented",
    },
    {"id": "receipts", "label": "Important actions emit receipts", "status": "implemented"},
    {
        "id": "uncertain_outcome",
        "label": "Uncertain outcomes re-enter via observation or reconciliation",
        "status": "implemented",
    },
    {
        "id": "durable_reentry",
        "label": "Input drift / witness drift / approval drift use durable re-entry",
        "status": "implemented",
    },
    {
        "id": "artifact_context",
        "label": "Artifact-native context is the default runtime path",
        "status": "implemented",
    },
    {
        "id": "memory_evidence",
        "label": "Memory writes are evidence-bound and kernel-backed",
        "status": "implemented",
    },
    {
        "id": "proof_export",
        "label": "Verifiable profile exposes proof coverage and exportable bundles",
        "status": "implemented",
    },
    {
        "id": "signed_proofs",
        "label": "Signed proofs and inclusion proofs are available",
        "status": "implemented",
    },
]


def repository_claim_status() -> dict[str, Any]:
    rows = [dict(row) for row in _ROWS]
    blockers = [row["id"] for row in rows if row["status"] != "implemented"]
    profiles = {
        "core": {"claimable": not blockers, "label": "Hermit Kernel v0.1 Core"},
        "governed": {"claimable": not blockers, "label": "Hermit Kernel v0.1 Core + Governed"},
        "verifiable": {
            "claimable": not blockers,
            "label": "Hermit Kernel v0.1 Core + Governed + Verifiable",
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
