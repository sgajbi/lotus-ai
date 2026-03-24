from __future__ import annotations

from app.config import settings
from app.contracts.retrieval import (
    RetrievalDocumentVersionLifecycleStatus,
    RetrievalIngestionDeliveryStage,
    RetrievalIngestionJobStatus,
    RetrievalIngestionStatusResponse,
)
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.async_job_type_catalog import get_async_job_type_descriptor
from app.services.artifact_runtime import ACTIVE_ARTIFACT_DOMAINS, build_artifact_runtime_status
from app.services.retrieval_ingestion_artifacts import load_retrieval_ingestion_artifact_refs
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
            running_ingestion_job_count=0,
            failed_ingestion_job_count=0,
            completed_ingestion_job_count=0,
            artifact_backed_job_count=0,
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
    running_job_count = sum(1 for job in jobs if job.status == RetrievalIngestionJobStatus.RUNNING)
    failed_job_count = sum(1 for job in jobs if job.status == RetrievalIngestionJobStatus.FAILED)
    completed_job_count = sum(
        1 for job in jobs if job.status == RetrievalIngestionJobStatus.COMPLETED
    )
    ingestion_job_type = get_async_job_type_descriptor(job_type="document_ingestion")
    async_enabled = bool(ingestion_job_type and ingestion_job_type.enabled)
    artifact_runtime = build_artifact_runtime_status()
    artifact_review_ready = (
        artifact_runtime.metadata_store.status is RuntimeReadinessStatus.READY
        and artifact_runtime.object_store.status is RuntimeReadinessStatus.READY
        and "retrieval" in ACTIVE_ARTIFACT_DOMAINS
    )
    recent_jobs = [
        job.model_copy(
            update={"artifact_refs": load_retrieval_ingestion_artifact_refs(job_id=job.job_id)}
        )
        for job in jobs[:10]
    ]
    artifact_backed_job_count = sum(
        1 for job in jobs if load_retrieval_ingestion_artifact_refs(job_id=job.job_id)
    )

    findings = [
        "Durable ingestion job and document-version state is now present for governed corpus lineage review.",
    ]
    if async_enabled:
        findings.append(
            "Bounded ingestion jobs can now execute through the durable async runtime and hand off to retrieval indexing."
        )
    else:
        findings.append(
            "Live ingestion execution remains disabled until async ingestion and corpus-refresh runtime support is implemented."
        )
    if blocked_job_count > 0:
        findings.append(
            "Some corpus-change requests remain blocked because live onboarding execution is not enabled yet."
        )
    if withdrawn_count > 0:
        findings.append(
            "Withdrawn document versions remain visible as historical corpus state and are not deleted."
        )
    if artifact_backed_job_count > 0:
        findings.append(
            "Bounded ingestion diagnostics now persist through the governed artifact backbone for corpus-change review."
        )
    elif async_enabled and not artifact_review_ready:
        findings.append(
            "Runtime-backed ingestion execution is available, but artifact-backed corpus-change diagnostics are not yet fully operational through the governed artifact backbone."
        )
    if failed_job_count > 0:
        findings.append(
            "Some ingestion jobs now report failed terminal posture and should be reviewed through bounded artifact-backed diagnostics."
        )
    findings.append(
        "Retrieval observability incident views now include ingestion and corpus-change posture instead of only live-search activation blockers."
    )

    return RetrievalIngestionStatusResponse(
        service=settings.service_name,
        delivery_phase=settings.delivery_phase,
        retrieval_mode=settings.retrieval_mode,
        retrieval_store_mode=settings.retrieval_store_mode,
        ingestion_delivery_stage=(
            RetrievalIngestionDeliveryStage.OPERATIONALLY_HARDENED
            if async_enabled and artifact_review_ready
            else (
                RetrievalIngestionDeliveryStage.RUNTIME_CONVERGED
                if async_enabled
                else RetrievalIngestionDeliveryStage.DURABLE_STATE_READY
            )
        ),
        live_ingestion_enabled=async_enabled,
        document_version_count=len(versions),
        active_document_version_count=active_count,
        superseded_document_version_count=superseded_count,
        withdrawn_document_version_count=withdrawn_count,
        ingestion_job_count=len(jobs),
        staged_ingestion_job_count=staged_job_count,
        blocked_ingestion_job_count=blocked_job_count,
        running_ingestion_job_count=running_job_count,
        failed_ingestion_job_count=failed_job_count,
        completed_ingestion_job_count=completed_job_count,
        artifact_backed_job_count=artifact_backed_job_count,
        runtime_findings=findings,
        recent_document_versions=versions[:10],
        recent_ingestion_jobs=recent_jobs,
    )
