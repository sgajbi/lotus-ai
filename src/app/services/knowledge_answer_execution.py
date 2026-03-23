from __future__ import annotations

from collections.abc import Sequence

from app.config import settings
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.retrieval import RetrievalExecutionStage, RetrievalSearchHit
from app.services.knowledge_retrieval_payloads import build_citation_entries, top_support_score
from app.services.knowledge_retrieval_runtime import execute_knowledge_retrieval
from app.services.task_execution_models import TaskExecutionContext

_MINIMUM_SUPPORT_SCORE = 0.75


def execute_knowledge_answer(*, context: TaskExecutionContext) -> ProviderExecutionResponse:
    retrieval = execute_knowledge_retrieval(context=context)
    is_catalog_only = (
        retrieval.retrieval_response.execution_stage == RetrievalExecutionStage.CATALOG_ONLY
    )
    provider_id = "retrieval.answer" if is_catalog_only else "retrieval.live_answer"
    provider_mode = "catalog_answer" if is_catalog_only else "live_answer"
    hits = retrieval.retrieval_response.hits
    citations = build_citation_entries(hits)
    support_score = top_support_score(hits)
    answer_mode = "CITATION_BACKED"
    answer = _build_conservative_answer(query=retrieval.query, hits=hits)
    if support_score < _MINIMUM_SUPPORT_SCORE:
        answer_mode = "REFUSED_INSUFFICIENT_SUPPORT"
        answer = (
            f"Insufficient support from approved Lotus sources to answer '{retrieval.query}' "
            "conservatively. Review the cited search hits directly."
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
            "catalog_only": is_catalog_only,
            "query": retrieval.query,
            "source_ids": retrieval.source_ids,
            "vector_store": retrieval.retrieval_response.vector_store,
            "execution_stage": retrieval.retrieval_response.execution_stage.value,
            "retrieval_status": retrieval.retrieval_response.status.value,
            "hit_count": len(hits),
            "citation_count": len(citations),
            "citations": citations,
            "support_score": support_score,
            "answer_mode": answer_mode,
            "hits": [hit.model_dump(mode="json") for hit in hits],
            "answer": answer,
        },
    )


def _build_conservative_answer(*, query: str, hits: Sequence[RetrievalSearchHit]) -> str:
    snippets = [hit.snippet.strip().rstrip(".") for hit in hits[:2] if hit.snippet]
    source_refs = [f"{hit.source_id}:{hit.document_id}" for hit in hits[:2]]
    summary = " ".join(snippets)
    citations = ", ".join(source_refs)
    return (
        f"Based on approved Lotus sources for '{query}', the currently approved corpus indicates: "
        f"{summary}. Sources: {citations}."
    )
