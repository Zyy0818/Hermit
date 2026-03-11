# Hermit 架构说明

这份文档只描述当前仓库已经落地的实现，不描述旧设计稿，也不把未来想法写成现状。

## 总览

Hermit 的主执行链路非常短：

```text
CLI / Feishu Adapter / Scheduler / Webhook
                    |
                    v
               AgentRunner
                    |
        +-----------+-----------+
        |                       |
        v                       v
   SessionManager         PluginManager
                                |
                                +--> hooks / tools / commands / subagents / adapters / MCP
                    |
                    v
               AgentRuntime
                    |
                    v
                 Provider
                    |
                    +--> Claude API
                    +--> OpenAI Responses API
                    +--> Codex OAuth flow
```

核心目标不是“平台功能越多越好”，而是：

- runtime 主链路尽量短
- 插件扩展点清晰
- 状态文件容易检查和恢复

## 启动路径

主入口在 [`hermit/main.py`](../hermit/main.py)。

启动顺序大致是：

1. 读取 `~/.hermit/.env` 到进程环境
2. 构造 `Settings`
3. 创建 `~/.hermit` 必需目录
4. 发现并加载 builtin / installed plugins
5. 构建工具注册表
6. 注册插件工具、命令、subagent、MCP
7. 构建基础 system prompt + 规则 + skills + hook 注入片段
8. 构造 provider 与 `AgentRuntime`
9. 交给 CLI / adapter / scheduler / webhook 使用同一套 runner

## 核心模块

### [`hermit/main.py`](../hermit/main.py)

职责：

- CLI 命令定义
- workspace 初始化
- 运行前鉴权与自检
- `serve` / `reload` 生命周期
- runtime / runner 组装

### [`hermit/config.py`](../hermit/config.py)

职责：

- 解析 `.env`、shell env、`config.toml` profile
- 处理 provider 兼容字段与旧字段别名
- 暴露所有运行时路径
- 汇总鉴权状态、webhook 默认值等派生属性

### [`hermit/provider/services.py`](../hermit/provider/services.py)

职责：

- 根据 `settings.provider` 构造 provider
- 组装 `AgentRuntime`
- 构造结构化抽取与图像分析服务

当前实际 provider：

- `claude`
- `codex`
- `codex-oauth`

### [`hermit/provider/runtime.py`](../hermit/provider/runtime.py)

职责：

- 统一的 model tool loop
- tool result 截断与序列化
- streaming / non-streaming 兼容
- usage 指标累加

这里是 Hermit 的模型执行中心。当前已经不是“只支持 Anthropic Messages API”的实现，而是 provider 协议之上的统一 runtime。

### [`hermit/core/runner.py`](../hermit/core/runner.py)

职责：

- slash command 分发
- session 生命周期
- `SESSION_START` / `PRE_RUN` / `POST_RUN` / `SESSION_END` hooks
- 把普通用户消息交给 `AgentRuntime`

它是 CLI、adapter、webhook、scheduler 共用的统一编排层。

### [`hermit/core/session.py`](../hermit/core/session.py)

职责：

- 单 session 单 JSON 文件持久化
- 空闲超时自动归档
- token 用量统计累计

session 文件是普通 JSON，不是 JSONL。

### [`hermit/core/tools.py`](../hermit/core/tools.py)

内置核心工具：

- `read_file`
- `write_file`
- `bash`
- `read_hermit_file`
- `write_hermit_file`
- `list_hermit_files`

其中只读工具会被 `readonly_only=True` 过滤，供 `/plan` 这类只读模式使用。

### [`hermit/plugin/manager.py`](../hermit/plugin/manager.py)

职责：

- 发现插件
- 加载 skills / rules / tools / commands / subagents / adapters / MCP
- 构建最终 system prompt
- 启停 MCP servers
- 注入 subagent delegation tools

它是插件体系的总装配层。

## Provider 层

当前 provider 选择来自 `Settings.provider`。

### `claude`

- 直接调用 Anthropic API
- 或走兼容 Claude 的自定义网关

### `codex`

- 通过 OpenAI Responses API
- 需要本地可用的 OpenAI API key

### `codex-oauth`

- 读取 `~/.codex/auth.json`
- 使用 access / refresh token

