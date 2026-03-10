# Hermit 配置文档

## 目标

这份文档说明 Hermit 的配置来源、启动时注入的上下文、目录约定、插件体系、MCP Server 接入，以及"自我配置能力"应该如何使用。

当前版本的设计目标不是做一个复杂的配置中心，而是让配置保持：

- 可读
- 可审计
- 可被 Agent 自己理解和修改
- 不依赖数据库

---

## 配置优先级

Hermit 当前遵循以下优先级（后者覆盖前者）：

1. 代码默认值
2. `.env` 文件
3. 环境变量

`Settings` 由 `pydantic-settings` 驱动，默认前缀是 `HERMIT_`，但 `ANTHROPIC_API_KEY` 也会被识别。

---

## 核心配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` / `HERMIT_ANTHROPIC_API_KEY` | 无 | Claude API Key |
| `HERMIT_AUTH_TOKEN` | 无 | Bearer Token 认证，适合代理网关 |
| `HERMIT_BASE_URL` | 无 | 自定义 Anthropic 兼容网关地址 |
| `HERMIT_CUSTOM_HEADERS` | 无 | 自定义请求头，格式：`Key: Value, Key2: Value2` |
| `HERMIT_MODEL` | `claude-3-7-sonnet-latest` | 默认模型 |
| `HERMIT_IMAGE_MODEL` | 空 | 图片语义分析模型；未设置时回退到 `HERMIT_MODEL` |
| `HERMIT_IMAGE_CONTEXT_LIMIT` | `3` | 单次提示中注入的近期图片上下文数量上限 |
| `HERMIT_MAX_TOKENS` | `2048` | 单次 `messages.create` 的 `max_tokens` |
| `HERMIT_THINKING_BUDGET` | `0` | Extended Thinking token 预算，`0` 为关闭 |
| `HERMIT_MAX_TURNS` | `10` | 单次 agent loop 的最大轮数 |
| `HERMIT_TOOL_OUTPUT_LIMIT` | `4000` | 工具输出截断长度（字符数） |
| `HERMIT_LOG_LEVEL` | `INFO` | 日志级别 |
| `HERMIT_SANDBOX_MODE` | `l0` | 当前支持 `l0`（无沙箱）/ `l1`（受限执行） |
| `HERMIT_COMMAND_TIMEOUT_SECONDS` | `30` | `bash` 工具超时时间 |
| `HERMIT_SESSION_IDLE_TIMEOUT_SECONDS` | `1800` | Session 空闲超时（秒），超时后归档 |
| `HERMIT_BASE_DIR` | `~/.hermit` | Hermit 自身配置目录 |

**关于 `HERMIT_THINKING_BUDGET`**：启用时，`effective_max_tokens` 自动调整为 `thinking_budget + max_tokens`，确保模型有足够输出空间。

---

## 目录结构

`HERMIT_BASE_DIR` 默认是 `~/.hermit`，启动后会确保以下目录存在：

```text
~/.hermit/
├── context.md              # 长期背景、身份、目标、协作偏好
├── serve-<adapter>.pid     # serve 进程 PID 文件（运行时自动创建/清理）
├── memory/
│   ├── memories.md         # 可衰减的长期记忆
│   └── session_state.json  # 会话计数和增量处理状态
├── skills/                 # 用户自定义 Skill 插件目录
├── rules/                  # 强约束规则（*.md，启动时注入）
├── hooks/                  # 生命周期脚本目录（骨架，当前由插件机制接管）
├── plugins/                # 外部插件安装目录
├── image-memory/           # 图片资产、语义记录与跨 session 索引
└── sessions/               # 会话历史持久化
    └── archive/            # 空闲超时后的归档会话
```

各目录职责：

- **`context.md`** — 长期背景、身份、目标、协作偏好，启动时直接注入 system prompt
- **`memory/memories.md`** — 可衰减的长期记忆，适合存"事实化、被验证过的记忆"
- **`memory/session_state.json`** — 会话计数和增量处理状态，由 memory 插件维护
- **`rules/`** — 强约束、不可轻易违背的规则，启动时拼接注入 system prompt
- **`skills/`** — 用户自定义工作流或专门能力，支持 `skills/<name>/SKILL.md` 格式
- **`plugins/`** — 外部插件目录，每个子目录需含 `plugin.toml` 清单文件
- **`image-memory/`** — 跨 session 图片记忆目录，包含图片文件、语义记录和 session/global 索引
- **`sessions/`** — 会话历史，按 `<session_id>.json` 存储；飞书场景用 `{chat_id}:{sender_id}` 做 key

