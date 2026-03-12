# Serve Troubleshooting

This document focuses on long-running issues around `hermit serve --adapter feishu`, especially when:

- the service appears to have “died unexpectedly”
- Feishu still shows the last reply, but later messages get no response
- the menubar is still running while `serve` itself is gone
- the logs have no traceback and only a stale PID remains

## Start with Three Perspectives

### 1. Process Perspective: Is the service still alive?

Use the environment control script first:

```bash
make env-status ENV=dev
```

Focus on:

- whether `[service]` is empty
- whether `PID_FILE=` still contains an old PID
- whether `[menubar]` is still running

Common patterns:

- `service` is empty but `menubar` is still running: the control layer is still alive, but the `serve` process has already exited
- `PID_FILE` has a value but the process does not exist: that is a stale PID, not a live process

### 2. Lifecycle Perspective: What caused the last exit?

From this version onward, `serve` writes its current state and the last exit reason to:

- `~/.hermit/logs/serve-feishu-status.json`
- `~/.hermit/logs/serve-feishu-exit-history.jsonl`

For `dev` / `test`, the corresponding files are:

- `~/.hermit-dev/logs/serve-feishu-status.json`
- `~/.hermit-dev/logs/serve-feishu-exit-history.jsonl`

Start with:

```bash
cat ~/.hermit-dev/logs/serve-feishu-status.json
```

Common fields:

- `phase`: `starting` / `running` / `reloading` / `stopped` / `crashed`
- `reason`: `startup` / `signal` / `adapter_stopped` / `exception`
- `signal`: for example `SIGTERM` / `SIGHUP` / `SIGINT`
- `detail`: human-readable exit explanation
- `exception_type` / `exception_message` / `traceback`: written for unhandled exceptions

Notes:

- `SIGTERM`, `SIGHUP`, and `SIGINT` are now recorded
- `SIGKILL` cannot be caught by the process, so a `SIGKILL` case usually leaves only a stale PID, not a graceful exit record

### 3. Business Perspective: Did a task fail, or did the service die?

If Feishu shows that “the last message was sent successfully,” do not immediately assume the business logic failed. Check the kernel ledger first:

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select event_type, actor, datetime(occurred_at,'unixepoch','localtime') as occurred_local, substr(payload_json,1,220) as payload
   from events
   order by occurred_at desc
   limit 40;"
```

If you see:

- `approval.granted`
- `receipt.issued`
- `task.completed`

then the task path itself succeeded.

If there are no new `task.created` / `step.started` events after that point, and later Feishu messages never enter the kernel, the usual explanation is that the `serve` host process died, not that a single task failed.

## Work Backward from “the Last Reply”

This is the most useful path for issues like “it replied at 14:03 and then died.”

### 1. Find the last conversation

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select conversation_id, status, datetime(updated_at,'unixepoch','localtime') as updated_local,
          total_input_tokens, total_output_tokens
   from conversations
   order by updated_at desc
   limit 10;"
```

### 2. Inspect that conversation’s messages and tasks

```bash
sqlite3 -line ~/.hermit-dev/kernel/state.db \
  "select id, role, created_at, content_json
   from conversation_messages
   where conversation_id='你的 conversation_id'
   order by id;"
```

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select task_id, status, datetime(created_at,'unixepoch','localtime') as created_local,
          datetime(updated_at,'unixepoch','localtime') as updated_local, title
   from tasks
   where conversation_id='你的 conversation_id'
   order by updated_at desc;"
```

### 3. Check whether the task actually completed

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select task_id, event_type, actor,
          datetime(occurred_at,'unixepoch','localtime') as occurred_local,
          substr(payload_json,1,220) as payload
   from events
   where task_id='你的 task_id'
   order by occurred_at;"
```

If the end of the event stream includes `task.completed`, that means:

- the task itself finished
- “the service disappeared after the last reply” is more likely a process lifecycle problem than a task logic failure

## Check What the Tools Actually Did

If the task involved approvals, shell commands, or file writes, do not guess. Check the receipts and artifacts directly.

### 1. Check receipts

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select receipt_id, action_type, result_summary,
          datetime(created_at,'unixepoch','localtime') as created_local
   from receipts
   where task_id='你的 task_id'
   order by created_at;"
```

### 2. Check the actual command input / output

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select artifact_id, kind, uri,
          datetime(created_at,'unixepoch','localtime') as created_local
   from artifacts
   where task_id='你的 task_id'
   order by created_at;"
```

Then open the corresponding files directly:

- `tool_input`: the actual tool input
- `tool_output`: the actual stdout / stderr / returncode
- `approval_packet`: the command preview shown to the user during approval

This lets you clearly distinguish:

- whether only read-only commands were executed
- whether files were actually deleted
- whether approval mismatch triggered a new approval request

## How to Read the Logs

`serve`-related logs are usually in:

- `~/.hermit-dev/logs/dev-restart-service.out`
- `~/.hermit-dev/logs/serve-feishu-status.json`
- `~/.hermit-dev/logs/serve-feishu-exit-history.jsonl`

`menubar`-related logs are usually in:

- `~/.hermit-dev/logs/companion.log`
- `~/.hermit-dev/logs/feishu-menubar-stdout.log`
- `~/.hermit-dev/logs/feishu-menubar-stderr.log`

Notes:

- historically, `dev-restart-service.out` could be affected by block buffering under redirected output, so “nothing appeared in the last few minutes” was not always trustworthy
- `serve` now forces unbuffered stdout/stderr at startup, so the logs are more reliable for diagnosis

## The Most Useful Decision Path for This Class of Issue

If you hit a problem similar to this one, use this order:

1. `make env-status ENV=dev`
2. inspect `serve-feishu-status.json`
3. inspect the latest `events` in `kernel/state.db`
4. inspect the matching task’s `receipts` and `artifacts`
5. only then go back to `dev-restart-service.out`

The reason is simple:

- `status.json` tells you how the process died
- `kernel` tells you whether the last task actually completed
- `artifacts` tell you what the tools really did
- plain stdout logs are only supporting evidence, not the single source of truth

## Known Boundaries

- `SIGTERM` / `SIGHUP` / `SIGINT`: now recorded
- unhandled Python exceptions: now record traceback
- `SIGKILL`: cannot be caught gracefully; you can only infer it from stale PIDs, missing kernel events, and system-level traces
- if the service was started temporarily by an external host and later reclaimed by that host, Hermit can only record the signal it received itself; it cannot always know who sent it
