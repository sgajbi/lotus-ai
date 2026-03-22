from __future__ import annotations

import pytest

from app.async_runtime.job_registry import (
    AsyncJobArtifactValidationError,
    validate_async_job_artifacts,
)


def test_validate_async_job_artifacts_accepts_current_shape() -> None:
    payload = {
        "jobs": [
            {
                "job_id": "asyncjob_retrieval_indexing_001",
                "job_type": "retrieval_indexing",
                "status": "QUEUED",
                "submitted_at": "2026-03-22T10:15:00Z",
                "caller_app": "lotus-platform",
                "execution_path": "future_worker_queue",
                "notes": "Seeded async job artifact.",
            }
        ]
    }

    validate_async_job_artifacts(registry_payload=payload)


def test_validate_async_job_artifacts_rejects_duplicate_job_ids() -> None:
    payload = {
        "jobs": [
            {
                "job_id": "dup_job",
                "job_type": "retrieval_indexing",
                "status": "QUEUED",
                "submitted_at": "2026-03-22T10:15:00Z",
                "caller_app": "lotus-platform",
                "execution_path": "future_worker_queue",
                "notes": "First.",
            },
            {
                "job_id": "dup_job",
                "job_type": "evaluation_execution",
                "status": "SUPERSEDED",
                "submitted_at": "2026-03-22T11:15:00Z",
                "caller_app": "lotus-ai",
                "execution_path": "future_worker_queue",
                "notes": "Second.",
            },
        ]
    }

    with pytest.raises(AsyncJobArtifactValidationError, match="Duplicate async job artifact id"):
        validate_async_job_artifacts(registry_payload=payload)
