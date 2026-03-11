from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import structlog

from hermit.builtin.memory.engine import MemoryEngine
from hermit.builtin.memory.types import MemoryEntry
from hermit.plugin.base import HookEvent, PluginContext
from hermit.provider.services import StructuredExtractionService, build_provider
from hermit.storage import JsonStore

log = structlog.get_logger()

_MAX_TRANSCRIPT_CHARS = 16000
_MAX_MSG_CHARS = 800
_CHECKPOINT_MIN_CHARS = 300
_CHECKPOINT_MIN_MESSAGES = 6
_CHECKPOINT_MIN_USER_MESSAGES = 2

_EXPLICIT_MEMORY_RE = re.compile(
    r"(记住|牢记|以后都|今后都|统一使用|统一回复|不要再|必须|务必|偏好|约定|规则|规范|"
    r"always|never|remember this|preference|rule|policy|convention)",
    re.IGNORECASE,
)
_DECISION_SIGNAL_RE = re.compile(
    r"(决定|改为|采用|切换到|标准化|规范为|路径|端口|分支|部署|"
    r"decided|switch to|migrate to|branch\b|port\b|deploy)",
    re.IGNORECASE,
)

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
        HookEvent.PRE_RUN,
        lambda prompt, **kwargs: _inject_relevant_memory(engine, prompt),
        priority=15,
    )
    ctx.add_hook(
        HookEvent.POST_RUN,
        lambda result, session_id="", **kwargs: _checkpoint_memories(
            engine,
            settings,
            session_id,
            getattr(result, "messages", []) or [],
        ),
        priority=20,
    )
    ctx.add_hook(
        HookEvent.SESSION_END,
        lambda session_id, messages: _save_memories(engine, settings, session_id, messages),
        priority=90,
    )


def _inject_memory(engine: MemoryEngine) -> str:
    categories = engine.load()
    prompt = engine.summary_prompt(categories, limit_per_category=3)
    if not prompt:
        log.info("memory_injected", categories=0, entries=0)
        return ""
    entry_count = sum(min(3, len(entries)) for entries in categories.values() if entries)
    category_count = sum(1 for entries in categories.values() if entries)
    log.info("memory_injected", categories=category_count, entries=entry_count)
    return f"<memory_context>\n{prompt}\n</memory_context>"


def _inject_relevant_memory(engine: MemoryEngine, prompt: str) -> str:
    relevant = engine.retrieval_prompt(prompt, limit=5, char_budget=900)
    if not relevant:
        return prompt
    return f"<relevant_memory>\n{relevant}\n</relevant_memory>\n\n{prompt}"


def _save_memories(
    engine: MemoryEngine,
    settings: Any,
    session_id: str,
    messages: List[Dict[str, Any]],
) -> None:
    if not messages:
        log.info("memory_save_skipped", session_id=session_id, reason="no_messages")
        return
    if not settings.has_auth:
        log.info("memory_save_skipped", session_id=session_id, reason="no_auth")
        return
    try:
        _extract_and_save(engine, settings, messages)
    except Exception:
        log.exception("memory_save_failed", session_id=session_id)
    finally:
        _clear_session_progress(settings.session_state_file, session_id)


def _checkpoint_memories(
    engine: MemoryEngine,
    settings: Any,
    session_id: str,
    messages: List[Dict[str, Any]],
) -> None:
    if not session_id:
        log.info("memory_checkpoint_skipped", reason="missing_session_id")
        return
    if session_id == "cli-oneshot":
        log.info("memory_checkpoint_skipped", session_id=session_id, reason="cli_oneshot")
        return
    if not messages:
        log.info("memory_checkpoint_skipped", session_id=session_id, reason="no_messages")
        return
    if not settings.has_auth:
        log.info("memory_checkpoint_skipped", session_id=session_id, reason="no_auth")
        return

    delta, processed = _pending_messages(settings.session_state_file, session_id, messages)
    if not delta:
        log.info("memory_checkpoint_skipped", session_id=session_id, reason="no_pending_delta")
        return

    should_checkpoint, reason = _should_checkpoint(delta)
    if not should_checkpoint:
        log.info("memory_checkpoint_skipped", session_id=session_id, reason=reason, pending_messages=len(delta))
        return

    try:
        extraction = _extract_memory_payload(engine, settings, delta, max_tokens=1024)
    except Exception:
        log.exception("memory_checkpoint_failed", session_id=session_id, reason=reason)
        return

    new_entries = extraction["new_entries"]
    if not new_entries:
        log.info(
            "memory_checkpoint_no_entries",
            session_id=session_id,
            reason=reason,
            pending_messages=len(delta),
        )
        return

    engine.append_entries(new_entries)
    _mark_messages_processed(settings.session_state_file, session_id, len(messages))
    log.info(
        "memory_checkpoint_saved",
        session_id=session_id,
        reason=reason,
        new=len(new_entries),
        processed_before=processed,
        processed_after=len(messages),
    )


