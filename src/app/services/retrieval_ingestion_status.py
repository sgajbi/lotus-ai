from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalDocumentVersionLifecycleStatus,
    RetrievalIngestionDeliveryStage,
    RetrievalIngestionJobStatus,
    RetrievalIngestionStatusResponse,
)
from app.services.retrieval_store import get_retrieval_repository
from app.services.runtime_readiness import get_retrieval_store_runtime_status


def build_retrieval_ingestion_status() -> RetrievalIngestionStatusResponse:
    store_status = get_retrieval_store_runtime_status()
    if store_status.status != "READY":
        return RetrievalIngestionStatusResponse(
            service=settings.service_name,
            delivery_phase=settings.delivery_phase,
            retrieval_mode=settings.retrieval_mode,
            retrieval_store_mode=settings.retrieval_store_mode,
            ingestion_delivery_stage=RetrievalIngestionDeliveryStage.CATALOG_ONLY,
            live_ingestion_enabled=False,
            document_version_count=0,
            active_document_version_count=0,
            superseded_document_version_count=0,
            withdrawn_document_version_count=0,
            ingestion_job_count=0,
            staged_ingestion_job_count=0,
            blocked_ingestion_job_count=0,
            runtime_findings=[
                "Retrieval ingestion durable state is unavailable because the active retrieval store is not ready."
            ],
            recent_document_versions=[],
            recent_ingestion_jobs=[],
        )

    repository = get_retrieval_repository()
    versions = repository.list_document_versions()
    jobs = repository.list_ingestion_jobs()

    active_count = sum(
        1
        for version in versions
        if version.lifecycle_status == RetrievalDocumentVersionLifecycleStatus.ACTIVE
    )
    superseded_count = sum(
        1
        for version in versions
        if version.lifecycle_status == RetrievalDocumentVersionLifecycleStatus.SUPERSEDED
    )
    withdrawn_count = sum(
        1
        for version in versions
        if version.lifecycle_status == RetrievalDocumentVersionLifecycleStatus.WITHDRAWN
    )
    staged_job_count = sum(1 for job in jobs if job.status == RetrievalIngestionJobStatus.STAGED)
    blocked_job_count = sum(1 for job in jobs if job.status == RetrievalIngestionJobStatus.BLOCKED)

    findings = [
        "Durable ingestion job and document-version state is now present for governed corpus lineage review.",
        "Live ingestion execution remains disabled until async ingestion and corpus-refresh runtime support is implemented.",
    ]
    if blocked_job_count > 0:
        findings.append(
            "Some corpus-change requests remain blocked because live onboarding execution is not enabled yet."
        )
    if withdrawn_count > 0:
        findings.append(
            "Withdrawn document versions remain visible as historical corpus state and are not deleted."
        )

    return RetrievalIngestionStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        retrieval_store_mode=settings.retrieval_store_mode,
        ingestion_delivery_stage=RetrievalIngestionDeliveryStage.DURABLE_STATE_READY,
        live_ingestion_enabled=False,
        document_version_count=len(versions),
        active_document_version_count=active_count,
        superseded_document_version_count=superseded_count,
        withdrawn_document_version_count=withdrawn_count,
        ingestion_job_count=len(jobs),
        staged_ingestion_job_count=staged_job_count,
        blocked_ingestion_job_count=blocked_job_count,
        runtime_findings=findings,
        recent_document_versions=versions[:10],
        recent_ingestion_jobs=jobs[:10],
    )
