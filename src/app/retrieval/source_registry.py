from __future__ import annotations

from app.contracts.retrieval import (
    RetrievalSourceCatalogResponse,
)
from app.config import settings
from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_store import get_retrieval_repository

__all__ = ["VECTOR_STORE_STRATEGY", "list_retrieval_sources"]


def list_retrieval_sources() -> RetrievalSourceCatalogResponse:
    return RetrievalSourceCatalogResponse(
        service=settings.service_name,
        retrieval_mode=resolve_runtime_mode_config().retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        sources=get_retrieval_repository().list_sources(),
    )