---

## 启动时注入了什么

执行 `hermit run` 或 `hermit chat` 时，Hermit 构造一份完整的 startup context 注入给模型。

### 1. 运行时上下文

告诉模型：

- 当前工作目录
- Hermit 自身配置目录（`base_dir`）
- memory / context / rules / skills / hooks / plugins / image-memory 各路径
- 默认模型、token 上限、最大轮数、沙箱模式等运行参数

这部分解决"模型知道自己在哪里运行、能改哪里、不能改哪里"。

### 2. 自我配置约束

明确注入如下原则：

- 允许通过专用工具修改 Hermit 自己的配置目录
- 修改前先读
- 保持最小改动
- 不覆盖用户已有内容
- 不把 secrets 写进 `context.md`、`memories.md`、`rules`、`skills`

### 3. 用户上下文与规则

启动时还会拼接：

- `context.md`
- `memory/memories.md` 生成的记忆 prompt（由 memory 插件的 SYSTEM_PROMPT hook 注入）
- `rules/*.md` 拼接结果

### 4. 插件贡献的 Prompt 片段

每个插件可通过订阅 `SYSTEM_PROMPT` hook 向 system prompt 追加内容（如记忆片段、规则片段）。

### 5. Skills 目录

Skills 采用渐进式披露机制（见下方「Skills 系统」章节）：

- 启动时只注入 `<available_skills>` 目录（约 50–100 tokens/条）
- Agent 通过 `read_skill` 工具按需加载完整 SKILL.md 内容

查看完整启动 prompt：

```bash
hermit startup-prompt
```

---

## 插件体系

Hermit 使用基于 `plugin.toml` 清单文件的插件体系，支持 6 个维度扩展。

### 插件格式

每个插件是一个包含 `plugin.toml` 的目录：

```toml
[plugin]
name = "my-plugin"
version = "1.0.0"
description = "插件说明"
builtin = false          # true = 内置插件，使用包内路径加载

[entry]
tools     = "tools:register"     # 注册工具（ToolSpec）
hooks     = "hooks:register"     # 注册生命周期钩子
subagents = "subagents:register" # 注册子 Agent（SubagentSpec）
adapter   = "adapter:register"   # 注册消息通道 Adapter（AdapterSpec）
mcp       = "mcp:register"       # 注册 MCP Server（McpServerSpec）
```

`entry` 中每个键对应一个 `<module>:<function>` 格式的入口，加载时会调用 `function(ctx: PluginContext)`。

### 插件发现顺序

1. `hermit/builtin/` — 随包分发的内置插件
2. `~/.hermit/plugins/` — 用户安装的外部插件

同名 key 的 MCP server 配置：后加载覆盖先加载（项目级 `.mcp.json` 覆盖全局 `~/.hermit/mcp.json`）。

### 内置插件清单

| 插件 | 维度 | 说明 |
| --- | --- | --- |
| `memory` | hooks | 跨会话记忆：score 衰减、LLM 合并、SYSTEM_PROMPT 注入 |
| `image_memory` | hooks + tools | 跨 session 图片资产、语义分析、检索、飞书复用 |
| `orchestrator` | hooks + subagents | 多 Agent 委派：researcher / coder 子 Agent |
| `web-tools` | tools | Web 搜索（DuckDuckGo Lite）+ 网页内容抓取 |
| `github` | mcp + skills | 内置 GitHub MCP 接入 + GitHub 工作流 skill |
| `mcp-loader` | mcp | 从 `.mcp.json` 解析并注册 MCP Server |
| `feishu` | adapter | 飞书 WebSocket 长连接 Adapter |

### 生命周期 Hooks

