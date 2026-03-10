---
name: webhook-trigger
description: "Configure and manage inbound HTTP webhooks that trigger agent tasks — use when user asks about webhook setup, external system integrations (GitHub, Zendesk, etc.), or receiving events from third-party services."
---

## 能力说明

Hermit 内置 **webhook 插件**，在 `hermit serve` 启动时同步开启一个 HTTP 服务（默认端口 8321），可以接收外部系统（GitHub、Zendesk、自定义系统等）的 POST 事件，自动触发 Agent 处理并将结果推送到飞书。

**这是一个已内置的能力，无需安装额外插件。**

---

## 可用工具

| 工具 | 说明 |
|------|------|
| `webhook_list` | 列出所有已配置的路由 |
| `webhook_add` | 添加新路由（写入 webhooks.json） |
| `webhook_update` | 修改路由的模板/路径/签名/飞书推送 |
| `webhook_delete` | 删除路由 |

**注意：添加/修改/删除路由后需要重启 `hermit serve` 才生效。**

---

## 如何帮用户配置 webhook

当用户说「帮我配置 GitHub webhook」或「我想接收外部事件」时：

1. 调用 `webhook_list` 查看当前配置
2. 询问：接收哪个系统的事件？触发后做什么任务？结果推到哪个飞书群？
3. 调用 `webhook_add` 创建路由（飞书对话中从 `<feishu_chat_id>` 上下文读取 feishu_chat_id）
4. 提示用户重启 serve，并提供 curl 测试命令

---

## 配置文件

路径：`~/.hermit/webhooks.json`

```json
{
  "host": "0.0.0.0",
  "port": 8321,
  "routes": {
    "<路由名称>": {
      "path": "/webhook/<路径>",
      "secret": "<HMAC secret，可选>",
      "signature_header": "X-Hub-Signature-256",
      "prompt_template": "<用于驱动 Agent 的提示词模板，支持 {字段} 占位符>",
      "notify": {
        "feishu_chat_id": "<飞书群聊或单聊 ID>"
      }
    }
  }
}
```

### 关键字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `path` | 是 | HTTP 路由路径，如 `/webhook/github` |
| `prompt_template` | 是 | Agent 收到的提示词，可用 `{字段}` 从 payload 中提取值，支持嵌套如 `{pull_request.title}` |
| `secret` | 否 | HMAC-SHA256 签名 secret，填写后校验 `signature_header` |
| `signature_header` | 否 | 签名 header 名，默认 `X-Hub-Signature-256` |
| `notify.feishu_chat_id` | 否 | 飞书推送目标，`oc_` 开头为群聊，`ou_` 开头为单聊。不填则不推飞书 |

---

## 典型配置示例

### GitHub PR 自动 Code Review

```json
{
  "routes": {
    "github": {
      "path": "/webhook/github",
      "secret": "your_github_secret",
      "signature_header": "X-Hub-Signature-256",
      "prompt_template": "收到 GitHub {action} 事件。\n仓库：{repository.full_name}\nPR 标题：{pull_request.title}\nPR 描述：{pull_request.body}\n\n请对这个 PR 进行简要的 Code Review，指出潜在问题和改进建议。",
      "notify": {
        "feishu_chat_id": "oc_xxxxxx"
      }
    }
  }
}
```

### 自定义系统通知

```json
{
  "routes": {
    "custom": {
      "path": "/webhook/custom",
      "prompt_template": "{message}",
      "notify": {
        "feishu_chat_id": "oc_xxxxxx"
      }
    }
  }
}
```

---

## 调用方式（外部系统）

```bash
# 无签名
curl -X POST http://your-server:8321/webhook/custom \
  -H "Content-Type: application/json" \
  -d '{"message": "部署完成，请检查生产环境状态"}'

# 有签名（GitHub 风格）
SECRET="your_secret"
BODY='{"action":"opened","pull_request":{"title":"Fix bug"},"repository":{"full_name":"org/repo"}}'
SIG="sha256=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"
curl -X POST http://your-server:8321/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$BODY"
```

成功返回 `HTTP 202 Accepted`，Agent 在后台异步处理，完成后结果推送到配置的飞书对话。

---

## 调试端点

| 端点 | 说明 |
|------|------|
| `GET /health` | 健康检查，返回 `{"status": "ok"}` |
| `GET /routes` | 列出所有已注册路由及是否有签名 |

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HERMIT_WEBHOOK_ENABLED` | `true` | 设为 `false` 禁用 webhook 插件 |
| `HERMIT_WEBHOOK_HOST` | `0.0.0.0` | 监听地址 |
| `HERMIT_WEBHOOK_PORT` | `8321` | 监听端口 |

---

## prompt_template 语法

模板支持从 webhook payload 提取字段，使用 `{字段名}` 语法：

- **顶层字段**：`{action}` → payload 的 `action` 字段
- **嵌套字段**：`{pull_request.title}` → `payload.pull_request.title`
- **深层嵌套**：`{repository.owner.login}`
- **缺失字段**：原样保留占位符 `{missing_field}`，不报错

---

## 典型对话场景

### 查看当前配置

```python
webhook_list()
```

### 添加 GitHub PR 自动 Review 路由

```python
webhook_add(
    name="github",
    prompt_template="收到 GitHub {action} 事件。\n仓库：{repository.full_name}\nPR：{pull_request.title}\n\n请进行 Code Review。",
    secret="your_github_webhook_secret",
    feishu_chat_id="<从上下文 <feishu_chat_id> 读取>",
)
```

### 修改推送目标

```python
webhook_update(name="github", feishu_chat_id="oc_new_group_id")
```

### 删除路由

```python
webhook_delete(name="github")
```
