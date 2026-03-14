# Feishu Ingress Spec

This document defines how Hermit should interpret a new Feishu message inside an existing chat.

## Goals

- keep one Feishu chat usable for both long-running tasks and ordinary conversation
- avoid accidentally attaching a new message to the wrong in-flight task
- avoid accidentally reviving stale task memory when the user is only greeting or chatting
- keep task routing deterministic and easy to debug from logs and kernel events

## Terms

- `conversation_id`: the Feishu chat scope used for session and storage grouping
- `open task`: a task in `queued`, `running`, `blocked`, or equivalent resumable state
- `focus task`: the single implicit task that should receive deictic follow-ups such as `这个`, `上面`, `继续`
- `terminal task`: a task whose status is `completed`, `failed`, or `cancelled`
- `append_note`: attach the message to an existing task as a `task.note.appended`
- `fork_child`: create a new child task related to an existing open task
- `continuation_anchor`: a structured reference to a recent terminal task outcome used when a follow-up should start a new task instead of reopening the old one
- `start_new_root`: create a fresh root task in the same conversation
- `chat_only`: treat the message as ordinary conversation, not as a continuation of the active task
- `pending_disambiguation`: preserve the ingress without binding it until the user clarifies
- `control`: approval and task control text such as `批准`, `继续执行`, `拒绝`, `切到任务 task_xxx`

## Decision Order

Hermit must classify each Feishu message in this order:

1. `control`
2. explicit task / approval / receipt target
3. reply-to or quoted-message target
4. `chat_only`
5. `append_note` to focus or strongest open-task candidate
6. `fork_child`
7. `continue_terminal_outcome`
8. conservative `start_new_root`
9. `pending_disambiguation`

The first matching class wins.

## Routing Classes

### 1. Control

Handled before task ingress routing.

Examples:

- `批准`
- `确认执行`
- `拒绝 approval_xxx`
- `查看当前任务`

Outcome:

- do not create a new task
- do not append a task note
- dispatch to the existing control-intent handler

### 2. Chat-Only

Messages that should receive an answer, but should not inherit the active task’s unfinished intent.

Examples:

- `你好`
- `在吗`
- `hello`
- low-signal punctuation such as `？`

Outcome:

- create a fresh task in the conversation
- do not append to the focus task
- do not default-parent the new task to the previous active task
- suppress conversation-scoped task-state retrieval unless the user text itself is task-related

### 3. Explicit New Task

Messages that clearly declare topic separation.

Examples:

- `新任务：整理桌面`
- `另一个问题`
- `重新开始`
- `换个话题`

Outcome:

- create a fresh task
- do not append to the focus task
- do not default-parent the new task to the previous active task

### 4. Append Note To Open Task

Messages that clearly refine or extend an open task.

Examples:

- `加上和 Grok 的对比`
- `放桌面`
- `改成表格`
- `继续`
- `然后告诉我最重要的一条`

Matching signals:

- explicit task ids, approval ids, or receipt ids
- adapter reply or quote metadata that maps to a task card or task reply message
- explicit continuation markers such as `继续`, `加上`, `补充`, `改成`
- references like `这个`, `那个`, `上面`, `刚才`
- focus task
- lexical/topic overlap with an open task’s title, goal, or recent appended notes

Outcome:

- append a `task.note.appended` event to the chosen task
- do not create a new task

### 5. Fork Child

Messages that introduce a related branch without mutating the current task.

Examples:

- `顺便查一下竞品价格`
- `另外把这份导出成 Markdown`

Outcome:

- create a new child task
- preserve `conversation_id`
- set `parent_task_id` to the related open task
- do not inherit the full parent working state

### 6. Continue Recent Terminal Outcome

Messages that refer back to a recent completed result, but should not revive the old task.

Examples:

- `你说一下你刚才查的北京天气是怎么样的`
- `把上面那个结论再说短一点`
- `你刚才那个结果再总结一下`

Matching signals:

- open-task continuation was not selected
- inspect only recent terminal tasks from the same conversation
- candidate text comes from the task title, goal, recent appended notes, and outcome summary
- match when:
  - explicit or ambiguous follow-up markers are present and topic or lexical overlap exists, or
  - topic or lexical overlap is strong enough on its own
- markers like `刚才`, `上面`, `那个` alone are not sufficient

Outcome:

- create a fresh task
- do not reopen the terminal task
- do not default-parent the new task to the terminal task
- write a `continuation_anchor` into the new task ingress metadata
- the anchor should carry:
  - `anchor_task_id`
  - `anchor_kind=completed_outcome`
  - `selection_reason`
  - `outcome_status`
  - `outcome_summary`
- `source_artifact_refs`

### 7. Conservative Start-New-Root Fallback

If the message is neither control, nor chat-only, nor an obvious continuation, Hermit should start a new task.

Reason:

- starting a new task is safer than silently polluting an in-flight task

### 8. Pending Disambiguation

If multiple open tasks are plausible and no structural signal wins, Hermit should preserve the ingress as `pending_disambiguation`.

Outcome:

- store the ingress durably without mutating a task
- return candidate tasks and rationale
- let the product surface ask the user to clarify or switch focus
- if the user later issues `切到任务 task_xxx`, the pending ingress may be rebound and appended to that task

## Current Implementation Notes

- `conversation_id` is only a container. It does not decide task ownership by itself.
- task routing is decided by `TaskController.decide_ingress()` plus durable ingress binding state
- Feishu should pass message-level reply or quote metadata into ingress binding whenever available
- low-signal punctuation should be dropped before enqueue
- retrieval query must come from the user’s raw text, not from a system-augmented prompt
- conversation projection should strip internal Feishu tags before recent notes are reused
- conversation projection should expose compact `continuation_candidates` for recent terminal tasks

## Observable Outputs

The ingress classifier should emit:

- `mode`
- `intent`
- `reason`
- `resolution`
- `task_id` when continuing an existing task
- `anchor_task_id`
- `anchor_kind`
- `anchor_reason`
- `parent_task_id` for `fork_child`
- candidate tasks when the result is `pending_disambiguation`

These fields may be written into ingress metadata for audit and debugging.
