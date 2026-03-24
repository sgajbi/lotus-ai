from pathlib import Path

import pytest
from fastapi import HTTPException
from unittest.mock import patch

from app.contracts.async_runtime import AsyncJobSubmissionRequest
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.services.async_job_service import build_async_job_catalog
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.async_submission_service import (
    _find_active_duplicate_submission,
    _validate_async_job_target,
    submit_async_job,
)
from app.config import settings
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_delivery_queue import get_test_async_delivery_queue
from tests.support.migration_runner import upgrade_database_to_head


def test_submit_async_job_accepts_allowlisted_runtime_backed_job_type() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-001",
            payload_summary="Index newly approved RFC documents.",
        )
    )

    assert response.service == "lotus-ai"
    assert response.submission_status == "ACCEPTED"
    assert response.accepted is True
    assert response.job_id is not None
    assert response.target_id == "retjob_lotus_platform_rfcs"
    assert response.cutover_state == "in_process_only"
    assert response.queue_mode == "DISABLED"
    assert response.worker_mode == "IN_PROCESS_ONLY"


def test_submit_async_job_persists_sql_backed_runtime_submission(tmp_path: Path) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-submission.db'}"
    upgrade_database_to_head(settings.database_url)

    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-001-sql",
            payload_summary="Index newly approved RFC documents.",
        )
    )
    reset_async_runtime_store_cache()

    catalog = build_async_job_catalog()
    runtime_job = next(job for job in catalog.jobs if job.job_id == response.job_id)

    assert response.accepted is True
    assert runtime_job.target_id == "retjob_lotus_platform_rfcs"
    assert runtime_job.status == "QUEUED"
    assert runtime_job.record_source == "RUNTIME_STATE"


def test_submit_async_job_publishes_bounded_shadow_queue_message_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.async_cutover_state = "queue_delivery_shadow"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )

    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-shadow-001",
            payload_summary="Index newly approved RFC documents.",
        )
    )

    published_message = queue.list_messages()[0]

    assert response.accepted is True
    assert response.cutover_state == "queue_delivery_shadow"
    assert response.queue_mode == "SHADOW"
    assert response.worker_mode == "IN_PROCESS_ONLY"
    assert published_message.job_id == response.job_id
    assert published_message.job_type == "retrieval_indexing"
    assert published_message.target_id == "retjob_lotus_platform_rfcs"
    assert published_message.correlation_id == "corr-async-shadow-001"


def test_submit_async_job_rejects_duplicate_active_runtime_submission() -> None:
    first = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-duplicate-001",
            payload_summary="Index newly approved RFC documents.",
        )
    )

    duplicate = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-duplicate-002",
            payload_summary="Index newly approved RFC documents again.",
        )
    )

    assert first.accepted is True
    assert duplicate.submission_status == "DUPLICATE_REJECTED"
    assert duplicate.accepted is False
    assert duplicate.job_id is None
    assert duplicate.existing_job_id == first.job_id


def test_submit_async_job_rejects_missing_retrieval_target_id() -> None:
    try:
        submit_async_job(
            AsyncJobSubmissionRequest(
                job_type="retrieval_indexing",
                caller_app="lotus-platform",
                correlation_id="corr-async-001-missing-target",
                payload_summary="Index newly approved RFC documents.",
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "requires a concrete retrieval index job target_id" in str(exc.detail)
    else:
        raise AssertionError("Expected async submission to reject missing retrieval target_id.")


def test_submit_async_job_rejects_documentation_only_job_type() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="evaluation_execution",
            target_id="provider_runtime_examples",
            caller_app="lotus-platform",
            correlation_id="corr-async-001-eval",
            payload_summary="Run staged evaluation family.",
        )
    )

    assert response.service == "lotus-ai"
    assert response.submission_status == "ACCEPTED"
    assert response.accepted is True
    assert response.job_id is not None
    assert response.cutover_state == "in_process_only"
    assert response.queue_mode == "DISABLED"
    assert response.worker_mode == "IN_PROCESS_ONLY"


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


def test_submit_async_job_rejects_disabled_non_evaluation_job_type() -> None:
    with patch("app.services.async_submission_service.get_async_job_type_descriptor") as descriptor:
        descriptor.return_value = type(
            "JobTypeDescriptor",
            (),
            {
                "enabled": False,
                "execution_path": "future_worker_queue",
            },
        )()
        response = submit_async_job(
            AsyncJobSubmissionRequest(
                job_type="document_ingestion",
                target_id="doc-001",
                caller_app="lotus-platform",
                correlation_id="corr-async-disabled-doc-ingestion",
                payload_summary="Ingest large document.",
            )
        )

    assert response.accepted is False
    assert response.submission_status == "REJECTED"
    assert "staged-only" in response.message


def test_validate_async_job_target_ignores_non_retrieval_job_types() -> None:
    _validate_async_job_target(
        request=AsyncJobSubmissionRequest(
            job_type="evaluation_execution",
            target_id="provider_runtime_examples",
            caller_app="lotus-platform",
            correlation_id="corr-async-ignore-target",
            payload_summary="Run evaluation family.",
        )
    )


def test_find_active_duplicate_submission_ignores_non_matching_runtime_jobs() -> None:
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_ai_architecture",
            lifecycle_status="COMPLETED",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="other-app",
            correlation_id="corr-001",
            payload_summary="Completed job should not block duplicates.",
            execution_path="durable_runtime_submission",
            related_evaluation_run_id=None,
            latest_message="Completed.",
            attempt_count=1,
        )
    )
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="attempt-001",
            job_id="async-job-001",
            attempt_number=1,
            lifecycle_status="COMPLETED",
            worker_id="worker-a",
            claimed_at="2026-03-23T00:00:00Z",
            heartbeat_at="2026-03-23T00:00:00Z",
            started_at="2026-03-23T00:00:00Z",
            completed_at="2026-03-23T00:01:00Z",
            failure_reason=None,
            recorded_message="Completed.",
        )
    )

    duplicate = _find_active_duplicate_submission(
        request=AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-duplicate-ignore",
            payload_summary="Fresh request.",
        )
    )

    assert duplicate is None


def test_submit_async_job_rejects_unknown_retrieval_target() -> None:
    with pytest.raises(HTTPException) as exc_info:
        submit_async_job(
            AsyncJobSubmissionRequest(
                job_type="retrieval_indexing",
                target_id="missing_retrieval_job",
                caller_app="lotus-platform",
                correlation_id="corr-async-missing-retrieval-job",
                payload_summary="Index missing retrieval target.",
            )
        )

    assert exc_info.value.status_code == 404


def test_find_active_duplicate_submission_ignores_same_target_for_different_caller() -> None:
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-duplicate-other-caller",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="RUNNING",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="other-app",
            correlation_id="corr-001",
            payload_summary="Running job for different caller.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Running.",
            attempt_count=1,
        )
    )

    duplicate = _find_active_duplicate_submission(
        request=AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-different-caller",
            payload_summary="Fresh request.",
        )
    )

    assert duplicate is None
