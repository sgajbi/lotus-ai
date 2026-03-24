from app.services.retrieval_ingestion_job_service import (
    build_retrieval_ingestion_job_catalog,
    get_retrieval_ingestion_job_detail,
)
from app.services.retrieval_ingestion_async_execution import submit_retrieval_ingestion_job_async


def test_retrieval_ingestion_job_catalog_returns_seeded_jobs() -> None:
    catalog = build_retrieval_ingestion_job_catalog()

    assert any(job.job_id == "ingjob_lotus_platform_rfcs_refresh_0069" for job in catalog.jobs)
    assert any(job.status == "BLOCKED" for job in catalog.jobs)


def test_retrieval_ingestion_job_detail_reports_async_overlay_and_index_followthrough() -> None:
    submission = submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ingestion-detail-001",
    )

    detail = get_retrieval_ingestion_job_detail("ingjob_lotus_platform_rfcs_refresh_0069")

    assert submission.accepted is True
    assert detail.job.status == "QUEUED"
    assert detail.job.linked_async_job_id == submission.job_id
    assert detail.steps[2].runtime_status == "QUEUED"
    assert detail.steps[2].linked_async_job_id == submission.job_id
