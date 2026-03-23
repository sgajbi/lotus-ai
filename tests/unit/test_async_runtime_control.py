from datetime import UTC, datetime
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import HTTPException

from app.config import settings
from app.contracts.async_runtime import AsyncControlActionRequest, AsyncControlActionType
from app.repositories.memory_async_runtime_repository import InMemoryAsyncRuntimeRepository
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_control import (
    apply_async_control_action,
    build_async_control_history,
)
from app.services.async_runtime_store import (
    get_async_runtime_store,
    reset_async_runtime_store_cache,
)
from app.services.async_submission_service import submit_async_job
from app.services.async_worker_runtime import claim_next_async_job, fail_async_job, start_async_job
from app.contracts.async_runtime import AsyncJobSubmissionRequest
from tests.support.migration_runner import upgrade_database_to_head


def test_async_control_action_retries_failed_job_and_records_event(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 16, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-control-001",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim_next_async_job(worker_id="worker-a")
    fail_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        failure_reason="UPSTREAM_FAILURE",
        retryable=False,
    )

    monkeypatch.setattr(
        "app.services.async_runtime_control._utcnow",
        lambda: "2026-03-23T16:05:00Z",
    )
    action = apply_async_control_action(
        AsyncControlActionRequest(
            job_id=response.job_id or "",
            action_type=AsyncControlActionType.RETRY_FAILED_JOB,
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Retry after transient investigation.",
        )
    )

    detail = build_async_job_detail(job_id=response.job_id or "")
    assert action.event.prior_status == "FAILED"
    assert action.event.resulting_status == "QUEUED"
    assert detail.job.status.value == "QUEUED"
    assert detail.attempts[-1].status == "QUEUED"
    assert detail.control_events[0].action_type.value == "RETRY_FAILED_JOB"


def test_async_control_action_history_survives_sql_store_reset(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-control.db'}"
    upgrade_database_to_head(settings.database_url)

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 17, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-control-002",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim_next_async_job(worker_id="worker-a")
    start_async_job(job_id=response.job_id or "", worker_id="worker-a")

    monkeypatch.setattr(
        "app.services.async_runtime_control._utcnow",
        lambda: "2026-03-23T17:05:00Z",
    )
    apply_async_control_action(
        AsyncControlActionRequest(
            job_id=response.job_id or "",
            action_type=AsyncControlActionType.ABANDON_ACTIVE_JOB,
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Manual stop for recovery validation.",
        )
    )
    reset_async_runtime_store_cache()

    history = build_async_control_history()
    detail = build_async_job_detail(job_id=response.job_id or "")

    assert history.latest_events[0].job_id == response.job_id
    assert history.latest_events[0].action_type.value == "ABANDON_ACTIVE_JOB"
    assert detail.job.status.value == "ABANDONED"
    assert detail.control_events[0].action_type.value == "ABANDON_ACTIVE_JOB"


def test_async_control_history_reports_memory_store_note() -> None:
    history = build_async_control_history()

    assert any("process-local" in note for note in history.notes)


def test_async_control_action_raises_not_found_for_missing_job() -> None:
    with pytest.raises(HTTPException) as exc_info:
        apply_async_control_action(
            AsyncControlActionRequest(
                job_id="missing-job",
                action_type=AsyncControlActionType.RETRY_FAILED_JOB,
                requested_by="operator-a",
                approved_by="approver-a",
                reason="Retry missing job.",
            )
        )

    assert exc_info.value.status_code == 404


def test_async_control_action_requeues_abandoned_job() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-control-003",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim_next_async_job(worker_id="worker-a")
    start_async_job(job_id=response.job_id or "", worker_id="worker-a")
    apply_async_control_action(
        AsyncControlActionRequest(
            job_id=response.job_id or "",
            action_type=AsyncControlActionType.ABANDON_ACTIVE_JOB,
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Abandon before requeue.",
        )
    )

    action = apply_async_control_action(
        AsyncControlActionRequest(
            job_id=response.job_id or "",
            action_type=AsyncControlActionType.REQUEUE_ABANDONED_JOB,
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Requeue after manual abandon.",
        )
    )

    detail = build_async_job_detail(job_id=response.job_id or "")
    assert action.event.prior_status == "ABANDONED"
    assert action.event.resulting_status == "QUEUED"
    assert detail.job.status.value == "QUEUED"
    assert detail.control_events[0].action_type.value == "REQUEUE_ABANDONED_JOB"


@pytest.mark.parametrize(
    ("initial_status", "action_type", "expected_detail"),
    [
        ("QUEUED", AsyncControlActionType.RETRY_FAILED_JOB, "is not in FAILED state"),
        ("QUEUED", AsyncControlActionType.REPLAY_TERMINAL_JOB, "is not terminal"),
        (
            "QUEUED",
            AsyncControlActionType.REQUEUE_ABANDONED_JOB,
            "is not in ABANDONED state",
        ),
        (
            "QUEUED",
            AsyncControlActionType.ABANDON_ACTIVE_JOB,
            "is not actively claimed or running",
        ),
    ],
)
def test_async_control_action_rejects_invalid_state_transitions(
    initial_status: str,
    action_type: AsyncControlActionType,
    expected_detail: str,
) -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id=f"corr-{action_type.value}",
            payload_summary="Refresh retrieval documents.",
        )
    )

    if initial_status != "QUEUED":
        raise AssertionError("Test setup only supports queued initial status.")

    with pytest.raises(HTTPException) as exc_info:
        apply_async_control_action(
            AsyncControlActionRequest(
                job_id=response.job_id or "",
                action_type=action_type,
                requested_by="operator-a",
                approved_by="approver-a",
                reason="Invalid transition coverage.",
            )
        )

    assert exc_info.value.status_code == 409
    assert expected_detail in str(exc_info.value.detail)


def test_async_control_action_rejects_missing_active_lease() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-control-004",
            payload_summary="Refresh retrieval documents.",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        apply_async_control_action(
            AsyncControlActionRequest(
                job_id=response.job_id or "",
                action_type=AsyncControlActionType.ABANDON_ACTIVE_JOB,
                requested_by="operator-a",
                approved_by="approver-a",
                reason="Missing lease coverage.",
            )
        )

    assert exc_info.value.status_code == 409


def test_async_control_action_rejects_missing_attempt_for_active_lease() -> None:
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-control-005",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    runtime_store = get_async_runtime_store()
    assert isinstance(runtime_store, InMemoryAsyncRuntimeRepository)
    runtime_store._attempts[response.job_id or ""] = []

    with pytest.raises(HTTPException) as exc_info:
        apply_async_control_action(
            AsyncControlActionRequest(
                job_id=response.job_id or "",
                action_type=AsyncControlActionType.ABANDON_ACTIVE_JOB,
                requested_by="operator-a",
                approved_by="approver-a",
                reason="Missing attempt coverage.",
            )
        )

    assert exc_info.value.status_code == 409
