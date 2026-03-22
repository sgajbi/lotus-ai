from __future__ import annotations

from copy import deepcopy
from typing import cast

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalEmbeddingStatus,
    RetrievalDocumentDescriptor,
    RetrievalDocumentPromotionStatus,
    RetrievalIndexedChunkDescriptor,
    RetrievalIndexJobEventDescriptor,
    RetrievalIndexJobEventStatus,
    RetrievalIndexJobDescriptor,
    RetrievalIndexStatus,
    RetrievalJobStatus,
    RetrievalPipelineStage,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.foundation_embedding import build_preview_embedding


class InMemoryRetrievalRepository(RetrievalRepository):
    def __init__(self) -> None:
        self._sources: list[RetrievalSourceDescriptor] = [
            RetrievalSourceDescriptor(
                source_id="lotus-platform-rfcs",
                kind=RetrievalSourceKind.RFC,
                enabled=True,
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
                enabled=True,
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
                    promotion_status=RetrievalDocumentPromotionStatus.SEARCHABLE,
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.INDEXED,
                ),
                RetrievalDocumentDescriptor(
                    document_id="lotus-platform-rfc-0069",
                    source_id="lotus-platform-rfcs",
                    title="RFC-0069 lotus-ai Shared AI Platform Service",
                    location="lotus-platform/rfcs/RFC-0069-lotus-ai-shared-ai-platform-service.md",
                    promotion_status=RetrievalDocumentPromotionStatus.SEARCHABLE,
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.INDEXED,
                ),
            ],
            "lotus-platform-standards": [
                RetrievalDocumentDescriptor(
                    document_id="lotus-platform-observability-standards",
                    source_id="lotus-platform-standards",
                    title="Platform Observability Standards",
                    location="lotus-platform/Platform Observability Standards.md",
                    promotion_status=RetrievalDocumentPromotionStatus.STAGED,
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
                    promotion_status=RetrievalDocumentPromotionStatus.SEARCHABLE,
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.INDEXED,
                ),
                RetrievalDocumentDescriptor(
                    document_id="lotus-ai-retrieval-vector-store-guide",
                    source_id="lotus-ai-architecture",
                    title="lotus-ai Retrieval and Vector Store Guide",
                    location="lotus-ai/docs/guides/retrieval-and-vector-store.md",
                    promotion_status=RetrievalDocumentPromotionStatus.SEARCHABLE,
                    chunk_count=1,
                    index_status=RetrievalIndexStatus.INDEXED,
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
                    content_checksum="sha256:chunk-rfc-0068-0001",
                    preview="Move ownership of shared platform infrastructure to lotus-platform.",
                    index_status=RetrievalIndexStatus.INDEXED,
                )
            ],
            "lotus-platform-rfc-0069": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_rfc_0069_0001",
                    document_id="lotus-platform-rfc-0069",
                    source_id="lotus-platform-rfcs",
                    chunk_order=1,
                    token_estimate=210,
                    content_checksum="sha256:chunk-rfc-0069-0001",
                    preview="Introduce lotus-ai as a dedicated shared AI platform service for Lotus applications.",
                    index_status=RetrievalIndexStatus.INDEXED,
                )
            ],
            "lotus-platform-observability-standards": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_obs_0001",
                    document_id="lotus-platform-observability-standards",
                    source_id="lotus-platform-standards",
                    chunk_order=1,
                    token_estimate=165,
                    content_checksum="sha256:chunk-obs-0001",
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
                    content_checksum="sha256:chunk-system-overview-0001",
                    preview="lotus-ai is the shared AI platform service for Lotus.",
                    index_status=RetrievalIndexStatus.INDEXED,
                )
            ],
            "lotus-ai-retrieval-vector-store-guide": [
                RetrievalChunkDescriptor(
                    chunk_id="chunk_retrieval_guide_0001",
                    document_id="lotus-ai-retrieval-vector-store-guide",
                    source_id="lotus-ai-architecture",
                    chunk_order=1,
                    token_estimate=190,
                    content_checksum="sha256:chunk-retrieval-guide-0001",
                    preview="The first vector-store architecture for lotus-ai is PostgreSQL plus pgvector.",
                    index_status=RetrievalIndexStatus.INDEXED,
                )
            ],
        }
        self._embedding_records: dict[str, dict[str, object]] = {
            "emb_chunk_rfc_0068_0001": {
                "chunk_id": "chunk_rfc_0068_0001",
                "document_id": "lotus-platform-rfc-0068",
                "source_id": "lotus-platform-rfcs",
                "embedding_model": "foundation.text-embedding-preview",
                "embedding_status": RetrievalEmbeddingStatus.PERSISTED,
                "vector_dimensions": 16,
                "content_checksum": "sha256:chunk-rfc-0068-0001",
                "embedding_vector": build_preview_embedding(
                    "RFC-0068 Centralized Shared Infrastructure Ownership and Migration "
                    "Move ownership of shared platform infrastructure to lotus-platform."
                ),
            },
            "emb_chunk_rfc_0069_0001": {
                "chunk_id": "chunk_rfc_0069_0001",
                "document_id": "lotus-platform-rfc-0069",
                "source_id": "lotus-platform-rfcs",
                "embedding_model": "foundation.text-embedding-preview",
                "embedding_status": RetrievalEmbeddingStatus.PERSISTED,
                "vector_dimensions": 16,
                "content_checksum": "sha256:chunk-rfc-0069-0001",
                "embedding_vector": build_preview_embedding(
                    "RFC-0069 lotus-ai Shared AI Platform Service "
                    "Introduce lotus-ai as a dedicated shared AI platform service for Lotus applications."
                ),
            },
            "emb_chunk_system_overview_0001": {
                "chunk_id": "chunk_system_overview_0001",
                "document_id": "lotus-ai-system-overview",
                "source_id": "lotus-ai-architecture",
                "embedding_model": "foundation.text-embedding-preview",
                "embedding_status": RetrievalEmbeddingStatus.PERSISTED,
                "vector_dimensions": 16,
                "content_checksum": "sha256:chunk-system-overview-0001",
                "embedding_vector": build_preview_embedding(
                    "lotus-ai System Overview lotus-ai is the shared AI platform service for Lotus."
                ),
            },
            "emb_chunk_retrieval_guide_0001": {
                "chunk_id": "chunk_retrieval_guide_0001",
                "document_id": "lotus-ai-retrieval-vector-store-guide",
                "source_id": "lotus-ai-architecture",
                "embedding_model": "foundation.text-embedding-preview",
                "embedding_status": RetrievalEmbeddingStatus.PERSISTED,
                "vector_dimensions": 16,
                "content_checksum": "sha256:chunk-retrieval-guide-0001",
                "embedding_vector": build_preview_embedding(
                    "lotus-ai Retrieval and Vector Store Guide "
                    "The first vector-store architecture for lotus-ai is PostgreSQL plus pgvector."
                ),
            },
        }
        self._job_events: dict[str, list[RetrievalIndexJobEventDescriptor]] = {
            "retjob_lotus_platform_rfcs": [
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_platform_rfcs_source_curation",
                    job_id="retjob_lotus_platform_rfcs",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.COMPLETED,
                    recorded_at="2026-03-22T08:00:00Z",
                    notes="Approved RFC source inventory and promoted documents are ready for deterministic indexing.",
                ),
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_platform_rfcs_document_inventory",
                    job_id="retjob_lotus_platform_rfcs",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.COMPLETED,
                    recorded_at="2026-03-22T08:01:00Z",
                    notes="Document inventory and chunk checksums were recorded for replayable indexing.",
                ),
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_platform_rfcs_embedding_generation",
                    job_id="retjob_lotus_platform_rfcs",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.COMPLETED,
                    recorded_at="2026-03-22T08:02:00Z",
                    notes="Persisted preview embeddings are available for promoted RFC chunks and can back bounded indexed retrieval.",
                ),
            ],
            "retjob_lotus_platform_standards": [
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_platform_standards_source_curation",
                    job_id="retjob_lotus_platform_standards",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.COMPLETED,
                    recorded_at="2026-03-22T08:10:00Z",
                    notes="Standards source inventory is approved and staged for indexing.",
                ),
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_platform_standards_document_inventory",
                    job_id="retjob_lotus_platform_standards",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.FAILED,
                    recorded_at="2026-03-22T08:11:00Z",
                    notes="Indexing is blocked because staged standards documents are not yet promoted into searchable scope.",
                ),
            ],
            "retjob_lotus_ai_architecture": [
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_ai_architecture_source_curation",
                    job_id="retjob_lotus_ai_architecture",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.COMPLETED,
                    recorded_at="2026-03-22T08:20:00Z",
                    notes="Architecture source inventory and promoted documents are ready for deterministic indexing.",
                ),
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_ai_architecture_document_inventory",
                    job_id="retjob_lotus_ai_architecture",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.COMPLETED,
                    recorded_at="2026-03-22T08:21:00Z",
                    notes="Document inventory and chunk checksums were recorded for replayable indexing.",
                ),
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_ai_architecture_embedding_generation",
                    job_id="retjob_lotus_ai_architecture",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.COMPLETED,
                    recorded_at="2026-03-22T08:22:00Z",
                    notes="Persisted preview embeddings are available for promoted architecture chunks and can back bounded indexed retrieval.",
                ),
            ],
            "retjob_lotus_openapi_derived": [
                RetrievalIndexJobEventDescriptor(
                    event_id="evt_retjob_lotus_openapi_derived_source_curation",
                    job_id="retjob_lotus_openapi_derived",
                    stage=RetrievalPipelineStage.STAGED,
                    status=RetrievalIndexJobEventStatus.FAILED,
                    recorded_at="2026-03-22T08:30:00Z",
                    notes="No promoted documents are available yet for this source, so indexing cannot proceed.",
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

    def list_searchable_indexed_chunks(
        self, source_ids: list[str]
    ) -> list[RetrievalIndexedChunkDescriptor]:
        requested_source_ids = set(source_ids)
        documents_by_id = {
            document.document_id: document
            for documents in self._documents.values()
            for document in documents
        }
        chunks_by_id = {
            chunk.chunk_id: chunk
            for chunks in self._chunks.values()
            for chunk in chunks
        }
        indexed_chunks: list[RetrievalIndexedChunkDescriptor] = []
        for embedding_id, record in self._embedding_records.items():
            source_id = str(record["source_id"])
            if requested_source_ids and source_id not in requested_source_ids:
                continue
            document = documents_by_id.get(str(record["document_id"]))
            chunk = chunks_by_id.get(str(record["chunk_id"]))
            if document is None or chunk is None:
                continue
            if document.promotion_status != RetrievalDocumentPromotionStatus.SEARCHABLE:
                continue
            if document.index_status != RetrievalIndexStatus.INDEXED:
                continue
            if chunk.index_status != RetrievalIndexStatus.INDEXED:
                continue
            if record["embedding_status"] != RetrievalEmbeddingStatus.PERSISTED:
                continue
            if str(record["content_checksum"]) != chunk.content_checksum:
                continue
            indexed_chunks.append(
                RetrievalIndexedChunkDescriptor(
                    embedding_id=embedding_id,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_id=chunk.source_id,
                    document_title=document.title,
                    content_checksum=chunk.content_checksum,
                    snippet=chunk.preview,
                    embedding_model=str(record["embedding_model"]),
                    embedding_status=record["embedding_status"],
                    vector_dimensions=cast(int, record["vector_dimensions"]),
                    embedding_vector=cast(list[float], record["embedding_vector"]),
                )
            )
        return indexed_chunks

    def count_embedding_records(self) -> int:
        return len(self._embedding_records)

    def count_embedding_records_for_source(self, source_id: str) -> int:
        return sum(
            1
            for record in self._embedding_records.values()
            if record["source_id"] == source_id
        )

    def list_index_jobs(self) -> list[RetrievalIndexJobDescriptor]:
        jobs: list[RetrievalIndexJobDescriptor] = []
        for source in self._sources:
            documents = self._documents.get(source.source_id, [])
            chunk_count = sum(
                len(self._chunks.get(document.document_id, [])) for document in documents
            )
            searchable_documents = [
                document
                for document in documents
                if document.promotion_status == RetrievalDocumentPromotionStatus.SEARCHABLE
            ]
            indexed_document_count = sum(
                1 for document in searchable_documents if document.index_status == RetrievalIndexStatus.INDEXED
            )
            if not documents:
                status = RetrievalJobStatus.PENDING
                message = "No staged documents yet for this retrieval source."
            elif searchable_documents and indexed_document_count == len(searchable_documents):
                status = RetrievalJobStatus.COMPLETED
                message = "Promoted documents have persisted embeddings and are ready for bounded indexed retrieval."
            else:
                status = RetrievalJobStatus.STAGED
                message = "Documents are staged for indexing, but promoted indexed coverage is incomplete."
            jobs.append(
                RetrievalIndexJobDescriptor(
                    job_id=f"retjob_{source.source_id.replace('-', '_')}",
                    source_id=source.source_id,
                    status=status,
                    document_count=len(documents),
                    chunk_count=chunk_count,
                    embedding_record_count=self.count_embedding_records_for_source(source.source_id),
                    message=message,
                )
            )
        return jobs

    def get_index_job(self, job_id: str) -> RetrievalIndexJobDescriptor | None:
        for job in self.list_index_jobs():
            if job.job_id == job_id:
                return job
        return None

    def list_index_job_events(self, job_id: str) -> list[RetrievalIndexJobEventDescriptor]:
        return deepcopy(self._job_events.get(job_id, []))
