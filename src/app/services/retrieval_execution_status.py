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
            live_indexing_enabled=True,
            message=(
                "Live retrieval search remains disabled, but runtime-backed retrieval indexing is "
                "enabled for allowlisted async jobs."
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
            "Retrieval mode is enabled in configuration, runtime-backed indexing is available, "
            "but live retrieval search is not yet wired."
        ),
    )
