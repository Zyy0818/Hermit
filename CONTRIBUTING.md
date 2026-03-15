# Contributing to Hermit

Hermit is still early enough that architecture-sensitive contributions can materially shape the project.

This is not just a feature-accumulation repository. It is a codebase moving from a local-first agent runtime toward a local-first governed agent kernel. Contributions should strengthen that direction.

## Before You Start

Read these first:

- [README.md](./README.md)
- [docs/why-hermit.md](./docs/why-hermit.md)
- [docs/architecture.md](./docs/architecture.md)
- [docs/kernel-spec-v0.1.md](./docs/kernel-spec-v0.1.md)
- [docs/roadmap.md](./docs/roadmap.md)

Use this mental model while contributing:

- README explains the project and why it matters
- `architecture.md` describes the current implementation
- `kernel-spec-v0.1.md` defines the target architecture
- roadmap tracks the distance between those two

## What Kinds Of Contributions Matter Most

High-leverage areas:

- task, step, and step-attempt semantics
- policy, approval, decision, and scoped authority flow
- receipts, proofs, and rollback coverage
- artifact handling and context compilation
- belief and memory governance
- operator visibility, inspectability, and recovery paths
- docs that sharpen current-state vs target-state boundaries

Lower-leverage contributions are still welcome, but they should not pull Hermit back toward "just another chat-plus-tools shell."

## Development Workflow

Recommended local workflow:

```bash
make env-up ENV=dev
make env-watch ENV=dev
make test
```

Common commands:

```bash
make lint
make test
make test-cov
make verify
make env-status ENV=dev
make env-restart ENV=dev
make env-down ENV=dev
```

If you need to run Hermit directly inside the dev environment:

```bash
scripts/hermit-env.sh dev chat
scripts/hermit-env.sh dev serve feishu
```

## Contribution Rules

### 1. Keep Current State And Target State Separate

When you touch docs or architecture-sensitive code, be explicit about which of these you are describing:

- **current implementation**
- **partial implementation**
- **target architecture**
- **experimental behavior**

Good phrasing:

- `Hermit currently ships...`
- `Hermit is converging toward...`
- `The v0.1 kernel spec defines...`
- `This path is still experimental...`

Avoid:

- presenting the spec as fully shipped
- calling every runtime path "kernelized"
- using "verifiable" or "event-sourced" as blanket claims without scope

### 2. Optimize For Kernel Consistency

Prefer changes that reinforce:

- task-first execution
- event-backed truth
- governed side effects
- artifact-native context
- evidence-bound memory
- receipt-aware completion
- rollback-aware recovery

### 3. Do Not Hide Complexity

Hermit should stay readable, but not by flattening away important execution law.

If a path needs policy, approval, permits, receipts, witness checks, or rollback semantics, keep those concepts visible in code and docs.

### 4. Preserve Operator Visibility

A strong Hermit change tends to improve at least one of these:

- what the operator can inspect
- what can be approved or denied
- what evidence is retained
- what can be explained later
- what can be rolled back

## Doc Writing Rules

When writing docs:

- explain value before architecture on landing pages
- explain architecture before internals in deep docs
- keep the README strong and short
- keep the spec precise and normative
- always mark target-state content clearly

Suggested wording:

- `Hermit is a local-first governed agent kernel.`
- `Hermit currently ships kernel ledger objects such as Task, Approval, Receipt, and MemoryRecord.`
- `The v0.1 kernel spec defines the target architecture, not the full current repo state.`

## Pull Request Expectations

Good PRs usually include:

- a clear statement of what changed
- why the change matters in Hermit's kernel direction
- notes on current-state vs target-state impact
- tests for behavior changes
- doc updates when terminology, operator behavior, or architectural understanding changes

If the change affects a governed execution path, task lifecycle, memory behavior, or proof/rollback semantics, include documentation updates in the same PR whenever practical.

## Where To Start

If you want a high-signal first contribution:

1. Improve a current implementation doc so it is more honest and more legible.
2. Add tests around a kernel object lifecycle or policy boundary.
3. Tighten a path where side effects should be more explicitly governed.
4. Improve operator-facing inspection, proof, or rollback ergonomics.

Hermit does not need more vague features. It needs sharper semantics, clearer docs, and stronger governed execution.
