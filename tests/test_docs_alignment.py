from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_docs_describe_kernel_first_positioning() -> None:
    readme = _read("README.md")
    architecture = _read("docs/architecture.md")
    pyproject = _read("pyproject.toml")

    assert "local-first governed agent kernel" in readme
    assert "kernel-first" in architecture
    assert "governed agent kernel" in pyproject


def test_public_docs_state_v0_1_is_target_not_completion_claim() -> None:
    readme = _read("README.md")
    architecture = _read("docs/architecture.md")

    assert "`v0.1` kernel spec" in readme
    assert "target architecture" in readme
    assert "does not treat the `v0.1` kernel spec as fully shipped" in architecture


def test_public_docs_call_out_governance_hard_cut_and_proof_boundary() -> None:
    readme = _read("README.md")
    architecture = _read("docs/architecture.md")

    assert "tool governance" in readme
    assert "Approval resolution" in readme
    assert "fail closed" in architecture
    assert "missing proof coverage" in architecture


def test_conformance_matrix_tracks_exit_criteria_and_claim_boundary() -> None:
    matrix = _read("docs/kernel-conformance-matrix-v0.1.md")

    assert "Spec exit criterion" in matrix
    assert "No direct model-to-tool execution bypass" in matrix
    assert "Input drift / witness drift / approval drift use durable re-entry" in matrix
    assert "The repo should not yet claim" in matrix
