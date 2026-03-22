from __future__ import annotations

from fastapi import HTTPException, status

from app.async_runtime.runtime_job_store import record_runtime_async_job
from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobStatus,
    AsyncJobSubmissionRequest,
    AsyncJobSubmissionResponse,
    AsyncQueueMode,
    AsyncSubmissionStatus,
    AsyncWorkerMode,
)
from app.services.retrieval_indexing_refresh import refresh_retrieval_index_job
from app.services.async_runtime_status import build_async_runtime_status


def submit_async_job(request: AsyncJobSubmissionRequest) -> AsyncJobSubmissionResponse:
    runtime = build_async_runtime_status()
    supported_job_types = {job.job_type for job in runtime.supported_job_types}
    if request.job_type not in supported_job_types:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lotus-ai async job type: {request.job_type}",
        )

    if (
        request.job_type == "retrieval_indexing"
        and runtime.queue_mode == AsyncQueueMode.STUBBED
        and runtime.worker_mode == AsyncWorkerMode.STUBBED
    ):
        if not request.target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="retrieval_indexing async jobs require target_id.",
            )
        refresh = refresh_retrieval_index_job(request.target_id)
        runtime_job = record_runtime_async_job(
            job_type=request.job_type,
            caller_app=request.caller_app,
            execution_path="in_process_stub",
            status=(
                AsyncJobStatus.COMPLETED
                if refresh.refresh.status == "COMPLETED"
                else AsyncJobStatus.FAILED
            ),
            notes=f"{request.target_id}: {refresh.refresh.message}",
        )
        return AsyncJobSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            delivery_phase=settings.delivery_phase,
            submission_status=AsyncSubmissionStatus.ACCEPTED,
            queue_mode=runtime.queue_mode,
            worker_mode=runtime.worker_mode,
            job_type=request.job_type,
            accepted=True,
            job_id=runtime_job.job_id,
            message=(
                "Async retrieval indexing ran through the in-process stub path and recorded a "
                "runtime job artifact."
            ),
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
