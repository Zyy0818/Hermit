# Roadmap

Hermit is best understood today as an **alpha local-first governed agent kernel**.

It is not starting from zero. The repository already contains real kernel objects, governance paths, proof primitives, and rollback support for selected actions. But the whole system is still converging on the `v0.1` kernel spec.

This roadmap separates four things clearly:

- what Hermit already ships
- what is partially implemented
- what the `v0.1` spec defines as target behavior
- what remains experimental or open

## Current Status Snapshot

### Safe current-state claims

- Hermit already ships a local kernel ledger with first-class task-related records.
- Hermit already has governed execution primitives such as policy evaluation, approvals, decisions, permits, and path grants.
- Hermit already issues receipts and exposes proof summaries and proof export.
- Hermit already supports rollback for supported receipt classes.
- Hermit already has context compilation and memory governance primitives.

### Careful current-state claims

- Core is close to claimable as an alpha kernel.
- Governed execution is materially visible and already important to the current repo.
- Verifiable execution has meaningful primitives, but should still be described as in-progress.
- Not every runtime surface should be described as fully aligned with the target kernel spec.

## Status Matrix

| Area | Current state | Direction |
| --- | --- | --- |
| Task-first execution | real and visible | continue unifying all ingress paths |
| Event-backed truth | real in the kernel ledger | deepen projection and replay semantics |
| Governed execution | real and visible | extend coverage and tighten invariants |
| Receipts and proofs | real primitives exist | broaden coverage and operator ergonomics |
| Rollback | supported for selected receipts | expand safe rollback classes |
| Artifact-native context | real direction with implementation | make it more central across all paths |
| Evidence-bound memory | real direction with implementation | tighten promotion, invalidation, and inspection |
| Public API stability | not a current goal | later concern after kernel semantics settle |

## Near-Term Milestones

### Milestone 1: Spec `0.1` Convergence

Focus:

- make task, step, and step-attempt semantics the dominant execution model
- remove ambiguous gaps between runtime surfaces and kernel paths
- keep current-state docs honest while increasing kernel visibility

### Milestone 2: Governed Execution Hardening

Focus:

- broaden policy coverage for consequential actions
- strengthen approval and witness drift semantics
- improve scoped authority handling

### Milestone 3: Receipt And Proof Coverage

Focus:

- increase receipt coverage across important action classes
- improve proof bundle completeness
- make operator inspection and proof export more usable

### Milestone 4: Recovery And Context

Focus:

- improve rollback coverage where safe
- deepen observation and resolution semantics
- strengthen artifact-native context and carry-forward behavior

## Contribution Priorities

The highest-leverage contributions right now are:

- task lifecycle correctness
- governance correctness
- receipt and proof coverage
- rollback safety
- context and memory discipline
- docs that sharply separate current implementation from target architecture

## What The Roadmap Is Not

The roadmap is not a promise that Hermit is trying to become:

- a giant multi-tenant cloud platform
- a no-tradeoff autonomous agent system
- a surface-level tool catalog race

Hermit's goal is narrower and stronger:

to become a local-first governed kernel for durable agent work that operators can inspect, approve, and recover.
