# Memory Model

Hermit's memory model is built around a simple idea:

**memory should not be an ungoverned place where assertions quietly become authority**

That is why Hermit separates working state, beliefs, and durable memory records.

## The Three Layers

### Working State

Working state is bounded execution state for active work.

It should be:

- task-scoped
- size-bounded
- shaped for continuation and planning
- easy to supersede

Working state is not the same thing as durable memory.

### Beliefs

Beliefs are revisable working truths.

A belief represents what the system currently treats as true enough to reason with inside or near a task boundary. Beliefs can cite evidence, carry confidence, and later be invalidated or superseded.

In practical terms, beliefs help Hermit avoid two bad choices:

- pretending every claim is durable memory
- pretending every claim should disappear with the current turn

### Memory Records

Memory records are durable cross-task knowledge.

They are for facts and conventions that should survive beyond the current task, but only under governance rules such as:

- evidence references
- scope
- retention class
- expiration
- invalidation or supersession

## Why Evidence Matters

Memory without provenance becomes hidden system prompt.

Hermit's direction is that durable memory promotion should cite evidence and remain inspectable later. This makes memory less like a bag of sticky notes and more like a governed knowledge layer.

## Scope And Retention

The current codebase already contains memory governance logic for:

- scope matching
- retention classes
- expiration
- static injection eligibility
- retrieval eligibility
- supersession logic

Examples of scope kinds include:

- global
- conversation
- workspace
- entity

This matters because not every memory should follow the system everywhere.

## Promotion And Retrieval

The practical lifecycle is:

1. working activity produces claims
2. some claims become beliefs
3. some beliefs become durable memory records
4. retrieval logic decides what can re-enter context
5. invalidation and supersession keep memory from silently rotting

The key design choice is that promotion is not just "the model thought this sounded useful."

## What Exists Today

Safe claims:

- the repository already defines `BeliefRecord` and `MemoryRecord`
- the repository already has memory governance services
- current logic already covers classification, scope, retention, expiry, and supersession paths

Careful claims:

- the memory model is materially real, but still evolving
- evidence-bound memory is a shipped direction with partial implementation, not a fully settled final system

## Why This Matters

Many agent systems say they have memory. Fewer say what kind of memory, under what scope, with what evidence, and with what invalidation rule.

Hermit's memory model matters because durable work needs:

- memory that can be trusted enough to use
- memory that can still be challenged
- memory that does not silently outrank evidence
