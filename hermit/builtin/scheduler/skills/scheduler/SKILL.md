---
name: scheduler
description: "Create and manage scheduled tasks (cron/once/interval) that run agent prompts automatically — use when user asks to set up periodic tasks, reminders, recurring reports, or timed executions."
---

## 能力说明

Hermit 内置**定时任务调度器**，可以让 Agent 在指定时间自动执行任务，结果推送到飞书。

**前提：需要 `hermit serve` 在运行**，调度器随 serve 进程启动。

---

## 可用工具

| 工具 | 说明 |
|------|------|
| `schedule_create` | 创建定时任务 |
| `schedule_list` | 列出所有任务 |
| `schedule_update` | 修改任务（名称/提示词/开关/cron/飞书推送） |
| `schedule_delete` | 删除任务 |
| `schedule_history` | 查看执行历史 |

---

## 三种调度模式

### 1. Cron（推荐）

用标准 5 段 cron 表达式：

```
分 时 日 月 周
0  9  *  *  1-5   → 工作日早 9 点
0  18 *  *  *     → 每天晚 6 点
0  */2 * *  *     → 每 2 小时
30 8  *  *  1     → 每周一早 8:30
0  9  1  *  *     → 每月 1 日早 9 点
```

### 2. Once（一次性）

指定 ISO 格式时间，如 `2026-03-15T14:00:00`。执行一次后自动禁用。

### 3. Interval（固定间隔）

每隔 N 秒执行一次，最少 60 秒。

---

## 飞书推送

创建任务时传入 `feishu_chat_id`，任务执行完毕结果自动推到该对话。

**在飞书对话中创建任务时，必须从上下文读取 `feishu_chat_id`：**

消息上下文中会有 `<feishu_chat_id>oc_xxx...</feishu_chat_id>` 标签，直接用这个值作为 `feishu_chat_id` 参数，不要问用户。

---

## 典型对话场景

### 设置每日定时任务

用户说「每天早上 9 点帮我搜索 AI 行业新闻并推到这里」：

```python
schedule_create(
    name="AI 行业日报",
    prompt="搜索今日 AI 行业最重要的 3 条新闻，整理成简报推送到飞书",
    schedule_type="cron",
    cron_expr="0 9 * * *",
    feishu_chat_id="<从上下文读取>",
)
```

### 定时提醒

用户说「每周一早 9 点提醒我做周报」：

```python
schedule_create(
    name="周报提醒",
    prompt="提醒：今天是周一，请记得提交本周周报。",
    schedule_type="cron",
    cron_expr="0 9 * * 1",
    feishu_chat_id="<从上下文读取>",
)
```

### 查看任务状态

用户说「我的定时任务都有哪些」：

```python
schedule_list()
```

### 查看执行历史

用户说「上次定时任务跑成功了吗」：

```python
schedule_history(limit=5)
```

### 暂停/恢复任务

```python
schedule_update(job_id="xxx", enabled=False)   # 暂停
schedule_update(job_id="xxx", enabled=True)    # 恢复
```

---

## 注意事项

- 时区：使用系统本地时间，通常为运行 `hermit serve` 机器的时区
- 任务 prompt 写得越具体，执行结果越好；避免过于宽泛的 prompt
- `interval` 模式最少 60 秒；高频任务建议用 cron
- serve 停止时任务暂停，重启后会补执行启动期间错过的任务（catch-up 机制）
- 使用 `schedule_history` 确认任务是否正常执行，失败时查看错误信息
