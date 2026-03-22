from __future__ import annotations

from datetime import datetime, timezone

from app.contracts.async_runtime import AsyncJobArtifactDescriptor, AsyncJobStatus

_runtime_jobs: list[AsyncJobArtifactDescriptor] = []


def list_runtime_async_jobs() -> list[AsyncJobArtifactDescriptor]:
    return list(_runtime_jobs)


def record_runtime_async_job(
    *,
    job_type: str,
    caller_app: str,
    execution_path: str,
    status: AsyncJobStatus,
    notes: str,
    related_evaluation_run_id: str | None = None,
) -> AsyncJobArtifactDescriptor:
    job = AsyncJobArtifactDescriptor(
        job_id=f"asyncjob_runtime_{job_type}_{len(_runtime_jobs) + 1:03d}",
        job_type=job_type,
        status=status,
        submitted_at=_utc_now_iso(),
        caller_app=caller_app,
        related_evaluation_run_id=related_evaluation_run_id,
        execution_path=execution_path,
        notes=notes,
    )
    _runtime_jobs.insert(0, job)
    return job


def reset_runtime_async_jobs() -> None:
    _runtime_jobs.clear()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
