---
name: web-search
description: How to use web_search effectively — recency-first strategy, parameter selection, and fallback escalation. Read when performing any web search, especially for current events or news.
---

## 优先考虑 grok_search

如果 `grok_search` 工具可用（XAI_API_KEY 已配置），对于新闻、时事、股价等时效性查询**优先使用 grok_search**，它具备实时网页读取能力，结果比 DuckDuckGo 更新更准。

`web_search` 作为备用：当 grok_search 不可用、查询为技术文档/百科知识、或只需快速链接时使用。

---

## 搜索策略：优先最新，按需扩大

**核心原则**：凡涉及新闻、时事、动态、价格、发布、事件等有时效性的查询，**先搜最近**，搜不到再扩大范围。不要一开始就用无限制的全局搜索。

---

## 参数速查

| 参数 | 取值 | 说明 |
|------|------|------|
| `search_type` | `"news"` / `"web"` | 新闻/时事用 `news`；文档、代码、百科用 `web` |
| `time_filter` | `"day"` / `"week"` / `"month"` / `"year"` | 结果时间范围；不填则不限制 |
| `region` | `"cn-zh"` / `"us-en"` / `"wt-wt"` | 中文内容用 `cn-zh`；默认全球 |

---

## 搜索升级策略（Escalation）

对于**有时效性**的问题，按以下顺序逐步放宽，找到有效结果即停：

```
第 1 次：search_type="news", time_filter="day"     ← 今日新闻
第 2 次：search_type="news", time_filter="week"    ← 近一周
第 3 次：search_type="news", time_filter="month"   ← 近一个月
第 4 次：search_type="web"（不限时间）              ← 兜底全局
```

**何时判断"无有效结果"**：返回结果少于 2 条，或所有结果标题/摘要与问题无关，则升级到下一档。

---

## 判断是否有时效性

**有时效性**（走升级策略）：
- 新闻事件：战争、灾难、政策、外交、市场行情
- 产品/版本：最新发布、更新日志、价格变动
- 人物动态：声明、任命、逮捕、去世
- 体育/娱乐：比赛结果、上映信息

**无时效性**（直接 `search_type="web"`，不加 `time_filter`）：
- 技术文档、API 参考、库的使用方法
- 历史事件、地理、科学知识
- 编程问题、语法、概念解释

---

## 示例

### 查最新新闻（升级策略）

```json
// 第 1 次
{"query": "伊朗油库 以色列袭击", "search_type": "news", "time_filter": "day"}

// 第 1 次无结果 → 第 2 次
{"query": "伊朗油库 以色列袭击", "search_type": "news", "time_filter": "week"}
```

### 查技术文档（直接全局）

```json
{"query": "Python asyncio event loop tutorial", "search_type": "web"}
```

### 中文新闻（指定区域）

```json
{"query": "A股 今日涨跌", "search_type": "news", "time_filter": "day", "region": "cn-zh"}
```
