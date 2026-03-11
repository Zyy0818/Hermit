from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set

import structlog

from hermit.builtin.memory.engine import MemoryEngine
from hermit.builtin.memory.types import MemoryEntry
from hermit.plugin.base import HookEvent, PluginContext
from hermit.provider.services import StructuredExtractionService, build_provider
from hermit.storage import JsonStore

log = structlog.get_logger()

_MAX_TRANSCRIPT_CHARS = 16000
_MAX_MSG_CHARS = 800

_EXTRACTION_PROMPT = """\
你是通用记忆提取助手。从对话中全面提取所有值得长期记忆的信息，不限于技术内容。只输出合法 JSON：
{
  "used_keywords": ["关键词1"],
  "new_memories": [
    {"category": "分类名", "content": "简洁描述"}
  ]
}

## 分类说明
- 用户偏好：沟通习惯、语言偏好、工作风格、审美倾向、常用工具、个人习惯
- 项目约定：项目结构、命名规范、分支策略、部署流程、团队分工、协作规则
- 技术决策：技术选型及理由、架构设计、踩过的坑、性能优化、Bug 修复方案
- 环境与工具：开发环境配置、工具链、API 地址、代理设置、服务端口、安装步骤
- 其他：人物关系、日程习惯、知识见解、任何不属于以上分类但值得记住的信息
- 进行中的任务：明确的待办事项、未完成工作、后续计划

## 提取范围（尽量全面）
- 用户明确表达的偏好、要求、纠正
- 做出的决策及其理由
- 发现的问题及解决方案
- 项目结构、约定、流程的新增或变更
- 具体配置（文件路径、命令、端口、参数名）
- 人物及其职责、项目所属关系
- 反复出现的模式或问题
- 用户提到的日程、计划、习惯
- 学到的经验教训

## 质量要求
- used_keywords：从 <existing_memories> 中找到本次对话涉及的关键词（人名、项目名、技术名词等）
- content 必须简洁自包含，脱离上下文也能理解
- 保留具体细节（路径、命令、参数名），避免泛泛而谈
- 一条记忆只记一件事，不要合并不相关的信息
- 已有记忆中已存在的信息不要重复提取
- 纯粹的闲聊寒暄不需要记忆
- 如无值得记忆的信息，返回空数组"""


def register(ctx: PluginContext) -> None:
    settings = ctx.settings
    if settings is None:
        return

    engine = MemoryEngine(settings.memory_file)
    ctx.add_hook(HookEvent.SYSTEM_PROMPT, lambda: _inject_memory(engine), priority=10)
    ctx.add_hook(
        HookEvent.SESSION_END,
        lambda session_id, messages: _save_memories(engine, settings, session_id, messages),
        priority=90,
    )


def _inject_memory(engine: MemoryEngine) -> str:
    categories = engine.load()
    prompt = engine.summary_prompt(categories)
    if not prompt:
        return ""
    return f"<memory_context>\n{prompt}\n</memory_context>"


def _save_memories(
    engine: MemoryEngine, settings: Any, session_id: str, messages: List[Dict[str, Any]],
) -> None:
    if not messages or not settings.has_auth:
        return
    try:
        _extract_and_save(engine, settings, messages)
    except Exception:
        log.exception("memory_save_failed", session_id=session_id)


def _extract_and_save(
    engine: MemoryEngine, settings: Any, messages: List[Dict[str, Any]],
) -> None:
    transcript = _format_transcript(messages)
    if len(transcript.strip()) < 20:
        return

    existing = engine.load()
    existing_text = engine.summary_prompt(existing)

    user_content = (
        f"<existing_memories>\n{existing_text}\n</existing_memories>\n\n"
        f"<conversation>\n{transcript}\n</conversation>"
    )

    provider = build_provider(settings, model=settings.model)
    service = StructuredExtractionService(provider, model=settings.model)
    data = service.extract_json(
        system_prompt=_EXTRACTION_PROMPT,
        user_content=user_content,
        max_tokens=2048,
    )
    if not data:
        return

    used_keywords: Set[str] = set(data.get("used_keywords", []))
    new_entries: List[MemoryEntry] = []
    for item in data.get("new_memories", []):
        content = item.get("content", "").strip()
        if content:
            new_entries.append(MemoryEntry(
                category=item.get("category", "其他"),
                content=content,
            ))

    if not new_entries and not used_keywords:
        log.info("memory_nothing_to_save")
        return

    session_idx = _bump_session_index(settings.session_state_file)
    engine.record_session(
        new_entries=new_entries,
        used_keywords=used_keywords,
        session_index=session_idx,
    )
    log.info("memories_saved", new=len(new_entries), keywords=len(used_keywords))


# ── helpers ──────────────────────────────────────────────


def _format_transcript(messages: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    total = 0
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")

        if isinstance(content, list):
            parts: List[str] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", "")[:_MAX_MSG_CHARS])
                elif btype == "tool_use":
                    inp = json.dumps(block.get("input", {}), ensure_ascii=False)[:120]
                    parts.append(f"[Tool: {block.get('name', '')}({inp})]")
                elif btype == "tool_result":
                    parts.append(f"[Tool Result: {str(block.get('content', ''))[:200]}]")
            text = "\n".join(parts)
        elif isinstance(content, str):
            text = content[:_MAX_MSG_CHARS]
        else:
            text = str(content)[:_MAX_MSG_CHARS] if content else ""

        if not text.strip():
            continue

        label = {"user": "User", "assistant": "Assistant"}.get(role, role)
        entry = f"[{label}] {text}"
        total += len(entry)
        if total > _MAX_TRANSCRIPT_CHARS:
            lines.append("[... conversation truncated ...]")
            break
        lines.append(entry)

    return "\n\n".join(lines)

def _parse_json(text: str) -> Any:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for suffix in ("}", "]}", "]}"):
            try:
                return json.loads(cleaned + suffix)
            except json.JSONDecodeError:
                continue
        log.warning("memory_json_parse_failed", text=text[:200])
        return None


def _bump_session_index(state_file: Path) -> int:
    """Atomically increment session_index and return the new value.

    Uses JsonStore.update() to eliminate the read-modify-write TOCTOU race:
    the lock is held for the entire read → increment → write sequence.
    """
    store = JsonStore(state_file, default={"session_index": 0}, cross_process=True)
    try:
        with store.update() as data:
            idx = data.get("session_index", 0) + 1
            data["session_index"] = idx
        return idx
    except Exception:
        log.warning("session_state_update_failed")
        return 1
