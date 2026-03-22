from __future__ import annotations

from fastapi import APIRouter

from app.contracts.retrieval import (
    RetrievalDocumentCatalogResponse,
    RetrievalIndexStatusResponse,
    RetrievalSearchRequest,
    RetrievalSearchResponse,
    RetrievalSourceCatalogResponse,
)
from app.retrieval.source_registry import list_retrieval_sources
from app.services.retrieval_catalog_service import (
    get_documents_for_source,
    get_retrieval_index_status,
)
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
    responses={
        200: {"description": "Retrieval source catalog returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_retrieval_sources_route() -> RetrievalSourceCatalogResponse:
    return list_retrieval_sources()


@router.get(
    "/index-status",
    response_model=RetrievalIndexStatusResponse,
    summary="Get retrieval indexing status",
    description=(
        "Returns source-level indexing status for the approved retrieval corpus currently known "
        "to lotus-ai."
    ),
    responses={
        200: {"description": "Retrieval indexing status returned successfully."},
        500: {"description": "Unexpected server error."},
    },
)
async def get_retrieval_index_status_route() -> RetrievalIndexStatusResponse:
    return get_retrieval_index_status()


@router.get(
    "/sources/{source_id}/documents",
    response_model=RetrievalDocumentCatalogResponse,
    summary="List staged retrieval documents for a source",
    description=(
        "Returns the currently staged retrieval documents associated with a source identifier."
    ),
    responses={
        200: {"description": "Retrieval document catalog returned successfully."},
        404: {"description": "Retrieval source not found."},
        500: {"description": "Unexpected server error."},
    },
)
async def list_retrieval_documents_route(source_id: str) -> RetrievalDocumentCatalogResponse:
    return get_documents_for_source(source_id)


@router.post(
    "/search",
    response_model=RetrievalSearchResponse,
    summary="Search approved retrieval sources",
    description=(
        "Searches approved lotus-ai retrieval sources. In the current phase, this endpoint "
        "returns a governed conflict response until live retrieval is enabled."
    ),
    responses={
        200: {"description": "Retrieval search completed successfully."},
        409: {"description": "Retrieval is not enabled or requested sources are not enabled."},
        500: {"description": "Unexpected server error."},
    },
)
async def search_retrieval_sources_route(
    request: RetrievalSearchRequest,
) -> RetrievalSearchResponse:
    return search_sources(request)
