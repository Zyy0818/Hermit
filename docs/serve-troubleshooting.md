# Serve 故障排查

这份文档聚焦 `hermit serve --adapter feishu` 的长期运行问题，尤其是：

- 服务看起来“突然挂了”
- 飞书还能看到最后一条回复，但后续消息没有响应
- menubar 还在，`serve` 本体却不在
- 日志里没有 traceback，只剩一个 stale PID

## 先看三个事实面

### 1. 进程面：服务是不是还活着

优先用环境控制脚本确认：

```bash
make env-status ENV=dev
```

重点看：

- `[service]` 是否为空
- `PID_FILE=` 里是不是还留着旧 PID
- `[menubar]` 是否还在

常见现象：

- `service` 为空、`menubar` 还在：说明控制层还活着，但 `serve` 本体已经退出
- `PID_FILE` 有值但进程不存在：说明这是 stale PID，不是活进程

### 2. 生命周期面：最后一次退出原因是什么

从这版开始，`serve` 会把当前状态和最后一次退出原因写到：

- `~/.hermit/logs/serve-feishu-status.json`
- `~/.hermit/logs/serve-feishu-exit-history.jsonl`

`dev` / `test` 环境对应：

- `~/.hermit-dev/logs/serve-feishu-status.json`
- `~/.hermit-dev/logs/serve-feishu-exit-history.jsonl`

推荐先看：

```bash
cat ~/.hermit-dev/logs/serve-feishu-status.json
```

常见字段：

- `phase`: `starting` / `running` / `reloading` / `stopped` / `crashed`
- `reason`: `startup` / `signal` / `adapter_stopped` / `exception`
- `signal`: 例如 `SIGTERM` / `SIGHUP` / `SIGINT`
- `detail`: 人类可读的退出说明
- `exception_type` / `exception_message` / `traceback`: 未处理异常时会写

注意：

- `SIGTERM`、`SIGHUP`、`SIGINT` 现在都能记录
- `SIGKILL` 无法被进程捕获，所以如果是 `SIGKILL`，通常只会留下 stale PID，而不会有优雅退出记录

### 3. 业务面：是任务失败，还是服务本身死了

如果飞书里“最后一条消息成功发出”，不要立刻假设业务逻辑崩了。先看 kernel 账本：

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select event_type, actor, datetime(occurred_at,'unixepoch','localtime') as occurred_local, substr(payload_json,1,220) as payload
   from events
   order by occurred_at desc
   limit 40;"
```

如果你看到：

- `approval.granted`
- `receipt.issued`
- `task.completed`

说明任务链路本身是走通的。

如果这些事件之后突然再也没有新的 `task.created` / `step.started`，而飞书后续消息也不进 kernel，通常说明挂的是 `serve` 宿主，而不是单个任务。

## 从“最后一条回复”逆推

这是排 `14:03 回复完就崩` 这类问题最有用的路径。

### 1. 查最后一个 conversation

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select conversation_id, status, datetime(updated_at,'unixepoch','localtime') as updated_local,
          total_input_tokens, total_output_tokens
   from conversations
   order by updated_at desc
   limit 10;"
```

### 2. 查这条 conversation 的消息与 task

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

### 3. 查 task 有没有真正跑完

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select task_id, event_type, actor,
          datetime(occurred_at,'unixepoch','localtime') as occurred_local,
          substr(payload_json,1,220) as payload
   from events
   where task_id='你的 task_id'
   order by occurred_at;"
```

如果最后能看到 `task.completed`，说明：

- 任务本身已经完成
- “最后一条回复之后服务不见了”更像进程生命周期问题，不像任务逻辑失败

## 查工具到底执行了什么

如果任务里有审批、shell 命令、文件写入，不要猜。直接看 receipt 和 artifact。

### 1. 查 receipt

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select receipt_id, action_type, result_summary,
          datetime(created_at,'unixepoch','localtime') as created_local
   from receipts
   where task_id='你的 task_id'
   order by created_at;"
```

### 2. 查实际命令输入 / 输出

```bash
sqlite3 -header -column ~/.hermit-dev/kernel/state.db \
  "select artifact_id, kind, uri,
          datetime(created_at,'unixepoch','localtime') as created_local
   from artifacts
   where task_id='你的 task_id'
   order by created_at;"
```

然后直接打开对应文件：

- `tool_input`：实际工具输入
- `tool_output`：实际 stdout / stderr / returncode
- `approval_packet`：审批时给用户看的命令预览

这一步可以明确区分：

- 是不是只执行了只读命令
- 有没有真的删文件
- 有没有因为 approval mismatch 重新发起审批

## 日志怎么读

`serve` 相关日志通常在：

- `~/.hermit-dev/logs/dev-restart-service.out`
- `~/.hermit-dev/logs/serve-feishu-status.json`
- `~/.hermit-dev/logs/serve-feishu-exit-history.jsonl`

`menubar` 相关日志通常在：

- `~/.hermit-dev/logs/companion.log`
- `~/.hermit-dev/logs/feishu-menubar-stdout.log`
- `~/.hermit-dev/logs/feishu-menubar-stderr.log`

注意：

- 过去 `dev-restart-service.out` 在重定向场景下容易被 block buffering 影响，导致“最后几分钟什么都没刷出来”
- 现在 `serve` 启动时会强制 stdout/stderr 走无缓冲模式，定位会更可靠

## 这次问题里最有用的判断方式

如果你遇到和这次类似的现象，可以按这个顺序判断：

1. `make env-status ENV=dev`
2. 看 `serve-feishu-status.json`
3. 看 `kernel/state.db` 里最后几条 `events`
4. 看对应 task 的 `receipts` 和 `artifacts`
5. 最后再回头看 `dev-restart-service.out`

原因很简单：

- `status.json` 告诉你进程是怎么死的
- `kernel` 告诉你最后一个任务有没有真正完成
- `artifact` 告诉你工具到底做了什么
- 普通 stdout 日志只能作为补充，不能单独当真相来源

## 已知边界

- `SIGTERM` / `SIGHUP` / `SIGINT`：现在能记录
- 未处理 Python 异常：现在能记录 traceback
- `SIGKILL`：无法优雅捕获，只能从 stale PID、kernel 事件中断、系统层痕迹反推
- 如果服务是由外部宿主临时拉起又被宿主回收，Hermit 只能记录“自己收到的退出信号”，无法总是知道“是谁发的”
