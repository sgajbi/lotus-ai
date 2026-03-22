from __future__ import annotations

from app.contracts.retrieval import (
    RetrievalChunkCatalogResponse,
    RetrievalDocumentCatalogResponse,
    RetrievalIndexStatusResponse,
    RetrievalSourceStatusDescriptor,
)
from app.config import settings
from app.retrieval.inventory_summary import summarize_retrieval_source_inventory
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.services.retrieval_store import get_retrieval_repository


def list_documents_for_source(source_id: str) -> RetrievalDocumentCatalogResponse:
    return RetrievalDocumentCatalogResponse(
        source_id=source_id,
        vector_store=VECTOR_STORE_STRATEGY,
        documents=get_retrieval_repository().list_documents_for_source(source_id),
    )


def list_chunks_for_document(document_id: str) -> RetrievalChunkCatalogResponse | None:
    repository = get_retrieval_repository()
    document = repository.get_document(document_id)
    if document is not None:
        return RetrievalChunkCatalogResponse(
            document_id=document_id,
            source_id=document.source_id,
            vector_store=VECTOR_STORE_STRATEGY,
            chunks=repository.list_chunks_for_document(document_id),
        )
    return None

def build_retrieval_index_status() -> RetrievalIndexStatusResponse:
    source_statuses: list[RetrievalSourceStatusDescriptor] = []
    repository = get_retrieval_repository()
    for source_id in repository.list_source_ids():
        inventory = summarize_retrieval_source_inventory(source_id)
        source_statuses.append(
            RetrievalSourceStatusDescriptor(
                source_id=inventory.source_id,
                index_status=inventory.index_status,
                document_count=inventory.document_count,
                chunk_count=inventory.chunk_count,
            )
        )

    return RetrievalIndexStatusResponse(
        service=settings.service_name,
        retrieval_mode=settings.retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        sources=source_statuses,
    )