| Hook Event | 触发时机 | 典型用途 |
| --- | --- | --- |
| `SYSTEM_PROMPT` | 构建 system prompt 时 | 注入记忆、规则等内容片段 |
| `REGISTER_TOOLS` | 工具注册完成后 | 按需追加动态工具 |
| `SESSION_START` | 会话开始时 | 加载会话状态、初始化上下文 |
| `SESSION_END` | 会话结束时 | 持久化记忆、归档会话 |
| `PRE_RUN` | Agent 执行前 | 预处理用户输入 |
| `POST_RUN` | Agent 执行后 | 后处理结果、发送通知 |

同一事件可注册多个 handler，通过 `priority` 参数（数字越小越先执行）控制顺序。

### 插件目录结构规范

每个插件（内置或自定义）使用统一的目录布局：

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
  rules/                      # [可选] 启动时注入 system prompt 的静态规则
    <rule-name>.md
```

**关键约定：**

- `plugin.toml` 是唯一必需文件，`[entry]` 中各 key 格式为 `module:function`（必须带冒号）
- 入口模块名与维度约定对应：`tools.py` / `commands.py` / `hooks.py` / `mcp.py` / `adapter.py` / `subagents.py`
- 内置插件需在 `plugin.toml` 声明 `builtin = true`；自定义插件省略或设为 `false`，两者格式完全相同
- `skills/` 下每个子目录对应一个技能，`SKILL.md` 使用 YAML frontmatter 声明 `name` 和 `description`
- 一个插件可同时注册多个维度：例如同时声明 `tools` 和 `hooks`

**最小可用插件示例：**

```
my-plugin/
  plugin.toml
  tools.py
```

```toml
# plugin.toml
[plugin]
name = "my-plugin"
version = "0.1.0"
description = "示例插件"

[entry]
tools = "tools:register"
```

```python
# tools.py
from hermit.core.tools import ToolSpec
from hermit.plugin.base import PluginContext

def register(ctx: PluginContext) -> None:
    ctx.add_tool(ToolSpec(
        name="my_tool",
        description="做某件事",
        input_schema={
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        },
        handler=lambda payload: f"结果: {payload['input']}",
    ))
```

**含 Skill 的插件示例：**

```
my-plugin/
  plugin.toml
  tools.py
  skills/
    my-workflow/
      SKILL.md
```

```markdown
<!-- skills/my-workflow/SKILL.md -->
---
name: my-workflow
description: 说明何时让 Agent 激活并读取此 Skill
---

## 使用指南
...
```

### 创建外部插件

```bash
# 创建插件目录
mkdir ~/.hermit/plugins/my-plugin

# 创建清单文件
cat > ~/.hermit/plugins/my-plugin/plugin.toml << 'EOF'
[plugin]
name = "my-plugin"
version = "0.1.0"
description = "我的自定义插件"

[entry]
tools = "tools:register"
EOF

# 创建工具实现
cat > ~/.hermit/plugins/my-plugin/tools.py << 'EOF'
from hermit.core.tools import ToolSpec
from hermit.plugin.base import PluginContext

def register(ctx: PluginContext) -> None:
    ctx.add_tool(ToolSpec(
        name="my_tool",
        description="我的自定义工具",
        input_schema={
            "type": "object",
            "properties": {"input": {"type": "string"}},
            "required": ["input"],
        },
        handler=lambda payload: f"处理结果: {payload['input']}",
    ))
EOF
```

从 Git 仓库一键安装：

```bash
hermit plugin install https://github.com/example/my-hermit-plugin
```

---

## Skills 系统

Skills 是写给 Agent 看的专项指令，采用三层渐进式披露机制，避免不必要的 token 消耗。

### 三层披露机制

1. **Catalog 层**（启动时自动注入）  
   只注入技能的 `name` 和 `description`，约 50–100 tokens/条：

   ```xml
   <available_skills>
   The following skills provide specialized instructions.
   When a task matches a skill's description, call read_skill to load its full instructions.

     <skill name="feishu-output-format">Format output for Feishu messaging</skill>
   </available_skills>
   ```

2. **Instructions 层**（按需加载）  
   Agent 判断任务匹配某技能时，调用 `read_skill` 工具加载完整 SKILL.md 内容（通常 < 5000 tokens）：

   ```xml
   <skill_content name="feishu-output-format">
   <!-- SKILL.md 完整内容 -->
   </skill_content>
   ```

3. **Resources 层**（指令引用时加载）  
   SKILL.md 内引用的脚本、参考资料等，在执行时按需读取。

### 预加载技能（Adapter 场景）

Adapter 可声明需要强制预加载的技能列表（等同于 Claude Code 子 Agent 的 `skills` 字段）：

```python
class FeishuAdapter:
    @property
    def required_skills(self) -> list[str]:
        return ["feishu-output-format"]
