from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.retrieval import RetrievalDocumentCatalogResponse, RetrievalIndexStatusResponse
from app.retrieval.document_registry import build_retrieval_index_status, list_documents_for_source
from app.retrieval.source_registry import list_retrieval_sources


def get_retrieval_index_status() -> RetrievalIndexStatusResponse:
    return build_retrieval_index_status()


def get_documents_for_source(source_id: str) -> RetrievalDocumentCatalogResponse:
    source_catalog = list_retrieval_sources()
    if not any(source.source_id == source_id for source in source_catalog.sources):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown retrieval source_id: {source_id}",
        )
    return list_documents_for_source(source_id)
