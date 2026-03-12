from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ReconcileOutcome:
    result_code: str
    summary: str
    observed_refs: list[str]


class ReconcileService:
    def reconcile(
        self,
        *,
        action_type: str,
        tool_input: dict[str, Any],
        workspace_root: str,
    ) -> ReconcileOutcome:
        if action_type in {"write_local", "patch_file"}:
            path = str(tool_input.get("path", "")).strip()
            content = str(tool_input.get("content", ""))
            if path and workspace_root:
                candidate = (Path(workspace_root) / path).resolve()
                if candidate.exists():
                    try:
                        actual = candidate.read_text(encoding="utf-8")
                    except OSError:
                        actual = None
                    if actual == content:
                        return ReconcileOutcome(
                            result_code="reconciled_applied",
                            summary=f"Reconciled local write for {path}.",
                            observed_refs=[],
                        )
                    return ReconcileOutcome(
                        result_code="reconciled_not_applied",
                        summary=f"Observed local state does not match requested write for {path}.",
                        observed_refs=[],
                    )
        return ReconcileOutcome(
            result_code="still_unknown",
            summary=f"Unable to reconcile outcome for {action_type}.",
            observed_refs=[],
        )
