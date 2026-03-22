from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalExecutionStage,
    RetrievalExecutionStatusResponse,
)
from app.retrieval.policy import VECTOR_STORE_STRATEGY


def build_retrieval_execution_status() -> RetrievalExecutionStatusResponse:
    if settings.retrieval_mode != "enabled":
        return RetrievalExecutionStatusResponse(
            service=settings.service_name,
            delivery_phase=settings.delivery_phase,
            retrieval_mode=settings.retrieval_mode,
            execution_stage=RetrievalExecutionStage.SEARCH_DISABLED,
            vector_store=VECTOR_STORE_STRATEGY,
            live_search_enabled=False,
            live_indexing_enabled=False,
            message=(
                "Retrieval remains in catalog-and-indexing-contract mode; live search and "
                "indexing execution are disabled."
            ),
        )

    return RetrievalExecutionStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        execution_stage=RetrievalExecutionStage.INDEXING_DISABLED,
        vector_store=VECTOR_STORE_STRATEGY,
        live_search_enabled=False,
        live_indexing_enabled=False,
        message=(
            "Retrieval mode is enabled in configuration, but no live retrieval execution backend "
            "is wired yet."
        ),
    )
