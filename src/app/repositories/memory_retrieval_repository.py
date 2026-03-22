from __future__ import annotations

from copy import deepcopy

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalIndexStatus,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.repositories.retrieval_repository import RetrievalRepository


class InMemoryRetrievalRepository(RetrievalRepository):
    def __init__(self) -> None:
        self._sources: list[RetrievalSourceDescriptor] = [
            RetrievalSourceDescriptor(
                source_id="lotus-platform-rfcs",
                kind=RetrievalSourceKind.RFC,
                enabled=False,
                description="Approved Lotus platform RFC documents.",
            ),
            RetrievalSourceDescriptor(
                source_id="lotus-platform-standards",
                kind=RetrievalSourceKind.STANDARD,
                enabled=False,
                description="Approved Lotus standards and governance documents.",
            ),
            RetrievalSourceDescriptor(
                source_id="lotus-ai-architecture",
                kind=RetrievalSourceKind.ARCHITECTURE,
                enabled=False,
                description="lotus-ai architecture, guides, and service-local design documentation.",
            ),
            RetrievalSourceDescriptor(
                source_id="lotus-openapi-derived",
                kind=RetrievalSourceKind.OPENAPI,
                enabled=False,
                description="OpenAPI-derived documentation and approved schema references.",
            ),
        ]
        self._documents: dict[str, list[RetrievalDocumentDescriptor]] = {
            "lotus-platform-rfcs": [
                RetrievalDocumentDescriptor(
                    document_id="lotus-platform-rfc-0068",
                    source_id="lotus-platform-rfcs",
                    title="RFC-0068 Centralized Shared Infrastructure Ownership and Migration",
                    location="lotus-platform/rfcs/RFC-0068-centralized-shared-infrastructure-ownership-and-migration.md",
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.STAGED,
                ),
                RetrievalDocumentDescriptor(
                    document_id="lotus-platform-rfc-0069",
                    source_id="lotus-platform-rfcs",
                    title="RFC-0069 lotus-ai Shared AI Platform Service",
                    location="lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md",
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.STAGED,
                ),
            ],
            "lotus-platform-standards": [
                RetrievalDocumentDescriptor(
                    document_id="lotus-platform-observability-standards",
                    source_id="lotus-platform-standards",
                    title="Platform Observability Standards",
                    location="lotus-platform/Platform Observability Standards.md",
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.STAGED,
                ),
            ],
            "lotus-ai-architecture": [
                RetrievalDocumentDescriptor(
                    document_id="lotus-ai-system-overview",
                    source_id="lotus-ai-architecture",
                    title="lotus-ai System Overview",
                    location="lotus-ai/docs/architecture/system-overview.md",
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.STAGED,
                ),
                RetrievalDocumentDescriptor(
                    document_id="lotus-ai-retrieval-vector-store-guide",
                    source_id="lotus-ai-architecture",
                    title="lotus-ai Retrieval and Vector Store Guide",
                    location="lotus-ai/docs/guides/retrieval-and-vector-store.md",
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.STAGED,
                ),
            ],
            "lotus-openapi-derived": [],
        }
        self._chunks: dict[str, list[RetrievalChunkDescriptor]] = {
            "lotus-platform-rfc-0068": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_rfc_0068_0001",
                    document_id="lotus-platform-rfc-0068",
                    source_id="lotus-platform-rfcs",
                    chunk_order=1,
                    token_estimate=180,
                    preview="Move ownership of shared platform infrastructure to lotus-platform.",
                    index_status=RetrievalIndexStatus.STAGED,
                )
            ],
            "lotus-platform-rfc-0069": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_rfc_0069_0001",
                    document_id="lotus-platform-rfc-0069",
                    source_id="lotus-platform-rfcs",
                    chunk_order=1,
                    token_estimate=210,
                    preview="Introduce lotus-ai as a dedicated shared AI platform service for Lotus applications.",
                    index_status=RetrievalIndexStatus.STAGED,
                )
            ],
            "lotus-platform-observability-standards": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_obs_0001",
                    document_id="lotus-platform-observability-standards",
                    source_id="lotus-platform-standards",
                    chunk_order=1,
                    token_estimate=165,
                    preview="Cross-cutting governance for this stack is defined in Platform Observability Standards.",
                    index_status=RetrievalIndexStatus.STAGED,
                )
            ],
            "lotus-ai-system-overview": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_system_overview_0001",
                    document_id="lotus-ai-system-overview",
                    source_id="lotus-ai-architecture",
                    chunk_order=1,
                    token_estimate=170,
                    preview="lotus-ai is the shared AI platform service for Lotus.",
                    index_status=RetrievalIndexStatus.STAGED,
                )
            ],
            "lotus-ai-retrieval-vector-store-guide": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_retrieval_guide_0001",
                    document_id="lotus-ai-retrieval-vector-store-guide",
                    source_id="lotus-ai-architecture",
                    chunk_order=1,
                    token_estimate=190,
                    preview="The first vector-store architecture for lotus-ai is PostgreSQL plus pgvector.",
                    index_status=RetrievalIndexStatus.STAGED,
                )
            ],
        }

    def list_sources(self) -> list[RetrievalSourceDescriptor]:
        return deepcopy(self._sources)

    def list_source_ids(self) -> list[str]:
        return [source.source_id for source in self._sources]

    def get_source(self, source_id: str) -> RetrievalSourceDescriptor | None:
        for source in self._sources:
            if source.source_id == source_id:
                return deepcopy(source)
        return None

    def list_documents_for_source(self, source_id: str) -> list[RetrievalDocumentDescriptor]:
        return deepcopy(self._documents.get(source_id, []))

    def get_document(self, document_id: str) -> RetrievalDocumentDescriptor | None:
        for documents in self._documents.values():
            for document in documents:
                if document.document_id == document_id:
                    return deepcopy(document)
        return None

    def list_chunks_for_document(self, document_id: str) -> list[RetrievalChunkDescriptor]:
        return deepcopy(self._chunks.get(document_id, []))
