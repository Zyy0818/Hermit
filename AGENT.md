# AGENT.md

Hermit 项目的 AI 辅助开发指南。

---

## 项目概述

Hermit 是面向个人使用场景的轻量 AI Agent，基于 Anthropic Messages API 手写 tool loop。

核心特性：
- 手写 tool loop，完整控制 Claude 多轮交互
- 跨会话长期记忆（衰减 + 合并 + 持久化）
- 跨 session 图片记忆（语义摘要 + 标签检索）
- 6 维插件体系：Skills、Rules、Hooks、Tools、Subagents、MCP
- 兼容 Claude Code / Cursor `.mcp.json` MCP Server 配置格式
- 飞书长连接 Adapter（WebSocket，无需公网域名）
- macOS 防睡眠（`caffeinate -i`）+ 开机自启（`launchd`）

---

## 开发环境

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"          # 含测试依赖
pip install -e ".[feishu]"       # 飞书 Adapter 可选依赖
```

运行测试：

```bash
pytest
```

**Python >= 3.11 强制要求**（`pyproject.toml` 中 `requires-python = ">=3.11"`）。

---

## 目录结构

```
hermit/
├── core/               # Agent 核心
│   ├── agent.py        # ClaudeAgent：tool loop 实现（481 行）
│   ├── runner.py       # AgentRunner：session + plugin 编排层
│   ├── tools.py        # ToolSpec / ToolRegistry + 内置工具注册
│   ├── session.py      # SessionManager：会话持久化（JSONL）
│   ├── sandbox.py      # CommandSandbox：bash 执行沙箱（l0/l1）
│   └── orchestrator.py # 子 Agent 编排入口（已迁移至 builtin）
├── plugin/             # 插件框架
│   ├── base.py         # 类型定义：HookEvent / PluginContext / McpServerSpec 等
│   ├── manager.py      # PluginManager：插件生命周期管理（309 行）
│   ├── loader.py       # 插件发现与加载（plugin.toml 解析）
│   ├── hooks.py        # HooksEngine：事件总线（priority 排序 + fire/fire_first）
│   ├── mcp_client.py   # McpClientManager：MCP 连接 / 工具发现 / 调用路由
│   ├── rules.py        # Rules 加载
│   └── skills.py       # Skills 加载（渐进式披露：catalog → on-demand 读取）
├── builtin/            # 内置插件（与外部插件完全相同格式）
│   ├── memory/         # 跨会话记忆（engine.py + hooks.py + types.py）
│   ├── image_memory/   # 图片资产与语义记忆
│   ├── orchestrator/   # 多 Agent 委派（researcher / coder 子 Agent）
│   ├── web_tools/      # DuckDuckGo 搜索 + 网页抓取（零外部依赖）
│   ├── grok/           # xAI Grok 实时搜索（需 XAI_API_KEY）
│   ├── scheduler/      # 定时任务（cron/once/interval + SCHEDULE_RESULT 广播）
│   ├── mcp_loader/     # MCP 配置加载（.mcp.json 解析）
│   └── feishu/         # 飞书消息 Adapter（WebSocket 长连接）
├── storage/            # 持久化原语
│   ├── atomic.py       # atomic_write()：tempfile + os.replace() 原子写
│   ├── lock.py         # FileGuard：threading.RLock + fcntl.flock 两层锁
│   └── store.py        # JsonStore：带 FileGuard 的 JSON 读写封装
├── config.py           # Settings（pydantic-settings，HERMIT_ 前缀）
├── context.py          # 启动 system prompt 构建
├── logging.py          # structlog 日志配置
├── autostart.py        # macOS launchd 开机自启管理
└── main.py             # CLI 入口（typer）：run / chat / serve / plugin / autostart
```

---

## CLI 命令

| 命令 | 说明 |
| --- | --- |
| `hermit init` | 初始化 `~/.hermit` 目录结构 |
| `hermit run "提示词"` | 单次 one-shot 对话 |
| `hermit chat` | 交互式多轮对话（支持 `/quit` `/new` `/history`） |
| `hermit serve --adapter feishu` | 启动长连接服务 |
| `hermit sessions` | 列出已存储的 session |
| `hermit startup-prompt` | 打印完整启动 system prompt |
| `hermit plugin list` | 列出已加载插件（内置 + 已安装） |
| `hermit plugin install <git-url>` | 从 Git 仓库安装外部插件 |
| `hermit plugin remove <name>` | 卸载外部插件 |
| `hermit plugin info <name>` | 查看插件详情 |
| `hermit autostart enable` | 启用 macOS 开机自启（launchd） |
| `hermit autostart disable` | 禁用开机自启 |
| `hermit autostart status` | 查看自启状态 |
| `hermit schedule list` | 列出所有定时任务 |
| `hermit schedule add --name "..." --cron "..." --prompt "..."` | 添加定时任务（支持 --cron/--once/--interval） |
| `hermit schedule remove <id>` | 删除定时任务 |
| `hermit schedule enable/disable <id>` | 启用/禁用定时任务 |
| `hermit schedule history` | 查看执行历史 |

---

## 关键配置项

环境变量全部使用 `HERMIT_` 前缀，`ANTHROPIC_API_KEY` 例外。

配置加载优先级（低 → 高）：代码默认值 → `.env` → `~/.hermit/.env` → shell 环境变量。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | 无 | Claude API Key |
| `HERMIT_AUTH_TOKEN` | 无 | Bearer Token（代理网关模式） |
| `HERMIT_BASE_URL` | 无 | 自定义 Anthropic 兼容网关地址 |
| `HERMIT_CUSTOM_HEADERS` | 无 | 额外请求头，格式：`Key: Value, Key2: Value2` |
| `HERMIT_MODEL` | `claude-3-7-sonnet-latest` | 默认模型 |
| `HERMIT_IMAGE_MODEL` | 空 | 图片分析模型，未设置时回退主模型 |
| `HERMIT_MAX_TOKENS` | `2048` | 单次 max_tokens |
| `HERMIT_THINKING_BUDGET` | `0` | Extended Thinking token 预算，0 为关闭 |
| `HERMIT_MAX_TURNS` | `100` | 单次 agent loop 最大轮数 |
| `HERMIT_TOOL_OUTPUT_LIMIT` | `4000` | 工具输出截断字符数 |
| `HERMIT_SANDBOX_MODE` | `l0` | `l0`（无沙箱） / `l1`（受限执行） |
| `HERMIT_COMMAND_TIMEOUT_SECONDS` | `30` | bash 工具超时（秒） |
| `HERMIT_SESSION_IDLE_TIMEOUT_SECONDS` | `1800` | session 空闲超时（秒） |
| `HERMIT_BASE_DIR` | `~/.hermit` | 配置根目录 |
| `HERMIT_PREVENT_SLEEP` | `true` | macOS 防深度睡眠 |
| `HERMIT_SCHEDULER_ENABLED` | `true` | 定时任务总开关 |
| `HERMIT_SCHEDULER_CATCH_UP` | `true` | 启动时补执行错过的任务 |
| `HERMIT_SCHEDULER_FEISHU_CHAT_ID` | 无 | 飞书推送目标 chat_id |
| `XAI_API_KEY` | 无 | xAI Grok 插件必需 |

---

## 插件系统

### 插件目录结构规范

内置与自定义插件使用完全相同的目录格式：

```
<plugin-name>/
  plugin.toml                 # [必需] 插件清单
  tools.py                    # [按需] entry.tools = "tools:register"
  commands.py                 # [按需] entry.commands = "commands:register"
  hooks.py                    # [按需] entry.hooks = "hooks:register"
  mcp.py                      # [按需] entry.mcp = "mcp:register"
  adapter.py                  # [按需] entry.adapter = "adapter:register"
  subagents.py                # [按需] entry.subagents = "subagents:register"
  skills/                     # [可选] Agent 技能文档
    <skill-name>/
      SKILL.md                # YAML frontmatter（name/description）+ Markdown 正文
  rules/                      # [可选] 静态规则，启动时注入 system prompt
    <rule-name>.md
