from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.retrieval import (
    RetrievalExecutionRequest,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.services.retrieval_gateway import execute_retrieval_search
from app.services.retrieval_store import get_retrieval_repository


def search_sources(request: RetrievalSearchRequest) -> RetrievalSearchResponse:
    enabled_source_ids = {
        source.source_id for source in get_retrieval_repository().list_sources() if source.enabled
    }
    if request.source_ids and not set(request.source_ids).issubset(enabled_source_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested source_ids include one or more sources that are not enabled.",
        )

    execution = execute_retrieval_search(
        RetrievalExecutionRequest(
            query=request.query,
            caller_app=request.caller_app,
            correlation_id=request.correlation_id,
            source_ids=request.source_ids,
            limit=request.limit,
        )
    )
    if execution.status.value == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=execution.message,
        )

    return RetrievalSearchResponse(
        status=execution.status,
        execution_stage=execution.execution_stage,
        query=request.query,
        vector_store=execution.vector_store,
        hits=execution.hits,
        message=execution.message,
    )
