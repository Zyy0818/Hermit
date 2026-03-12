from __future__ import annotations

import time
from pathlib import Path

from hermit.builtin.memory.engine import MemoryEngine
from hermit.builtin.memory.types import MemoryEntry
from hermit.kernel.models import BeliefRecord, MemoryRecord
from hermit.kernel.store import KernelStore


class BeliefService:
    def __init__(self, store: KernelStore) -> None:
        self.store = store

    def record(
        self,
        *,
        task_id: str,
        conversation_id: str | None,
        scope_kind: str,
        scope_ref: str,
        category: str,
        content: str,
        confidence: float,
        evidence_refs: list[str],
        trust_tier: str = "observed",
        supersedes: list[str] | None = None,
        contradicts: list[str] | None = None,
    ) -> BeliefRecord:
        return self.store.create_belief(
            task_id=task_id,
            conversation_id=conversation_id,
            scope_kind=scope_kind,
            scope_ref=scope_ref,
            category=category,
            content=content,
            confidence=confidence,
            trust_tier=trust_tier,
            evidence_refs=evidence_refs,
            supersedes=supersedes,
            contradicts=contradicts,
        )

    def supersede(self, belief_id: str, superseded_contents: list[str]) -> None:
        self.store.update_belief(belief_id, status="superseded", supersedes=superseded_contents)

    def contradict(self, belief_id: str, contradicting_ids: list[str]) -> None:
        self.store.update_belief(belief_id, status="contradicted", contradicts=contradicting_ids)

    def invalidate(self, belief_id: str) -> None:
        self.store.update_belief(belief_id, status="invalidated", invalidated_at=time.time())


class MemoryRecordService:
    def __init__(self, store: KernelStore, *, mirror_path: Path | None = None) -> None:
        self.store = store
        self.mirror_path = mirror_path

    def bootstrap_from_markdown(self, path: Path | None = None) -> bool:
        mirror = path or self.mirror_path
        if mirror is None or not mirror.exists():
            return False
        if self.store.list_memory_records(limit=1):
            return False
        engine = MemoryEngine(mirror)
        imported = False
        for category, entries in engine.load().items():
            for entry in entries:
                self.store.create_memory_record(
                    task_id="memory_bootstrap",
                    conversation_id=None,
                    category=category,
                    content=entry.content,
                    status="active",
                    confidence=entry.confidence,
                    trust_tier="bootstrap",
                    evidence_refs=[],
                    supersedes=list(entry.supersedes),
                )
                imported = True
        if imported:
            self.render_mirror(mirror)
        return imported

    def promote_from_belief(
        self,
        *,
        belief: BeliefRecord,
        conversation_id: str | None,
    ) -> MemoryRecord:
        existing = self.store.list_memory_records(status="active", conversation_id=conversation_id, limit=500)
        superseded_records: list[MemoryRecord] = []
        for record in existing:
            if record.category != belief.category:
                continue
            if MemoryEngine._is_duplicate([self._entry_from_memory(record)], belief.content):
                return record
            if MemoryEngine._shares_topic(record.content, belief.content):
                superseded_records.append(record)
        supersedes = [record.content for record in superseded_records]
        memory = self.store.create_memory_record(
            task_id=belief.task_id,
            conversation_id=conversation_id,
            category=belief.category,
            content=belief.content,
            status="active",
            confidence=belief.confidence,
            trust_tier="durable",
            evidence_refs=list(belief.evidence_refs),
            supersedes=supersedes,
            source_belief_ref=belief.belief_id,
        )
        self.store.update_belief(belief.belief_id, memory_ref=memory.memory_id)
        for record in superseded_records:
            self.store.update_memory_record(
                record.memory_id,
                status="superseded",
                supersedes=list({*record.supersedes, memory.content}),
            )
        return memory

    def invalidate(self, memory_id: str) -> None:
        self.store.update_memory_record(memory_id, status="invalidated", invalidated_at=time.time())

    def render_mirror(self, path: Path | None = None) -> None:
        mirror = path or self.mirror_path
        if mirror is None:
            return
        engine = MemoryEngine(mirror)
        categories: dict[str, list[MemoryEntry]] = {}
        for record in self.store.list_memory_records(status="active", limit=1000):
            categories.setdefault(record.category, []).append(self._entry_from_memory(record))
        engine.save(categories)

    def active_categories(self, *, conversation_id: str | None = None) -> dict[str, list[MemoryEntry]]:
        categories: dict[str, list[MemoryEntry]] = {}
        for record in self.store.list_memory_records(status="active", conversation_id=conversation_id, limit=1000):
            categories.setdefault(record.category, []).append(self._entry_from_memory(record))
        return categories

    @staticmethod
    def _entry_from_memory(record: MemoryRecord) -> MemoryEntry:
        return MemoryEntry(
            category=record.category,
            content=record.content,
            score=8 if record.trust_tier in {"durable", "bootstrap"} else 5,
            locked=record.trust_tier in {"durable", "bootstrap"},
            confidence=record.confidence,
            supersedes=list(record.supersedes),
        )