```

预加载技能的完整内容会在启动时直接注入 system prompt，无需 Agent 主动调用 `read_skill`。

### 技能目录

| 来源 | 路径格式 |
| --- | --- |
| 内置插件 | `hermit/builtin/<plugin>/skills/<name>/SKILL.md` |
| 用户自定义 | `~/.hermit/skills/<name>/SKILL.md` |
| 外部插件 | `~/.hermit/plugins/<plugin>/skills/<name>/SKILL.md` |

---

## MCP Server 集成

Hermit 通过内置 `mcp-loader` 插件支持 MCP（Model Context Protocol）Server 接入，兼容 Claude Code / Cursor 的 `.mcp.json` 配置格式。

### 配置文件位置

| 路径 | 作用域 | 优先级 |
| --- | --- | --- |
| `~/.hermit/mcp.json` | 全局 | 低 |
| `./.mcp.json`（当前工作目录） | 项目级 | 高（覆盖全局） |

### 配置格式

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

| 字段 | 说明 |
| --- | --- |
| `command` | Stdio 传输：可执行文件路径（如 `npx`、`uvx`、绝对路径） |
| `args` | Stdio 传输：命令参数列表 |
| `env` | 注入子进程的环境变量 |
| `url` | HTTP 传输：Streamable HTTP endpoint URL |
| `headers` | HTTP 传输：额外请求头（如认证 header） |
| `allowedTools` | 工具白名单，省略则加载该 Server 所有工具 |
| `description` | 可选，Server 说明（注入 ToolSpec description 前缀） |

### 工具命名约定

MCP 工具自动以 `mcp__{server}__{tool}` 格式注册到 ToolRegistry：

```
mcp__notion__search          →  notion server 的 search 工具
mcp__github__create_issue    →  github server 的 create_issue 工具
```

Agent 通过 `tool_use` 调用时，Hermit 自动路由到对应的 MCP Server，对 ClaudeAgent 完全透明。

### 传输类型

| 传输 | 配置字段 | 适用场景 |
| --- | --- | --- |
| **Stdio** | `command` + `args` + `env` | 本地 MCP Server（npm 包、Python 包） |
| **Streamable HTTP** | `url` + `headers` | 远程 MCP Server（SaaS 服务、自托管） |

### 连接生命周期

```
hermit run / chat / serve
  └── _build_agent()
        ├── pm.setup_tools(registry)           # 注册内置工具 + 插件工具
        ├── pm.start_mcp_servers(registry)     # 连接 MCP Server，发现工具，注册到 registry
        └── ClaudeAgent(registry)              # Agent 工具循环无需感知 MCP
  └── finally: pm.stop_mcp_servers()           # 断开连接，终止子进程
