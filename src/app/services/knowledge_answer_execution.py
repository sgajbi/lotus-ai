from __future__ import annotations

from collections.abc import Sequence

from app.config import settings
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.retrieval import RetrievalExecutionStage, RetrievalSearchHit
from app.services.knowledge_answer_support import (
    assess_knowledge_answer_support,
    select_primary_hits,
)
from app.services.knowledge_retrieval_payloads import build_citation_entries
from app.services.knowledge_retrieval_runtime import execute_knowledge_retrieval
from app.services.task_execution_models import TaskExecutionContext

_KNOWLEDGE_ANSWER_PROVIDER_ID = "retrieval.answer"
_KNOWLEDGE_ANSWER_INDEXED_PROVIDER_ID = "retrieval.indexed_answer"


def execute_knowledge_answer(*, context: TaskExecutionContext) -> ProviderExecutionResponse:
    retrieval = execute_knowledge_retrieval(context=context)
    hits = retrieval.retrieval_response.hits
    execution_stage = retrieval.retrieval_response.execution_stage
    primary_hits = select_primary_hits(hits)
    citations = build_citation_entries(primary_hits)
    support = assess_knowledge_answer_support(execution_stage=execution_stage, hits=hits)
    provider_id = (
        _KNOWLEDGE_ANSWER_INDEXED_PROVIDER_ID
        if execution_stage == RetrievalExecutionStage.INDEXED_SEARCH
        else _KNOWLEDGE_ANSWER_PROVIDER_ID
    )
    provider_mode = (
        "indexed_answer"
        if execution_stage == RetrievalExecutionStage.INDEXED_SEARCH
        else "catalog_answer"
    )
    answer = (
        _build_conservative_answer(
            query=retrieval.query,
            hits=primary_hits,
            execution_stage=execution_stage,
        )
        if support.meets_support_threshold
        else _build_refusal_answer(query=retrieval.query, refusal_reason=support.refusal_reason)
    )
    return ProviderExecutionResponse(
        provider_id=provider_id,
        provider_mode=provider_mode,
        stubbed=False,
        message=answer,
        structured_output={
            "phase": settings.delivery_phase,
            "provider_id": provider_id,
            "provider_mode": provider_mode,
            "catalog_only": execution_stage == RetrievalExecutionStage.CATALOG_ONLY,
            "retrieval_execution_stage": execution_stage.value,
            "query": retrieval.query,
            "source_ids": retrieval.source_ids,
            "vector_store": retrieval.retrieval_response.vector_store,
            "retrieval_status": retrieval.retrieval_response.status.value,
            "hit_count": len(hits),
            "citation_count": len(citations),
            "citations": citations,
            "support_score": support.support_score,
            "combined_support_score": support.combined_support_score,
            "answer_mode": support.answer_mode,
            "support_assessment": {
                "minimum_required_score": support.minimum_required_score,
                "meets_support_threshold": support.meets_support_threshold,
                "citation_count": support.citation_count,
                "unique_source_count": support.unique_source_count,
                "refusal_reason": support.refusal_reason,
            },
            "hits": [hit.model_dump(mode="json") for hit in hits],
            "answer": answer,
        },
    )


def _build_conservative_answer(
    *,
    query: str,
    hits: Sequence[RetrievalSearchHit],
    execution_stage: RetrievalExecutionStage,
) -> str:
    snippets = [hit.snippet.strip().rstrip(".") for hit in hits[:2] if hit.snippet]
    source_ids = [hit.source_id for hit in hits[:2]]
    summary = " ".join(snippets)
    citations = ", ".join(source_ids)
    corpus_label = (
        "the current indexed retrieval corpus"
        if execution_stage == RetrievalExecutionStage.INDEXED_SEARCH
        else "the currently staged governed corpus"
    )
    return (
        f"Based on approved Lotus sources for '{query}', {corpus_label} indicates: "
        f"{summary}. Sources: {citations}."
    )


def _build_refusal_answer(*, query: str, refusal_reason: str | None) -> str:
    reason = refusal_reason or "UNSPECIFIED_RETRIEVAL_SUPPORT_GAP"
    return (
        f"Insufficient support from approved Lotus sources to answer '{query}' conservatively. "
        f"Refusal reason: {reason}. Review the cited search hits directly."
    )
