from __future__ import annotations

from app.contracts.async_runtime import (
    AsyncJobArtifactDescriptor,
    AsyncJobAttemptDescriptor,
    AsyncJobLeaseDescriptor,
    AsyncJobRecordSource,
    AsyncJobStatus,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
)


def map_async_runtime_job(record: AsyncRuntimeJobRecord) -> AsyncJobArtifactDescriptor:
    return AsyncJobArtifactDescriptor(
        job_id=record.job_id,
        job_type=record.job_type,
        target_id=record.target_id,
        status=AsyncJobStatus(record.lifecycle_status),
        record_source=AsyncJobRecordSource.RUNTIME_STATE,
        submitted_at=record.submitted_at,
        caller_app=record.caller_app,
        related_evaluation_run_id=record.related_evaluation_run_id,
        execution_path=record.execution_path,
        notes=record.latest_message,
    )


def map_async_runtime_attempt(record: AsyncRuntimeAttemptRecord) -> AsyncJobAttemptDescriptor:
    return AsyncJobAttemptDescriptor(
        attempt_id=record.attempt_id,
        attempt_number=record.attempt_number,
        status=record.lifecycle_status,
        worker_id=record.worker_id,
        claimed_at=record.claimed_at,
        heartbeat_at=record.heartbeat_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        failure_reason=record.failure_reason,
        recorded_message=record.recorded_message,
    )


def map_async_runtime_lease(record: AsyncRuntimeLeaseRecord) -> AsyncJobLeaseDescriptor:
    return AsyncJobLeaseDescriptor(
        lease_id=record.lease_id,
        attempt_id=record.attempt_id,
        worker_id=record.worker_id,
        claimed_at=record.claimed_at,
        heartbeat_at=record.heartbeat_at,
        lease_expires_at=record.lease_expires_at,
    )