```

### 调试 MCP 连接

启动时日志会输出连接结果：

```
hermit run "搜索相关 Notion 文档" 2>&1 | grep mcp
```

或设置 DEBUG 级别查看详细日志：

```bash
HERMIT_LOG_LEVEL=DEBUG hermit run "..."
```

---

## Adapter 系统

Adapter 是消息通道适配器，负责将外部消息平台（飞书、Slack 等）与 Agent 桥接，通过 `hermit serve --adapter <name>` 启动。

### 内置飞书 Adapter

飞书 Adapter 使用 lark-oapi SDK 的 WebSocket 长连接模式，无需公网域名。

**安装依赖：**

```bash
pip install -e ".[feishu]"
```

**环境变量：**

| 变量 | 说明 |
| --- | --- |
| `HERMIT_FEISHU_APP_ID` | 飞书应用 App ID（推荐） |
| `HERMIT_FEISHU_APP_SECRET` | 飞书应用 App Secret（推荐） |
| `FEISHU_APP_ID` | 飞书应用 App ID（兼容旧写法） |
| `FEISHU_APP_SECRET` | 飞书应用 App Secret（兼容旧写法） |

**启动：**

```bash
hermit serve --adapter feishu
```

**Session 隔离策略：**

- 私聊：`session_id = {chat_id}`（一条私聊会话对应一个 session）
- 群聊：`session_id = {chat_id}:{sender_id}`（群聊中不同成员互相隔离）

**输出格式：**

飞书 Adapter 预加载 `feishu-output-format` 技能，Agent 输出自动适配飞书 Markdown 格式，并自动包裹为 Feishu interactive card JSON 2.0 的 `body.elements[].tag="markdown"` 组件。

**图片支持：**

- 飞书图片消息会先下载到本地图片记忆目录，再立即生成 `summary`、`tags`、`ocr_text`
- 当用户追问“刚才那张图”“截图”“二维码”等内容时，插件会自动注入近期相关图片摘要
- Agent 可显式调用 `image_search` / `image_get` 查询历史图片
- 若需要在飞书回复中重新展示已存图片，可调用 `image_attach_to_feishu`，并在最终回复里保留返回的 `<feishu_image key='...'/>` 标签

### 内置图片记忆插件

图片记忆插件默认保存到 `~/.hermit/image-memory/`，并在图片进入系统时立即生成轻量语义。

**目录结构：**

```text
~/.hermit/image-memory/
├── assets/                 # 原始图片文件
├── records/                # 单图结构化记录（summary/tags/ocr_text）
└── indexes/
    ├── global.json         # 全局图片索引
    └── session/            # 各 session 的图片索引
```

**内置工具：**

- `image_store_from_path` — 导入本地图片并立即分析
- `image_store_from_feishu` — 将飞书图片消息下载并入库
- `image_search` — 按关键词、标签、OCR、session 搜索历史图片
- `image_get` — 读取单张图片元数据
- `image_attach_to_feishu` — 生成 `<feishu_image key='...'/>` 标签，供飞书回复渲染图片组件

### Graceful Reload（热重载）

`hermit serve` 支持通过 SIGHUP 信号触发热重载，无需手动停止再启动。重载时会：

1. 优雅停止当前 Adapter（关闭 WebSocket 连接、flush 所有活跃 session）
2. 清除配置缓存，重新读取 `Settings`（环境变量、`.env`）
3. 重新发现并加载所有插件（builtin + installed）
4. 重建工具注册表、系统 prompt、MCP Server 连接
5. 重新启动 Adapter
6. 通过 `DISPATCH_RESULT` Hook 发送重载成功通知（需配置 `HERMIT_SCHEDULER_FEISHU_CHAT_ID`）

**使用方式：**

```bash
# 方式 1：CLI 命令（推荐）
hermit reload --adapter feishu

# 方式 2：直接发信号
kill -HUP $(cat ~/.hermit/serve-feishu.pid)
```

**PID 文件：**

serve 启动时会将进程 PID 写入 `~/.hermit/serve-<adapter>.pid`，退出时自动清理。`reload` 命令读取此文件发送 SIGHUP。

**适用场景：**

- 修改了环境变量或 `.env` 配置
- 安装或更新了插件
- 修改了 `context.md`、`rules/`、`skills/` 内容
- 更新了 MCP Server 配置（`.mcp.json`）
- 更新了 webhook 路由配置

**注意事项：**

- 仅支持 macOS / Linux（Unix 信号），Windows 不支持
- 重载期间正在处理的消息会完成后再停止
- 重载会创建全新的 Adapter 实例，WebSocket 连接会重新建立

### 创建自定义 Adapter

```python
# ~/.hermit/plugins/my-adapter/adapter.py
from hermit.plugin.base import AdapterProtocol, AdapterSpec, PluginContext
from hermit.core.runner import AgentRunner

class MyAdapter:
    @property
    def required_skills(self) -> list[str]:
        return []  # 预加载的 Skill 名称列表

    async def start(self, runner: AgentRunner) -> None:
        # 启动消息监听，调用 runner.handle(session_id, message) 处理消息
        ...

    async def stop(self) -> None:
        # 优雅关闭
        ...

def register(ctx: PluginContext) -> None:
    ctx.add_adapter(AdapterSpec(
        name="my-adapter",
        description="我的自定义 Adapter",
        factory=lambda settings: MyAdapter(),
    ))
