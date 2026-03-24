from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.contracts.async_runtime import AsyncJobSubmissionRequest
from app.contracts.retrieval import RetrievalIngestionJobStatus
from app.services.async_submission_service import submit_async_job
from app.services.async_job_service import build_async_job_detail
from app.services.retrieval_catalog_service import (
    get_retrieval_ingestion_job_detail_or_raise,
    get_retrieval_job_detail_or_raise,
)
from app.services.retrieval_ingestion_async_execution import (
    run_next_retrieval_ingestion_job,
    run_retrieval_ingestion_job_by_id,
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


def test_run_retrieval_ingestion_job_by_id_returns_none_for_unknown_job() -> None:
    assert (
        run_retrieval_ingestion_job_by_id(async_job_id="missing-job", worker_id="worker-a") is None
    )


def test_run_retrieval_ingestion_job_by_id_fails_blocked_target_and_persists_diagnostics() -> None:
    submission = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="document_ingestion",
            target_id="ingjob_lotus_openapi_onboard_pending",
            caller_app="lotus-platform",
            correlation_id="corr-ingestion-by-id-blocked-001",
            payload_summary="blocked ingestion replay",
        )
    )

    result = run_retrieval_ingestion_job_by_id(
        async_job_id=submission.job_id or "",
        worker_id="worker-a",
    )

    assert result is not None
    assert result.terminal_status == RetrievalIngestionJobStatus.FAILED.value

    async_detail = build_async_job_detail(job_id=submission.job_id or "")
    ingestion_detail = get_retrieval_ingestion_job_detail_or_raise(
        "ingjob_lotus_openapi_onboard_pending"
    )

    assert async_detail.job.status.value == "FAILED"
    assert ingestion_detail.job.status.value == "FAILED"
    assert len(ingestion_detail.job.artifact_refs) == 1


def test_run_retrieval_ingestion_job_by_id_rejects_unsupported_claim_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async_job_id = "asyncjob_wrong_type"
    failure_calls: list[tuple[str, str, str, bool]] = []
    monkeypatch.setattr(
        "app.services.retrieval_ingestion_async_execution.claim_async_job_by_id",
        lambda job_id, worker_id: SimpleNamespace(
            job=SimpleNamespace(
                job_id=async_job_id,
                job_type="retrieval_indexing",
                target_id="retjob_lotus_platform_rfcs",
                caller_app="lotus-platform",
                correlation_id="corr-unsupported",
            )
        ),
    )
    monkeypatch.setattr(
        "app.services.retrieval_ingestion_async_execution.fail_async_job",
        lambda job_id, worker_id, failure_reason, retryable: failure_calls.append(
            (job_id, worker_id, failure_reason, retryable)
        ),
    )

    result = run_retrieval_ingestion_job_by_id(async_job_id=async_job_id, worker_id="worker-a")

    assert result is None
    assert failure_calls == [(async_job_id, "worker-a", "UNSUPPORTED_ASYNC_JOB_TYPE", False)]


def test_run_next_retrieval_ingestion_job_records_terminal_failure_when_follow_on_submission_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submit_response = submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ingestion-async-fail-001",
    )
    monkeypatch.setattr(
        "app.services.retrieval_ingestion_async_execution.submit_retrieval_index_job_async",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("follow-on indexing unavailable")),
    )

    result = run_next_retrieval_ingestion_job(worker_id="worker-a")

    assert result is not None
    assert result.async_job_id == submit_response.job_id
    assert result.terminal_status == RetrievalIngestionJobStatus.FAILED.value

    async_detail = build_async_job_detail(job_id=submit_response.job_id or "")
    ingestion_detail = get_retrieval_ingestion_job_detail_or_raise(
        "ingjob_lotus_platform_rfcs_refresh_0069"
    )

    assert async_detail.job.status.value == "FAILED"
    assert ingestion_detail.job.status.value == "FAILED"
    assert len(ingestion_detail.job.artifact_refs) == 1


def test_run_next_retrieval_ingestion_job_reports_reused_follow_on_index_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-ingestion-async-existing-001",
    )
    monkeypatch.setattr(
        "app.services.retrieval_ingestion_async_execution.submit_retrieval_index_job_async",
        lambda **kwargs: SimpleNamespace(
            accepted=False,
            job_id=None,
            existing_job_id="asyncjob_reused_index_001",
            message="existing retrieval indexing job reused",
        ),
    )

    result = run_next_retrieval_ingestion_job(worker_id="worker-a")

    assert result is not None
    ingestion_detail = get_retrieval_ingestion_job_detail_or_raise(
        "ingjob_lotus_platform_rfcs_refresh_0069"
    )
    assert "reused active async job 'asyncjob_reused_index_001'" in ingestion_detail.job.message
