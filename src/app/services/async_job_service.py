from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobCatalogResponse,
    AsyncJobArtifactDescriptor,
    AsyncJobDetailResponse,
    AsyncJobStatus,
)
from app.async_runtime.job_registry import load_async_job_artifacts
from app.services.async_job_mapping import map_async_runtime_job
from app.services.async_runtime_store import get_async_runtime_store


def build_async_job_catalog() -> AsyncJobCatalogResponse:
    runtime_jobs = [map_async_runtime_job(record) for record in get_async_runtime_store().list_jobs()]
    staged_jobs = load_async_job_artifacts()
    jobs = sorted(runtime_jobs + staged_jobs, key=lambda job: job.submitted_at, reverse=True)
    queued_job_count = sum(1 for job in jobs if job.status == AsyncJobStatus.QUEUED)
    return AsyncJobCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        job_count=len(jobs),
        queued_job_count=queued_job_count,
        jobs=jobs,
    )


def build_async_job_detail(*, job_id: str) -> AsyncJobDetailResponse:
    runtime_record = get_async_runtime_store().get_job(job_id=job_id)
    job: AsyncJobArtifactDescriptor | None
    if runtime_record is not None:
        job = map_async_runtime_job(runtime_record)
    else:
        jobs = load_async_job_artifacts()
        job = next((item for item in jobs if item.job_id == job_id), None)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Async job artifact '{job_id}' was not found.",
        )
    return AsyncJobDetailResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        job=job,
    )