```

关键约定：
- `[entry]` 中每个 value 格式必须是 `module:function`（带冒号，不能省略函数名）
- 内置插件声明 `builtin = true`；自定义插件省略或设为 `false`，其余格式完全一致
- 模块名与维度约定对应：tools / commands / hooks / mcp / adapter / subagents
- `SKILL.md` 使用 YAML frontmatter 声明 `name` 和 `description`，供渐进式披露

### 插件发现路径

1. `hermit/builtin/` — 内置插件
2. `~/.hermit/plugins/` — 用户安装的外部插件

### plugin.toml 格式

```toml
[plugin]
name = "my-plugin"
version = "1.0.0"
description = "示例插件"
author = "Author"

[entry]
tools     = "tools:register"     # 注册工具
hooks     = "hooks:register"     # 注册生命周期钩子
subagents = "subagents:register" # 注册子 Agent
adapter   = "adapter:register"   # 注册消息 Adapter
mcp       = "mcp:register"       # 注册 MCP Server
commands  = "commands:register"  # 注册斜杠命令
```

### 注册工具示例

```python
from hermit.core.tools import ToolSpec
from hermit.plugin.base import PluginContext

def register(ctx: PluginContext) -> None:
    ctx.add_tool(ToolSpec(
        name="my_tool",
        description="做某件事",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        handler=lambda payload: f"结果: {payload['query']}",
    ))
