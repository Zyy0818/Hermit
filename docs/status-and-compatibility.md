# Status And Compatibility

This document is the short honesty layer for Hermit's docs.

Use it when you want to know what is shipped, what is partial, what is target-only, and what should still be treated as unstable.

## Current Positioning

Hermit is best described today as:

**an alpha local-first governed agent kernel**

That means:

- the repo already contains real kernel semantics and control paths
- the repo is still converging toward the full `v0.1` target architecture

## Status Matrix

| Area | Status | Notes |
| --- | --- | --- |
| Task ledger and core records | shipped | task, step, step attempt, approval, decision, permit, grant, artifact, receipt, belief, memory, rollback, conversation, ingress |
| Governed execution | shipped with ongoing hardening | policy, approval, and scoped authority are already real in the codebase |
| Proof summaries and proof export | shipped | usable today through the task CLI |
| Rollback | partial | supported for selected receipt classes, not universal |
| Artifact-native context | partial but real | context compiler and context packs already exist |
| Evidence-bound memory | partial but real | memory governance primitives already exist |
| Full spec `0.1` convergence | in progress | target architecture, not full current-state claim |
| Stable public kernel API | not a current promise | interfaces may still change as semantics settle |

## Recommended Wording

### Safe wording

- `Hermit is a local-first governed agent kernel.`
- `Hermit currently ships a local kernel ledger with first-class task and execution records.`
- `Hermit already exposes approvals, receipts, proofs, and rollback support for selected actions.`
- `Hermit is converging toward the v0.1 kernel spec.`

### Wording to scope carefully

- `event-sourced`
- `verifiable`
- `auditable`
- `rollback-capable`
- `stable`

Use these only when you also say what layer or surface you mean.

## Compatibility Expectations

Current expectations:

- CLI and local-first workflows are the primary operator surface
- kernel semantics are more stable than outer packaging claims, but still not a final public contract
- docs should distinguish current implementation from target architecture

If you are building on Hermit today, assume:

- the direction is strong
- the semantics matter
- some interfaces may still move as the kernel model settles

## Read This Alongside

- [architecture.md](./architecture.md)
- [kernel-spec-v0.1.md](./kernel-spec-v0.1.md)
- [roadmap.md](./roadmap.md)
