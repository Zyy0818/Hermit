from __future__ import annotations

from typing import Any

CLAIM_ROWS: list[dict[str, Any]] = [
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
    {
        "id": "receipts",
        "label": "Important actions emit receipts",
        "status": "implemented",
    },
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

PROFILE_LABELS = {
    "core": "Hermit Kernel v0.1 Core",
    "governed": "Hermit Kernel v0.1 Core + Governed",
    "verifiable": "Hermit Kernel v0.1 Core + Governed + Verifiable",
}


__all__ = ["CLAIM_ROWS", "PROFILE_LABELS"]
