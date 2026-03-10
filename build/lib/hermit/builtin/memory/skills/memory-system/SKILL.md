---
name: memory-system
description: Explains how Hermit's cross-session memory works — automatic saving, scoring, decay, and how to interact with it. Read this when the user asks about memory, asks why something wasn't remembered, or when deciding whether to manually write to memories.md.
---

## How Memory Works

Hermit memory is **automatic and score-based**. You do not need to manually write to `memories.md` after each conversation — a built-in plugin handles extraction and saving at session end.

### The Automatic Pipeline

```
Session ends (close_session called)
  └── SESSION_END hook fires
        └── _save_memories() runs
              ├── Formats the conversation transcript (up to 16 000 chars)
              ├── Calls Claude API with an extraction prompt
              ├── Receives JSON: { new_memories, used_keywords }
              └── Calls engine.record_session() → saves to memories.md
```

### When SESSION_END Fires (memories save)

| Scenario | Saves? |
|---|---|
| `hermit run "..."` completes normally | ✅ |
| `hermit chat` exits via `/quit` or Ctrl+C at the input prompt | ✅ |
| `hermit chat` `/new` resets the session | ✅ |
| `hermit serve --adapter feishu` — session idle past timeout | ✅ (swept every 5 min) |
| `hermit serve --adapter feishu` — adapter stops (Ctrl+C) | ✅ (flush on stop) |
| Process killed with SIGKILL | ❌ no graceful close |

### The Score System

Every memory entry has a score (0–10):

| Event | Score change |
|---|---|
| New entry | starts at **5** |
| Keyword from this session matches the entry | **+1** (max 10) |
| Not referenced this session | **−1** (min 0) |
| Score reaches **7** | **locked** 🔒 — never decayed or deleted |
| Score reaches **0** | **deleted** on next save |
| Category "项目约定" | slow decay: −1 every **2 sessions** instead of every session |

### What's Injected at Startup

At startup, the memory plugin injects a `<memory_context>` block into your system prompt — up to 10 entries per category. This is what you see when the session begins. It reflects the state of `memories.md` **at the time the session started**, not the current moment.

---

## How to Interact with Memory

### ✅ Trust the automatic pipeline

For most conversations, do nothing special. The extraction LLM will identify what's worth remembering and write it at session end.

### ✅ Use `write_hermit_file` for immediate, urgent facts

When the user says "remember this permanently" or you learn something critical mid-session that you want to guarantee survives (e.g. a new API key location, an important rule), write it directly:

```
write_hermit_file(path="memory/memories.md", ...)
```

Read the current file first (`read_hermit_file`), then append the new entry in the correct format:

```
- [YYYY-MM-DD] [s:8🔒] Your memory content here.
```

Use score **8🔒** for facts the user explicitly asked to lock in. Use **5** for ordinary new entries.

### ❌ Don't rewrite the entire file

Never overwrite the whole `memories.md`. Always append or edit individual lines. Rewriting destroys scores and locked entries.

### ✅ Read memories.md when asked about memory state

When the user asks "what do you remember about X?" or "why didn't you remember Y?", use `read_hermit_file(path="memory/memories.md")` to inspect the current file directly — the startup `<memory_context>` may be stale if many sessions have passed.

---

## Why the Agent May Not Remember Something

1. **Score decayed to 0** — the entry wasn't referenced in enough sessions
2. **Session ended abnormally** — process killed with SIGKILL, no SESSION_END fired
3. **`has_auth` was False** — extraction LLM call skipped silently
4. **Extraction LLM missed it** — the entry wasn't prominent enough in the transcript
5. **Startup context is stale** — the `<memory_context>` shown at session start reflects an older snapshot; read the file directly for the current state

---

## The memories.md Format

```markdown
## 用户偏好

- [2026-03-09] [s:8🔒] 用户偏好中文回答。

## 技术决策

- [2026-03-09] [s:5] pydantic-settings 使用 model_config 加载 .env 文件。

## 项目约定

- [2026-03-09] [s:6] feat/expert-app 分支负责 H5 侧 Expert JSBridge 集成。
```

Categories (in order): 用户偏好 / 技术决策 / 项目约定 / 环境与工具 / 人物与职责 / 其他 / 进行中的任务
