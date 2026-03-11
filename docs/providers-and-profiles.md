# Provider 与 Profile

这份文档专门说明 Hermit 当前支持的 provider 模式、鉴权来源，以及 `config.toml` profile 的用法。

## 当前支持的 provider

当前代码支持三种 provider：

- `claude`
- `codex`
- `codex-oauth`

provider 入口在 [`hermit/provider/services.py`](../hermit/provider/services.py)。

## 1. `claude`

默认 provider。

适用场景：

- 直接使用 Anthropic API
- 使用 Claude 兼容的企业网关 / 代理

### 直连 Anthropic

最简单配置：

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

### 走兼容网关

```bash
HERMIT_PROVIDER=claude
HERMIT_AUTH_TOKEN=your-bearer-token
HERMIT_BASE_URL=https://your-gateway.example.com/llm/claude
HERMIT_CUSTOM_HEADERS=X-Biz-Id: my-team
HERMIT_MODEL=claude-3-7-sonnet-latest
```

兼容别名：

- `HERMIT_CLAUDE_AUTH_TOKEN` 等价 `HERMIT_AUTH_TOKEN`
- `HERMIT_CLAUDE_BASE_URL` 等价 `HERMIT_BASE_URL`
- `HERMIT_CLAUDE_HEADERS` 等价 `HERMIT_CUSTOM_HEADERS`

## 2. `codex`

这不是“调用本机 codex CLI”，而是直接走 OpenAI Responses API。

最常见配置：

```bash
HERMIT_PROVIDER=codex
HERMIT_OPENAI_API_KEY=sk-...
HERMIT_MODEL=gpt-5.4
```

可选项：

```bash
HERMIT_OPENAI_BASE_URL=https://api.openai.com/v1
HERMIT_OPENAI_HEADERS=X-Project: hermit
```

### 一个容易误解的点

如果本机有 `~/.codex/auth.json`，但其中没有可用的 OpenAI API key，`codex` 模式不会自动帮你“借用桌面登录态”。

当前实现会直接报错，提示：

- 需要 `HERMIT_OPENAI_API_KEY`
- 或本地 `~/.codex/auth.json` 里存在 API-key-backed auth state

## 3. `codex-oauth`

这个模式才会真正读取 `~/.codex/auth.json` 里的 OAuth token。

适用场景：

- 你已经在本机登录了 Codex / ChatGPT 桌面体系
- 想直接重用 access / refresh token

示例：

```bash
HERMIT_PROVIDER=codex-oauth
HERMIT_MODEL=gpt-5.4
```

要求：

- `~/.codex/auth.json` 存在
- 其中同时包含 `access_token` 与 `refresh_token`

如果文件不存在，Hermit 会在启动时直接报错。

## model 解析逻辑

provider 选择后，最终 model 解析还有一个细节：

- 如果你在 `codex` / `codex-oauth` 模式下仍请求了 `claude...` 开头的模型名
- Hermit 会尝试读取 `~/.codex/config.toml` 里的 `model`
- 如果仍拿不到，就回退到默认的 `gpt-5.4`

也就是说，`codex*` 模式不适合继续保留 Claude 风格的默认 model 名。

## `config.toml` profile

profile 文件路径：

```text
~/.hermit/config.toml
```

最常见写法：

```toml
default_profile = "codex-local"

[profiles.codex-local]
provider = "codex-oauth"
model = "gpt-5.4"
max_turns = 60

[profiles.claude-work]
provider = "claude"
model = "claude-3-7-sonnet-latest"
claude_base_url = "https://example.internal/claude"
claude_headers = "X-Biz-Id: workbench"
```

### 选择 profile 的方式

1. `default_profile`
2. `HERMIT_PROFILE`
3. `profiles resolve --name ...` 只是查看，不会写入

环境变量仍然可以覆盖 profile 值。

## 推荐配置示例

### 个人本机，直接用 Claude

```toml
default_profile = "default"

[profiles.default]
provider = "claude"
model = "claude-3-7-sonnet-latest"
```

再把 `ANTHROPIC_API_KEY` 放进 `~/.hermit/.env`。

### 个人本机，重用 Codex 登录态

```toml
default_profile = "codex-local"

[profiles.codex-local]
provider = "codex-oauth"
model = "gpt-5.4"
max_turns = 60
```

### 团队内网，走 Claude 兼容网关

```toml
default_profile = "work"

[profiles.work]
provider = "claude"
model = "claude-3-7-sonnet-latest"
claude_base_url = "https://gateway.example.com/claude"
claude_headers = "X-Biz-Id: hermit"
```

再用 shell env 或 `~/.hermit/.env` 注入 token。

## 插件变量也来自 `config.toml`

除了 `[profiles.*]`，还支持：

```toml
[plugins.github.variables]
github_pat = "ghp_xxx"
github_mcp_url = "https://api.githubcopilot.com/mcp/"
```

插件变量会在加载 `plugin.toml` 时参与模板渲染，例如：

```toml
[config]
url = "{{ github_mcp_url }}"

[config.headers]
Authorization = "Bearer {{ github_pat }}"
```

## 常用检查命令

```bash
hermit profiles list
hermit profiles resolve --name codex-local
hermit auth status
hermit config show
```

最实用的排查顺序通常是：

1. `hermit profiles list`
2. `hermit profiles resolve --name ...`
3. `hermit auth status`
4. `hermit config show`

## 这轮审查确认的事实

- `codex` 当前已经明确绑定 OpenAI Responses API
- `codex-oauth` 才是读取 `~/.codex/auth.json` token 的模式
- profile 与 env 的叠加关系是真实可用能力，不应继续只靠测试文件理解
