from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.access_control import AuthorizationCapabilityType
from app.contracts.retrieval import (
    RetrievalExecutionRequest,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
)
from app.services.access_control_authorization import authorize_request, require_authorized
from app.services.deployment_split_routing import resolve_retrieval_search_route
from app.services.deployment_split_shared import resolve_effective_deployment_split_stage
from app.services.retrieval_gateway import execute_retrieval_search
from app.services.retrieval_store import get_retrieval_repository


def search_sources(request: RetrievalSearchRequest) -> RetrievalSearchResponse:
    route = resolve_retrieval_search_route(
        effective_stage=resolve_effective_deployment_split_stage()[0]
    )
    authorization = require_authorized(
        authorize_request(
            caller_app=request.caller_app,
            capability_type=AuthorizationCapabilityType.RETRIEVAL_EXECUTION,
            tenant_id=request.tenant_id,
            source_ids=request.source_ids,
        )
    )
    effective_source_ids = authorization.effective_source_ids
    enabled_source_ids = {
        source.source_id for source in get_retrieval_repository().list_sources() if source.enabled
    }
    if effective_source_ids and not set(effective_source_ids).issubset(enabled_source_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested source_ids include one or more sources that are not enabled.",
        )

    execution = execute_retrieval_search(
        RetrievalExecutionRequest(
            query=request.query,
            caller_app=request.caller_app,
            correlation_id=request.correlation_id,
            source_ids=effective_source_ids,
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
        query=request.query,
        execution_stage=execution.execution_stage,
        vector_store=execution.vector_store,
        hits=execution.hits,
        message=f"{execution.message} {route.detail}",
    )
