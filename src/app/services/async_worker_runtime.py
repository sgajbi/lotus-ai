from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.contracts.async_runtime import AsyncJobStatus
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
)
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_runtime_transitions import queue_next_async_attempt

_LEASE_SECONDS = 300


@dataclass(frozen=True)
class AsyncWorkerClaimResult:
    job: AsyncRuntimeJobRecord
    attempt: AsyncRuntimeAttemptRecord
    lease: AsyncRuntimeLeaseRecord


def claim_next_async_job(*, worker_id: str) -> AsyncWorkerClaimResult | None:
    now = _utcnow()
    recover_expired_async_jobs(now=now)
    claimed = get_async_runtime_store().claim_next_runnable_job(
        worker_id=worker_id,
        claimed_at=_isoformat(now),
        heartbeat_at=_isoformat(now),
        lease_expires_at=_isoformat(now + timedelta(seconds=_LEASE_SECONDS)),
        latest_message=(
            f"Job claimed by worker '{worker_id}' and is waiting for explicit execution start."
        ),
        attempt_message=f"Attempt claimed by worker '{worker_id}'.",
    )
    if claimed is None:
        return None
    return AsyncWorkerClaimResult(
        job=claimed.job,
        attempt=claimed.attempt,
        lease=claimed.lease,
    )


def start_async_job(*, job_id: str, worker_id: str) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    job, attempt, lease = _load_claimed_runtime_state(job_id=job_id, worker_id=worker_id)
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id=attempt.attempt_id,
            job_id=attempt.job_id,
            attempt_number=attempt.attempt_number,
            lifecycle_status=AsyncJobStatus.RUNNING.value,
            worker_id=attempt.worker_id,
            claimed_at=attempt.claimed_at,
            heartbeat_at=_isoformat(now),
            started_at=attempt.started_at or _isoformat(now),
            completed_at=None,
            failure_reason=None,
            recorded_message=f"Attempt started by worker '{worker_id}'.",
        )
    )
    store.save_lease(
        AsyncRuntimeLeaseRecord(
            lease_id=lease.lease_id,
            job_id=lease.job_id,
            attempt_id=lease.attempt_id,
            worker_id=lease.worker_id,
            claimed_at=lease.claimed_at,
            heartbeat_at=_isoformat(now),
            lease_expires_at=_isoformat(now + timedelta(seconds=_LEASE_SECONDS)),
        )
    )
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job.job_id,
            job_type=job.job_type,
            target_id=job.target_id,
            lifecycle_status=AsyncJobStatus.RUNNING.value,
            submitted_at=job.submitted_at,
            caller_app=job.caller_app,
            correlation_id=job.correlation_id,
            payload_summary=job.payload_summary,
            execution_path=job.execution_path,
            related_evaluation_run_id=job.related_evaluation_run_id,
            latest_message=f"Job is running under worker '{worker_id}'.",
            attempt_count=job.attempt_count,
        )
    )


def heartbeat_async_job(*, job_id: str, worker_id: str) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    _job, attempt, lease = _load_claimed_runtime_state(job_id=job_id, worker_id=worker_id)
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id=attempt.attempt_id,
            job_id=attempt.job_id,
            attempt_number=attempt.attempt_number,
            lifecycle_status=attempt.lifecycle_status,
            worker_id=attempt.worker_id,
            claimed_at=attempt.claimed_at,
            heartbeat_at=_isoformat(now),
            started_at=attempt.started_at,
            completed_at=attempt.completed_at,
            failure_reason=attempt.failure_reason,
            recorded_message=f"Heartbeat recorded from worker '{worker_id}'.",
        )
    )
    store.save_lease(
        AsyncRuntimeLeaseRecord(
            lease_id=lease.lease_id,
            job_id=lease.job_id,
            attempt_id=lease.attempt_id,
            worker_id=lease.worker_id,
            claimed_at=lease.claimed_at,
            heartbeat_at=_isoformat(now),
            lease_expires_at=_isoformat(now + timedelta(seconds=_LEASE_SECONDS)),
        )
    )


