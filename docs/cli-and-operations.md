# CLI 与运维参考

这份文档覆盖当前实际存在的 CLI 命令、常见启动方式，以及长期运行相关的操作约定。

## 顶层命令

`uv run hermit --help` 当前可见命令：

- `setup`
- `init`
- `startup-prompt`
- `run`
- `chat`
- `serve`
- `reload`
- `sessions`
- `plugin`
- `autostart`
- `schedule`
- `config`
- `profiles`
- `auth`

## 基础命令

### `hermit setup`

交互式首次配置向导：

- 写入 `~/.hermit/.env`
- 可选配置 Feishu
- 自动初始化 workspace

### `hermit init`

初始化 workspace 目录与默认上下文文件。

### `hermit startup-prompt`

打印最终启动 system prompt，适合调试：

- base context
- rules
- skills catalog
- hook 注入内容

### `hermit run "..."`

单次执行，不进入交互式会话。

### `hermit chat`

进入交互式多轮会话。

可选参数：

- `--session-id`
- `--debug`

## chat / serve 中可用的 slash commands

core commands：

- `/new`
- `/history`
- `/help`
- `/quit`（仅 CLI）

builtin 插件额外命令：

- `/compact`
- `/plan`
- `/usage`

注意：这些 slash commands 是 `AgentRunner` 系统层命令，不经过 LLM。

## `serve` 与 `reload`

### `hermit serve --adapter feishu`

长期运行模式。当前内置 adapter 主要是 `feishu`。

serve 启动过程会：

1. 读取配置
2. 做环境自检
3. 发现插件
4. 构建 runtime
5. 启动 adapter
6. 同时让 scheduler / webhook 等 `SERVE_START` hook 生效

### `hermit reload --adapter feishu`

向运行中的服务发送 `SIGHUP`，触发优雅重载：

1. 停止当前 adapter
2. 重新读取配置
3. 重新发现插件
4. 重建工具和 system prompt
5. 重启 adapter

这比直接重启进程更适合保留原 PID 和由外部进程管理器接管的场景。

## 启动前环境自检

`serve` 命令会在真正启动前输出一轮预检。

以 `feishu` adapter 为例，会检查：

- profile 来源
- provider 与 model
- LLM 鉴权是否可用
- 飞书 App ID / Secret 来源
- 飞书进度卡片是否开启
- scheduler 默认飞书通知是否配置

如果关键项缺失，`serve` 会直接退出，而不是半启动后失败。

## `config` / `profiles` / `auth`

### `hermit config show`

输出当前解析后的完整配置快照。

最适合确认：

- 当前选中的 profile
- 实际 provider / model
- webhook / scheduler 是否开启
- auth 状态是否可用

### `hermit profiles list`

列出 `~/.hermit/config.toml` 中的所有 profile。

### `hermit profiles resolve --name <profile>`

查看某个 profile 被解析后的值。

### `hermit auth status`

查看当前 provider 会使用哪种鉴权来源。

## `plugin` 子命令

### `hermit plugin list`

列出 builtin 与已安装插件。

### `hermit plugin install <git-url>`

通过 `git clone --depth 1` 安装插件到 `~/.hermit/plugins/<name>`。

### `hermit plugin remove <name>`

删除已安装插件目录。

### `hermit plugin info <name>`

输出插件 manifest 的核心信息。

## `schedule` 子命令

### `hermit schedule list`

列出所有已注册任务及下次执行时间。

### `hermit schedule add`

三种互斥调度方式：

- `--cron`
- `--once`
- `--interval`

示例：

```bash
hermit schedule add \
  --name "daily-summary" \
  --prompt "总结今天的 issue 更新" \
  --cron "0 18 * * 1-5"
```

```bash
hermit schedule add \
  --name "one-shot" \
  --prompt "明天下午提醒我检查部署" \
  --once "2026-03-15T14:00"
```

```bash
hermit schedule add \
  --name "polling" \
  --prompt "检查 webhook 错误日志" \
  --interval 300
```

注意：

- `interval` 最小值是 `60`
- 添加任务后，要等下次 `hermit serve` 启动时才真正进入运行态

### 其他命令

- `hermit schedule remove <id>`
- `hermit schedule enable <id>`
- `hermit schedule disable <id>`
- `hermit schedule history --job-id ... --limit 20`

## `autostart` 子命令

当前仅面向 macOS `launchd`：

- `hermit autostart enable --adapter feishu`
- `hermit autostart disable --adapter feishu`
- `hermit autostart status`

实现特点：

- 每个 adapter 有独立 LaunchAgent plist
- 不同 adapter 之间不会互相覆盖

## `sessions`

`hermit sessions` 会列出当前已知 session 文件名。

session 持久化位置：

- 活跃：`~/.hermit/sessions/*.json`
- 归档：`~/.hermit/sessions/archive/*.json`

## Docker / Compose

当前 compose 里的服务等价命令是：

```bash
hermit serve --adapter feishu
```

不要再写成：

```bash
hermit serve feishu
```

因为当前 CLI 实现里 `adapter` 是 option，不是 positional argument。

## menu bar companion

menu bar companion 的相关命令：

- `hermit-menubar --adapter feishu`
- `hermit-menubar-install-app --adapter feishu --open`

它不是 `serve` 的替代品，而是 macOS 上的控制层。

## 测试与排查

运行测试：

```bash
uv run pytest -q
```

查看命令帮助：

```bash
uv run hermit --help
uv run hermit schedule add --help
uv run hermit serve --help
```

## 这轮更新里修正的运维文档问题

- `serve` 的正确调用方式是 `--adapter feishu`
- `config` / `profiles` / `auth` 三组命令此前几乎没有被文档化
- `schedule add` 的三种互斥模式此前没有被明确写清
