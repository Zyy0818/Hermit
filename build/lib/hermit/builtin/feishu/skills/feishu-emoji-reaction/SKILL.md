---
name: feishu-emoji-reaction
description: "Feishu emoji reaction rules. Pre-loaded when serving via Feishu adapter — guides the bot to react with emojis based on message content."
---

## 你能做什么

通过 `feishu_react` 工具，在飞书消息上添加 emoji 表情回复，让机器人更有人情味。

**消息 ID 在哪里**：用户消息最顶部有一行 `<feishu_msg_id>om_xxxxxx</feishu_msg_id>`，这就是你需要传给 `feishu_react` 的 `message_id`。

---

## 何时使用

**主动触发条件**（满足任意一条）：

| 场景 | 推荐 emoji | 示例触发词 |
|------|-----------|-----------|
| 用户分享好消息/成果 | `congrats` / `clap` | "上线了！""成功了！""终于搞定了" |
| 用户表达感谢或称赞 | `heart` / `smile` | "太棒了""谢谢""你真厉害" |
| 用户完成一个里程碑 | `fire` / `ok` | "发布了""合并了""发版了" |
| 用户问了个有趣的问题 | `thinking` | 哲学性/脑洞问题 |
| 用户分享了突发新闻 | `surprised` | "刚刚发现…""你知道吗…" |
| 回复了一个明确的任务请求 | `thumbsup` | "帮我...""麻烦你..." |

**不要使用表情**的场景：

- 用户在抱怨或表达不满（避免被误读为嘲弄）
- 消息是纯信息查询，没有情感色彩
- 刚刚已经做过表情回复了（同一条消息只回复一次）
- 消息内容不确定或模糊

---

## 调用方式

```
feishu_react(
  message_id="<feishu_msg_id> 标签中的值",
  emoji="thumbsup"   // 或其他 alias
)
```

### 可用 emoji alias（友好名称）

| alias | 含义 | 对应符号 |
|-------|------|---------|
| `thumbsup` | 赞 / 同意 | 👍 |
| `clap` | 鼓掌 / 太棒了 | 👏 |
| `congrats` | 恭喜 / 庆祝 | 🎉 |
| `fire` | 牛！/ 热门 | 🔥 |
| `heart` | 喜欢 / 感谢 | ❤️ |
| `ok` | 完成 / 没问题 | ✅ |
| `smile` | 开心 / 友好 | 😊 |
| `thinking` | 有趣 / 思考中 | 🤔 |
| `surprised` | 惊讶 / 原来如此 | 😮 |
| `eyes` | 收到了，在看 | 👀 |
| `thumbsdown` | 不认同 | 👎 |
| `cry` | 难过 | 😢 |

> 也可以直接传 Feishu 原生 emoji_type 字符串，如 `"THUMBSUP"`、`"FIRE"`。

---

## 使用原则

1. **克制**：每条用户消息最多回复 1 次，宁可不用也不滥用。
2. **时机**：在你正式回复**之前**或**之后**调用均可，但不要中断主要回复。
3. **匹配情绪**：表情应当与用户的实际情感一致，不要用于调侃用户抱怨。
4. **异步无妨**：`feishu_react` 失败不会影响正文回复，放心调用。
