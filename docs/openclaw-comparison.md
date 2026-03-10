# Hermit 与 OpenClaw 的比较

## 这份文档的目的

这不是一份“谁更强”的结论文档，而是一份定位文档。它要回答的问题是：

- Hermit 在架构上到底是什么
- 它和 OpenClaw 的重心差在哪里
- 如果继续演进，Hermit 应该向 OpenClaw 学什么，又不该盲目复制什么

OpenClaw 相关描述基于 2026-03-10 能访问到的公开资料：

- [OpenClaw 官网](https://openclaw.ai/)
- [OpenClaw 公开落地页](https://openclaws.io/)
- [OpenClaw GitHub 仓库](https://github.com/openclaw/openclaw)
- [OpenClaw FAQ](https://docs.openclaw.ai/help/faq)

## 一段话总结

Hermit 和 OpenClaw 都属于本地优先 agent 体系，但它们的优化目标并不一样：

- Hermit 优先优化“小而清晰、可读、可改”的 runtime
- OpenClaw 优先优化“更广的平台能力面、更多通道、更多控制面”

如果只说最短结论：

- 选 Hermit，是因为你想要一个自己能读懂、能改、能持续演化的本地 agent runtime
- 选 OpenClaw，是因为你想直接获得一个更大、更完整、更多通道和控制面的 assistant platform

## 产品哲学差异

### Hermit

Hermit 的中心不是“平台”，而是“runtime”。

它的结构非常克制：

- 一个手写的 Anthropic tool loop
- 一个统一的插件系统
- 一个 `~/.hermit` 状态目录
- 一批围绕个人工作流的 builtin plugin

这意味着 Hermit 的很多价值来自“源码可理解性”。

### OpenClaw

从公开资料看，OpenClaw 的中心更接近“平台”：

- 多聊天通道
- Gateway WebSocket 控制面
- Web 和 app 表面
- 浏览器控制 / Canvas / A2UI 一类交互表面
- 远程访问和更多操作面
- 多模型提供方，包含本地模型

这是一种明显更大的产品目标。

## 架构中心差异

### Hermit：runtime-first

Hermit 的主链路很直接：

`AgentRunner -> ClaudeAgent -> ToolRegistry -> 本地工具 / 插件工具 / MCP`

最关键的实现文件只有几处：

- [`hermit/core/runner.py`](../hermit/core/runner.py)
- [`hermit/core/agent.py`](../hermit/core/agent.py)
- [`hermit/plugin/manager.py`](../hermit/plugin/manager.py)

Hermit 目前没有额外抽象出一个庞大的控制平面。它更像一个“单机可组合 runtime”。

### OpenClaw：platform-first

OpenClaw 的公开描述明显强调 Gateway 和多 surface 结构。也就是说，它更像一个带控制面的 assistant platform，而不是一个单纯的本地 agent loop。

这种架构的优点是：

- 平台能力面更广
- 可接入的终端更多
- 控制 UI 和通道层更强

代价也很明显：

- 运行面更复杂
- 组件更多
- 理解成本更高

这其实就是两者最大的结构性差异。

## 状态模型差异

### Hermit

Hermit 把 agent 自己的长期状态放在 `~/.hermit`：

- `.env`
- `context.md`
- `memory/memories.md`
- `sessions/`
- `plugins/`
- `skills/`
- `rules/`
- `image-memory/`
- `schedules/`

当前项目 workspace 仍然只是“任务工作区”，不是 agent 自身的长期家目录。

### OpenClaw

根据 OpenClaw FAQ，`~/.openclaw` 用于保存配置、凭据、session、日志和共享 skills，而像 `AGENTS.md`、`SOUL.md`、`USER.md`、`MEMORY.md` 这类文件则更深地参与 workspace 级 prompt / memory 结构。

这带来的差别是：

- Hermit 更强调“agent 状态”和“项目状态”分离
- OpenClaw 更强调 workspace 内 agent 文件本身就是核心运行面的一部分

对个人 coding/runtime 场景来说，Hermit 的分离方式更简单。对多 workspace、复杂人格和工作区 agent 文件体系来说，OpenClaw 的做法更灵活。

## 扩展模型差异

### Hermit

Hermit 的扩展模型比较紧凑，核心是 `plugin.toml`。

当前实际使用的维度包括：

- `tools`
- `hooks`
- `commands`
- `subagents`
- `adapter`
- `mcp`

并且 builtin plugin 和 external plugin 的目录结构完全一致。

这个设计的优点是：

- 扩展方式容易学
- 内置功能不容易变成特殊分支
- 外部插件和内置插件的心智模型一致

### OpenClaw

OpenClaw 从公开资料看更强调一个更大的 skills / integrations 生态。它的能力面更宽，但生态运行在一个更复杂的平台结构里，而不是一个非常小的本地 runtime 里。

因此可以很直接地概括成：

- Hermit 的扩展模型更小、更容易内化
- OpenClaw 的生态更大，但平台复杂度也更高

## 通道策略差异

### Hermit

Hermit 当前仓库里真实存在的 surface 比较克制：

- CLI
- Feishu
- 定时任务
- Webhook 触发
- MCP 接外部系统

它并没有尝试覆盖所有聊天通道。

### OpenClaw

OpenClaw 的公开资料则明确强调更广的通道能力，例如 WhatsApp、Telegram、Slack、Discord、Signal、iMessage、Feishu、Matrix 等，以及 Web / app 端表面。

如果需求是“一个 assistant 打通很多终端入口”，OpenClaw 当前显然更有平台优势。

## 模型策略差异

### Hermit

Hermit 当前是围绕 Anthropic Messages API 设计的。它的 prompt cache、thinking budget、tool loop 结构都直接围绕这套接口展开。

好处是实现非常一致，逻辑也清楚。

代价是 provider abstraction 不是当前第一中心。

### OpenClaw

OpenClaw 的公开定位更偏 model-agnostic，支持托管 API，也支持本地模型和兼容 OpenAI API 的本地端点。

如果“多 provider / 本地模型兼容”是硬要求，OpenClaw 当前公开能力面更广。

## 记忆策略差异

### Hermit

Hermit 的记忆是很明确的一套文件化模型：

- `memory` plugin 在 session 结束时抽取长期记忆
- 记忆条目带 score，会衰减、合并、再注入
- `image_memory` 增加多模态记忆层

优点是清晰、可审计、可手工修复。

### OpenClaw

OpenClaw 同样强调 persistent memory，但从公开资料看，它把更大的 workspace 文件表面和 `~/.openclaw` 下的状态共同用作记忆和行为面。

因此两者更像两种不同方向：

- Hermit：更小、更显式、更文件化
- OpenClaw：更广、更丰富、更平台化

## 运维复杂度差异

### Hermit

Hermit 更接近：

- 一个 runtime
- 一个状态目录
- 一套 manifest 插件体系

因此它的调试路径相对短：

- prompt 怎么拼的，源码可追
- 工具怎么注册的，源码可追
- session 存哪里，文件可看
- 插件怎么装配的，源码可追

### OpenClaw

OpenClaw 的平台能力面更大，所以通常也意味着更多运维层面：

- Gateway
- dashboard / control UI
- app surface
- 更多 channel
- 更多环境相关配置

这些并不是坏事，但它们是真实的复杂度。

## Hermit 应该向 OpenClaw 学什么

OpenClaw 比较值得学习的地方包括：

- 多通道广度
- 控制面和可视化操作面
- provider 灵活性
- 更成熟的生态包装
- 不同终端表面的产品化能力

如果 Hermit 继续往外长，这些方向都值得研究。

## Hermit 不应该盲目复制什么

Hermit 的优势并不是“做一个更小的 OpenClaw”。

Hermit 当前最有价值的地方恰恰是：

- 核心链路短
- 源码可读
- 状态模型清楚
- 插件边界明确
- 面向个人 runtime，而不是大平台

如果过早追求 OpenClaw 那样的平台广度，Hermit 反而可能失去现在最有辨识度的优点。

## 建议对外表述

如果要用一段话来描述 Hermit 和 OpenClaw 的差异，可以这样说：

Hermit 是一个本地优先、面向个人工作流的 AI Agent runtime。它的重点是一个小而可理解的核心：手写 Anthropic tool loop、`~/.hermit` 下的文件化持久状态，以及围绕 memory、MCP、adapter、scheduler、subagent 向外扩展的统一插件体系。和 OpenClaw 相比，Hermit 在通道和平台广度上更克制，但在可读性、可维护性和单仓库可演化性上更直接。
