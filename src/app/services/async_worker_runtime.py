from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json

from fastapi import HTTPException, status

from app.contracts.async_runtime import AsyncJobStatus
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeClaimTransition,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
)
from app.services.eval_attempt_runtime import (
    abandon_active_evaluation_attempt,
    claim_active_evaluation_attempt,
    queue_next_evaluation_attempt,
)
from app.repositories.artifact_repository import ArtifactRecord
from app.services.artifact_payloads import stage_json_artifact
from app.services.artifact_store import get_artifact_object_store, get_artifact_repository
from app.services.async_submission_shared import publish_async_attempt_if_configured
from app.services.async_runtime_store import get_async_runtime_store

_LEASE_SECONDS = 300


@dataclass(frozen=True)
class AsyncWorkerClaimResult:
    job: AsyncRuntimeJobRecord
    attempt: AsyncRuntimeAttemptRecord
    lease: AsyncRuntimeLeaseRecord


def claim_next_async_job(*, worker_id: str) -> AsyncWorkerClaimResult | None:
    return claim_next_async_job_for_types(worker_id=worker_id, job_types=None)


def claim_next_async_job_for_types(
    *,
    worker_id: str,
    job_types: tuple[str, ...] | None,
) -> AsyncWorkerClaimResult | None:
    now = _utcnow()
    recover_expired_async_jobs(now=now)
    claimed = get_async_runtime_store().claim_next_runnable_job(
        worker_id=worker_id,
        job_types=job_types,
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
    if claimed.job.related_evaluation_run_id is not None:
        claim_active_evaluation_attempt(
            run_id=claimed.job.related_evaluation_run_id,
            worker_id=worker_id,
            reason_message=(
                f"Evaluation attempt claimed by worker '{worker_id}' and is waiting for explicit execution start."
            ),
        )
    return AsyncWorkerClaimResult(
        job=claimed.job,
        attempt=claimed.attempt,
        lease=claimed.lease,
    )


def claim_async_job_by_id(*, job_id: str, worker_id: str) -> AsyncWorkerClaimResult | None:
    now = _utcnow()
    recover_expired_async_jobs(now=now)
    claimed = get_async_runtime_store().claim_runnable_job_by_id(
        job_id=job_id,
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
    if claimed.job.related_evaluation_run_id is not None:
        claim_active_evaluation_attempt(
            run_id=claimed.job.related_evaluation_run_id,
            worker_id=worker_id,
            reason_message=(
                f"Evaluation attempt claimed by worker '{worker_id}' and is waiting for explicit execution start."
            ),
        )
    return AsyncWorkerClaimResult(
        job=claimed.job,
        attempt=claimed.attempt,
        lease=claimed.lease,
    )


def start_async_job(*, job_id: str, worker_id: str, attempt_id: str) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    transitioned = store.transition_current_claim(
        job_id=job_id,
        worker_id=worker_id,
        attempt_id=attempt_id,
        now=_isoformat(now),
        job_status=AsyncJobStatus.RUNNING.value,
        job_message=f"Job is running under worker '{worker_id}'.",
        attempt_status=AsyncJobStatus.RUNNING.value,
        attempt_message=f"Attempt started by worker '{worker_id}'.",
        failure_reason=None,
        lease_expires_at=_isoformat(now + timedelta(seconds=_LEASE_SECONDS)),
        terminal_artifact=None,
    )
    _require_current_claim(transitioned, job_id=job_id, worker_id=worker_id)


def heartbeat_async_job(*, job_id: str, worker_id: str, attempt_id: str) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    transitioned = store.transition_current_claim(
        job_id=job_id,
        worker_id=worker_id,
        attempt_id=attempt_id,
        now=_isoformat(now),
        job_status=None,
        job_message=None,
        attempt_status=None,
        attempt_message=f"Heartbeat recorded from worker '{worker_id}'.",
        failure_reason=None,
        lease_expires_at=_isoformat(now + timedelta(seconds=_LEASE_SECONDS)),
        terminal_artifact=None,
    )
    _require_current_claim(transitioned, job_id=job_id, worker_id=worker_id)


def complete_async_job(*, job_id: str, worker_id: str, attempt_id: str, message: str) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    job, attempt, _lease = _load_claimed_runtime_state(
        job_id=job_id, worker_id=worker_id, attempt_id=attempt_id
    )
    completion_artifact = stage_json_artifact(
        domain="async",
        artifact_type="job_terminal_output",
        source_object_kind="async_job",
        source_object_id=job.job_id,
        created_at=_isoformat(now),
        created_by=worker_id,
        tenant_id=job.tenant_id,
        payload_json=json.dumps(
            {
                "job_id": job.job_id,
                "attempt_id": attempt.attempt_id,
                "job_type": job.job_type,
                "target_id": job.target_id,
                "status": AsyncJobStatus.COMPLETED.value,
                "message": message,
                "related_evaluation_run_id": job.related_evaluation_run_id,
            },
            sort_keys=True,
        ).encode("utf-8"),
    )
    transitioned = store.transition_current_claim(
        job_id=job_id,
        worker_id=worker_id,
        attempt_id=attempt_id,
        now=_isoformat(now),
        job_status=AsyncJobStatus.COMPLETED.value,
        job_message=message,
        attempt_status=AsyncJobStatus.COMPLETED.value,
        attempt_message=message,
        failure_reason=None,
        lease_expires_at=None,
        terminal_artifact=completion_artifact,
    )
    _publish_terminal_artifact_or_reject(
        transition=transitioned,
        artifact=completion_artifact,
        job_id=job_id,
        worker_id=worker_id,
    )


def fail_async_job(
    *,
    job_id: str,
    worker_id: str,
    attempt_id: str,
    failure_reason: str,
    retryable: bool,
) -> None:
    store = get_async_runtime_store()
    now = _utcnow()
    job, attempt, _lease = _load_claimed_runtime_state(
        job_id=job_id, worker_id=worker_id, attempt_id=attempt_id
    )
    attempt_message = f"Attempt failed under worker '{worker_id}' with reason '{failure_reason}'."
    if retryable:
        next_attempt_number = job.attempt_count + 1
        next_attempt = AsyncRuntimeAttemptRecord(
            attempt_id=f"{job.job_id}_attempt_{next_attempt_number:03d}",
            job_id=job.job_id,
            attempt_number=next_attempt_number,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message=f"Retry queued after failure reason '{failure_reason}'.",
        )
        transitioned = store.transition_current_claim(
            job_id=job_id,
            worker_id=worker_id,
            attempt_id=attempt_id,
            now=_isoformat(now),
            job_status=AsyncJobStatus.QUEUED.value,
            job_message=next_attempt.recorded_message,
            attempt_status=AsyncJobStatus.FAILED.value,
            attempt_message=attempt_message,
            failure_reason=failure_reason,
            lease_expires_at=None,
            terminal_artifact=None,
            next_attempt=next_attempt,
        )
        transitioned = _require_current_claim(transitioned, job_id=job_id, worker_id=worker_id)
        publish_async_attempt_if_configured(job=transitioned.job, attempt=next_attempt)
        return
    failure_artifact = stage_json_artifact(
        domain="async",
        artifact_type="job_terminal_output",
        source_object_kind="async_job",
        source_object_id=job.job_id,
        created_at=_isoformat(now),
        created_by=worker_id,
        tenant_id=job.tenant_id,
        payload_json=json.dumps(
            {
                "job_id": job.job_id,
                "attempt_id": attempt.attempt_id,
                "job_type": job.job_type,
                "target_id": job.target_id,
                "status": AsyncJobStatus.FAILED.value,
                "failure_reason": failure_reason,
                "related_evaluation_run_id": job.related_evaluation_run_id,
            },
            sort_keys=True,
        ).encode("utf-8"),
    )
    transitioned = store.transition_current_claim(
        job_id=job_id,
        worker_id=worker_id,
        attempt_id=attempt_id,
        now=_isoformat(now),
        job_status=AsyncJobStatus.FAILED.value,
        job_message=f"Job failed terminally with reason '{failure_reason}'.",
        attempt_status=AsyncJobStatus.FAILED.value,
        attempt_message=attempt_message,
        failure_reason=failure_reason,
        lease_expires_at=None,
        terminal_artifact=failure_artifact,
    )
    _publish_terminal_artifact_or_reject(
        transition=transitioned,
        artifact=failure_artifact,
        job_id=job_id,
        worker_id=worker_id,
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
        next_attempt = AsyncRuntimeAttemptRecord(
            attempt_id=f"{job.job_id}_attempt_{job.attempt_count + 1:03d}",
            job_id=job.job_id,
            attempt_number=job.attempt_count + 1,
            lifecycle_status=AsyncJobStatus.QUEUED.value,
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Retry queued after lease expiry recovery.",
        )
        recovered = store.recover_expired_claim(
            job_id=job.job_id,
            recovered_at=_isoformat(recovery_time),
            next_attempt=next_attempt,
        )
        if recovered is None:
            continue
        publish_async_attempt_if_configured(job=recovered.job, attempt=recovered.next_attempt)
        if job.related_evaluation_run_id is not None:
            abandon_active_evaluation_attempt(
                run_id=job.related_evaluation_run_id,
                reason_message="Evaluation attempt abandoned after async lease expiry recovery.",
                failure_reason="LEASE_EXPIRED",
            )
            queue_next_evaluation_attempt(
                run_id=job.related_evaluation_run_id,
                reason_message="Evaluation retry queued after async lease expiry recovery.",
            )
        recovered_job_ids.append(recovered.job.job_id)
    return recovered_job_ids


def _load_claimed_runtime_state(
    *,
    job_id: str,
    worker_id: str,
    attempt_id: str,
) -> tuple[AsyncRuntimeJobRecord, AsyncRuntimeAttemptRecord, AsyncRuntimeLeaseRecord]:
    store = get_async_runtime_store()
    job = store.get_job(job_id=job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Async job '{job_id}' was not found in runtime state.",
        )
    lease = store.get_active_lease(job_id=job_id)
    if lease is None or lease.worker_id != worker_id or lease.attempt_id != attempt_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Async job '{job_id}' is not actively leased by worker '{worker_id}'.",
        )
    attempt = store.get_attempt(attempt_id=attempt_id)
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Active runtime attempt '{lease.attempt_id}' was not found for job '{job_id}'.",
        )
    return job, attempt, lease


def _require_current_claim(
    transition: AsyncRuntimeClaimTransition | None, *, job_id: str, worker_id: str
) -> AsyncRuntimeClaimTransition:
    if transition is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Async job '{job_id}' no longer has an unexpired current claim for worker "
                f"'{worker_id}'."
            ),
        )
    return transition


def _publish_terminal_artifact_or_reject(
    *,
    transition: AsyncRuntimeClaimTransition | None,
    artifact: ArtifactRecord,
    job_id: str,
    worker_id: str,
) -> None:
    """Publish compatibility metadata only after the durable claim transition.

    The SQL runtime repository writes this metadata in the same transaction as
    the job terminal state. The idempotent repository save preserves the
    in-memory development-store contract without giving a stale claim a
    visible artifact record.
    """

    if transition is None:
        object_key = artifact.storage_reference.split("://", maxsplit=1)[-1]
        get_artifact_object_store().delete_object(object_key=object_key)
        _require_current_claim(transition, job_id=job_id, worker_id=worker_id)
    get_artifact_repository().save_artifact(artifact)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _isoformat(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
