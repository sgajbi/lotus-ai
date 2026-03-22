from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobCatalogResponse,
    AsyncJobDetailResponse,
    AsyncJobStatus,
)
from app.async_runtime.job_registry import load_async_job_artifacts


def build_async_job_catalog() -> AsyncJobCatalogResponse:
    jobs = load_async_job_artifacts()
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
