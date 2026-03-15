# Context Model

Hermit treats context as more than message history.

Message history still matters, but it is not the primary substrate for durable work. Hermit is moving toward an artifact-native context model where the kernel compiles a task-scoped context pack from structured state.

This matters because durable work should be grounded in what the system actually knows, what it has observed, and what it has produced, not just what happened to be said recently.

## Core Principle

Most agents treat transcript as default context. Hermit treats artifacts and structured state as default context units.

In practice, Hermit wants context assembly to answer:

- what task is in focus
- what state is currently bounded and active
- what beliefs are currently usable
- what durable memories are in scope
- what artifacts are relevant evidence
- what recent deltas matter for continuation

## Context Pack

The current codebase already contains a context compiler and a context pack model.

Current pack ingredients include:

- static memory
- retrieval memory
- selected beliefs
- working state
- task summary
- step summary
- policy summary
- planning state
- carry-forward information
- recent notes
- relevant artifact references
- ingress artifact references
- focus summary

This is one of the strongest implementation signals that Hermit is no longer just transcript-driven.

## Artifact-Native Context

Artifacts matter because they can be:

- cited
- hashed
- referred to by receipts
- reused across task boundaries
- treated as evidence instead of just raw text

Examples include:

- input payloads
- output payloads
- receipt bundles
- proof bundles
- context manifests
- state witnesses

The point is not to eliminate text. The point is to make text only one context source among several.

## Working State, Beliefs, And Memory

Hermit distinguishes among:

- **working state**: bounded execution state for active work
- **beliefs**: revisable working truth with evidence references
- **memory records**: durable cross-task knowledge promoted under governance rules

This separation helps prevent two failure modes:

- transcript-only drift
- memory turning into hidden authority

## Continuation And Carry-Forward

A durable task often needs more than "continue the conversation."

Hermit's direction is to carry forward:

- the right task anchor
- the right recent notes
- the right artifacts
- the right bounded state

without flattening everything into unbounded transcript replay.

## What Exists Today

Safe claims:

- the repository already has a context compiler
- the repository already has a structured context pack
- artifacts, beliefs, and memories already participate in context assembly

Careful claims:

- Hermit is still converging on artifact-native context everywhere
- transcript still exists as part of the broader runtime and provider flow

## Why This Matters

Artifact-native context is one of the main reasons Hermit does not collapse back into a generic agent wrapper.

It gives the kernel a better answer to:

- what was in scope
- what evidence informed the action
- what state should carry forward
- what should be durable versus revisable