```

### 生命周期 Hook 事件

| 事件 | 触发时机 |
| --- | --- |
| `SYSTEM_PROMPT` | 构建 system prompt |
| `REGISTER_TOOLS` | 注册工具时 |
| `SESSION_START` | session 开始 |
| `SESSION_END` | session 结束（保存记忆） |
| `PRE_RUN` | 每次 agent run 前 |
| `POST_RUN` | 每次 agent run 后 |
| `SERVE_START` | serve 启动后（传递 runner + settings） |
| `SERVE_STOP` | serve 关闭前 |
| `SCHEDULE_RESULT` | 定时任务执行完毕后广播（传递 job + result_text + success） |

---

## 持久化层

**所有文件写入必须经过 `hermit.storage` 原语，禁止裸 `write_text()`。**

```python
from hermit.storage import atomic_write, FileGuard, JsonStore

# 原子写（tempfile + os.replace）
atomic_write(path, content)

# 带文件锁的写（in-process RLock + 可选 flock）
with FileGuard.acquire(path, cross_process=True):
    data = json.loads(path.read_text())
    data["key"] = "value"
    atomic_write(path, json.dumps(data))

# JSON 读写封装
store = JsonStore(path)
data = store.load()
store.save(data)
```

---

## 内置工具（核心工具集）

每次 agent 启动时，以下工具自动注册：

| 工具 | 说明 |
| --- | --- |
| `read_file` | 读取 workspace 内 UTF-8 文本文件 |
| `write_file` | 写入 workspace 内 UTF-8 文本文件（原子写） |
| `bash` | 在沙箱中执行 shell 命令 |
| `read_hermit_file` | 读取 `~/.hermit/` 内文件 |
| `write_hermit_file` | 写入 `~/.hermit/` 内文件（原子写） |
| `list_hermit_files` | 列出 `~/.hermit/` 内文件 |

插件可通过 `PluginContext.add_tool()` 追加工具。MCP 工具命名格式为 `mcp__{server}__{tool}`。

---

## MCP Server 集成

兼容 Claude Code / Cursor `.mcp.json` 格式，两个作用域：

- `~/.hermit/mcp.json` — 全局配置
- `./.mcp.json` — 项目级配置（优先级更高）

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-notion"],
      "env": { "NOTION_API_KEY": "your-key" }
    }
  }
}
```

