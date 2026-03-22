from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.providers import ProviderExecutionResponse
from app.contracts.retrieval import RetrievalSearchRequest
from app.services.retrieval_service import search_sources
from app.services.task_execution_models import TaskExecutionContext

_KNOWLEDGE_SEARCH_PROVIDER_ID = "retrieval.catalog"
_KNOWLEDGE_SEARCH_PROVIDER_MODE = "catalog_only"


def execute_knowledge_search(*, context: TaskExecutionContext) -> ProviderExecutionResponse:
    payload = context.request.context.payload
    query = _extract_query(payload)
    source_ids = _extract_source_ids(payload)
    limit = _extract_limit(payload)
    retrieval_response = search_sources(
        RetrievalSearchRequest(
            query=query,
            caller_app=context.request.caller.caller_app,
            correlation_id=context.request.caller.correlation_id,
            source_ids=source_ids,
            limit=limit,
        )
    )
    return ProviderExecutionResponse(
        provider_id=_KNOWLEDGE_SEARCH_PROVIDER_ID,
        provider_mode=_KNOWLEDGE_SEARCH_PROVIDER_MODE,
        stubbed=False,
        message=(
            f"Knowledge search returned {len(retrieval_response.hits)} bounded "
            f"{retrieval_response.vector_store} hits for query: {query}"
        ),
        structured_output={
            "phase": settings.delivery_phase,
            "provider_id": _KNOWLEDGE_SEARCH_PROVIDER_ID,
            "provider_mode": _KNOWLEDGE_SEARCH_PROVIDER_MODE,
            "catalog_only": True,
            "query": query,
            "source_ids": source_ids,
            "vector_store": retrieval_response.vector_store,
            "retrieval_status": retrieval_response.status.value,
            "hit_count": len(retrieval_response.hits),
            "hits": [hit.model_dump(mode="json") for hit in retrieval_response.hits],
        },
    )


def _extract_query(payload: dict[str, Any]) -> str:
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "knowledge_search.v1 requires context.payload.query as a non-empty string."
            ),
        )
    return query.strip()


def _extract_source_ids(payload: dict[str, Any]) -> list[str]:
    raw_source_ids = payload.get("source_ids", [])
    if not isinstance(raw_source_ids, list) or any(
        not isinstance(source_id, str) or not source_id.strip() for source_id in raw_source_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "knowledge_search.v1 requires context.payload.source_ids to be a list of "
                "non-empty strings when supplied."
            ),
        )
    return [source_id.strip() for source_id in raw_source_ids]


def _extract_limit(payload: dict[str, Any]) -> int:
    raw_limit = payload.get("limit", 5)
    if not isinstance(raw_limit, int) or isinstance(raw_limit, bool) or not 1 <= raw_limit <= 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "knowledge_search.v1 requires context.payload.limit to be an integer between "
                "1 and 20 when supplied."
            ),
        )
    return raw_limit