`build_provider()` 会根据 provider 类型决定是否允许启动；缺少所需鉴权时会直接报错。

## 插件模型

Hermit 插件由 `plugin.toml` 驱动。

当前真实支持并被使用的入口维度：

- `tools`
- `hooks`
- `commands`
- `subagents`
- `adapter`
- `mcp`

示例：

```toml
[plugin]
name = "my-plugin"
version = "0.1.0"
description = "Example plugin"

[entry]
tools = "tools:register"
hooks = "hooks:register"
commands = "commands:register"
subagents = "subagents:register"
adapter = "adapter:register"
mcp = "mcp:register"
```

发现顺序：

1. `hermit/builtin/`
2. `~/.hermit/plugins/`

## Plugin Context 与变量解析

每个插件加载时都会得到 `PluginContext`，可注册：

- hook
- tool
- command
- subagent
- adapter
- MCP server

插件变量的来源有三层：

1. `~/.hermit/config.toml` 的 `[plugins.<name>.variables]`
2. `Settings` 映射字段
3. 环境变量与 `plugin.toml` 默认值

模板渲染通过 `{{ variable_name }}` 完成。

## Hook 事件

当前有效事件：

- `SYSTEM_PROMPT`
- `REGISTER_TOOLS`
- `SESSION_START`
- `SESSION_END`
- `PRE_RUN`
- `POST_RUN`
- `SERVE_START`
- `SERVE_STOP`
- `DISPATCH_RESULT`

其中：

- `PRE_RUN` 可返回修改后的 prompt，也可返回控制参数，例如 `disable_tools`
- `DISPATCH_RESULT` 被 scheduler、webhook、reload 通知等复用

## Builtin 插件在架构中的位置

### `memory`

- `SYSTEM_PROMPT` 注入静态长期记忆
- `PRE_RUN` 注入与当前 prompt 相关的记忆
- `POST_RUN` 做轻量 checkpoint
- `SESSION_END` 做完整 settlement

### `image_memory`

- 存储图片资产
- 提取图片语义元数据
- 为多轮对话或飞书工作流注入近期图片上下文

### `orchestrator`

- 注册 researcher / coder 子 agent
- 对外暴露 `delegate_<name>` 工具

### `scheduler`

- 维护 `~/.hermit/schedules/jobs.json`
- `SERVE_START` 时启动后台调度线程
- 完成后触发 `DISPATCH_RESULT`

### `webhook`

- 暴露 HTTP webhook 能力
- 执行完 agent 后同样走 `DISPATCH_RESULT`

### `feishu`

- 提供 adapter
- 提供飞书工具与回执
- 监听 `DISPATCH_RESULT`，主动把结果推送回飞书

### `github` / `mcp-loader`

- 负责产生 MCP server 规格
- 真正的 server 启停由 `PluginManager` 统一处理

## Session 与状态模型

长期状态默认位于 `~/.hermit`：

```text
~/.hermit/
├── config.toml
├── context.md
├── memory/
├── image-memory/
├── sessions/
├── schedules/
├── skills/
├── rules/
├── plugins/
└── hooks/
```

几个关键文件：

- `memory/memories.md`
- `memory/session_state.json`
- `sessions/<session>.json`
- `sessions/archive/*.json`
- `schedules/jobs.json`
- `schedules/history.json`

## `serve` / `reload` / menu bar 的边界

`hermit serve --adapter feishu` 是后台 runtime 主进程。

`hermit reload --adapter feishu` 通过 `SIGHUP` 通知正在运行的服务：

1. 停 adapter
2. 重读配置
3. 重扫插件
4. 重建工具与 system prompt
5. 重启 adapter

macOS menu bar companion 不是插件，也不是 runtime 本体；它只是一个独立控制进程，负责：

- 查看当前运行状态
- 启停 / reload 服务
- 管理 `launchd` 自启
- 打开配置、日志和 base dir

## 当前代码审查中确认的架构事实

- runtime 已经是 provider-agnostic 的 `AgentRuntime`，旧文档里“ClaudeAgent”为中心的表述已经过时
- `profiles` / `auth` / `config show` 已经是正式 CLI 面，不应继续只在代码里存在
- desktop companion 已是独立模块 `hermit/companion/`
- `scheduler`、`webhook`、`reload` 通知统一走 `DISPATCH_RESULT`
