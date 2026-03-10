# Hermit 架构说明

## 总览

Hermit 是一个本地优先、面向个人工作流的 AI Agent runtime。它的核心设计非常克制，只围绕三件事展开：

- 手写 Anthropic tool loop
- `~/.hermit` 下的文件化持久状态
- 基于 `plugin.toml` 的插件系统

这意味着 Hermit 不是一个“所有能力都堆进核心层”的项目。相反，核心尽量保持小而可读，能力增长尽量通过 builtin plugin 和 external plugin 向外扩展。

## 核心运行链路

```text
CLI / Adapter / Scheduler / Webhook
                 |
                 v
            AgentRunner
                 |
                 +--> SessionManager
                 +--> PluginManager
                 |      +--> hooks
                 |      +--> skills
                 |      +--> rules
                 |      +--> tools
                 |      +--> commands
                 |      +--> adapters
                 |      +--> subagents
                 |      +--> MCP specs
                 |
                 v
            ClaudeAgent
                 |
                 +--> ToolRegistry
                 +--> Anthropic Messages API
                 +--> 本地工具 / 插件工具 / MCP 工具
```

这张图就是理解整个仓库最重要的入口。

## 启动到执行的完整流程

### 1. 启动

启动主入口在 [`hermit/main.py`](../hermit/main.py)。

启动时会做这些事：

1. 加载 `Settings`
2. 确保 `~/.hermit` 和运行所需目录存在
3. 扫描 `hermit/builtin/` 下的内置插件
4. 扫描 `~/.hermit/plugins/` 下的外部插件
5. 构建基础 system prompt
6. 注册核心工具、插件工具、命令、subagent、adapter、MCP 工具

Hermit 的一个关键特征是：大部分“产品能力”并不直接写死在启动代码里，而是通过插件系统装配进 runtime。

### 2. 基础 Prompt 构建

基础 system prompt 在 [`hermit/context.py`](../hermit/context.py) 中构建。这里会注入：

- 当前工作目录
- Hermit 自身目录和关键文件路径
- 默认模型、token 上限、最大轮数、sandbox 模式
- 自我配置原则

随后 [`PluginManager.build_system_prompt()`](../hermit/plugin/manager.py) 会继续拼接：

- 插件 `rules/`
- skill catalog 或预加载 skill 内容
- 各个 `SYSTEM_PROMPT` hook 注入的动态片段

因此，Hermit 的 prompt 结构不是一整块硬编码字符串，而是一个可分层扩展的结构：

1. runtime 基础上下文
2. 规则
3. skill catalog / skill content
4. 动态插件片段

这让 Hermit 可以在不污染核心的前提下，增加记忆、图片、通道、MCP 等能力。

### 3. 请求分发

[`AgentRunner`](../hermit/core/runner.py) 是整个运行时的调度边界。

它统一承接：

- CLI 输入
- Adapter 进来的消息
- Scheduler 触发的 prompt
- 未来任何需要“像一次消息一样运行 agent”的入口

`dispatch()` 的逻辑很简单：

- 如果输入以 `/` 开头，按 slash command 处理
- 否则进入 `handle()`

`handle()` 负责：

1. 加载或创建 session
2. 首次进入活跃 session 时触发 `SESSION_START`
3. 执行 `PRE_RUN` hook，允许插件改写 prompt 或传入控制选项
4. 补一段 `<session_time>` 时间上下文
5. 调用 `ClaudeAgent.run(...)`
6. 持久化 session
7. 触发 `POST_RUN`

这意味着不同入口共享同一套 session 语义、hook 语义和 prompt 语义，而不是每个入口各写一套运行链路。

### 4. 模型循环

[`ClaudeAgent`](../hermit/core/agent.py) 是 Hermit 最核心的引擎。

它实现的是一个手写的 Anthropic Messages API tool loop：

1. 组装消息
2. 给可缓存的 prompt 区段打 cache 标记
3. 附带 thinking budget
4. 附带工具 schema
5. 调用 `client.messages.create(...)`
6. 规范化返回 block
7. 若 `stop_reason == "tool_use"`，执行工具并回填结果
8. 否则返回最终文本和 usage

这个文件的价值在于“显式”：

- prompt caching 是显式控制的
- thinking block 的处理是显式的
- tool output 截断是显式的
- API error 处理是显式的

这也是 Hermit 和很多“框架封装式 agent”最大的区别之一：你可以在一个文件里看清工具循环到底是怎么跑的。

## 核心模块职责

### `hermit/core/agent.py`

职责：

- 组装 Anthropic payload
- 控制 tool loop
- 回填 tool result
- 处理 prompt cache
- 统计 token usage
- 归一化 API 错误

### `hermit/core/runner.py`

职责：

- 统一请求分发
- 统一 session 生命周期
- 统一 slash command 入口
- 把 hook 系统串到 agent loop 前后

它是一个“运行时调度层”，而不是模型层本身。

### `hermit/core/session.py`

职责：

- 活跃 session 缓存
- session JSON 持久化
- idle timeout 判断
- session 归档

Hermit 使用文件而不是数据库保存 session，这让状态可读、可审计、可手工恢复。

### `hermit/plugin/manager.py`

职责：

