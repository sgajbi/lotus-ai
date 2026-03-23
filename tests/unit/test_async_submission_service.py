from pathlib import Path

from fastapi import HTTPException

from app.contracts.async_runtime import AsyncJobSubmissionRequest
from app.services.async_job_service import build_async_job_catalog
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.async_submission_service import submit_async_job
from app.config import settings
from tests.support.migration_runner import upgrade_database_to_head


def test_submit_async_job_accepts_allowlisted_runtime_backed_job_type() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            caller_app="lotus-platform",
            correlation_id="corr-async-001",
            payload_summary="Index newly approved RFC documents.",
        )
    )

    assert response.service == "lotus-ai"
    assert response.submission_status == "ACCEPTED"
    assert response.accepted is True
    assert response.job_id is not None
    assert response.queue_mode == "STUBBED"
    assert response.worker_mode == "DOCUMENTED_ONLY"


def test_submit_async_job_persists_sql_backed_runtime_submission(tmp_path: Path) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-submission.db'}"
    upgrade_database_to_head(settings.database_url)

    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            caller_app="lotus-platform",
            correlation_id="corr-async-001-sql",
            payload_summary="Index newly approved RFC documents.",
        )
    )
    reset_async_runtime_store_cache()

    catalog = build_async_job_catalog()
    runtime_job = next(job for job in catalog.jobs if job.job_id == response.job_id)

    assert response.accepted is True
    assert runtime_job.status == "QUEUED"
    assert runtime_job.record_source == "RUNTIME_STATE"


def test_submit_async_job_rejects_documentation_only_job_type() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="evaluation_execution",
            caller_app="lotus-platform",
            correlation_id="corr-async-001-eval",
            payload_summary="Run staged evaluation family.",
        )
    )

    assert response.service == "lotus-ai"
    assert response.submission_status == "REJECTED"
    assert response.accepted is False
    assert response.job_id is None
    assert response.queue_mode == "STUBBED"


def test_submit_async_job_raises_not_found_for_unknown_job_type() -> None:
    try:
        submit_async_job(
            AsyncJobSubmissionRequest(
                job_type="missing_job_type",
                caller_app="lotus-platform",
                correlation_id="corr-async-002",
                payload_summary="Unknown work.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Unknown lotus-ai async job type: missing_job_type"
    else:
        raise AssertionError("Expected async submission to raise HTTPException.")
