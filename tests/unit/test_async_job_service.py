from fastapi import HTTPException

from app.services.async_job_service import build_async_job_catalog, build_async_job_detail


def test_async_job_catalog_reports_seeded_jobs() -> None:
    catalog = build_async_job_catalog()

    assert catalog.service == "lotus-ai"
    assert catalog.job_count == 2
    assert catalog.queued_job_count == 0
    assert catalog.jobs[0].job_id == "asyncjob_retrieval_indexing_001"
    assert catalog.jobs[0].status == "STAGED"
    assert catalog.jobs[0].record_source == "STAGED_ARTIFACT"
    assert catalog.jobs[1].status == "SUPERSEDED"
    assert catalog.jobs[1].related_evaluation_run_id == "foundation_eval_2026_03_21_001"


def test_async_job_detail_returns_requested_job() -> None:
    detail = build_async_job_detail(job_id="asyncjob_retrieval_indexing_001")

    assert detail.service == "lotus-ai"
    assert detail.job.job_type == "retrieval_indexing"
    assert detail.job.status == "STAGED"
    assert detail.job.record_source == "STAGED_ARTIFACT"
    assert detail.job.related_evaluation_run_id is None


def test_async_job_detail_raises_not_found_for_unknown_job() -> None:
    try:
        build_async_job_detail(job_id="missing_async_job")
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Async job artifact 'missing_async_job' was not found."
    else:
        raise AssertionError("Expected async job lookup to raise HTTPException.")
