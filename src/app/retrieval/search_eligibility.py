from __future__ import annotations

from dataclasses import dataclass

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalDocumentVersionDescriptor,
    RetrievalDocumentVersionLifecycleStatus,
    RetrievalIngestionAction,
    RetrievalIngestionJobDescriptor,
    RetrievalIngestionJobStatus,
    RetrievalIndexStatus,
    RetrievalSourceDescriptor,
)


@dataclass(frozen=True)
class RetrievalDocumentEligibility:
    governance_status: str
    search_enabled: bool
    active_version_id: str | None
    active_version_refresh_action: RetrievalIngestionAction | None
    active_version_created_at: str | None
    pending_ingestion_job_count: int
    notes: str


def build_document_eligibility(
    *,
    source: RetrievalSourceDescriptor,
    document: RetrievalDocumentDescriptor,
    document_versions: list[RetrievalDocumentVersionDescriptor],
    ingestion_jobs: list[RetrievalIngestionJobDescriptor],
) -> RetrievalDocumentEligibility:
    active_version = next(
        (
            version
            for version in sorted(document_versions, key=lambda item: item.created_at, reverse=True)
            if version.lifecycle_status == RetrievalDocumentVersionLifecycleStatus.ACTIVE
        ),
        None,
    )
    latest_version = (
        None
        if not document_versions
        else max(document_versions, key=lambda item: (item.created_at, item.version_id))
    )
    pending_ingestion_job_count = sum(
        1
        for job in ingestion_jobs
        if job.status
        in {
            RetrievalIngestionJobStatus.STAGED,
            RetrievalIngestionJobStatus.RECORDED,
            RetrievalIngestionJobStatus.QUEUED,
            RetrievalIngestionJobStatus.RUNNING,
        }
    )
    if latest_version is not None and latest_version.lifecycle_status == RetrievalDocumentVersionLifecycleStatus.WITHDRAWN:
        return RetrievalDocumentEligibility(
            governance_status="WITHDRAWN",
            search_enabled=False,
            active_version_id=None,
            active_version_refresh_action=None,
            active_version_created_at=None,
            pending_ingestion_job_count=pending_ingestion_job_count,
            notes="Latest governed document lineage is withdrawn, so the document is withheld from live search.",
        )
    if not source.enabled:
        return RetrievalDocumentEligibility(
            governance_status="BLOCKED_BY_SOURCE",
            search_enabled=False,
            active_version_id=None if active_version is None else active_version.version_id,
            active_version_refresh_action=None
            if active_version is None
            else active_version.refresh_action,
            active_version_created_at=(
                None if active_version is None else active_version.created_at
            ),
            pending_ingestion_job_count=pending_ingestion_job_count,
            notes="Document remains blocked from live search because its source is not enabled.",
        )
    runtime_pending_ingestion_job_count = sum(
        1
        for job in ingestion_jobs
        if job.status
        in {
            RetrievalIngestionJobStatus.QUEUED,
            RetrievalIngestionJobStatus.RUNNING,
        }
    )
    if runtime_pending_ingestion_job_count > 0:
        return RetrievalDocumentEligibility(
            governance_status="REFRESH_PENDING",
            search_enabled=False,
            active_version_id=None if active_version is None else active_version.version_id,
            active_version_refresh_action=None
            if active_version is None
            else active_version.refresh_action,
            active_version_created_at=(
                None if active_version is None else active_version.created_at
            ),
            pending_ingestion_job_count=runtime_pending_ingestion_job_count,
            notes="Governed corpus-change work is still in flight, so live search remains withheld until refresh and reindex settle.",
        )
    if active_version is None:
        return RetrievalDocumentEligibility(
            governance_status="LINEAGE_INCOMPLETE",
            search_enabled=False,
            active_version_id=None,
            active_version_refresh_action=None,
            active_version_created_at=None,
            pending_ingestion_job_count=pending_ingestion_job_count,
            notes="No active governed document version is currently recorded for this document.",
        )
    if document.index_status == RetrievalIndexStatus.INDEXED:
        return RetrievalDocumentEligibility(
            governance_status="SEARCH_ENABLED",
            search_enabled=True,
            active_version_id=active_version.version_id,
            active_version_refresh_action=active_version.refresh_action,
            active_version_created_at=active_version.created_at,
            pending_ingestion_job_count=pending_ingestion_job_count,
            notes="Document is promoted through an enabled source and is fully indexed for live search.",
        )
    return RetrievalDocumentEligibility(
        governance_status="INDEX_PENDING",
        search_enabled=False,
        active_version_id=active_version.version_id,
        active_version_refresh_action=active_version.refresh_action,
        active_version_created_at=active_version.created_at,
        pending_ingestion_job_count=pending_ingestion_job_count,
        notes="Source is enabled, but the document is not fully indexed yet and cannot enter live search.",
    )


def is_live_search_chunk_eligible(
    *,
    source: RetrievalSourceDescriptor,
    document: RetrievalDocumentDescriptor,
    chunk: RetrievalChunkDescriptor,
    document_versions: list[RetrievalDocumentVersionDescriptor],
    ingestion_jobs: list[RetrievalIngestionJobDescriptor],
) -> bool:
    document_eligibility = build_document_eligibility(
        source=source,
        document=document,
        document_versions=document_versions,
        ingestion_jobs=ingestion_jobs,
    )
    return (
        document_eligibility.search_enabled and chunk.index_status == RetrievalIndexStatus.INDEXED
    )
