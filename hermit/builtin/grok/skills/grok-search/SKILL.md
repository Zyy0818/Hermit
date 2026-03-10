---
name: grok-search
description: When to use grok_search vs web_search — Grok has real-time live web access and synthesizes answers directly, making it the preferred tool for news, stock prices, current events, or any time-sensitive query.
---

## grok_search vs web_search

| 特性 | `grok_search` | `web_search` |
|------|---------------|--------------|
| 实时性 | ✅ Grok 直接读取当前网页 | ⚠️ DDG 索引（可能有延迟） |
| 回答质量 | 综合分析 + 内联引用 | 返回搜索结果片段 |
| 适合场景 | 新闻、股价、时事、突发事件 | 文档、代码、百科 |
| 速度 | 较慢（LLM 处理） | 较快（纯抓取） |
| 依赖 | 需要 XAI_API_KEY | 无需 API Key |

---

## 何时用 grok_search（优先）

使用 `grok_search` 当：
- 用户问**今日/最新/最近**的新闻、事件、价格
- 问题涉及**股票、财经、市场**动态
- 问**某人/某公司最新动态**
- `web_search` 搜到的结果过旧或相关性差

## 何时用 web_search（备用）

使用 `web_search` 当：
- 查技术文档、API 用法、代码示例
- 查历史事件、百科知识
- `grok_search` 失败或 XAI_API_KEY 未配置
- 只需要快速找几条链接即可

---

## 使用示例

### 股价/财经

```json
{"query": "MiniMax 01912.HK 今日股价大涨原因分析"}
```

### 时事新闻

```json
{"query": "以色列袭击伊朗油库最新进展 2026年3月"}
```

### 强制开启实时搜索

```json
{"query": "当前比特币价格", "search_mode": "on"}
```

---

## 如果 XAI_API_KEY 未设置

工具会返回错误提示。此时回退到 `web_search` 升级策略（day → week → month）。
