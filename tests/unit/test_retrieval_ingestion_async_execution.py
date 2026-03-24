import pytest
from fastapi import HTTPException

from app.services.async_job_service import build_async_job_detail
from app.services.retrieval_catalog_service import (
    get_retrieval_ingestion_job_detail_or_raise,
    get_retrieval_job_detail_or_raise,
)
from app.services.retrieval_ingestion_async_execution import (
    run_next_retrieval_ingestion_job,
    submit_retrieval_ingestion_job_async,
)


def test_submit_retrieval_ingestion_job_async_targets_concrete_ingestion_job() -> None:
    response = submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ingestion-async-001",
    )

    assert response.accepted is True
    assert response.target_id == "ingjob_lotus_platform_rfcs_refresh_0069"

    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.target_id == "ingjob_lotus_platform_rfcs_refresh_0069"
    assert detail.job.status.value == "QUEUED"


def test_submit_retrieval_ingestion_job_async_rejects_blocked_job() -> None:
    with pytest.raises(HTTPException) as exc_info:
        submit_retrieval_ingestion_job_async(
            job_id="ingjob_lotus_openapi_onboard_pending",
            caller_app="lotus-platform",
            correlation_id="corr-ingestion-async-blocked",
        )

    assert exc_info.value.status_code == 409
    assert "blocked" in str(exc_info.value.detail).lower()


def test_run_next_retrieval_ingestion_job_completes_and_queues_follow_on_indexing() -> None:
    submit_response = submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ingestion-async-002",
    )

    result = run_next_retrieval_ingestion_job(worker_id="worker-a")

    assert result is not None
    assert result.async_job_id == submit_response.job_id
    assert result.ingestion_job_id == "ingjob_lotus_platform_rfcs_refresh_0069"
    assert result.terminal_status == "COMPLETED"

    async_detail = build_async_job_detail(job_id=submit_response.job_id or "")
    ingestion_detail = get_retrieval_ingestion_job_detail_or_raise(
        "ingjob_lotus_platform_rfcs_refresh_0069"
    )
    retrieval_detail = get_retrieval_job_detail_or_raise("retjob_lotus_platform_rfcs")

    assert async_detail.job.status.value == "COMPLETED"
    assert ingestion_detail.job.status.value == "COMPLETED"
    assert len(ingestion_detail.job.artifact_refs) == 1
    assert ingestion_detail.steps[3].runtime_status == "QUEUED"
    assert ingestion_detail.steps[3].linked_async_job_id is not None
    assert retrieval_detail.job.status.value == "QUEUED"


def test_run_next_retrieval_ingestion_job_returns_none_when_no_jobs_are_claimed() -> None:
    assert run_next_retrieval_ingestion_job(worker_id="worker-a") is None
