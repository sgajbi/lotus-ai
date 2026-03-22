from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.contracts.retrieval import RetrievalExecutionStage, RetrievalSearchHit

_CATALOG_MINIMUM_SUPPORT_SCORE = 0.75
_INDEXED_MINIMUM_SUPPORT_SCORE = 0.65
_MINIMUM_CITATION_COUNT = 2


@dataclass(frozen=True)
class KnowledgeAnswerSupportAssessment:
    answer_mode: str
    support_score: float
    combined_support_score: float
    minimum_required_score: float
    citation_count: int
    unique_source_count: int
    meets_support_threshold: bool
    refusal_reason: str | None


def assess_knowledge_answer_support(
    *,
    execution_stage: RetrievalExecutionStage,
    hits: Sequence[RetrievalSearchHit],
) -> KnowledgeAnswerSupportAssessment:
    support_score = max((hit.score for hit in hits), default=0.0)
    combined_support_score = round(sum(hit.score for hit in hits[:2]), 6)
    minimum_required_score = (
        _INDEXED_MINIMUM_SUPPORT_SCORE
        if execution_stage == RetrievalExecutionStage.INDEXED_SEARCH
        else _CATALOG_MINIMUM_SUPPORT_SCORE
    )
    citation_count = min(len(hits), _MINIMUM_CITATION_COUNT)
    unique_source_count = len({hit.source_id for hit in hits[:_MINIMUM_CITATION_COUNT]})
    refusal_reason = _build_refusal_reason(
        support_score=support_score,
        minimum_required_score=minimum_required_score,
        citation_count=citation_count,
    )
    return KnowledgeAnswerSupportAssessment(
        answer_mode=(
            "CITATION_BACKED" if refusal_reason is None else "REFUSED_INSUFFICIENT_SUPPORT"
        ),
        support_score=support_score,
        combined_support_score=combined_support_score,
        minimum_required_score=minimum_required_score,
        citation_count=citation_count,
        unique_source_count=unique_source_count,
        meets_support_threshold=refusal_reason is None,
        refusal_reason=refusal_reason,
    )


def select_primary_hits(
    hits: Sequence[RetrievalSearchHit], *, limit: int = 2
) -> list[RetrievalSearchHit]:
    return list(hits[:limit])


def _build_refusal_reason(
    *,
    support_score: float,
    minimum_required_score: float,
    citation_count: int,
) -> str | None:
    if citation_count < _MINIMUM_CITATION_COUNT:
        return "INSUFFICIENT_CITATIONS"
    if support_score < minimum_required_score:
        return "LOW_SUPPORT_SCORE"
    return None
