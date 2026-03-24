from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.retrieval import (
    RetrievalIngestionJobCatalogResponse,
    RetrievalIngestionJobDescriptor,
    RetrievalIngestionJobDetailResponse,
    RetrievalIngestionJobStepDescriptor,
    RetrievalIngestionJobStatus,
    RetrievalPipelineStage,
)
from app.repositories.async_runtime_repository import AsyncRuntimeJobRecord
from app.services.retrieval_ingestion_artifacts import load_retrieval_ingestion_artifact_refs
from app.services.async_runtime_store import get_async_runtime_store
from app.services.retrieval_store import get_retrieval_repository


def build_retrieval_ingestion_job_catalog() -> RetrievalIngestionJobCatalogResponse:
    jobs = [
        _overlay_runtime_status(job) for job in get_retrieval_repository().list_ingestion_jobs()
    ]
    return RetrievalIngestionJobCatalogResponse(
        service=settings.service_name,
        jobs=jobs,
    )


def get_retrieval_ingestion_job_detail(job_id: str) -> RetrievalIngestionJobDetailResponse:
    descriptor = get_retrieval_ingestion_job_or_raise(job_id)
    follow_on_job = _get_follow_on_retrieval_index_job(source_id=descriptor.source_id)
    return RetrievalIngestionJobDetailResponse(
        service=settings.service_name,
        job=descriptor,
        steps=[
            RetrievalIngestionJobStepDescriptor(
                step_id=f"{job_id}.governance_record",
                name="Governance record",
                stage=RetrievalPipelineStage.ENABLED,
                runtime_status=None,
                linked_async_job_id=None,
                description=(
                    "Corpus-change intent is durably recorded as an ingestion job and remains independently reviewable from indexing state."
                ),
            ),
            RetrievalIngestionJobStepDescriptor(
                step_id=f"{job_id}.document_lineage",
                name="Document lineage",
                stage=(
                    RetrievalPipelineStage.ENABLED
                    if descriptor.target_version_id is not None
                    else RetrievalPipelineStage.STAGED
                ),
                runtime_status=None,
                linked_async_job_id=None,
                description=(
                    "Document-version lineage is recorded durably so refresh, supersession, and withdrawal posture can be inspected explicitly."
                ),
            ),
            RetrievalIngestionJobStepDescriptor(
                step_id=f"{job_id}.async_execution",
                name="Async ingestion execution",
                stage=(
                    RetrievalPipelineStage.ENABLED
                    if descriptor.linked_async_job_id is not None
                    else RetrievalPipelineStage.STAGED
                ),
                runtime_status=descriptor.runtime_status,
                linked_async_job_id=descriptor.linked_async_job_id,
                description=(
                    "Ingestion can execute through the durable async backbone instead of a separate long-running-job system."
                ),
            ),
            RetrievalIngestionJobStepDescriptor(
                step_id=f"{job_id}.index_followthrough",
                name="Index follow-through",
                stage=(
                    RetrievalPipelineStage.ENABLED
                    if follow_on_job is not None
                    else RetrievalPipelineStage.STAGED
                ),
                runtime_status=None if follow_on_job is None else follow_on_job.lifecycle_status,
                linked_async_job_id=None if follow_on_job is None else follow_on_job.job_id,
                description=(
                    "Completed ingestion can hand off to the existing retrieval indexing async path for the affected source."
                ),
            ),
        ],
    )


def get_retrieval_ingestion_job_or_raise(job_id: str) -> RetrievalIngestionJobDescriptor:
    descriptor = get_retrieval_repository().get_ingestion_job(job_id)
    if descriptor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown retrieval ingestion job_id: {job_id}",
        )
    return _overlay_runtime_status(descriptor)


def _overlay_runtime_status(
    descriptor: RetrievalIngestionJobDescriptor,
) -> RetrievalIngestionJobDescriptor:
    descriptor = descriptor.model_copy(
        update={"artifact_refs": load_retrieval_ingestion_artifact_refs(job_id=descriptor.job_id)}
    )
    runtime_job = _get_runtime_async_ingestion_job(job_id=descriptor.job_id)
    if runtime_job is None:
        return descriptor
    overlaid_status = descriptor.status
    if runtime_job.lifecycle_status in RetrievalIngestionJobStatus._value2member_map_:
        overlaid_status = RetrievalIngestionJobStatus(runtime_job.lifecycle_status)
    return descriptor.model_copy(
        update={
            "status": overlaid_status,
            "runtime_status": runtime_job.lifecycle_status,
            "linked_async_job_id": runtime_job.job_id,
            "message": runtime_job.latest_message,
        }
    )


def _get_runtime_async_ingestion_job(job_id: str) -> AsyncRuntimeJobRecord | None:
    jobs = [
        job
        for job in get_async_runtime_store().list_jobs()
        if job.job_type == "document_ingestion" and job.target_id == job_id
    ]
    if not jobs:
        return None
    return max(jobs, key=lambda item: item.submitted_at)


def _get_follow_on_retrieval_index_job(source_id: str) -> AsyncRuntimeJobRecord | None:
    retrieval_job_id = f"retjob_{source_id.replace('-', '_')}"
    jobs = [
        job
        for job in get_async_runtime_store().list_jobs()
        if job.job_type == "retrieval_indexing" and job.target_id == retrieval_job_id
    ]
    if not jobs:
        return None
    return max(jobs, key=lambda item: item.submitted_at)
