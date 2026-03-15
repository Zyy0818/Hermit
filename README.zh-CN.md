# Hermit

[English](./README.md) | [简体中文](./README.zh-CN.md)

[![CI](https://github.com/heggria/Hermit/actions/workflows/ci.yml/badge.svg)](https://github.com/heggria/Hermit/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-black)](./LICENSE)
[![Docs](https://img.shields.io/badge/docs-github%20pages-0F172A)](https://heggria.github.io/Hermit/)

> **Hermit 是一个本地优先、带治理能力的 Agent Kernel。**
>
> 它面向持久任务、受限执行、artifact 原生上下文、证据绑定记忆，以及那些不能只靠工具日志就草草收尾的重要动作。

Hermit 提供的不是“会聊天的工具壳”，而是一条更可控的执行路径：

- 关键动作先走审批
- 执行完成后留下 receipt 和 proof summary
- 对已支持的 receipt class 提供 rollback-aware recovery

如果你想要的是一个可以本地运行、可以中断、可以审批、可以审计、也可以追溯恢复的 Agent，Hermit 的价值就在这里。

文档站点：[heggria.github.io/Hermit](https://heggria.github.io/Hermit/)

## 一眼就能看出的差异

```mermaid
flowchart TB
    A["关键动作先审批"] --> B["执行后留下 receipt 和 proof"]
    B --> C["支持 rollback-aware recovery"]
    C --> D["artifact 原生上下文与受治理记忆"]

    style A fill:#f5efe6,stroke:#a35f3f,color:#1f1b17,stroke-width:2px
    style B fill:#f7f1e8,stroke:#a17a28,color:#1f1b17,stroke-width:2px
    style C fill:#eef2e7,stroke:#5d7a46,color:#1f1b17,stroke-width:2px
    style D fill:#efe9f6,stroke:#75608f,color:#1f1b17,stroke-width:2px
```

## 一条命令安装

仅限 macOS：

```bash
curl -fsSL https://raw.githubusercontent.com/heggria/Hermit/main/install-macos.sh | bash
```

这个安装脚本会完成这些事：

- 安装 Hermit
- 初始化 `~/.hermit`
- 安装可选的 macOS 菜单栏伴侣
- 尝试保留你当前 shell 里已有的 provider 凭据

它还会在 Hermit 自己还没有这些值时，尽量同步兼容来源里的配置：

- Claude Code：从 `~/.claude/settings.json` 的 `env` 中导入兼容字段
- Codex：直接复用 `~/.codex/auth.json` 作为 `codex-oauth`，并从 `~/.codex/config.toml` 读取模型
- OpenClaw：从 `~/.openclaw/openclaw.json` 导入 Feishu 凭据和默认模型提示

它不会覆盖现有的 `~/.hermit/.env`，也不会把 OpenClaw 的 OAuth token 自动改写成 `~/.codex/auth.json`。

## 一眼看懂 Hermit

Hermit 最容易理解的方式，是看一个任务如何变成“可检查的记录”，而不是执行完就消失在工具日志里。

```bash
hermit run "Summarize the current repository and leave a durable task record"
hermit task list
hermit task show <task_id>
hermit task proof <task_id>
hermit task receipts --task-id <task_id>
```

如果这个任务产出了可回滚的 receipt：

```bash
hermit task rollback <receipt_id>
```

Hermit 关心的不只是“模型把事情做了”，而是“事情做完之后，你还能看见什么、确认什么、恢复什么”。

如果你想录屏或做展示，先看 [docs/demo-flows.md](./docs/demo-flows.md)。

下面这张图使用仓库内真实生成的 CLI 输出：

![Hermit task show、proof 与 rollback 示例](./docs/site/assets/task-proof-rollback-demo.png)

而 Hermit 真正特别的地方，不只是能把任务跑完，而是这条受治理的执行闭环：

```mermaid
flowchart LR
    A["CLI / Chat / Feishu / Scheduler / Webhook"] --> B["Task -> Step -> StepAttempt"]
    B --> C["Policy + Approval + Scoped authority"]
    C --> D["工具执行"]
    D --> E["Receipt + Proof"]
    E --> F["支持时可回滚"]

    style A fill:#f5efe6,stroke:#a35f3f,color:#1f1b17,stroke-width:2px
    style B fill:#fbf8f2,stroke:#c9b8a4,color:#1f1b17,stroke-width:2px
    style C fill:#f8ecdf,stroke:#c98c69,color:#1f1b17,stroke-width:2px
    style D fill:#fbf8f2,stroke:#c9b8a4,color:#1f1b17,stroke-width:2px
    style E fill:#fbf8f2,stroke:#c9b8a4,color:#1f1b17,stroke-width:2px
    style F fill:#eef2e7,stroke:#5d7a46,color:#1f1b17,stroke-width:2px
```

## 为什么它值得点 Star

- 它把工作当成持久任务，而不是一次性聊天回合
- 它在模型和副作用之间放入 policy、approval 和 scoped authority
- 它用 receipt 和 proof 来收尾，而不是模糊的工具调用日志
- 它把本地状态、artifact 和 memory 留在可检查的表面上

## Hermit 的核心思路

大多数 Agent 系统追求的是“此刻足够有帮助”。Hermit 更在意的是“过后依然看得清楚”。

很多系统把执行理解成“模型调用了工具”。Hermit 更强调这条受治理的路径：

`task -> step -> step attempt -> policy -> approval -> scoped authority -> execution -> receipt -> proof / rollback`

重点不只是把工具调起来，而是让长期工作变得可检查、可控制、可追溯。

### 核心概念

- **Task-first kernel**
  Hermit 不是 session-first。CLI、chat、scheduler、webhook、adapter 都在收敛到统一的 task / step / step-attempt 语义上。

- **Governed execution**
  模型提出动作，kernel 决定这个动作是否允许、是否需要审批、以及能拿到什么权限边界。

- **Receipts, proofs, rollback**
  工具执行不是终点。重要动作会留下 receipt，proof summary 和 proof bundle 让链路可检查；部分 receipt class 支持 rollback。

- **Artifact-native context**
  上下文不只是 transcript。Hermit 会把 artifact、working state、belief、memory record 和 task state 一起编排进上下文。

- **Evidence-bound memory**
  Memory 不是随手贴便签。持久记忆的提升、保留、失效和覆盖，都应该和证据、作用域、生命周期绑定。

- **Local-first operator trust**
  运行时尽量离操作者更近：本地状态、可见 artifact、可检查 ledger、审批界面和恢复路径都尽量留在本地。

## 当前已经有什么

Hermit 还很早，但已经不是“只有想法”的阶段。

仓库当前已经有：

- 一套真正的 kernel ledger，对 `Task`、`Step`、`StepAttempt`、`Approval`、`Decision`、`ExecutionPermit`、`PathGrant`、`Artifact`、`Receipt`、`Belief`、`MemoryRecord`、`Rollback`、`Conversation`、`Ingress` 等对象进行持久化
- 基于事件的 task history 和 hash-chained verification primitives
- 带 policy evaluation、approval handling、scoped permit 的 governed tool execution
- receipt issuance、proof summary、proof export，以及对已支持 receipt 的 rollback
- CLI、长运行 `serve`、scheduler、webhook、Feishu ingress 等本地运行表面

当前状态需要说得直接一些：

- **Core** 已经接近一个可以公开 claim 的 alpha kernel
- **Governed execution** 在代码里已经是可见的，不只是概念
- **Verifiable execution** 有了强基础，但还不该被表述成“已经完全完成”
- **`v0.1` kernel spec** 代表目标架构，不代表所有表面都已经迁移完成

## 快速开始

如果你只是想最快评估，先跑上面的 demo 流程；如果想完整配置 provider、审批、proof export 和 rollback，再继续看 [docs/getting-started.md](./docs/getting-started.md)。

### 运行要求

- Python `3.11+`
- 推荐使用 [`uv`](https://docs.astral.sh/uv/)
- 如果要用 macOS 菜单栏伴侣，需要 `rumps`

### 安装

```bash
make install
```

或者手动安装：

```bash
uv sync
uv run hermit init
```

### 首次运行

交互式对话：

```bash
hermit chat
```

一次性任务：

```bash
hermit run "Summarize the current repository"
```

启动长运行服务：

```bash
hermit serve --adapter feishu
```

查看当前配置：

```bash
hermit config show
hermit auth status
```

### 常用 Kernel 检查命令

```bash
hermit task list
hermit task show <task_id>
hermit task events <task_id>
hermit task receipts --task-id <task_id>
hermit task proof <task_id>
hermit task proof-export <task_id>
hermit task approve <approval_id>
hermit task rollback <receipt_id>
```

这些命令的意义在于：任务不会在工具执行结束时消失，而会留下可以继续检查的结果表面。

## 文档入口

如果你想先理解“它为什么和一般 agent runtime 不一样”，建议先看这张总览图：

```mermaid
flowchart TB
    subgraph S["运行表面"]
        A["CLI"]
        B["Chat"]
        C["Feishu"]
        D["Scheduler"]
        E["Webhook"]
    end

    S --> K["Task kernel"]
    K --> T["Task controller"]
    K --> X["Context compiler"]
    K --> P["Policy engine"]
    K --> R["Execution layer"]
    R --> L["Ledger + Projections + Receipts + Proof + Rollback + Memory"]

    style K fill:#f8ecdf,stroke:#c98c69,color:#1f1b17,stroke-width:2px
    style T fill:#fbf8f2,stroke:#c9b8a4,color:#1f1b17
    style X fill:#fbf8f2,stroke:#c9b8a4,color:#1f1b17
    style P fill:#fbf8f2,stroke:#c9b8a4,color:#1f1b17
    style R fill:#fbf8f2,stroke:#c9b8a4,color:#1f1b17
    style L fill:#f5efe6,stroke:#a35f3f,color:#1f1b17,stroke-width:2px
```

推荐从这里开始：

- [docs/getting-started.md](./docs/getting-started.md)
- [docs/demo-flows.md](./docs/demo-flows.md)
- [docs/why-hermit.md](./docs/why-hermit.md)
- [docs/architecture.md](./docs/architecture.md)
- [docs/governance.md](./docs/governance.md)
- [docs/receipts-and-proofs.md](./docs/receipts-and-proofs.md)
- [docs/roadmap.md](./docs/roadmap.md)

目前更深的 `docs/` 文档仍以英文为主；这个中文 README 负责提供一个完整的中文入口页。

## 许可证

[MIT](./LICENSE)
