from __future__ import annotations

from app.contracts.async_runtime import AsyncJobStatus
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeRepository,
)


def queue_next_async_attempt(
    *,
    store: AsyncRuntimeRepository,
    job: AsyncRuntimeJobRecord,
    reason_message: str,
) -> AsyncRuntimeAttemptRecord:
    next_attempt_number = job.attempt_count + 1
    next_attempt_id = f"{job.job_id}_attempt_{next_attempt_number:03d}"
    attempt = AsyncRuntimeAttemptRecord(
        attempt_id=next_attempt_id,
        job_id=job.job_id,
        attempt_number=next_attempt_number,
        lifecycle_status=AsyncJobStatus.QUEUED.value,
        worker_id=None,
        claimed_at=None,
        heartbeat_at=None,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        recorded_message=reason_message,
    )
    store.save_attempt(attempt)
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job.job_id,
            job_type=job.job_type,
            target_id=job.target_id,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            submitted_at=job.submitted_at,
            caller_app=job.caller_app,
            correlation_id=job.correlation_id,
            payload_summary=job.payload_summary,
            execution_path=job.execution_path,
            related_evaluation_run_id=job.related_evaluation_run_id,
            latest_message=reason_message,
            attempt_count=next_attempt_number,
        )
    )
    return attempt
