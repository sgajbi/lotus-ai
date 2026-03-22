from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalExecutionStage,
    RetrievalExecutionStatusResponse,
)
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_store import get_retrieval_repository


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

    indexed_chunks_available = bool(get_retrieval_repository().list_searchable_indexed_chunks([]))
    if indexed_chunks_available:
        return RetrievalExecutionStatusResponse(
            service=settings.service_name,
            delivery_phase=settings.delivery_phase,
            retrieval_mode=settings.retrieval_mode,
            execution_stage=RetrievalExecutionStage.INDEXED_SEARCH,
            vector_store=VECTOR_STORE_STRATEGY,
            live_search_enabled=True,
            live_indexing_enabled=True,
            message=(
                "Retrieval execution is enabled and promoted indexed chunks are available for "
                "bounded live search."
            ),
        )

    return RetrievalExecutionStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        execution_stage=RetrievalExecutionStage.INDEXING_DISABLED,
        vector_store=VECTOR_STORE_STRATEGY,
        live_search_enabled=False,
        live_indexing_enabled=True,
        message=(
            "Retrieval mode is enabled in configuration, but no promoted indexed chunks are "
            "currently available for live search."
        ),
    )
