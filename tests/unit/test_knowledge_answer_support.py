from app.contracts.retrieval import RetrievalExecutionStage, RetrievalSearchHit
from app.services.knowledge_answer_support import assess_knowledge_answer_support


def _hit(*, source_id: str, score: float, suffix: str) -> RetrievalSearchHit:
    return RetrievalSearchHit(
        source_id=source_id,
        document_id=f"doc-{suffix}",
        chunk_id=f"chunk-{suffix}",
        score=score,
        snippet=f"snippet-{suffix}",
    )


def test_assess_knowledge_answer_support_accepts_indexed_multi_citation_result() -> None:
    assessment = assess_knowledge_answer_support(
        execution_stage=RetrievalExecutionStage.INDEXED_SEARCH,
        hits=[
            _hit(source_id="lotus-platform-rfcs", score=0.74, suffix="1"),
            _hit(source_id="lotus-ai-architecture", score=0.68, suffix="2"),
        ],
    )

    assert assessment.answer_mode == "CITATION_BACKED"
    assert assessment.meets_support_threshold is True
    assert assessment.refusal_reason is None
    assert assessment.citation_count == 2
    assert assessment.unique_source_count == 2
    assert assessment.minimum_required_score == 0.65


def test_assess_knowledge_answer_support_refuses_low_support_catalog_result() -> None:
    assessment = assess_knowledge_answer_support(
        execution_stage=RetrievalExecutionStage.CATALOG_ONLY,
        hits=[
            _hit(source_id="lotus-platform-rfcs", score=0.6, suffix="1"),
            _hit(source_id="lotus-platform-rfcs", score=0.3, suffix="2"),
        ],
    )

    assert assessment.answer_mode == "REFUSED_INSUFFICIENT_SUPPORT"
    assert assessment.meets_support_threshold is False
    assert assessment.refusal_reason == "LOW_SUPPORT_SCORE"
    assert assessment.minimum_required_score == 0.75


def test_assess_knowledge_answer_support_refuses_when_too_few_citations() -> None:
    assessment = assess_knowledge_answer_support(
        execution_stage=RetrievalExecutionStage.INDEXED_SEARCH,
        hits=[_hit(source_id="lotus-platform-rfcs", score=0.92, suffix="1")],
    )

    assert assessment.answer_mode == "REFUSED_INSUFFICIENT_SUPPORT"
    assert assessment.refusal_reason == "INSUFFICIENT_CITATIONS"
