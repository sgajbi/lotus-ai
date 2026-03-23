from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_job_service import build_async_job_detail
from app.services.retrieval_async_execution import (
    run_next_retrieval_index_job,
    submit_retrieval_index_job_async,
)
from app.services.retrieval_catalog_service import (
    get_documents_for_source,
    get_retrieval_job_detail_or_raise,
)


def test_submit_retrieval_index_job_async_targets_concrete_retrieval_job() -> None:
    response = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-ret-async-001",
    )

    assert response.accepted is True
    assert response.target_id == "retjob_lotus_platform_rfcs"

    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.target_id == "retjob_lotus_platform_rfcs"
    assert detail.job.status.value == "QUEUED"


def test_run_next_retrieval_index_job_completes_and_updates_retrieval_state() -> None:
    submit_response = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-ret-async-002",
    )

    result = run_next_retrieval_index_job(worker_id="worker-a")

    assert result is not None
    assert result.async_job_id == submit_response.job_id
    assert result.retrieval_job_id == "retjob_lotus_platform_rfcs"
    assert result.terminal_status == "COMPLETED"

    async_detail = build_async_job_detail(job_id=submit_response.job_id or "")
    retrieval_detail = get_retrieval_job_detail_or_raise("retjob_lotus_platform_rfcs")
    source_documents = get_documents_for_source("lotus-platform-rfcs")

    assert async_detail.job.status.value == "COMPLETED"
    assert retrieval_detail.job.status.value == "COMPLETED"
    assert retrieval_detail.steps[2].runtime_status == "COMPLETED"
    assert retrieval_detail.steps[2].linked_async_job_id == submit_response.job_id
    assert all(document.index_status.value == "INDEXED" for document in source_documents.documents)


def test_run_next_retrieval_index_job_returns_none_when_no_jobs_are_claimed() -> None:
    assert run_next_retrieval_index_job(worker_id="worker-a") is None


def test_run_next_retrieval_index_job_fails_unsupported_runtime_job_type() -> None:
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-unsupported",
            job_type="evaluation_execution",
            target_id=None,
            lifecycle_status="QUEUED",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="lotus-platform",
            correlation_id="corr-ret-async-unsupported",
            payload_summary="Unsupported async job type.",
            execution_path="durable_async_backbone",
            related_evaluation_run_id=None,
            latest_message="Queued unsupported job.",
            attempt_count=1,
        )
    )
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="async-job-unsupported_attempt_001",
            job_id="async-job-unsupported",
            attempt_number=1,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Queued.",
        )
    )

    result = run_next_retrieval_index_job(worker_id="worker-a")

    assert result is None
    detail = build_async_job_detail(job_id="async-job-unsupported")
    assert detail.job.status.value == "FAILED"
    assert detail.attempts[0].failure_reason == "UNSUPPORTED_ASYNC_JOB_TYPE"
