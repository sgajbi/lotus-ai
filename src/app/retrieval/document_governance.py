from __future__ import annotations

from collections.abc import Iterable

from app.config import settings
from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.retrieval import (
    RetrievalDocumentVersionDescriptor,
    RetrievalIngestionJobDescriptor,
    RetrievalDocumentGovernanceDescriptor,
    RetrievalDocumentGovernanceResponse,
)
from app.repositories.retrieval_repository import RetrievalRepository
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.retrieval.search_eligibility import build_document_eligibility
from app.services.retrieval_store import get_retrieval_repository


def build_retrieval_document_governance(
    *,
    source_ids: Iterable[str] | None = None,
    repository: RetrievalRepository | None = None,
) -> RetrievalDocumentGovernanceResponse:
    repository = repository or get_retrieval_repository()
    allowed_source_ids = None if source_ids is None else set(source_ids)
    versions_by_document: dict[str, list[RetrievalDocumentVersionDescriptor]] = {}
    for version in repository.list_document_versions():
        versions_by_document.setdefault(version.document_id, []).append(version)
    jobs_by_document: dict[str, list[RetrievalIngestionJobDescriptor]] = {}
    jobs_by_source: dict[str, list[RetrievalIngestionJobDescriptor]] = {}
    for job in repository.list_ingestion_jobs():
        if job.document_id is not None:
            jobs_by_document.setdefault(job.document_id, []).append(job)
        jobs_by_source.setdefault(job.source_id, []).append(job)
    documents: list[RetrievalDocumentGovernanceDescriptor] = []
    for source in repository.list_sources():
        if allowed_source_ids is not None and source.source_id not in allowed_source_ids:
            continue
        for document in repository.list_documents_for_source(source.source_id):
            eligibility = build_document_eligibility(
                source=source,
                document=document,
                document_versions=versions_by_document.get(document.document_id, []),
                ingestion_jobs=[
                    *[
                        job
                        for job in jobs_by_source.get(source.source_id, [])
                        if job.document_id is None
                    ],
                    *jobs_by_document.get(document.document_id, []),
                ],
            )
            documents.append(
                RetrievalDocumentGovernanceDescriptor(
                    document_id=document.document_id,
                    source_id=document.source_id,
                    title=document.title,
                    governance_status=eligibility.governance_status,
                    search_enabled=eligibility.search_enabled,
                    chunk_count=document.chunk_count,
                    index_status=document.index_status,
                    active_version_id=eligibility.active_version_id,
                    active_version_refresh_action=eligibility.active_version_refresh_action,
                    active_version_created_at=eligibility.active_version_created_at,
                    pending_ingestion_job_count=eligibility.pending_ingestion_job_count,
                    notes=eligibility.notes,
                )
            )

    documents.sort(key=lambda item: (item.source_id, item.document_id))
    return RetrievalDocumentGovernanceResponse(
        service=settings.service_name,
        retrieval_mode=resolve_runtime_mode_config().retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        searchable_document_count=sum(1 for document in documents if document.search_enabled),
        index_pending_document_count=sum(
            1 for document in documents if document.governance_status == "INDEX_PENDING"
        ),
        blocked_document_count=sum(
            1 for document in documents if document.governance_status == "BLOCKED_BY_SOURCE"
        ),
        refresh_pending_document_count=sum(
            1 for document in documents if document.governance_status == "REFRESH_PENDING"
        ),
        withdrawn_document_count=sum(
            1 for document in documents if document.governance_status == "WITHDRAWN"
        ),
        documents=documents,
    )
