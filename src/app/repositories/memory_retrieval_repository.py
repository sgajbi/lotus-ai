from __future__ import annotations

from copy import deepcopy

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalIndexJobDescriptor,
    RetrievalIndexStatus,
    RetrievalJobStatus,
    RetrievalSearchHit,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.search_eligibility import is_live_search_chunk_eligible
from app.retrieval.search_scoring import score_terms


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

    def search_indexed_chunks(
        self, *, query: str, source_ids: list[str], limit: int
    ) -> list[RetrievalSearchHit]:
        allowed_source_ids = set(source_ids)
        ranked_hits: list[RetrievalSearchHit] = []
        for source in self._sources:
            if not source.enabled:
                continue
            if allowed_source_ids and source.source_id not in allowed_source_ids:
                continue
            for document in self._documents.get(source.source_id, []):
                for chunk in self._chunks.get(document.document_id, []):
                    if not is_live_search_chunk_eligible(
                        source=source,
                        document=document,
                        chunk=chunk,
                    ):
                        continue
                    score = score_terms(
                        query=query,
                        searchable_text=f"{document.title} {chunk.preview}",
                    )
                    if score <= 0.0:
                        continue
                    ranked_hits.append(
                        RetrievalSearchHit(
                            source_id=chunk.source_id,
                            document_id=chunk.document_id,
                            chunk_id=chunk.chunk_id,
                            score=score,
                            snippet=chunk.preview,
                        )
                    )

        ranked_hits.sort(key=lambda hit: (-hit.score, hit.source_id, hit.document_id, hit.chunk_id))
        return [hit.model_copy(deep=True) for hit in ranked_hits[:limit]]

    def list_index_jobs(self) -> list[RetrievalIndexJobDescriptor]:
        jobs: list[RetrievalIndexJobDescriptor] = []
        overrides = getattr(self, "_index_job_overrides", {})
        for source in self._sources:
            documents = self._documents.get(source.source_id, [])
            chunk_count = sum(
                len(self._chunks.get(document.document_id, [])) for document in documents
            )
            if not documents:
                status = RetrievalJobStatus.PENDING
                message = "No staged documents yet for this retrieval source."
            else:
                status = RetrievalJobStatus.STAGED
                message = (
                    "Documents are staged for indexing, but vector indexing is not enabled yet."
                )
            job_id = f"retjob_{source.source_id.replace('-', '_')}"
            if job_id in overrides:
                jobs.append(deepcopy(overrides[job_id]))
                continue
            jobs.append(
                RetrievalIndexJobDescriptor(
                    job_id=job_id,
                    source_id=source.source_id,
                    status=status,
                    document_count=len(documents),
                    chunk_count=chunk_count,
                    message=message,
                )
            )
        return jobs

    def get_index_job(self, job_id: str) -> RetrievalIndexJobDescriptor | None:
        for job in self.list_index_jobs():
            if job.job_id == job_id:
                return job
        return None

    def save_index_job(self, descriptor: RetrievalIndexJobDescriptor) -> None:
        source_id = descriptor.source_id
        for source in self._sources:
            if source.source_id == source_id:
                break
        if source_id not in self._documents:
            self._documents[source_id] = []

        # Persist as source-derived descriptor by keeping message and status through document state plus this seed.
        documents = self._documents.get(source_id, [])
        chunk_count = sum(len(self._chunks.get(document.document_id, [])) for document in documents)
        self._documents[source_id] = documents
        self._index_job_overrides = getattr(self, "_index_job_overrides", {})
        self._index_job_overrides[descriptor.job_id] = RetrievalIndexJobDescriptor(
            job_id=descriptor.job_id,
            source_id=source_id,
            status=descriptor.status,
            document_count=descriptor.document_count or len(documents),
            chunk_count=descriptor.chunk_count or chunk_count,
            message=descriptor.message,
        )

    def set_source_index_status(self, *, source_id: str, index_status: str) -> None:
        new_documents: list[RetrievalDocumentDescriptor] = []
        for document in self._documents.get(source_id, []):
            new_documents.append(
                RetrievalDocumentDescriptor(
                    document_id=document.document_id,
                    source_id=document.source_id,
                    title=document.title,
                    location=document.location,
                    chunk_count=document.chunk_count,
                    index_status=RetrievalIndexStatus(index_status),
                )
            )
            self._chunks[document.document_id] = [
                RetrievalChunkDescriptor(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_id=chunk.source_id,
                    chunk_order=chunk.chunk_order,
                    token_estimate=chunk.token_estimate,
                    preview=chunk.preview,
                    index_status=RetrievalIndexStatus(index_status),
                )
                for chunk in self._chunks.get(document.document_id, [])
            ]
        self._documents[source_id] = new_documents