```

---

## 自我配置能力

当前版本已具备最小自我配置能力，通过受限工具只操作 `HERMIT_BASE_DIR`。

### 可用的自我配置工具

| 工具 | 说明 |
| --- | --- |
| `list_hermit_files` | 列出 `~/.hermit` 下的文件或目录 |
| `read_hermit_file` | 读取 `~/.hermit` 下的文本文件 |
| `write_hermit_file` | 写入 `~/.hermit` 下的文本文件 |

这些工具只能访问 Hermit 自己的配置目录，不能逃逸到其它路径。

---

## 推荐的配置落点

当用户要求"以后都按这个方式做"时，建议写入位置如下：

| 需求类型 | 推荐位置 |
| --- | --- |
| 长期背景 / 个人偏好 / 项目上下文 | `context.md` |
| 强约束规则 | `rules/*.md` |
| 可复用操作流程 | `skills/<name>/SKILL.md` |
| 密钥 / token / endpoint | `.env` |
| MCP Server 连接配置 | `.mcp.json`（项目级）或 `~/.hermit/mcp.json`（全局） |
| 会随会话衰减的经验和事实 | `memory/memories.md` |

---

## `context.md` 的建议写法

推荐保持结构化，便于模型稳定读取：

```md
# Hermit Context

## 身份
- 你是一个偏个人使用场景的 AI Agent。

## 长期目标
- 优先帮助我做研发、自动化和知识沉淀。

## 工作方式
- 回答先简洁后展开。
- 修改自己配置前先读现有内容。

## 当前项目背景
- 这个仓库主要用于搭建个人 AI agent 基础设施。
```

---

## 安全建议

- 不要把 API Key 写进 `context.md`
- 不要把密码、cookie、令牌写进 `memory/memories.md`
- 如果必须让模型知道某个密钥的存在，优先只告诉它"有这个变量"，不要注入真实值
- `write_hermit_file` 应优先修改 markdown 配置，不应默认改写敏感文件
- MCP Server 的认证 header / env 只写在 `.mcp.json`，不要注入 `context.md`

---

## 常用命令

初始化本地目录：

```bash
hermit init
```

查看完整 startup prompt（含插件注入内容）：

```bash
hermit startup-prompt
```

单次对话：

```bash
hermit run "检查你自己的配置目录，并告诉我还缺什么"
```

交互式多轮对话：

```bash
hermit chat
```

启动飞书 Adapter 服务：

```bash
hermit serve --adapter feishu
```

热重载 serve 进程（不停机重新加载配置、插件、工具）：

```bash
hermit reload --adapter feishu
```

列出已加载插件：

```bash
hermit plugin list
```

---

## Claude Code 风格代理配置兼容

如果你本地已经有一套 Claude Code 风格的代理配置，可以直接映射到 Hermit 的环境变量：

```bash
export HERMIT_AUTH_TOKEN="your-token"
export HERMIT_BASE_URL="https://your-proxy.example.com/llm/claude"
export HERMIT_CUSTOM_HEADERS="X-Biz-Id: claude-code"
export HERMIT_MODEL="claude-sonnet-4-6"
```

说明：

- `HERMIT_AUTH_TOKEN` — 传给 Anthropic SDK 的 `auth_token`
- `HERMIT_BASE_URL` — 传给 Anthropic SDK 的 `base_url`
- `HERMIT_CUSTOM_HEADERS` — 解析成 `default_headers`，格式：`Key: Value, Key2: Value2`
- `HERMIT_MODEL` — 直接覆盖默认模型

当前版本不自动读取 `ANTHROPIC_MODEL`、`ANTHROPIC_CUSTOM_HEADERS` 这类无前缀字段；Hermit 约定统一使用 `HERMIT_*`。

---

## 后续可扩展方向

- `hermit mcp list` / `mcp add` / `mcp test` — MCP Server 管理命令
- `profiles/` — 多 persona 支持（按场景切换 context + rules）
- `policy.md` — 工具权限做成可审计策略文件
- `self_update` — Agent 在用户批准后自动补全 rules/skills/context
- Session 跨设备同步（当前仅本地 JSON 文件）
