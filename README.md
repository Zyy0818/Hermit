# Hermit

Hermit 是一个面向个人工作流的本地优先 AI Agent runtime。它的核心不是一个庞大的平台层，而是三件事：

- 手写 Anthropic tool loop
- 文件化、可审计的持久状态
- manifest 驱动的插件体系

当前仓库已经覆盖的能力包括：

- CLI 对话与 one-shot 执行
- 跨 session 长期记忆
- 图片记忆与图片资产复用
- MCP Server 接入与 GitHub builtin MCP
- Feishu WebSocket 长连接 adapter
- 定时任务
- 子 agent 委派
- Web 搜索 / 页面抓取
- Webhook 事件触发
- macOS 开机自启

## 文档导航

- [`docs/architecture.md`](docs/architecture.md): 完整架构说明，讲清楚运行链路、模块边界、状态模型、插件设计
- [`docs/configuration.md`](docs/configuration.md): 配置、目录结构、MCP、Adapter、Scheduler、图片记忆等细节
- [`docs/openclaw-comparison.md`](docs/openclaw-comparison.md): Hermit 与 OpenClaw 的定位和架构比较
- [`AGENT.md`](AGENT.md): 面向协作开发者的仓库工作说明

## 设计目标

Hermit 更接近一个“可读、可改、可自托管的个人 agent runtime”，而不是一个大而全的平台。

核心取舍：

- 优先让核心链路足够简单，能直接从源码读懂
- 优先把复杂能力放到 builtin / external plugin，而不是堆进 core
- 优先使用文件持久化和原子写，而不是先引入数据库
- 优先支持个人环境、项目环境和消息通道之间的统一 agent runtime

## 一句话架构

```text
CLI / Adapter / Scheduler
          |
          v
    AgentRunner
          |
          +--> SessionManager
          +--> PluginManager
          |      +--> hooks / skills / rules / tools / commands / adapters / subagents / MCP
          |
          v
     ClaudeAgent
          |
          +--> ToolRegistry
          +--> Anthropic Messages API
```

对应的关键代码：

- [`hermit/core/agent.py`](hermit/core/agent.py): 手写 model loop、tool 调用、prompt cache、usage 统计
- [`hermit/core/runner.py`](hermit/core/runner.py): session 生命周期、命令分发、hook 编排
- [`hermit/plugin/manager.py`](hermit/plugin/manager.py): 插件发现、注册、system prompt 拼装、MCP 生命周期
- [`hermit/core/session.py`](hermit/core/session.py): session 持久化与归档
- [`hermit/storage/`](hermit/storage): 原子写、文件锁、JSON store

更完整的说明见 [`docs/architecture.md`](docs/architecture.md)。

## 快速开始

### 1. 安装

最简单的方式：

```bash
make
```

或者：

```bash
bash install.sh
```

安装脚本会做三件事：

1. 若系统没有 `uv`，自动安装
2. 将 `hermit` 作为全局命令安装
3. 读取当前 shell 中已有的 `ANTHROPIC_API_KEY`、`HERMIT_*`、`FEISHU_*` 等变量并写入 `~/.hermit/.env`

安装完成后可以直接运行：

```bash
hermit chat
```

### 2. 开发环境

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Python 要求：

- Python `>= 3.11`

### 3. 初始化

```bash
hermit init
```

这会创建默认的 `~/.hermit` 目录结构。

## CLI 概览

### 基础命令

| 命令 | 说明 |
| --- | --- |
| `hermit setup` | 交互式初始化和基础配置 |
| `hermit init` | 初始化 `~/.hermit` 目录结构 |
| `hermit startup-prompt` | 打印完整启动 system prompt |
| `hermit sessions` | 列出已保存的 session |

### 交互命令

| 命令 | 说明 |
| --- | --- |
| `hermit run "提示词"` | 单次执行 |
| `hermit chat` | 交互式会话 |

在 `chat` 中，内置 slash commands 包括：

- `/new`
- `/history`
- `/help`
- `/quit`

同时 builtin 插件还会扩展命令，例如 `compact`、`planner`、`usage`。

### 服务与通道

| 命令 | 说明 |
| --- | --- |
| `hermit serve --adapter feishu` | 启动 adapter 长连接服务 |
| `hermit reload --adapter feishu` | 热重载运行中的 adapter 进程 |

### 插件管理

| 命令 | 说明 |
| --- | --- |
| `hermit plugin list` | 查看已加载插件 |
| `hermit plugin install <git-url>` | 从 Git 仓库安装外部插件 |
| `hermit plugin remove <name>` | 删除外部插件 |
| `hermit plugin info <name>` | 查看插件详情 |

### macOS 自启

| 命令 | 说明 |
| --- | --- |
| `hermit autostart enable --adapter feishu` | 为指定 adapter 安装 launchd 自启 |
| `hermit autostart disable --adapter feishu` | 禁用指定 adapter 的自启 |
| `hermit autostart status` | 查看自启状态 |

### 定时任务

| 命令 | 说明 |
| --- | --- |
| `hermit schedule list` | 查看任务列表 |
| `hermit schedule add --name ... --prompt ... --cron ...` | 新增任务 |
| `hermit schedule add --name ... --prompt ... --once ...` | 新增一次性任务 |
| `hermit schedule add --name ... --prompt ... --interval ...` | 新增固定间隔任务 |
| `hermit schedule remove <id>` | 删除任务 |
| `hermit schedule enable <id>` | 启用任务 |
| `hermit schedule disable <id>` | 禁用任务 |
| `hermit schedule history` | 查看执行历史 |