def complete_async_job(*, job_id: str, worker_id: str, message: str) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    job, attempt, lease = _load_claimed_runtime_state(job_id=job_id, worker_id=worker_id)
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id=attempt.attempt_id,
            job_id=attempt.job_id,
            attempt_number=attempt.attempt_number,
            lifecycle_status=AsyncJobStatus.COMPLETED.value,
            worker_id=attempt.worker_id,
            claimed_at=attempt.claimed_at,
            heartbeat_at=_isoformat(now),
            started_at=attempt.started_at or attempt.claimed_at or _isoformat(now),
            completed_at=_isoformat(now),
            failure_reason=None,
            recorded_message=message,
        )
    )
    store.delete_lease(lease_id=lease.lease_id)
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job.job_id,
            job_type=job.job_type,
            target_id=job.target_id,
            lifecycle_status=AsyncJobStatus.COMPLETED.value,
            submitted_at=job.submitted_at,
            caller_app=job.caller_app,
            correlation_id=job.correlation_id,
            payload_summary=job.payload_summary,
            execution_path=job.execution_path,
            related_evaluation_run_id=job.related_evaluation_run_id,
            latest_message=message,
            attempt_count=job.attempt_count,
        )
    )


def fail_async_job(
    *,
    job_id: str,
    worker_id: str,
    failure_reason: str,
    retryable: bool,
) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    job, attempt, lease = _load_claimed_runtime_state(job_id=job_id, worker_id=worker_id)
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id=attempt.attempt_id,
            job_id=attempt.job_id,
            attempt_number=attempt.attempt_number,
            lifecycle_status=AsyncJobStatus.FAILED.value,
            worker_id=attempt.worker_id,
            claimed_at=attempt.claimed_at,
            heartbeat_at=_isoformat(now),
            started_at=attempt.started_at,
            completed_at=_isoformat(now),
            failure_reason=failure_reason,
            recorded_message=(
                f"Attempt failed under worker '{worker_id}' with reason '{failure_reason}'."
            ),
        )
    )
    store.delete_lease(lease_id=lease.lease_id)
    if retryable:
        queue_next_async_attempt(
            store=store,
            job=job,
            reason_message=f"Retry queued after failure reason '{failure_reason}'.",
        )
        return
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id=job.job_id,
            job_type=job.job_type,
            target_id=job.target_id,
            lifecycle_status=AsyncJobStatus.FAILED.value,
            submitted_at=job.submitted_at,
            caller_app=job.caller_app,
            correlation_id=job.correlation_id,
            payload_summary=job.payload_summary,
            execution_path=job.execution_path,
            related_evaluation_run_id=job.related_evaluation_run_id,
            latest_message=f"Job failed terminally with reason '{failure_reason}'.",
            attempt_count=job.attempt_count,
        )
    )


def recover_expired_async_jobs(*, now: datetime | None = None) -> list[str]:
    store = get_async_runtime_store()
    recovery_time = now or _utcnow()
    recovered_job_ids: list[str] = []
    for job in store.list_jobs():
        if job.lifecycle_status not in {
            AsyncJobStatus.CLAIMED.value,
            AsyncJobStatus.RUNNING.value,
        }:
            continue
        lease = store.get_active_lease(job_id=job.job_id)
        if lease is None:
            continue
        if lease.lease_expires_at > _isoformat(recovery_time):
            continue
        attempt = store.get_attempt(attempt_id=lease.attempt_id)
        if attempt is None:
            continue
        store.save_attempt(
            AsyncRuntimeAttemptRecord(
                attempt_id=attempt.attempt_id,
                job_id=attempt.job_id,
                attempt_number=attempt.attempt_number,
                lifecycle_status=AsyncJobStatus.ABANDONED.value,
                worker_id=attempt.worker_id,
                claimed_at=attempt.claimed_at,
                heartbeat_at=lease.heartbeat_at,
                started_at=attempt.started_at,
                completed_at=_isoformat(recovery_time),
                failure_reason="LEASE_EXPIRED",
                recorded_message="Attempt abandoned after lease expiry and queued for recovery.",
            )
        )
        store.delete_lease(lease_id=lease.lease_id)
        queue_next_async_attempt(
            store=store,
            job=job,
            reason_message="Retry queued after lease expiry recovery.",
        )
        recovered_job_ids.append(job.job_id)
    return recovered_job_ids


def _load_claimed_runtime_state(
    *,
    job_id: str,
    worker_id: str,
) -> tuple[AsyncRuntimeJobRecord, AsyncRuntimeAttemptRecord, AsyncRuntimeLeaseRecord]:
    store = get_async_runtime_store()
    job = store.get_job(job_id=job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Async job '{job_id}' was not found in runtime state.",
        )
    lease = store.get_active_lease(job_id=job_id)
    if lease is None or lease.worker_id != worker_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job_id}' is not actively leased by worker '{worker_id}'.",
        )
    attempt = store.get_attempt(attempt_id=lease.attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active runtime attempt '{lease.attempt_id}' was not found for job '{job_id}'.",
        )
    return job, attempt, lease


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
