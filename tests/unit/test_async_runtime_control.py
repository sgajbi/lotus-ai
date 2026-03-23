from datetime import UTC, datetime
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.contracts.async_runtime import AsyncControlActionRequest, AsyncControlActionType
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_control import (
    apply_async_control_action,
    build_async_control_history,
)
from app.services.async_runtime_store import reset_async_runtime_store_cache
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
