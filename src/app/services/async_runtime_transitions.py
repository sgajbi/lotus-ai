from __future__ import annotations

from dataclasses import replace

from app.contracts.async_runtime import AsyncJobStatus
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeRepository,
)
from app.services.async_submission_shared import publish_async_attempt_if_configured


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
        replace(
            job,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            latest_message=reason_message,
            attempt_count=next_attempt_number,
        )
    )
    queued_job = store.get_job(job_id=job.job_id)
    if queued_job is not None:
        publish_async_attempt_if_configured(job=queued_job, attempt=attempt)
    return attempt
