from __future__ import annotations

from app.contracts.retrieval import (
    RetrievalDocumentCatalogResponse,
    RetrievalDocumentDescriptor,
    RetrievalIndexStatus,
    RetrievalIndexStatusResponse,
    RetrievalSourceStatusDescriptor,
)
from app.config import settings
from app.retrieval.source_registry import VECTOR_STORE_STRATEGY

_DOCUMENTS: dict[str, list[RetrievalDocumentDescriptor]] = {
    "lotus-platform-rfcs": [
        RetrievalDocumentDescriptor(
            document_id="lotus-platform-rfc-0068",
            source_id="lotus-platform-rfcs",
            title="RFC-0068 Centralized Shared Infrastructure Ownership and Migration",
            location="lotus-platform/rfcs/RFC-0068-centralized-shared-infrastructure-ownership-and-migration.md",
            chunk_count=0,
            index_status=RetrievalIndexStatus.STAGED,
        ),
        RetrievalDocumentDescriptor(
            document_id="lotus-platform-rfc-0069",
            source_id="lotus-platform-rfcs",
            title="RFC-0069 lotus-ai Shared AI Platform Service",
            location="lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md",
            chunk_count=0,
            index_status=RetrievalIndexStatus.STAGED,
        ),
    ],
    "lotus-platform-standards": [
        RetrievalDocumentDescriptor(
            document_id="lotus-platform-observability-standards",
            source_id="lotus-platform-standards",
            title="Platform Observability Standards",
            location="lotus-platform/Platform Observability Standards.md",
            chunk_count=0,
            index_status=RetrievalIndexStatus.STAGED,
        ),
    ],
    "lotus-ai-architecture": [
        RetrievalDocumentDescriptor(
            document_id="lotus-ai-system-overview",
            source_id="lotus-ai-architecture",
            title="lotus-ai System Overview",
            location="lotus-ai/docs/architecture/system-overview.md",
            chunk_count=0,
            index_status=RetrievalIndexStatus.STAGED,
        ),
        RetrievalDocumentDescriptor(
            document_id="lotus-ai-retrieval-vector-store-guide",
            source_id="lotus-ai-architecture",
            title="lotus-ai Retrieval and Vector Store Guide",
            location="lotus-ai/docs/guides/retrieval-and-vector-store.md",
            chunk_count=0,
            index_status=RetrievalIndexStatus.STAGED,
        ),
    ],
    "lotus-openapi-derived": [],
}


def list_documents_for_source(source_id: str) -> RetrievalDocumentCatalogResponse:
    return RetrievalDocumentCatalogResponse(
        source_id=source_id,
        vector_store=VECTOR_STORE_STRATEGY,
        documents=_DOCUMENTS.get(source_id, []),
    )


def build_retrieval_index_status() -> RetrievalIndexStatusResponse:
    source_statuses: list[RetrievalSourceStatusDescriptor] = []
    for source_id, documents in _DOCUMENTS.items():
        chunk_count = sum(document.chunk_count for document in documents)
        if not documents:
            status = RetrievalIndexStatus.NOT_INDEXED
        elif all(document.index_status == RetrievalIndexStatus.INDEXED for document in documents):
            status = RetrievalIndexStatus.INDEXED
        else:
            status = RetrievalIndexStatus.STAGED
        source_statuses.append(
            RetrievalSourceStatusDescriptor(
                source_id=source_id,
                index_status=status,
                document_count=len(documents),
                chunk_count=chunk_count,
            )
        )

    return RetrievalIndexStatusResponse(
        service=settings.service_name,
        retrieval_mode=settings.retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        sources=source_statuses,
    )
