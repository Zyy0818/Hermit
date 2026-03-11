# Repository Layout

这份文档描述当前仓库的真实结构与职责边界，不再写“未来打算怎么整理”。

## 顶层结构

```text
.
├── docs/                 文档
├── hermit/               主 Python 包
├── tests/                测试
├── skills/               仓库内附带的辅助 skill
├── README.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── install.sh
└── Makefile
```

## `hermit/` 包结构

```text
hermit/
├── builtin/              内置插件
├── companion/            macOS 菜单栏 companion
├── core/                 runner / session / tools / sandbox
├── plugin/               插件契约、加载器、管理器
├── provider/             provider 协议、实现与 runtime services
├── storage/              原子写、文件锁、JSON store
├── config.py             Settings 与派生路径
├── context.py            基础 system prompt 上下文
├── i18n.py               本地化工具
├── locales/              文案 catalog
├── logging.py            日志配置
└── main.py               CLI 入口
```

## `hermit/builtin/`

内置插件目录，当前主要包括：

- `memory`
- `image_memory`
- `orchestrator`
- `web_tools`
- `grok`
- `computer_use`
- `scheduler`
- `webhook`
- `github`
- `mcp_loader`
- `feishu`
- `compact`
- `planner`
- `usage`

每个插件通常包含：

- `plugin.toml`
- `tools.py` / `hooks.py` / `commands.py` / `adapter.py` / `mcp.py`
- `skills/`
- 可选的 `rules/`

## `hermit/core/`

当前 runtime 核心层：

- `agent.py`
- `runner.py`
- `sandbox.py`
- `session.py`
- `tools.py`

这里不承载“产品能力”，只承载通用执行框架。

## `hermit/plugin/`

插件基础设施：

- `base.py` 定义 manifest、hook event、command / adapter / subagent 规格
- `loader.py` 负责解析 `plugin.toml` 和加载入口
- `manager.py` 汇总所有插件资产
- `config.py` 解析插件变量与模板

## `hermit/provider/`

provider 相关代码：

- `contracts.py` 统一 provider 协议
- `messages.py` block 规范化
- `runtime.py` 通用 tool loop
- `services.py` provider 构造与辅助服务
- `profiles.py` 解析 `config.toml`
- `providers/` 放具体 provider 实现

## `hermit/companion/`

独立的 macOS companion 层：

- `control.py` 服务控制
- `menubar.py` 菜单栏 UI
- `appbundle.py` 本地 app bundle 与 Login Item

它不属于插件系统。

## `docs/`

当前仓库内最重要的文档：

- `architecture.md`
- `configuration.md`
- `providers-and-profiles.md`
- `cli-and-operations.md`
- `desktop-companion.md`
- `i18n.md`
- `openclaw-comparison.md`

## `tests/`

测试覆盖面已经比较完整，当前重点包括：

- CLI
- config / profile
- provider runtime
- session / memory / hooks
- scheduler / webhook
- Feishu adapter
- companion

这轮检查实际跑通：

```bash
uv run pytest -q
```

结果：

- `332 passed`

## 当前仓库里的已知组织特征

### `build/` 是打包产物，不是源码

仓库当前包含 `build/lib/...` 产物镜像。阅读和修改时应以 `hermit/` 下源码为准。

### 根目录仍有少量非核心文件

例如：

- `beijing_weekend_trip_march2026.md`

这类文件不影响运行，但不属于核心项目结构。

### 插件层是功能扩展主战场

Hermit 的能力大多优先下沉到 `hermit/builtin/`，而不是继续膨胀 `core/`。

## 这份文档相对旧版本的变化

- 删掉了“下一步建议”式内容
- 改为按当前真实目录结构说明职责
- 明确区分源码、插件、companion、测试、打包产物
