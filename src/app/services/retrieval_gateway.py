from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.retrieval import (
    RetrievalExecutionRequest,
    RetrievalExecutionResponse,
    RetrievalExecutionStage,
    RetrievalSearchHit,
    RetrievalStatus,
)
from app.retrieval.policy import VECTOR_STORE_STRATEGY


def execute_retrieval_search(request: RetrievalExecutionRequest) -> RetrievalExecutionResponse:
    if settings.retrieval_mode != "enabled":
        return RetrievalExecutionResponse(
            status=RetrievalStatus.REJECTED,
            execution_stage=RetrievalExecutionStage.SEARCH_DISABLED,
            vector_store=VECTOR_STORE_STRATEGY,
            hits=[],
            message=(
                "Retrieval search is not enabled yet. lotus-ai currently exposes governed "
                "catalog and indexing contracts before live search is active."
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Retrieval execution mode is enabled in configuration but no live retrieval backend "
            "is wired yet."
        ),
    )


def build_catalog_only_hit(
    *,
    source_id: str,
    snippet: str,
) -> RetrievalSearchHit:
    return RetrievalSearchHit(source_id=source_id, score=0.0, snippet=snippet)
