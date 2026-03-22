from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.contracts.async_runtime import AsyncJobArtifactDescriptor
from app.evals.run_registry import load_evaluation_run_artifacts


class AsyncJobArtifactValidationError(ValueError):
    """Raised when the governed async job artifact registry is malformed."""


@lru_cache(maxsize=1)
def load_async_job_artifacts() -> list[AsyncJobArtifactDescriptor]:
    repo_root = Path(__file__).resolve().parents[3]
    registry_path = repo_root / "docs" / "async" / "job-artifacts.json"
    with registry_path.open("r", encoding="utf-8") as registry_file:
        payload = json.load(registry_file)
    validate_async_job_artifacts(registry_payload=payload)
    jobs = payload.get("jobs", [])
    return [AsyncJobArtifactDescriptor(**job) for job in jobs]


def validate_async_job_artifacts(*, registry_payload: dict[str, Any]) -> None:
    jobs = registry_payload.get("jobs")
    if not isinstance(jobs, list):
        raise AsyncJobArtifactValidationError(
            "Async job artifact registry must define jobs as a list."
        )

    evaluation_run_ids = {run.run_id for run in load_evaluation_run_artifacts()}
    job_ids: set[str] = set()
    for job in jobs:
        if not isinstance(job, dict):
            raise AsyncJobArtifactValidationError(
                "Each async job artifact entry must be an object."
            )
        job_id = job.get("job_id")
        _require_non_empty_string(job_id, field_name="jobs[].job_id")
        if job_id in job_ids:
            raise AsyncJobArtifactValidationError(f"Duplicate async job artifact id '{job_id}'.")
        job_ids.add(job_id)
        _require_non_empty_string(job.get("job_type"), field_name=f"{job_id}.job_type")
        _require_non_empty_string(job.get("submitted_at"), field_name=f"{job_id}.submitted_at")
        _require_non_empty_string(job.get("caller_app"), field_name=f"{job_id}.caller_app")
        related_evaluation_run_id = job.get("related_evaluation_run_id")
        if related_evaluation_run_id is not None:
            _require_non_empty_string(
                related_evaluation_run_id,
                field_name=f"{job_id}.related_evaluation_run_id",
            )
            if related_evaluation_run_id not in evaluation_run_ids:
                raise AsyncJobArtifactValidationError(
                    f"Async job artifact '{job_id}' references unknown evaluation run id "
                    f"'{related_evaluation_run_id}'."
                )
        _require_non_empty_string(
            job.get("execution_path"),
            field_name=f"{job_id}.execution_path",
        )
        _require_non_empty_string(job.get("notes"), field_name=f"{job_id}.notes")


def _require_non_empty_string(value: Any, *, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AsyncJobArtifactValidationError(
            f"Async job artifact field '{field_name}' must be a non-empty string."
        )
