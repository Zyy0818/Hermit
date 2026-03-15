# Kernel Conformance Matrix v0.1

This document tracks how the current repository maps to the `v0.1` kernel spec. It is intentionally stricter than the README: a row is only marked `implemented` when the repo has both a concrete code path and a regression test or operator surface that exercises it.

Status legend:

- `implemented`: shipped in code and covered by tests or operator output
- `partial`: kernel primitive exists, but not yet fully closed across every surface
- `planned`: named in the spec or roadmap, but not yet claimable

## Exit Criteria

| Spec exit criterion | Status | Primary implementation | Regression coverage / operator surface |
| --- | --- | --- | --- |
| Every ingress is task-first and durable | `partial` | `hermit/kernel/controller.py`, `hermit/kernel/ingress_router.py`, `hermit/kernel/store_tasks.py` | `tests/test_kernel_dispatch_and_controller_extra.py`, `tests/test_runner_extra.py` |
| Durable truth is event-backed and append-only | `implemented` | `hermit/kernel/store.py`, `hermit/kernel/store_tasks.py`, `hermit/kernel/store_ledger.py` | `tests/test_task_kernel.py`, `tests/test_kernel_topics_and_projections_extra.py` |
| No direct model-to-tool execution bypass | `implemented` | `hermit/core/tools.py`, `hermit/plugin/manager.py`, `hermit/plugin/mcp_client.py`, `hermit/builtin/github/mcp.py` | `tests/test_plugin_manager_extra.py`, `tests/test_mcp.py`, `tests/test_main_mcp_helpers.py` |
| Effectful execution uses scoped authority and approval packets | `implemented` | `hermit/kernel/executor.py`, `hermit/kernel/approvals.py`, `hermit/kernel/contracts.py`, `hermit/kernel/policy/rules.py` | `tests/test_task_kernel.py`, `tests/test_feishu_dispatcher.py` |
| Important actions emit receipts | `implemented` | `hermit/kernel/receipts.py`, `hermit/kernel/approvals.py`, `hermit/kernel/proofs.py` | `tests/test_task_kernel.py`, CLI `task proof-export` |
| Uncertain outcomes re-enter via observation or reconciliation | `partial` | `hermit/kernel/executor.py`, `hermit/kernel/observation.py`, `hermit/kernel/dispatch.py` | `tests/test_observation_and_client_extra.py`, `tests/test_tools.py` |
| Input drift / witness drift / approval drift use durable re-entry | `partial` | `hermit/kernel/controller.py`, `hermit/kernel/executor.py`, `hermit/kernel/dispatch.py` | `tests/test_task_kernel.py`, `tests/test_kernel_dispatch_and_controller_extra.py` |
| Artifact-native context is the default runtime path | `implemented` | `hermit/kernel/context_compiler.py`, `hermit/kernel/provider_input.py`, `hermit/kernel/artifacts.py` | `tests/test_context_compiler.py`, `tests/test_kernel_coverage_boost.py` |
| Memory writes are evidence-bound and kernel-backed | `partial` | `hermit/kernel/knowledge.py`, `hermit/kernel/memory_governance.py`, `hermit/builtin/memory/hooks.py` | `tests/test_memory_governance.py`, `tests/test_memory_hooks.py` |
| Verifiable profile exposes proof coverage and exportable bundles | `implemented` | `hermit/kernel/proofs.py`, `hermit/kernel/store_ledger.py`, `hermit/main.py` | `tests/test_task_kernel.py`, CLI `task proof-export` |
| Signed proofs / inclusion proofs | `planned` | reserved proof mode fields in `hermit/kernel/proofs.py` and ledger models | not yet claimable |

## Current Hard-Cut Boundaries

Implemented:

- tool governance metadata is mandatory for builtin, plugin, delegation, and MCP tools
- approval grant and deny transitions are ledger-backed decision + receipt events
- worker interruption no longer fabricates terminal failure for in-flight governed attempts
- memory injection and retrieval fail closed without kernel state
- proof export reports missing proof coverage instead of implying signed completeness

Still partial:

- some ingress observability still reflects transition-era metadata rather than pure kernel projections
- durable re-entry semantics are converging, but not every drift case shares one operator workflow yet
- memory mirror and markdown rendering still exist as export surfaces around kernel truth

## Claim Boundary

The repo can plausibly claim:

- `Core`: close to claimable
- `Governed`: materially implemented
- `Verifiable`: baseline implemented, strong profile still in progress

The repo should not yet claim:

- fully uniform drift recovery across every adapter and resume path
- signed or inclusion-proof verifiability
- complete elimination of transition-era operator surfaces
