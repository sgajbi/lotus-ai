from __future__ import annotations

from collections.abc import Sequence

from app.config import settings
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.retrieval import RetrievalSearchHit
from app.services.knowledge_retrieval_runtime import execute_knowledge_retrieval
from app.services.task_execution_models import TaskExecutionContext

_KNOWLEDGE_ANSWER_PROVIDER_ID = "retrieval.answer"
_KNOWLEDGE_ANSWER_PROVIDER_MODE = "catalog_answer"


def execute_knowledge_answer(*, context: TaskExecutionContext) -> ProviderExecutionResponse:
    retrieval = execute_knowledge_retrieval(context=context)
    hits = retrieval.retrieval_response.hits
    citations = [hit.source_id for hit in hits]
    answer = _build_conservative_answer(query=retrieval.query, hits=hits)
    return ProviderExecutionResponse(
        provider_id=_KNOWLEDGE_ANSWER_PROVIDER_ID,
        provider_mode=_KNOWLEDGE_ANSWER_PROVIDER_MODE,
        stubbed=False,
        message=answer,
        structured_output={
            "phase": settings.delivery_phase,
            "provider_id": _KNOWLEDGE_ANSWER_PROVIDER_ID,
            "provider_mode": _KNOWLEDGE_ANSWER_PROVIDER_MODE,
            "catalog_only": True,
            "query": retrieval.query,
            "source_ids": retrieval.source_ids,
            "vector_store": retrieval.retrieval_response.vector_store,
            "retrieval_status": retrieval.retrieval_response.status.value,
            "hit_count": len(hits),
            "citations": citations,
            "hits": [hit.model_dump(mode="json") for hit in hits],
            "answer": answer,
        },
    )


def _build_conservative_answer(*, query: str, hits: Sequence[RetrievalSearchHit]) -> str:
    snippets = [hit.snippet.strip().rstrip(".") for hit in hits[:2] if hit.snippet]
    source_ids = [hit.source_id for hit in hits[:2]]
    summary = " ".join(snippets)
    citations = ", ".join(source_ids)
    return (
        f"Based on approved Lotus sources for '{query}', the currently staged corpus indicates: "
        f"{summary}. Sources: {citations}."
    )
