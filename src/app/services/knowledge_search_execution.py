from __future__ import annotations

from app.config import settings
from app.contracts.providers import ProviderExecutionResponse
from app.services.knowledge_retrieval_runtime import execute_knowledge_retrieval
from app.services.task_execution_models import TaskExecutionContext

_KNOWLEDGE_SEARCH_PROVIDER_ID = "retrieval.catalog"
_KNOWLEDGE_SEARCH_PROVIDER_MODE = "catalog_only"


def execute_knowledge_search(*, context: TaskExecutionContext) -> ProviderExecutionResponse:
    retrieval = execute_knowledge_retrieval(context=context)
    retrieval_response = retrieval.retrieval_response
    return ProviderExecutionResponse(
        provider_id=_KNOWLEDGE_SEARCH_PROVIDER_ID,
        provider_mode=_KNOWLEDGE_SEARCH_PROVIDER_MODE,
        stubbed=False,
        message=(
            f"Knowledge search returned {len(retrieval_response.hits)} bounded "
            f"{retrieval_response.vector_store} hits for query: {retrieval.query}"
        ),
        structured_output={
            "phase": settings.delivery_phase,
            "provider_id": _KNOWLEDGE_SEARCH_PROVIDER_ID,
            "provider_mode": _KNOWLEDGE_SEARCH_PROVIDER_MODE,
            "catalog_only": True,
            "query": retrieval.query,
            "source_ids": retrieval.source_ids,
            "vector_store": retrieval_response.vector_store,
            "retrieval_status": retrieval_response.status.value,
            "hit_count": len(retrieval_response.hits),
            "hits": [hit.model_dump(mode="json") for hit in retrieval_response.hits],
        },
    )
