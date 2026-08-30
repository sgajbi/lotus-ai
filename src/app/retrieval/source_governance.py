from __future__ import annotations

from app.config import settings
from app.services.runtime_mode_config import resolve_runtime_mode_config
from app.contracts.retrieval import (
    RetrievalDocumentDescriptor,
    RetrievalDocumentVersionDescriptor,
    RetrievalIngestionJobDescriptor,
    RetrievalIndexStatus,
    RetrievalSourceDescriptor,
    RetrievalSourceGovernanceDescriptor,
    RetrievalSourceGovernanceResponse,
)
from app.retrieval.inventory_summary import summarize_retrieval_source_inventory
from app.retrieval.policy import VECTOR_STORE_STRATEGY
from app.retrieval.search_eligibility import build_document_eligibility
from app.services.retrieval_store import get_retrieval_repository


def build_retrieval_source_governance() -> RetrievalSourceGovernanceResponse:
    repository = get_retrieval_repository()
    sources = repository.list_sources()
    versions_by_document: dict[str, list[RetrievalDocumentVersionDescriptor]] = {}
    for version in repository.list_document_versions():
        versions_by_document.setdefault(version.document_id, []).append(version)
    jobs_by_document: dict[str, list[RetrievalIngestionJobDescriptor]] = {}
    jobs_by_source: dict[str, list[RetrievalIngestionJobDescriptor]] = {}
    for job in repository.list_ingestion_jobs():
        if job.document_id is not None:
            jobs_by_document.setdefault(job.document_id, []).append(job)
        jobs_by_source.setdefault(job.source_id, []).append(job)
    governance_sources = [
        _build_source_governance_descriptor(
            source=source,
            versions_by_document=versions_by_document,
            jobs_by_document=jobs_by_document,
            jobs_by_source=jobs_by_source,
        )
        for source in sources
    ]
    return RetrievalSourceGovernanceResponse(
        service=settings.service_name,
        retrieval_mode=resolve_runtime_mode_config().retrieval_mode,
        vector_store=VECTOR_STORE_STRATEGY,
        searchable_source_count=sum(1 for source in governance_sources if source.search_enabled),
        index_pending_source_count=sum(
            1 for source in governance_sources if source.governance_status == "INDEX_PENDING"
        ),
        blocked_source_count=sum(
            1 for source in governance_sources if source.governance_status == "BLOCKED_BY_SOURCE"
        ),
        empty_source_count=sum(
            1 for source in governance_sources if source.governance_status == "EMPTY"
        ),
        sources=governance_sources,
    )


def _build_source_governance_descriptor(
    *,
    source: RetrievalSourceDescriptor,
    versions_by_document: dict[str, list[RetrievalDocumentVersionDescriptor]],
    jobs_by_document: dict[str, list[RetrievalIngestionJobDescriptor]],
    jobs_by_source: dict[str, list[RetrievalIngestionJobDescriptor]],
) -> RetrievalSourceGovernanceDescriptor:
    repository = get_retrieval_repository()
    documents = repository.list_documents_for_source(source.source_id)
    inventory = summarize_retrieval_source_inventory(source.source_id)
    governance_status, notes = _derive_source_governance(
        source=source,
        documents=documents,
        index_status=inventory.index_status,
        versions_by_document=versions_by_document,
        jobs_by_document=jobs_by_document,
        jobs_by_source=jobs_by_source,
    )
    return RetrievalSourceGovernanceDescriptor(
        source_id=source.source_id,
        kind=source.kind,
        governance_status=governance_status,
        search_enabled=governance_status == "SEARCH_ENABLED",
        document_count=inventory.document_count,
        chunk_count=inventory.chunk_count,
        index_status=inventory.index_status,
        notes=notes,
    )


def _derive_source_governance(
    *,
    source: RetrievalSourceDescriptor,
    documents: list[RetrievalDocumentDescriptor],
    index_status: RetrievalIndexStatus,
    versions_by_document: dict[str, list[RetrievalDocumentVersionDescriptor]],
    jobs_by_document: dict[str, list[RetrievalIngestionJobDescriptor]],
    jobs_by_source: dict[str, list[RetrievalIngestionJobDescriptor]],
) -> tuple[str, str]:
    if any(
        build_document_eligibility(
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
        ).search_enabled
        for document in documents
    ):
        return (
            "SEARCH_ENABLED",
            "Source has at least one promoted indexed document eligible for live retrieval search.",
        )
    if not documents:
        return (
            "EMPTY",
            "Registered as an approved source class, but no staged documents are loaded yet.",
        )
    if source.enabled and index_status == RetrievalIndexStatus.STAGED:
        return (
            "INDEX_PENDING",
            "Source is enabled, but its staged documents are not fully indexed for live search yet.",
        )
    if index_status == RetrievalIndexStatus.STAGED:
        return (
            "BLOCKED_BY_SOURCE",
            "Documents are present but remain blocked from live search because the source is not enabled.",
        )
    return (
        "REGISTERED_ONLY",
        "Registered in the retrieval corpus, but no document is currently eligible for live search.",
    )