- 发现和加载插件
- 聚合 tools / hooks / skills / rules / commands / adapters / subagents / MCP
- 注册运行期能力
- 构建最终 system prompt
- 管理 MCP 生命周期

可以把它理解成 Hermit 的“能力拼装层”。

### `hermit/plugin/hooks.py`

职责：

- 管理生命周期事件
- 按优先级触发 hook

当前关键事件包括：

- `SYSTEM_PROMPT`
- `REGISTER_TOOLS`
- `SESSION_START`
- `SESSION_END`
- `PRE_RUN`
- `POST_RUN`
- `SERVE_START`
- `SERVE_STOP`
- `SCHEDULE_RESULT`

Hook 是 Hermit 把“运行时事件”和“产品能力”解耦开的关键手段。

### `hermit/storage/*`

Hermit 虽然使用文件持久化，但并不是“随便写文件”。

这里的三个模块是持久化安全底座：

- [`atomic.py`](../hermit/storage/atomic.py): 原子写
- [`lock.py`](../hermit/storage/lock.py): 进程内锁 + 可选跨进程 `flock`
- [`store.py`](../hermit/storage/store.py): JSON store 封装

这套基础设施的存在，是 Hermit 能继续坚持文件化状态模型的重要前提。

## 插件架构

Hermit 的插件以 `plugin.toml` 为契约，当前已经使用的扩展维度包括：

- `tools`
- `hooks`
- `commands`
- `subagents`
- `adapter`
- `mcp`

最重要的架构特点不是“支持很多维度”，而是：

- builtin plugin 和 external plugin 使用同一套目录结构
- builtin feature 不是核心层里的特例，大多只是“内置插件”

这带来几个直接好处：

- 内置能力更容易理解
- 外部扩展不需要另一套 authoring model
- core 可以保持比较稳定

## 主要 builtin plugin 的角色

### `memory`

负责：

- 在 `SESSION_END` 提取长期记忆
- 给记忆打分、衰减、合并
- 启动时向 system prompt 注入 `<memory_context>`

它回答的是“没有数据库时，Hermit 如何保持跨 session 连续性”。

### `image_memory`

负责：

- 保存图片资产
- 生成图片摘要和标签
- 支持跨 session 的图片检索和复用
- 给 Feishu 图片工作流提供支撑

这不是单纯的“附件落盘”，而是一层多模态记忆。

### `orchestrator`

负责：

- 注册 specialized subagent
- 把委派能力暴露成工具

Hermit 的 subagent 不是另一套引擎，而是同样基于 `ClaudeAgent`，只是 tool scope 和 system prompt 更窄。

### `scheduler`

负责：

- 保存定时任务
- 支持 cron / once / interval
- 在执行后通过 `SCHEDULE_RESULT` 广播结果

它把 Hermit 从“响应式对话 runtime”扩展成了“轻量自动化 runtime”。

### `feishu`

负责：

- 把飞书事件桥接到 `AgentRunner`
- 处理通道相关格式、表情、图片等能力

Adapter 是通道层，不是 agent core。

### `web_tools`

负责：

- 提供轻量 Web 搜索
- 提供页面抓取

### `webhook`

负责：

- 提供 HTTP Webhook 入口
- 配置路由和签名校验
- 用事件驱动方式触发 agent

### `mcp_loader`

负责：

- 读取 `~/.hermit/mcp.json`
- 读取项目级 `.mcp.json`
- 将配置转换成 `McpServerSpec`
- 让 MCP 工具注册进统一工具表

### `github`

负责：

- 注册 GitHub 官方 MCP endpoint
- 将 GitHub 工作流纳入 Hermit 的 MCP 能力面

## 状态模型

Hermit 的持久状态主要放在 `~/.hermit`：

```text
~/.hermit/
├── .env
├── context.md
├── memory/
│   ├── memories.md
│   └── session_state.json
├── sessions/
│   └── archive/
├── image-memory/
├── plugins/
├── skills/
├── rules/
└── schedules/
```

这里有一个很重要的边界：

- workspace 是当前项目的状态
- `~/.hermit` 是 agent 自己的长期状态

这使 Hermit 的记忆、规则、skills、adapter 配置不会和某一个具体项目仓库硬绑定在一起。

## 为什么这个架构成立

Hermit 当前架构能工作的核心原因，是把三件事分开了：

1. core runtime 正确性
2. 产品能力扩展
3. agent 持久状态

所以演化路径也很清楚：

- 改进 tool loop，而不影响插件结构
- 新增能力，优先通过 builtin plugin
- 给用户扩展能力，复用同一套插件模型

## 主要权衡

### 优势

- 代码路径短，容易读全
- 几乎没有重框架锁定
- 状态是文件化、可审计的
- 插件边界清楚
- builtin / external 扩展模型一致

### 代价

- 平台面没有大型 agent 平台那么广
- 文件持久化必须非常重视锁和原子写
- 目前更偏个人 runtime，而不是多租户平台
- provider 抽象不是当前第一优先级

## 一句话定位

Hermit 是一个本地优先的个人 AI Agent runtime：核心只保留手写 Anthropic tool loop、session 和插件装配，长期记忆、图片记忆、MCP、Adapter、Scheduler、Subagent 等能力都通过统一插件模型向外扩展。
