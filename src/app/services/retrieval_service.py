from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.retrieval import (
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalStatus,
)
from app.retrieval.source_registry import VECTOR_STORE_STRATEGY, list_retrieval_sources


def search_sources(request: RetrievalSearchRequest) -> RetrievalSearchResponse:
    if settings.retrieval_mode != "enabled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Retrieval search is not enabled yet. "
                "lotus-ai currently exposes the approved-source catalog before live retrieval is active."
            ),
        )

    catalog = list_retrieval_sources()
    enabled_source_ids = {source.source_id for source in catalog.sources if source.enabled}
    if request.source_ids and not set(request.source_ids).issubset(enabled_source_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Requested source_ids include one or more sources that are not enabled.",
        )

    return RetrievalSearchResponse(
        status=RetrievalStatus.READY,
        query=request.query,
        vector_store=VECTOR_STORE_STRATEGY,
        hits=[],
        message="Retrieval search is enabled but no backend implementation is wired yet.",
    )
