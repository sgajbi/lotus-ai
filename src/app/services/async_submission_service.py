from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.contracts.async_runtime import (
    AsyncJobStatus,
    AsyncJobSubmissionRequest,
    AsyncJobSubmissionResponse,
    AsyncQueueMode,
    AsyncSubmissionStatus,
    AsyncWorkerMode,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.services.async_job_type_catalog import get_async_job_type_descriptor
from app.services.async_runtime_store import get_async_runtime_store


def submit_async_job(request: AsyncJobSubmissionRequest) -> AsyncJobSubmissionResponse:
    job_type = get_async_job_type_descriptor(job_type=request.job_type)
    if job_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lotus-ai async job type: {request.job_type}",
        )

    if not job_type.enabled:
        return AsyncJobSubmissionResponse(
            service=settings.service_name,
            version=settings.service_version,
            delivery_phase=settings.delivery_phase,
            submission_status=AsyncSubmissionStatus.REJECTED,
            queue_mode=AsyncQueueMode.STUBBED,
            worker_mode=AsyncWorkerMode.STUBBED,
            job_type=request.job_type,
            accepted=False,
            job_id=None,
            message=(
                f"Async job type '{request.job_type}' remains staged-only in the current phase and "
                "is not yet allowlisted for durable runtime-backed submission and stubbed worker handling."
            ),
        )
    submitted_at = _utcnow().isoformat().replace("+00:00", "Z")
    job_id = f"asyncjob_{request.job_type}_{uuid4().hex[:12]}"
    attempt_id = f"{job_id}_attempt_001"
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job_id,
            job_type=request.job_type,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            submitted_at=submitted_at,
            caller_app=request.caller_app,
            correlation_id=request.correlation_id,
            payload_summary=request.payload_summary,
            execution_path=job_type.execution_path,
            related_evaluation_run_id=None,
            latest_message=(
                "Job accepted into durable async runtime state and is waiting for a later "
                "worker-enabled execution slice."
            ),
            attempt_count=1,
        )
    )
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id=attempt_id,
            job_id=job_id,
            attempt_number=1,
            lifecycle_status="SUBMITTED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Initial durable async submission recorded.",
        )
    )

    return AsyncJobSubmissionResponse(
        service=settings.service_name,
        version=settings.service_version,
        delivery_phase=settings.delivery_phase,
        submission_status=AsyncSubmissionStatus.ACCEPTED,
        queue_mode=AsyncQueueMode.STUBBED,
        worker_mode=AsyncWorkerMode.STUBBED,
        job_type=request.job_type,
        accepted=True,
        job_id=job_id,
        message=(
            f"Async job type '{request.job_type}' is allowlisted for durable submission. The job "
            "is recorded and queued, and can later move through stubbed worker claim and completion semantics. "
            "No dedicated worker fleet is active yet."
        ),
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)
