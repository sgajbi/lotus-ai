from __future__ import annotations

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobSubmissionRequest,
    AsyncJobSubmissionResponse,
    AsyncQueueMode,
    AsyncSubmissionStatus,
    AsyncWorkerMode,
)
from app.services.async_runtime_status import build_async_runtime_status


def submit_async_job(request: AsyncJobSubmissionRequest) -> AsyncJobSubmissionResponse:
    runtime = build_async_runtime_status()
    supported_job_types = {job.job_type for job in runtime.supported_job_types}
    if request.job_type not in supported_job_types:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lotus-ai async job type: {request.job_type}",
        )

    return AsyncJobSubmissionResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        submission_status=AsyncSubmissionStatus.REJECTED,
        queue_mode=AsyncQueueMode.DISABLED,
        worker_mode=AsyncWorkerMode.DOCUMENTED_ONLY,
        job_type=request.job_type,
        accepted=False,
        job_id=None,
        message=(
            "Async submission contracts are available, but queue-backed execution is not enabled "
            "yet in the foundation phase."
        ),
    )
