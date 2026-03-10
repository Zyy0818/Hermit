from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

from hermit.builtin.memory.engine import MemoryEngine
from hermit.builtin.memory.hooks import (
    _bump_session_index,
    _format_transcript,
    _parse_json,
)
from hermit.builtin.memory.types import MemoryEntry


def test_memory_engine_save_and_load(tmp_path) -> None:
    path = tmp_path / "memories.md"
    engine = MemoryEngine(path)
    source = {
        "用户偏好": [
            MemoryEntry(
                category="用户偏好",
                content="所有回答使用简体中文",
                score=8,
                locked=True,
                created_at=date(2026, 3, 9),
            )
        ]
    }

    engine.save(source)
    loaded = engine.load()

    assert loaded["用户偏好"][0].content == "所有回答使用简体中文"
    assert loaded["用户偏好"][0].locked is True


def test_memory_engine_record_session_applies_decay_and_reference_boost(tmp_path) -> None:
    path = tmp_path / "memories.md"
    engine = MemoryEngine(path)
    engine.save(
        {
            "技术决策": [
                MemoryEntry(category="技术决策", content="SQLite 适合 Agent 记忆", score=5),
                MemoryEntry(category="技术决策", content="ChromaDB 对 MVP 过重", score=5),
            ]
        }
    )

    updated = engine.record_session(
        new_entries=[],
        used_keywords={"SQLite"},
        session_index=1,
    )

    assert updated["技术决策"][0].score == 6
    assert updated["技术决策"][1].score == 4


def test_memory_engine_prevents_substring_duplicates(tmp_path) -> None:
    path = tmp_path / "memories.md"
    engine = MemoryEngine(path)
    engine.save(
        {
            "项目约定": [
                MemoryEntry(category="项目约定", content="H5Bridge 需兼容客户端参数"),
            ]
        }
    )

    updated = engine.record_session(
        new_entries=[MemoryEntry(category="项目约定", content="H5Bridge 需兼容客户端参数")],
        session_index=1,
    )

    assert len(updated["项目约定"]) == 1


def test_memory_engine_uses_merge_function_when_threshold_exceeded(tmp_path) -> None:
    path = tmp_path / "memories.md"
    engine = MemoryEngine(path)
    engine.save(
        {
            "其他": [MemoryEntry(category="其他", content=f"entry-{index}", score=5) for index in range(9)]
        }
    )

    merged = engine.record_session(
        new_entries=[],
        session_index=1,
        merge_threshold=8,
        merge_fn=lambda category, entries: [MemoryEntry(category=category, content="merged", score=6)],
    )

    assert [entry.content for entry in merged["其他"]] == ["merged"]


# ── hooks helper tests ──────────────────────────────────


def test_format_transcript_handles_mixed_content() -> None:
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": [
            {"type": "text", "text": "Let me search."},
            {"type": "tool_use", "name": "web_search", "input": {"query": "test"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "x", "content": "result data"},
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": "Here you go."}]},
    ]
    result = _format_transcript(messages)
    assert "[User] Hello" in result
    assert "[Tool: web_search" in result
    assert "[Tool Result:" in result
    assert "[Assistant] Here you go." in result


def test_format_transcript_truncates_long_conversations() -> None:
    messages = [{"role": "user", "content": "x" * 800} for _ in range(30)]
    result = _format_transcript(messages)
    assert "[... conversation truncated ...]" in result


def test_parse_json_handles_clean_json() -> None:
    assert _parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_strips_markdown_fences() -> None:
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_fixes_truncated_json() -> None:
    result = _parse_json('{"used_keywords": ["hello"]')
    assert result is not None
    assert result["used_keywords"] == ["hello"]


def test_parse_json_returns_none_on_garbage() -> None:
    assert _parse_json("not json at all") is None


def test_bump_session_index_initializes_and_increments(tmp_path) -> None:
    state_file = tmp_path / "session_state.json"
    assert _bump_session_index(state_file) == 1
    assert _bump_session_index(state_file) == 2
    assert _bump_session_index(state_file) == 3
    data = json.loads(state_file.read_text())
    assert data["session_index"] == 3
