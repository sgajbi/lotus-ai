from __future__ import annotations

from fastapi import APIRouter

from app.contracts.retrieval import (
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSourceCatalogResponse,
)
from app.retrieval.source_registry import list_retrieval_sources
from app.services.retrieval_service import search_sources

router = APIRouter(prefix="/platform/retrieval", tags=["retrieval"])


@router.get(
    "/sources",
    response_model=RetrievalSourceCatalogResponse,
    summary="List approved retrieval sources",
    description=(
        "Returns the approved retrieval sources known to lotus-ai, together with the current "
        "retrieval mode and planned vector-store strategy."
    ),
)
async def list_retrieval_sources_route() -> RetrievalSourceCatalogResponse:
    return list_retrieval_sources()


@router.post(
    "/search",
    response_model=RetrievalSearchResponse,
    summary="Search approved retrieval sources",
    description=(
        "Searches approved lotus-ai retrieval sources. In the current phase, this endpoint "
        "returns a governed conflict response until live retrieval is enabled."
    ),
)
async def search_retrieval_sources_route(
    request: RetrievalSearchRequest,
) -> RetrievalSearchResponse:
    return search_sources(request)
