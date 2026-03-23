from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import RetrievalExecutionStage
from app.contracts.providers import ProviderExecutionResponse
from app.services.knowledge_retrieval_payloads import build_citation_entries, top_support_score
from app.services.knowledge_retrieval_runtime import execute_knowledge_retrieval
from app.services.task_execution_models import TaskExecutionContext


def execute_knowledge_search(*, context: TaskExecutionContext) -> ProviderExecutionResponse:
    retrieval = execute_knowledge_retrieval(context=context)
    retrieval_response = retrieval.retrieval_response
    citations = build_citation_entries(retrieval_response.hits)
    is_catalog_only = retrieval_response.execution_stage == RetrievalExecutionStage.CATALOG_ONLY
    provider_id = "retrieval.catalog" if is_catalog_only else "retrieval.live_search"
    provider_mode = "catalog_only" if is_catalog_only else "live_search"
    return ProviderExecutionResponse(
        provider_id=provider_id,
        provider_mode=provider_mode,
        stubbed=False,
        message=(
            f"Knowledge search returned {len(retrieval_response.hits)} "
            f"{provider_mode.replace('_', ' ')} "
            f"{retrieval_response.vector_store} hits for query: {retrieval.query}"
        ),
        structured_output={
            "phase": settings.delivery_phase,
            "provider_id": provider_id,
            "provider_mode": provider_mode,
            "catalog_only": is_catalog_only,
            "query": retrieval.query,
            "source_ids": retrieval.source_ids,
            "vector_store": retrieval_response.vector_store,
            "execution_stage": retrieval_response.execution_stage.value,
            "retrieval_status": retrieval_response.status.value,
            "hit_count": len(retrieval_response.hits),
            "citation_count": len(citations),
            "support_score": top_support_score(retrieval_response.hits),
            "citations": citations,
            "hits": [hit.model_dump(mode="json") for hit in retrieval_response.hits],
        },
    )
