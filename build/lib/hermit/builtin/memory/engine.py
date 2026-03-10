from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from hermit.builtin.memory.types import DEFAULT_CATEGORIES, MemoryEntry
from hermit.storage import FileGuard, atomic_write

ENTRY_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\] \[s:(\d+)(🔒?)\] (.+)$")
HEADING_RE = re.compile(r"^## (.+)$")
MergeFn = Callable[[str, List[MemoryEntry]], List[MemoryEntry]]


class MemoryEngine:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Dict[str, List[MemoryEntry]]:
        if not self.path.exists():
            return {category: [] for category in DEFAULT_CATEGORIES}

        categories: Dict[str, List[MemoryEntry]] = {category: [] for category in DEFAULT_CATEGORIES}
        current_category: Optional[str] = None
        for line in self.path.read_text(encoding="utf-8").splitlines():
            heading_match = HEADING_RE.match(line)
            if heading_match:
                current_category = heading_match.group(1)
                categories.setdefault(current_category, [])
                continue
            entry_match = ENTRY_RE.match(line)
            if entry_match and current_category:
                created_at, score, locked, content = entry_match.groups()
                categories[current_category].append(
                    MemoryEntry(
                        category=current_category,
                        content=content,
                        score=int(score),
                        locked=bool(locked),
                        created_at=date.fromisoformat(created_at),
                    )
                )
        return categories

    def save(self, categories: Dict[str, List[MemoryEntry]]) -> None:
        """Atomically overwrite memories.md with *categories*."""
        lines: List[str] = []
        ordered_categories = list(DEFAULT_CATEGORIES)
        ordered_categories.extend(
            category for category in categories if category not in ordered_categories
        )

        for category in ordered_categories:
            entries = categories.get(category, [])
            lines.append(f"## {category}")
            if not entries:
                lines.append("")
                continue
            lines.extend(entry.render() for entry in entries)
            lines.append("")

        atomic_write(self.path, "\n".join(lines).rstrip() + "\n")

    def record_session(
        self,
        new_entries: List[MemoryEntry],
        used_keywords: Optional[Set[str]] = None,
        session_index: int = 1,
        merge_fn: Optional[MergeFn] = None,
        merge_threshold: int = 8,
    ) -> Dict[str, List[MemoryEntry]]:
        """Update memory scores, add new entries, and persist atomically.

        The entire load → modify → save sequence runs under FileGuard so that
        concurrent sessions cannot interleave their writes and lose data.
        cross_process=True also acquires an flock for multi-process safety.
        """
        with FileGuard.acquire(self.path, cross_process=True):
            categories = self.load()
            used_keywords = used_keywords or set()
            lowered_keywords = {keyword.lower() for keyword in used_keywords}

            for category, entries in categories.items():
                slow_decay = category == "项目约定" and session_index % 2 == 0
                for entry in entries:
                    if entry.locked:
                        continue
                    if self._entry_referenced(entry, lowered_keywords):
                        entry.score = min(10, entry.score + 1)
                    elif not slow_decay:
                        entry.score = max(0, entry.score - 1)
                    if entry.score >= 7:
                        entry.locked = True

            filtered: Dict[str, List[MemoryEntry]] = {
                category: [entry for entry in entries if entry.score > 0]
                for category, entries in categories.items()
            }

            for entry in new_entries:
                filtered.setdefault(entry.category, [])
                if not self._is_duplicate(filtered[entry.category], entry.content):
                    filtered[entry.category].append(entry)

            if merge_fn:
                for category, entries in list(filtered.items()):
                    unlocked = [entry for entry in entries if not entry.locked]
                    locked = [entry for entry in entries if entry.locked]
                    if len(unlocked) > merge_threshold:
                        filtered[category] = locked + merge_fn(category, unlocked)

            self.save(filtered)
            return filtered

    @staticmethod
    def summary_prompt(categories: Dict[str, List[MemoryEntry]], limit_per_category: int = 10) -> str:
        lines = ["以下是跨会话记忆，请优先遵循其中的长期约定："]
        for category, entries in categories.items():
            if not entries:
                continue
            lines.append(f"\n## {category}")
            for entry in entries[:limit_per_category]:
                lines.append(entry.render())
        return "\n".join(lines).strip()

    @staticmethod
    def _entry_referenced(entry: MemoryEntry, keywords: Set[str]) -> bool:
        text = entry.content.lower()
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _is_duplicate(entries: List[MemoryEntry], content: str) -> bool:
        normalized = content.strip().lower()
        for existing in entries:
            other = existing.content.strip().lower()
            shorter = min(len(normalized), len(other))
            longer = max(len(normalized), len(other))
            overlap_ratio = shorter / longer if longer else 1
            if normalized == other:
                return True
            if overlap_ratio >= 0.6 and (normalized in other or other in normalized):
                return True
        return False


def group_entries(entries: List[MemoryEntry]) -> Dict[str, List[MemoryEntry]]:
    grouped: Dict[str, List[MemoryEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.category].append(entry)
    return dict(grouped)
