from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from hermit.builtin.memory.engine import MemoryEngine
from hermit.kernel.models import ConversationRecord, TaskRecord

_BRANCH_MARKERS = (
    "顺便",
    "另外",
    "再查一下",
    "再问一下",
    "顺手",
)
_CONTINUE_MARKERS = (
    "继续",
    "接着",
    "然后",
    "补充",
    "补充一点",
    "补充说明",
    "说明",
    "加上",
    "再加",
    "改成",
    "改为",
    "放到",
    "发到",
    "写到",
    "去掉",
    "删掉",
    "保留",
    "就按",
    "按照",
    "extra note",
    "follow up",
)
_AMBIGUOUS_MARKERS = (
    "这个",
    "那个",
    "这份",
    "这条",
    "上面",
    "上一条",
    "刚才",
)


@dataclass(frozen=True)
class CandidateScore:
    task_id: str
    score: float
    reason_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BindingDecision:
    resolution: Literal[
        "control",
        "approval",
        "append_note",
        "fork_child",
        "start_new_root",
        "chat_only",
        "pending_disambiguation",
    ]
    chosen_task_id: str | None = None
    parent_task_id: str | None = None
    confidence: float = 0.0
    margin: float = 0.0
    candidates: list[CandidateScore] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)


class IngressRouter:
    def __init__(self, store: Any) -> None:
        self.store = store

    def bind(
        self,
        *,
        conversation: ConversationRecord | None,
        open_tasks: list[TaskRecord],
        normalized_text: str,
        explicit_task_ref: str | None = None,
        reply_to_task_id: str | None = None,
        pending_approval_task_id: str | None = None,
    ) -> BindingDecision:
        cleaned = self._normalize(normalized_text)
        if explicit_task_ref:
            return BindingDecision(
                resolution="append_note",
                chosen_task_id=explicit_task_ref,
                confidence=1.0,
                margin=1.0,
                reason_codes=["explicit_task_ref"],
            )
        if reply_to_task_id:
            return BindingDecision(
                resolution="append_note",
                chosen_task_id=reply_to_task_id,
                confidence=1.0,
                margin=1.0,
                reason_codes=["reply_target"],
            )
        if pending_approval_task_id and self._looks_like_approval_followup(cleaned):
            return BindingDecision(
                resolution="append_note",
                chosen_task_id=pending_approval_task_id,
                confidence=0.98,
                margin=0.98,
                reason_codes=["pending_approval_correlation"],
            )
        if not open_tasks:
            return BindingDecision(
                resolution="start_new_root",
                confidence=0.2,
                reason_codes=["no_open_tasks"],
            )
        if conversation is not None and conversation.focus_task_id and self._looks_like_focus_followup(cleaned):
            return BindingDecision(
                resolution="append_note",
                chosen_task_id=conversation.focus_task_id,
                confidence=0.92,
                margin=0.92,
                reason_codes=["focus_followup_marker"],
            )

        scored: list[CandidateScore] = []
        focus_task_id = conversation.focus_task_id if conversation is not None else None
        for task in open_tasks:
            score, reasons = self._score_task(task, cleaned, focus_task_id=focus_task_id)
            if score <= 0:
                continue
            scored.append(CandidateScore(task_id=task.task_id, score=score, reason_codes=reasons))
        scored.sort(key=lambda item: item.score, reverse=True)

        if self._has_branch_marker(cleaned):
            parent = focus_task_id or (scored[0].task_id if scored else open_tasks[0].task_id)
            return BindingDecision(
                resolution="fork_child",
                parent_task_id=parent,
                confidence=0.72 if scored else 0.6,
                margin=(scored[0].score - scored[1].score) if len(scored) > 1 else (scored[0].score if scored else 0.0),
                candidates=scored[:5],
                reason_codes=["branch_marker"],
            )

        if not scored:
            return BindingDecision(
                resolution="start_new_root",
                confidence=0.35,
                candidates=[],
                reason_codes=["no_candidate_match"],
            )

        best = scored[0]
        runner_up = scored[1] if len(scored) > 1 else None
        margin = best.score - runner_up.score if runner_up is not None else best.score
        if best.score >= 0.95 and margin >= 0.05:
            return BindingDecision(
                resolution="append_note",
                chosen_task_id=best.task_id,
                confidence=min(1.0, best.score),
                margin=margin,
                candidates=scored[:5],
                reason_codes=list(best.reason_codes),
            )
        if best.score >= 0.75 and margin < 0.05:
            return BindingDecision(
                resolution="pending_disambiguation",
                confidence=best.score,
                margin=margin,
                candidates=scored[:5],
                reason_codes=["ambiguous_top_candidates"],
            )
        if best.score >= 0.8:
            return BindingDecision(
                resolution="append_note",
                chosen_task_id=best.task_id,
                confidence=best.score,
                margin=margin,
                candidates=scored[:5],
                reason_codes=list(best.reason_codes),
            )
        return BindingDecision(
            resolution="start_new_root",
            confidence=0.4,
            margin=margin,
            candidates=scored[:5],
            reason_codes=["weak_candidate_match"],
        )

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(str(text or "").split()).strip()

    @staticmethod
    def _looks_like_approval_followup(text: str) -> bool:
        return any(marker in text for marker in ("执行", "批准", "approve", "草稿", "不要发", "改成"))

    @staticmethod
    def _looks_like_focus_followup(text: str) -> bool:
        return any(marker in text for marker in _CONTINUE_MARKERS) or any(
            marker in text for marker in _AMBIGUOUS_MARKERS
        )

    @staticmethod
    def _has_branch_marker(text: str) -> bool:
        return any(marker in text for marker in _BRANCH_MARKERS)

    def _score_task(self, task: TaskRecord, text: str, *, focus_task_id: str | None) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if focus_task_id and task.task_id == focus_task_id:
            score += 0.35
            reasons.append("focus_task")
        context_texts = [str(task.title or ""), str(task.goal or "")]
        for event in reversed(self.store.list_events(task_id=task.task_id, limit=50)):
            if event["event_type"] != "task.note.appended":
                continue
            payload = dict(event["payload"] or {})
            note_text = str(payload.get("inline_excerpt") or payload.get("raw_text") or "").strip()
            if note_text:
                context_texts.append(note_text)
            if len(context_texts) >= 6:
                break
        query_tokens = {token for token in MemoryEngine._topic_tokens(text) if len(token) >= 2}
        has_continue_marker = any(marker in text for marker in _CONTINUE_MARKERS)
        has_ambiguous_marker = any(marker in text for marker in _AMBIGUOUS_MARKERS)
        if has_continue_marker:
            score += 0.2
            reasons.append("continue_marker")
        if has_ambiguous_marker:
            score += 0.15
            reasons.append("ambiguous_marker")
        for candidate_text in context_texts:
            if not candidate_text:
                continue
            if MemoryEngine._shares_topic(candidate_text, text):
                score += 0.35
                reasons.append("topic_overlap")
                break
            candidate_tokens = {token for token in MemoryEngine._topic_tokens(candidate_text) if len(token) >= 2}
            if query_tokens & candidate_tokens:
                score += 0.3
                reasons.append("token_overlap")
                break
            if any(token in candidate_text for token in query_tokens):
                score += 0.2
                reasons.append("substring_overlap")
                break
        return min(score, 1.0), reasons


__all__ = ["BindingDecision", "CandidateScore", "IngressRouter"]
