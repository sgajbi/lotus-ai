from __future__ import annotations

from app.contracts.async_runtime import (
    AsyncJobArtifactDescriptor,
    AsyncJobRecordSource,
    AsyncJobStatus,
)
from app.repositories.async_runtime_repository import AsyncRuntimeJobRecord


def map_async_runtime_job(record: AsyncRuntimeJobRecord) -> AsyncJobArtifactDescriptor:
    return AsyncJobArtifactDescriptor(
        job_id=record.job_id,
        job_type=record.job_type,
        status=AsyncJobStatus.QUEUED,
        record_source=AsyncJobRecordSource.RUNTIME_STATE,
        submitted_at=record.submitted_at,
        caller_app=record.caller_app,
        related_evaluation_run_id=record.related_evaluation_run_id,
        execution_path=record.execution_path,
        notes=record.latest_message,
    )