def _extract_and_save(engine: MemoryEngine, settings: Any, messages: List[Dict[str, Any]]) -> None:
    log.info("memory_extraction_started", mode="session_end", message_count=len(messages))
    extraction = _extract_memory_payload(engine, settings, messages, max_tokens=2048)
    used_keywords = extraction["used_keywords"]
    new_entries = extraction["new_entries"]

    if not new_entries and not used_keywords:
        log.info("memory_nothing_to_save")
        return

    session_idx = _bump_session_index(settings.session_state_file)
    before = engine.load()
    engine.record_session(
        new_entries=new_entries,
        used_keywords=used_keywords,
        session_index=session_idx,
        merge_fn=_consolidate_category_entries,
        merge_threshold=6,
    )
    after = engine.load()
    before_total = sum(len(entries) for entries in before.values())
    after_total = sum(len(entries) for entries in after.values())
    if after_total < before_total + len(new_entries):
        log.info(
            "memory_consolidated",
            before=before_total,
            after=after_total,
            merged=max(0, before_total + len(new_entries) - after_total),
        )
    log.info("memories_saved", new=len(new_entries), keywords=len(used_keywords))


def _extract_memory_payload(
    engine: MemoryEngine,
    settings: Any,
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int,
) -> Dict[str, Any]:
    transcript = _format_transcript(messages)
    if len(transcript.strip()) < 20:
        log.info("memory_extraction_empty", reason="short_transcript", transcript_chars=len(transcript))
        return {"used_keywords": set(), "new_entries": []}

    existing = engine.load()
    existing_text = engine.summary_prompt(existing)
    user_content = (
        f"<existing_memories>\n{existing_text}\n</existing_memories>\n\n"
        f"<conversation>\n{transcript}\n</conversation>"
    )

    log.info(
        "memory_extraction_started",
        mode="checkpoint" if max_tokens <= 1024 else "session_end",
        message_count=len(messages),
        transcript_chars=len(transcript),
        existing_chars=len(existing_text),
        max_tokens=max_tokens,
    )
    provider = build_provider(settings, model=settings.model)
    service = StructuredExtractionService(provider, model=settings.model)
    data = service.extract_json(
        system_prompt=_EXTRACTION_PROMPT,
        user_content=user_content,
        max_tokens=max_tokens,
    )
    if not data:
        log.info("memory_extraction_empty", reason="no_provider_data", transcript_chars=len(transcript))
        return {"used_keywords": set(), "new_entries": []}

    used_keywords: Set[str] = set(data.get("used_keywords", []))
    new_entries: List[MemoryEntry] = []
    for item in data.get("new_memories", []):
        content = item.get("content", "").strip()
        if content:
            new_entries.append(MemoryEntry(
                category=item.get("category", "其他"),
                content=content,
                confidence=_infer_confidence(content),
            ))
    log.info(
        "memory_extraction_result",
        used_keywords=len(used_keywords),
        new_entries=len(new_entries),
        categories=len({entry.category for entry in new_entries}),
    )
    return {"used_keywords": used_keywords, "new_entries": new_entries}


def _consolidate_category_entries(category: str, entries: List[MemoryEntry]) -> List[MemoryEntry]:
    consolidated: List[MemoryEntry] = []
    for entry in sorted(
        entries,
        key=lambda item: (item.updated_at, item.created_at, item.score, item.confidence),
        reverse=True,
    ):
        merged = False
        for existing in consolidated:
            if not _should_merge_entries(existing, entry):
                continue
            existing.score = max(existing.score, entry.score)
            existing.confidence = max(existing.confidence, entry.confidence)
            existing.updated_at = max(existing.updated_at, entry.updated_at, entry.created_at)
            if entry.content != existing.content and entry.content not in existing.supersedes:
                existing.supersedes.append(entry.content)
            for value in entry.supersedes:
                if value not in existing.supersedes:
                    existing.supersedes.append(value)
            merged = True
            break
        if not merged:
            consolidated.append(entry)
    return consolidated


