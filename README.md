# Hermit

Hermit 是一个本地优先、文件状态优先的个人 AI Agent runtime。它不是一个厚平台，而是一个可直接读透源码、能长期运行、能挂接插件和外部通道的 Python runtime。

当前仓库已经落地的核心能力：

- CLI 单次执行与多轮会话
- `claude`、`codex`、`codex-oauth` 三种 provider 模式
- 文件化会话、长期记忆、图片记忆
- `plugin.toml` 驱动的 builtin / external 插件体系
- MCP server 装配与工具注册
- Feishu adapter
- scheduler / webhook / 子 agent 委派
- macOS `launchd` 自启
- macOS 菜单栏 companion

## 项目定位

Hermit 的取舍很明确：

- 核心链路短：CLI / adapter / webhook / scheduler 最终都汇到同一条 runner 链路
- 长期状态可审计：默认保存在 `~/.hermit`
- 插件是第一层扩展面：tools / hooks / commands / subagents / adapter / mcp
- 优先保留手写 runtime，而不是把行为藏进厚框架

如果你想要的是一个容易修改、容易加私有能力、容易排查状态的个人 agent runtime，这个仓库的结构是朝这个方向设计的。

## 文档导航

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/configuration.md`](docs/configuration.md)
- [`docs/providers-and-profiles.md`](docs/providers-and-profiles.md)
- [`docs/cli-and-operations.md`](docs/cli-and-operations.md)
- [`docs/desktop-companion.md`](docs/desktop-companion.md)
- [`docs/repository-layout.md`](docs/repository-layout.md)
- [`docs/i18n.md`](docs/i18n.md)
- [`docs/openclaw-comparison.md`](docs/openclaw-comparison.md)
- [`AGENT.md`](AGENT.md)

## 安装

要求：

- Python `>= 3.11`
- 推荐使用 `uv`
- macOS 菜单栏功能需要额外安装 `rumps`

最简单的安装方式：

```bash
make install
```

或：

```bash
bash install.sh
```

安装脚本会：

1. 安装 `uv`（如果不存在）
2. 以 `uv tool` 方式安装 Hermit
3. 初始化 `~/.hermit`
4. 自动把当前 shell 中已有的关键环境变量追加进 `~/.hermit/.env`
5. 在 macOS 上安装菜单栏 companion app bundle

开发环境：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

如果需要菜单栏 companion：

```bash
pip install -e ".[dev,macos]"
```

## 快速开始

初始化 workspace：

```bash
hermit init
```

交互式写入 `~/.hermit/.env`：

```bash
hermit setup
```

查看当前解析后的配置：

```bash
hermit config show
```

开始多轮聊天：

```bash
hermit chat
```

执行单次任务：

```bash
hermit run "总结当前仓库的插件系统"
```

以 Feishu adapter 进入长期运行模式：

```bash
hermit serve --adapter feishu
```

## Provider 模式

Hermit 当前源码支持三种 provider：

### 1. `claude`

默认模式。可直接使用 Anthropic API，也可走兼容 Claude 接口的 proxy / gateway。

常见变量：

- `ANTHROPIC_API_KEY` 或 `HERMIT_CLAUDE_API_KEY`
- `HERMIT_CLAUDE_AUTH_TOKEN` / `HERMIT_AUTH_TOKEN`
- `HERMIT_CLAUDE_BASE_URL` / `HERMIT_BASE_URL`
- `HERMIT_CLAUDE_HEADERS` / `HERMIT_CUSTOM_HEADERS`

### 2. `codex`

通过 OpenAI Responses API 运行，要求本地可用的 OpenAI API key。

常见变量：

- `HERMIT_PROVIDER=codex`
- `HERMIT_OPENAI_API_KEY` 或 `OPENAI_API_KEY`
- `HERMIT_OPENAI_BASE_URL`
- `HERMIT_OPENAI_HEADERS`

如果 `~/.codex/auth.json` 存在但不含本地 API key，Hermit 会明确报错，而不是静默回退。

### 3. `codex-oauth`

读取本机 `~/.codex/auth.json` 中的 access / refresh token，用 OAuth 方式调用。

常见场景：

- 本机已登录 Codex / ChatGPT 桌面体系
- 不想单独管理 OpenAI API key

更完整说明见 [`docs/providers-and-profiles.md`](docs/providers-and-profiles.md)。

## 配置方式

Hermit 不是单一 `.env` 项目，当前实现有三层来源：

1. 默认值
2. `~/.hermit/config.toml` 中的 profile
3. 当前目录 `.env`、`~/.hermit/.env`、shell 环境变量

实际行为上可以理解为：

- profile 负责定义“命名配置”
- `.env` 和 shell 负责覆盖 profile
- shell 变量优先级最高

常见命令：

```bash
hermit profiles list
hermit profiles resolve --name codex-local
hermit auth status
hermit config show
```

## CLI 概览

顶层命令：

- `hermit setup`
- `hermit init`
- `hermit startup-prompt`
- `hermit run "提示词"`
- `hermit chat`
- `hermit serve --adapter feishu`
- `hermit reload --adapter feishu`
- `hermit sessions`
- `hermit plugin ...`
- `hermit autostart ...`
- `hermit schedule ...`
- `hermit config show`
- `hermit profiles list`
- `hermit profiles resolve`
- `hermit auth status`

chat / serve 模式中的 core slash commands：

- `/new`
- `/history`
- `/help`
- `/quit`（仅 CLI）

当前 builtin 插件额外提供：

- `/compact`
- `/plan`
- `/usage`

更完整命令参考见 [`docs/cli-and-operations.md`](docs/cli-and-operations.md)。

## Builtin 插件

当前内置插件清单：

| 插件 | 入口维度 | 主要作用 |
| --- | --- | --- |
| `memory` | `hooks` | 长期记忆抽取、检索、衰减、合并 |
| `image_memory` | `hooks` | 图片资产与图片语义记忆 |
| `orchestrator` | `hooks`, `subagents` | researcher / coder 子 agent 委派 |
| `web-tools` | `tools` | Web 搜索与页面抓取 |
| `grok` | `tools` | Grok 实时搜索 |
| `computer_use` | `tools` | macOS screenshot / 鼠标 / 键盘控制 |
| `scheduler` | `tools`, `hooks` | 定时任务与结果广播 |
| `webhook` | `tools`, `hooks` | Webhook 路由与 agent 触发 |
| `github` | `mcp` | GitHub MCP 集成 |
| `mcp-loader` | `mcp` | 从 `mcp.json` / `.mcp.json` 加载 MCP server |
| `feishu` | `adapter`, `hooks` | 飞书 adapter、回执与工具 |
| `compact` | `commands` | 会话压缩 |
| `planner` | `commands` | 只读规划模式 |
| `usage` | `commands` | token 用量统计 |

## 状态目录

默认目录是 `~/.hermit`：

```text
~/.hermit/
├── .env
├── config.toml
├── context.md
├── hooks/
├── image-memory/
├── logs/
├── memory/
│   ├── memories.md
│   └── session_state.json
├── plugins/
├── rules/
├── schedules/
│   ├── history.json
│   └── jobs.json
├── sessions/
│   └── archive/
└── skills/
```

补充说明：

- `config.toml` 不会由 `hermit init` 自动生成，但菜单栏 companion 打开配置时会自动补默认模板
- `logs/` 主要由 menu bar companion 启动服务时写入
- `serve-<adapter>.pid` 在 `hermit serve` 运行期间写在根目录
- `plans/` 只有 `/plan` 首次落盘后才会出现

## 调试与验证

运行测试：

```bash
uv run pytest -q
```

查看启动前环境自检：

```bash
hermit serve --adapter feishu
```

查看最终 system prompt：

```bash
hermit startup-prompt
```

查看当前 session 列表：

```bash
hermit sessions
```

## Docker

仓库自带：

- [`Dockerfile`](Dockerfile)
- [`docker-compose.yml`](docker-compose.yml)

compose 示例当前以长期运行的 Feishu adapter 为目标，等价命令是：

```bash
hermit serve --adapter feishu
```

## 代码审查结论

这轮检查里，运行基线是通过的：

- `uv run pytest -q`
- 结果：`332 passed`

审查中确认的需要修正项已经同步到仓库：

- 文档长期滞后于源码，尤其是 provider / profile / config / companion / CLI 子命令
- `docker-compose.yml` 使用了过期的 `serve feishu` 调用方式
- `install.sh` 的最终提示里也保留了过期的 `hermit serve feishu` 示例

## 许可

MIT