## 当前 builtin 插件

仓库当前内置插件：

| 插件 | 维度 | 作用 |
| --- | --- | --- |
| `memory` | hooks | 长期记忆提取、衰减、合并、启动注入 |
| `image_memory` | hooks | 图片资产持久化、图片语义分析、图片检索 |
| `orchestrator` | hooks + subagents | researcher / coder 子 agent 委派 |
| `web-tools` | tools | DuckDuckGo Lite 搜索与页面抓取 |
| `grok` | tools | 基于 xAI Grok 的实时搜索 |
| `scheduler` | tools + hooks | 定时任务执行与结果广播 |
| `webhook` | tools + hooks | Webhook 路由、签名校验、事件驱动分发 |
| `github` | mcp | GitHub 官方 MCP builtin 接入 |
| `mcp-loader` | mcp | 解析 `~/.hermit/mcp.json` 与项目级 `.mcp.json` |
| `feishu` | adapter + hooks | 飞书长连接 adapter 与通道工具 |
| `compact` | commands | 会话压缩 |
| `planner` | commands | 规划模式 |
| `usage` | commands | token 统计 |

这套设计有一个很重要的特点：

- builtin 插件和外部插件使用同一套 `plugin.toml` 约定
- 功能尽量通过插件扩展，而不是在 core 中堆特殊分支

## 插件模型

Hermit 的扩展入口由 `plugin.toml` 驱动：

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

典型目录结构：

```text
my-plugin/
  plugin.toml
  tools.py
  hooks.py
  commands.py
  subagents.py
  adapter.py
  mcp.py
  skills/
    my-skill/
      SKILL.md
  rules/
    my-rule.md
```

Hermit 启动时会：

1. 扫描 `hermit/builtin/`
2. 扫描 `~/.hermit/plugins/`
3. 聚合工具、命令、hook、adapter、subagent、MCP server
4. 统一注册到 runtime

## MCP 集成

Hermit 兼容 Claude Code / Cursor 风格的 `.mcp.json`：

- `~/.hermit/mcp.json`: 全局配置
- `./.mcp.json`: 项目级配置，优先级更高

示例：

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-notion"],
      "env": {
        "NOTION_API_KEY": "your-key"
      }
    },
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer your-token"
      }
    }
  }
}
```

MCP 工具会自动以 `mcp__{server}__{tool}` 的形式注册到工具表中。

另外，Hermit 现在内置了 GitHub MCP：

- 默认 endpoint: `https://api.githubcopilot.com/mcp/`
- 支持通过 `GITHUB_MCP_URL` 覆盖
- 支持从 `GITHUB_PERSONAL_ACCESS_TOKEN`、`GITHUB_PAT`、`GITHUB_TOKEN` 读取认证

## 状态目录

Hermit 默认把自身状态放在 `~/.hermit`：

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

这套布局背后的原则是：

- 项目文件留在 workspace
- agent 自身状态留在 `~/.hermit`
- 尽量避免“项目配置”和“agent 长期记忆”混在一起

## 持久化原则

Hermit 不是“文件随便写”的项目。持久化层有明确约束：

- 文本写入优先走原子写
- 并发读写优先走 `FileGuard`
- JSON 状态优先走 `JsonStore`

对应代码在：

- [`hermit/storage/atomic.py`](hermit/storage/atomic.py)
- [`hermit/storage/lock.py`](hermit/storage/lock.py)
- [`hermit/storage/store.py`](hermit/storage/store.py)

这也是 Hermit 能继续保持文件化状态模型的前提。

## 部署模式

### 本地 CLI

```bash
hermit chat
```

### 飞书服务

```bash
cp .env.example .env
docker compose up -d
```

或本地直接：

```bash
hermit serve --adapter feishu
```

### 定时任务

```bash
hermit schedule add \
  --name "daily-summary" \
  --prompt "总结今天的 GitHub issue 和待办" \
  --cron "0 18 * * 1-5"
```

然后启动：

```bash
hermit serve --adapter feishu
```

## 与 OpenClaw 的关系

Hermit 和 OpenClaw 都属于本地优先 agent 体系，但重心不同：

- Hermit 更强调小核心、可读源码、文件化状态、repo 内可改
- OpenClaw 更强调大平台、多通道、控制平面、更多产品表面

如果你关心的是“这个仓库到底在架构上和 OpenClaw 差在哪”，请直接看：

- [`docs/openclaw-comparison.md`](docs/openclaw-comparison.md)

## 测试

开发环境下：

```bash
pytest
```

如果你用的是仓库内 venv：

```bash
.venv/bin/python -m pytest
```

## 当前最适合的使用场景

Hermit 目前最适合：

- 个人开发工作流
- 本地项目研究和改码
- 飞书驱动的个人 bot
- 需要长期记忆但不想引入复杂基础设施
- 希望沿着 MCP 和插件继续扩展能力

它现在还不是“所有渠道、所有 provider、所有设备”的大一统平台，但这恰好也是它当前最清晰的价值所在。
