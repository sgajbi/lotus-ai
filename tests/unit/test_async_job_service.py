from fastapi import HTTPException

from app.config import settings
from app.contracts.async_runtime import AsyncJobSubmissionRequest
from app.services.async_job_service import build_async_job_catalog, build_async_job_detail
from app.services.async_submission_service import submit_async_job


def test_async_job_catalog_reports_seeded_jobs() -> None:
    catalog = build_async_job_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.job_count == 2
    assert catalog.queued_job_count == 1
    assert catalog.jobs[0].job_id == "asyncjob_retrieval_indexing_001"
    assert catalog.jobs[1].status == "SUPERSEDED"
    assert catalog.jobs[1].related_evaluation_run_id == "foundation_eval_2026_03_21_001"


def test_async_job_detail_returns_requested_job() -> None:
    detail = build_async_job_detail(job_id="asyncjob_retrieval_indexing_001")

    assert detail.service == "lotus-ai"
    assert detail.job.job_type == "retrieval_indexing"
    assert detail.job.status == "QUEUED"
    assert detail.job.related_evaluation_run_id is None


def test_async_job_detail_raises_not_found_for_unknown_job() -> None:
    try:
        build_async_job_detail(job_id="missing_async_job")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Async job artifact 'missing_async_job' was not found."
    else:
        raise AssertionError("Expected async job lookup to raise HTTPException.")


def test_async_job_catalog_includes_runtime_jobs() -> None:
    settings.async_queue_mode = "stubbed"
    settings.async_worker_mode = "stubbed"
    submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            caller_app="lotus-platform",
            correlation_id="corr-async-005",
            target_id="retjob_lotus_platform_rfcs",
            payload_summary="Replay approved RFC retrieval indexing.",
        )
    )

    catalog = build_async_job_catalog()

    assert catalog.job_count == 3
    assert catalog.jobs[0].job_id.startswith("asyncjob_runtime_retrieval_indexing_")
    assert catalog.jobs[0].status == "COMPLETED"