支持 stdio（command 启动子进程）和 Streamable HTTP（url 直连）两种传输。

---

## Skills 渐进式披露

Skills 采用三层渐进式加载，**完整内容不预先注入 system prompt**：

1. **Catalog 层**：启动时注入 `name` + `description`（约 50 token/个）
2. **Instructions 层**：通过 `read_skill` 工具 on-demand 读取完整 SKILL.md（< 5000 token）
3. **Resources 层**：脚本 / 参考资料在指令引用时按需加载

Skills 目录：`~/.hermit/skills/<skill-name>/SKILL.md`

---

## 记忆系统

记忆文件：`~/.hermit/memory/memories.md`

记忆条目格式：
```
- [YYYY-MM-DD] [s:N🔒] 内容（N=强度 0-10，🔒=永久保留）
```

衰减规则：
- 新条目初始 5 分
- 被引用 +1（上限 10），每 2 个 session 未引用 -1
- ≥ 7 分加 🔒 永久保留
- 降至 0 分自动删除
- 条目数超过阈值（8）时触发 LLM 合并（SESSION_END）

分类：用户偏好 / 项目约定 / 技术决策 / 环境与工具 / 人物与职责 / 其他

---

## 代码风格规范

1. 所有文件写入使用 `hermit.storage` 原语
2. 新增工具在 `ToolSpec` 的 `input_schema` 中声明完整 JSON Schema
3. 插件注册函数签名统一为 `def register(ctx: PluginContext) -> None`
4. 内置插件与外部插件格式完全相同，无特殊待遇
5. 使用 `structlog.get_logger()` 而非 `logging.getLogger()`
6. 飞书 Adapter 输出遵循飞书卡片规范，普通短回复走纯文本，结构化内容走 `RichCardBuilder`
7. 不写无效注释（只写代码无法表达的意图）

---

## 注意事项

### 并发安全
- 多个 `hermit serve` 进程共享 `~/.hermit/sessions/` 和 `memory/memories.md`，存在竞态风险
- 写入 `memories.md` 时必须使用 `FileGuard.acquire(path, cross_process=True)`
- `JsonStore` 已内置 `FileGuard`，直接使用即可

### 飞书 Adapter
- 依赖 `lark-oapi`，需 `pip install -e ".[feishu]"`
- 环境变量：`HERMIT_FEISHU_APP_ID` / `HERMIT_FEISHU_APP_SECRET`
- WebSocket 长连接，无需公网 IP

### Grok 插件
- 需要 `XAI_API_KEY`（写入 `~/.hermit/.env` 或 shell export）
- 使用 xAI `/v1/responses` 接口 + `web_search` / `x_search` 工具
- 在 `config.py` 通过 `GRO_ENABLED` 开关控制是否启用

### Extended Thinking
- 设置 `HERMIT_THINKING_BUDGET > 0` 启用
- `effective_max_tokens = thinking_budget + max_tokens`，自动调整

### 定时任务（Scheduler 插件）
- 内置插件 `builtin/scheduler/`，通过 `SERVE_START` hook 在 serve 进程内启动 daemon 线程
- 支持三种调度模式：cron 表达式、一次性任务（once）、固定间隔（interval）
- 持久化存储：`~/.hermit/schedules/jobs.json`（JsonStore + FileGuard）
- 执行日志：`~/.hermit/schedules/logs/`
- 结果广播：通过 `SCHEDULE_RESULT` hook 事件广播，各插件自行订阅通知（feishu 插件自动推送）
- 100% 稳定触发链路：launchd KeepAlive → serve 永活 → catch-up 补执行错过的任务
- Agent 工具：`schedule_create` / `schedule_list` / `schedule_delete` / `schedule_update`
- CLI 命令：`hermit schedule list/add/remove/enable/disable/history`

### macOS 开机自启
- 每个 adapter 独立 plist：`~/Library/LaunchAgents/com.hermit.serve.<adapter>.plist`
- 多 adapter 互不覆盖