def _should_merge_entries(left: MemoryEntry, right: MemoryEntry) -> bool:
    if left.category != right.category:
        return False
    if MemoryEngine._is_duplicate([left], right.content):
        return True
    return MemoryEngine._shares_topic(left.content, right.content)


def _infer_confidence(content: str) -> float:
    strong_signal = ("必须", "务必", "统一", "默认", "固定", "不要", "采用", "改为")
    if any(signal in content for signal in strong_signal):
        return 0.8
    if len(content) >= 20:
        return 0.65
    return 0.55


def _should_checkpoint(messages: List[Dict[str, Any]]) -> Tuple[bool, str]:
    user_text = _collect_role_text(messages, "user")
    assistant_text = _collect_role_text(messages, "assistant")
    transcript = _format_transcript(messages)
    meaningful_count = sum(1 for msg in messages if _message_text(msg).strip())
    user_count = sum(1 for msg in messages if msg.get("role") == "user" and _message_text(msg).strip())

    if _EXPLICIT_MEMORY_RE.search(user_text):
        return True, "explicit_memory_signal"
    if _DECISION_SIGNAL_RE.search(user_text) or _DECISION_SIGNAL_RE.search(assistant_text):
        return True, "decision_signal"
    if len(transcript) >= _CHECKPOINT_MIN_CHARS and user_count >= _CHECKPOINT_MIN_USER_MESSAGES:
        return True, "conversation_batch"
    if meaningful_count >= _CHECKPOINT_MIN_MESSAGES:
        return True, "message_batch"
    return False, "below_threshold"


def _pending_messages(
    state_file: Path,
    session_id: str,
    messages: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    data = _read_state(state_file)
    sessions = data.get("sessions", {})
    meta = sessions.get(session_id, {}) if isinstance(sessions, dict) else {}
    processed = int(meta.get("processed_messages", 0))
    if processed < 0:
        processed = 0
    return messages[processed:], processed


def _mark_messages_processed(state_file: Path, session_id: str, count: int) -> None:
    store = JsonStore(state_file, default={"session_index": 0, "sessions": {}}, cross_process=True)
    with store.update() as data:
        sessions = data.setdefault("sessions", {})
        if not isinstance(sessions, dict):
            sessions = {}
            data["sessions"] = sessions
        meta = sessions.get(session_id)
        if not isinstance(meta, dict):
            meta = {}
            sessions[session_id] = meta
        meta["processed_messages"] = max(0, int(count))


def _clear_session_progress(state_file: Path, session_id: str) -> None:
    if not session_id:
        return
    store = JsonStore(state_file, default={"session_index": 0, "sessions": {}}, cross_process=True)
    with store.update() as data:
        sessions = data.get("sessions", {})
        if isinstance(sessions, dict):
            sessions.pop(session_id, None)


def _read_state(state_file: Path) -> Dict[str, Any]:
    return JsonStore(
        state_file,
        default={"session_index": 0, "sessions": {}},
        cross_process=True,
    ).read()


def _format_transcript(messages: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    total = 0
    for msg in messages:
        role = msg.get("role", "unknown")
        text = _message_text(msg)

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


def _message_text(msg: Dict[str, Any]) -> str:
    content = msg.get("content", "")
    if isinstance(content, str):
        return content[:_MAX_MSG_CHARS]
    if not isinstance(content, list):
        return str(content)[:_MAX_MSG_CHARS] if content else ""

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
    return "\n".join(parts).strip()


def _collect_role_text(messages: List[Dict[str, Any]], role: str) -> str:
    return "\n".join(
        _message_text(msg) for msg in messages if msg.get("role") == role
    ).strip()


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
    store = JsonStore(
        state_file,
        default={"session_index": 0, "sessions": {}},
        cross_process=True,
    )
    try:
        with store.update() as data:
            idx = data.get("session_index", 0) + 1
            data["session_index"] = idx
        return idx
    except Exception:
        log.warning("session_state_update_failed")
        return 1
