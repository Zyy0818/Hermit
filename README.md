## Hermit

面向个人使用场景的轻量 AI Agent：手写 tool loop、跨会话记忆、飞书 bot 接入、插件生态。

## 安装（一行）

```bash
make
```

或者 `bash install.sh`。

脚本做三件事，**全程无交互**：
1. 若没有 [uv](https://github.com/astral-sh/uv) 则自动安装
2. 将 `hermit` 注册为全局命令（`uv tool install`）
3. **自动读取当前 shell 里已有的 env var**（`ANTHROPIC_API_KEY`、`HERMIT_*`、`FEISHU_*` 等）写入 `~/.hermit/.env`，无需手动填写

完成后直接运行：

```bash
hermit chat
```

> 如果 API Key 还没在 shell 里，安装结束时会打印一行提示，`echo 'ANTHROPIC_API_KEY=...' >> ~/.hermit/.env` 即可。

### 飞书 bot 服务端部署

```bash
cp .env.example .env   # 填入 ANTHROPIC_API_KEY + FEISHU 凭据
docker compose up -d
```

---

## CLI 命令

| 命令 | 说明 |
| --- | --- |
| `hermit setup` | 交互向导配置 API Key 并初始化工作区 |
| `hermit chat` | 交互式多轮对话（支持 `/quit` `/new` `/history`） |
| `hermit run "提示词"` | 单次 one-shot 对话 |
| `hermit serve --adapter feishu` | 启动飞书 bot 长连接服务 |
| `hermit init` | 仅初始化 `~/.hermit` 目录结构 |
| `hermit sessions` | 列出已存储的 session |
| `hermit startup-prompt` | 打印完整启动 system prompt |
| `hermit plugin list` | 列出已加载插件（内置 + 已安装） |
| `hermit plugin install <git-url>` | 从 Git 仓库安装外部插件 |
| `hermit plugin remove <name>` | 卸载外部插件 |
| `hermit plugin info <name>` | 查看插件详情 |

## 核心能力

- 手写 tool loop，完整控制 Claude 多轮交互
- 可衰减、可合并的本地长期记忆
- 跨 session 图片记忆：图片资产落盘、语义摘要、标签检索、飞书复用
- 8 维插件体系：Skills、Rules、Hooks、Tools、Subagents、MCP、Commands、Adapters
- 兼容 Claude Code / Cursor 的 `.mcp.json` MCP Server 配置
- 飞书长连接 Adapter（WebSocket 模式，无需公网域名）
- 受限自我配置工具，Agent 可安全读写 `~/.hermit`

## 目录结构

```text
hermit/
├── core/                   # Agent 核心：loop、工具注册、沙箱、会话、编排
│   ├── agent.py            # ClaudeAgent：tool loop 实现
│   ├── runner.py           # AgentRunner：session + plugin 编排层
│   ├── tools.py            # ToolSpec / ToolRegistry
│   ├── session.py          # SessionManager：会话持久化
│   ├── sandbox.py          # CommandSandbox：bash 执行沙箱
│   └── orchestrator.py     # 子 Agent 编排（已迁移至 builtin）
├── plugin/                 # 插件框架
│   ├── base.py             # 类型定义：HookEvent / PluginContext / McpServerSpec 等
│   ├── manager.py          # PluginManager：插件生命周期管理
│   ├── loader.py           # 插件发现与加载（plugin.toml 解析）
│   ├── hooks.py            # HooksEngine：事件总线
│   ├── mcp_client.py       # McpClientManager：MCP 连接/工具发现/调用路由
│   ├── rules.py            # Rules 加载
│   └── skills.py           # Skills 加载与渐进式披露
├── builtin/                # 内置插件（与外部插件格式完全相同）
│   ├── memory/             # 跨会话记忆：衰减/合并/持久化
│   ├── image_memory/       # 跨 session 图片资产与语义记忆
│   ├── orchestrator/       # 多 Agent 委派：researcher / coder 子 Agent
│   ├── web_tools/          # Web 搜索 + 网页抓取
│   ├── mcp_loader/         # MCP 配置加载（.mcp.json 解析）
│   └── feishu/             # 飞书消息 Adapter（WebSocket 长连接）
├── config.py               # Settings（pydantic-settings，HERMIT_ 前缀）
├── context.py              # 启动上下文构建
├── logging.py              # 日志配置
└── main.py                 # CLI 入口（typer）
```

## 插件系统

Hermit 使用基于 `plugin.toml` 清单的插件体系，支持 6 个维度扩展：

```toml
[plugin]
name = "my-plugin"
version = "1.0.0"
description = "示例插件"

[entry]
tools     = "tools:register"     # 注册工具
hooks     = "hooks:register"     # 注册生命周期钩子
subagents = "subagents:register" # 注册子 Agent
adapter   = "adapter:register"   # 注册消息通道 Adapter
mcp       = "mcp:register"       # 注册 MCP Server
```

外部插件安装到 `~/.hermit/plugins/<name>/`，通过 `hermit plugin install <git-url>` 一键安装。

## MCP Server 集成

兼容 Claude Code / Cursor 的 `.mcp.json` 配置格式，支持两个作用域：

- `~/.hermit/mcp.json` — 全局配置
- `./.mcp.json` — 项目级配置（优先级更高）

配置示例：

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-notion"],
      "env": { "NOTION_API_KEY": "your-key" }
    },
    "github": {
      "url": "https://mcp.github.com/sse",
      "headers": { "Authorization": "Bearer your-token" },
      "allowedTools": ["create_issue", "search_code"]
    }
  }
}
```

MCP 工具自动注册到 Agent，命名格式为 `mcp__{server}__{tool}`（如 `mcp__notion__search`）。

另外，Hermit 内置了 `github` 插件，会默认注册 GitHub 官方 MCP（可用 `GITHUB_MCP_URL` 覆盖 endpoint，并从 `GITHUB_PERSONAL_ACCESS_TOKEN` / `GITHUB_PAT` / `GITHUB_TOKEN` 读取认证）。

## 测试

```bash
pytest
```

## 图片记忆

- 图片资产默认保存在 `~/.hermit/image-memory/`
- 首次进入系统时立即生成 `summary`、`tags`、可选 `ocr_text`
- Agent 可通过 `image_search` / `image_get` 查询历史图片
- 在飞书回复中，可通过 `image_attach_to_feishu` 生成 `<feishu_image key='...'/>` 标签，并由飞书卡片渲染为原生图片组件

## 配置文档

详细配置说明见 [`docs/configuration.md`](docs/configuration.md)。
