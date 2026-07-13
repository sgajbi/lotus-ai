from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import HTTPException

from app.config import settings
from app.contracts.access_control import (
    AuthorizationCapabilityType,
    AuthorizationDecision,
    AuthorizationOutcome,
    TenantPolicyMode,
)
from app.contracts.async_runtime import AsyncJobStatus
from app.services.async_delivery_queue import (
    AsyncQueueDeliveryMessage,
    get_test_async_delivery_queue,
)
from app.services.async_delivery_recovery import (
    quarantine_queued_async_job,
    redrive_queued_async_job,
)
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_control import build_async_control_history
from app.services.async_runtime_store import get_async_runtime_store
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.async_worker_fleet import (
    process_next_async_delivery,
    run_dedicated_worker_loop,
)
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
)
from app.services.eval_run_service import build_evaluation_run_detail
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.retrieval_catalog_service import get_retrieval_ingestion_job_detail_or_raise
from app.services.retrieval_ingestion_async_execution import submit_retrieval_ingestion_job_async
from app.services.retrieval_async_execution import submit_retrieval_index_job_async
from app.contracts.evals import EvaluationRunSubmissionRequest
from tests.support.migration_runner import upgrade_database_to_head


def _async_control_authorization() -> AuthorizationDecision:
    return AuthorizationDecision(
        caller_app="lotus-ai.operator-console",
        capability_type=AuthorizationCapabilityType.ASYNC_CONTROL,
        outcome=AuthorizationOutcome.ALLOWED,
        allowed=True,
        tenant_policy_mode=TenantPolicyMode.OPTIONAL,
        summary="Async control-plane action authorized for test operator.",
    )


def _runtime_job_record(
    job_id: str,
    *,
    lifecycle_status: str = AsyncJobStatus.QUEUED.value,
    attempt_count: int = 1,
) -> AsyncRuntimeJobRecord:
    return AsyncRuntimeJobRecord(
        job_id=job_id,
        job_type="retrieval_indexing",
        target_id="retjob_lotus_platform_rfcs",
        lifecycle_status=lifecycle_status,
        submitted_at="2026-03-24T00:00:00Z",
        caller_app="lotus-platform",
        correlation_id=f"corr-{job_id}",
        payload_summary="Queued retrieval indexing job.",
        execution_path="durable_runtime_worker_execution",
        related_evaluation_run_id=None,
        latest_message="Queued retrieval indexing job.",
        attempt_count=attempt_count,
        artifact_ids=[],
    )


def _runtime_attempt_record(
    attempt_id: str,
    *,
    job_id: str,
    lifecycle_status: str = AsyncJobStatus.QUEUED.value,
) -> AsyncRuntimeAttemptRecord:
    return AsyncRuntimeAttemptRecord(
        attempt_id=attempt_id,
        job_id=job_id,
        attempt_number=1,
        lifecycle_status=lifecycle_status,
        worker_id=None,
        claimed_at=None,
        heartbeat_at=None,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        recorded_message="Queued retrieval indexing job.",
    )


def test_process_next_async_delivery_executes_retrieval_job_in_dedicated_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-worker-fleet-retrieval-001",
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    detail = build_async_job_detail(job_id=submission.job_id or "")

    assert result is not None
    assert result.job_id == submission.job_id
    assert result.job_type == "retrieval_indexing"
    assert result.handled is True
    assert result.terminal_status == "COMPLETED"
    assert detail.job.status.value == "COMPLETED"


def test_process_next_async_delivery_returns_none_outside_dedicated_mode() -> None:
    settings.async_cutover_state = "in_process_only"

    assert process_next_async_delivery(worker_id="worker-a", timeout_seconds=0) is None


def test_process_next_async_delivery_executes_evaluation_job_in_dedicated_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-worker-fleet-eval-001",
            triggered_by="operator-a",
        )
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    run_detail = build_evaluation_run_detail(run_id=submission.run_id or "")

    assert result is not None
    assert result.job_id == submission.async_job_id
    assert result.job_type == "evaluation_execution"
    assert result.handled is True
    assert run_detail.run.status.value == "COMPLETED"


def test_process_next_async_delivery_ignores_duplicate_delivery_after_completion(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-worker-fleet-retrieval-duplicate-001",
    )
    first = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="duplicate-delivery-001",
            job_id=submission.job_id or "",
            attempt_id=f"{submission.job_id}_attempt_001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-worker-fleet-retrieval-duplicate-001",
            submitted_at="2026-03-24T00:00:00Z",
        )
    )

    duplicate = process_next_async_delivery(worker_id="worker-b", timeout_seconds=0)
    detail = build_async_job_detail(job_id=submission.job_id or "")

    assert first is not None
    assert duplicate is None or duplicate.handled is False
    assert detail.job.status.value == "COMPLETED"


def test_process_next_async_delivery_respects_worker_drain_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    settings.async_worker_drain_enabled = True
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-worker-fleet-drain-001",
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    detail = build_async_job_detail(job_id=submission.job_id or "")

    assert result is None
    assert detail.job.status.value == "QUEUED"
    assert queue.snapshot().pending_delivery_count == 1


def test_process_next_async_delivery_survives_sql_store_reset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-worker-fleet.db'}"
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    upgrade_database_to_head(settings.database_url)
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_retrieval_index_job_async(
        job_id="retjob_lotus_platform_rfcs",
        caller_app="lotus-platform",
        correlation_id="corr-worker-fleet-sql-001",
    )
    reset_async_runtime_store_cache()

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    detail = build_async_job_detail(job_id=submission.job_id or "")

    assert result is not None
    assert result.terminal_status == "COMPLETED"
    assert detail.job.status.value == "COMPLETED"


def test_process_next_async_delivery_marks_unknown_job_type_unhandled(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="asyncjob_unknown",
            job_type="unknown_job_type",
            target_id=None,
            lifecycle_status="QUEUED",
            submitted_at="2026-03-24T00:00:00Z",
            caller_app="lotus-platform",
            correlation_id="corr-unknown-001",
            payload_summary="Unsupported async delivery should be quarantined.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Queued unsupported async job.",
            attempt_count=1,
            artifact_ids=[],
        )
    )
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="attempt-unknown-001",
            job_id="asyncjob_unknown",
            attempt_number=1,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Queued unsupported delivery.",
        )
    )
    queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="delivery-unknown-001",
            job_id="asyncjob_unknown",
            attempt_id="attempt-unknown-001",
            job_type="unknown_job_type",
            target_id=None,
            caller_app="lotus-platform",
            correlation_id="corr-unknown-001",
            submitted_at="2026-03-24T00:00:00Z",
        )
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)

    assert result is not None
    assert result.handled is False
    assert result.terminal_status is None
    detail = build_async_job_detail(job_id="asyncjob_unknown")
    assert detail.job.status.value == "ABANDONED"
    assert detail.control_events[0].action_type.value == "QUARANTINE_QUEUED_JOB"
    assert detail.attempts[0].failure_reason == "DELIVERY_QUARANTINED"


def test_process_next_async_delivery_redrives_claim_miss(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.run_retrieval_index_job_by_id",
        lambda *, async_job_id, worker_id: None,
    )
    store = get_async_runtime_store()
    store.save_job(
        AsyncRuntimeJobRecord(
            job_id="asyncjob_claim_miss",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="QUEUED",
            submitted_at="2026-03-24T00:00:00Z",
            caller_app="lotus-platform",
            correlation_id="corr-claim-miss-001",
            payload_summary="Claim miss should be redriven.",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Queued retrieval indexing job.",
            attempt_count=1,
            artifact_ids=[],
        )
    )
    store.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="asyncjob_claim_miss_attempt_001",
            job_id="asyncjob_claim_miss",
            attempt_number=1,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Queued retrieval indexing job.",
        )
    )
    queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="asyncjob_claim_miss_attempt_001",
            job_id="asyncjob_claim_miss",
            attempt_id="asyncjob_claim_miss_attempt_001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-claim-miss-001",
            submitted_at="2026-03-24T00:00:00Z",
        )
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)

    assert result is not None
    assert result.handled is False
    assert queue.snapshot().pending_delivery_count == 1
    assert queue.snapshot().redelivery_count == 1
    detail = build_async_job_detail(job_id="asyncjob_claim_miss")
    assert detail.job.status.value == "QUEUED"
    assert detail.control_events[0].action_type.value == "REDRIVE_QUEUED_JOB"


def test_redrive_queued_async_job_rejects_job_without_attempt() -> None:
    store = get_async_runtime_store()
    job = _runtime_job_record("asyncjob_redrive_without_attempt", attempt_count=0)
    store.save_job(job)

    with pytest.raises(HTTPException) as exc_info:
        redrive_queued_async_job(
            job=job,
            requested_by="operator-a",
            approved_by="operator-b",
            reason="recover queued delivery without durable attempt",
            authorization=_async_control_authorization(),
        )

    assert exc_info.value.status_code == 409
    assert "has no attempt to re-drive" in str(exc_info.value.detail)


def test_redrive_queued_async_job_rejects_non_queued_job() -> None:
    store = get_async_runtime_store()
    job = _runtime_job_record(
        "asyncjob_redrive_completed",
        lifecycle_status=AsyncJobStatus.COMPLETED.value,
    )
    store.save_job(job)

    with pytest.raises(HTTPException) as exc_info:
        redrive_queued_async_job(
            job=job,
            requested_by="operator-a",
            approved_by="operator-b",
            reason="operator should not re-drive completed work",
            authorization=_async_control_authorization(),
        )

    assert exc_info.value.status_code == 409
    assert "is not QUEUED" in str(exc_info.value.detail)


def test_redrive_queued_async_job_rejects_non_queued_latest_attempt() -> None:
    store = get_async_runtime_store()
    job = _runtime_job_record("asyncjob_redrive_claimed_attempt")
    store.save_job(job)
    store.save_attempt(
        _runtime_attempt_record(
            "attempt-redrive-claimed-001",
            job_id=job.job_id,
            lifecycle_status=AsyncJobStatus.CLAIMED.value,
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        redrive_queued_async_job(
            job=job,
            requested_by="operator-a",
            approved_by="operator-b",
            reason="latest attempt is already claimed",
            authorization=_async_control_authorization(),
        )

    assert exc_info.value.status_code == 409
    assert "latest attempt is not QUEUED" in str(exc_info.value.detail)


def test_redrive_queued_async_job_requires_active_queue_publication() -> None:
    settings.async_cutover_state = "in_process_only"
    store = get_async_runtime_store()
    job = _runtime_job_record("asyncjob_redrive_queue_inactive")
    store.save_job(job)
    store.save_attempt(_runtime_attempt_record("attempt-redrive-inactive-001", job_id=job.job_id))

    with pytest.raises(HTTPException) as exc_info:
        redrive_queued_async_job(
            job=job,
            requested_by="operator-a",
            approved_by="operator-b",
            reason="managed queue must be active before re-drive",
            authorization=_async_control_authorization(),
        )

    assert exc_info.value.status_code == 409
    assert "managed queue publication is inactive" in str(exc_info.value.detail)


def test_quarantine_queued_async_job_rejects_active_worker_lease() -> None:
    store = get_async_runtime_store()
    job = _runtime_job_record("asyncjob_quarantine_active_lease")
    attempt = _runtime_attempt_record("attempt-quarantine-lease-001", job_id=job.job_id)
    store.save_job(job)
    store.save_attempt(attempt)
    store.save_lease(
        AsyncRuntimeLeaseRecord(
            lease_id="lease-quarantine-lease-001",
            job_id=job.job_id,
            attempt_id=attempt.attempt_id,
            worker_id="worker-a",
            claimed_at="2026-03-24T00:00:00Z",
            heartbeat_at="2026-03-24T00:00:03Z",
            lease_expires_at="2026-03-24T00:05:00Z",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        quarantine_queued_async_job(
            job=job,
            requested_by="operator-a",
            approved_by="operator-b",
            reason="active worker lease must fence operator quarantine",
            authorization=_async_control_authorization(),
        )

    assert exc_info.value.status_code == 409
    assert "has an active lease" in str(exc_info.value.detail)


def test_process_next_async_delivery_quarantines_missing_runtime_job(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-worker-missing-delivery.db'}"
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    upgrade_database_to_head(settings.database_url)
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )
    queue.enqueue(
        message=AsyncQueueDeliveryMessage(
            delivery_id="delivery-missing-job-001",
            job_id="asyncjob_missing_delivery",
            attempt_id="attempt-missing-delivery-001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-missing-delivery-001",
            submitted_at="2026-03-24T00:00:00Z",
        )
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    detail = build_async_job_detail(job_id="asyncjob_missing_delivery")
    history = build_async_control_history()

    assert result is not None
    assert result.handled is False
    assert detail.job.status.value == "ABANDONED"
    assert detail.job.execution_path == "dedicated_worker_delivery_recovery"
    assert detail.attempts[0].failure_reason == "MISSING_RUNTIME_JOB"
    assert history.latest_events[0].job_id == "asyncjob_missing_delivery"
    assert history.latest_events[0].action_type.value == "QUARANTINE_QUEUED_JOB"
    assert history.latest_events[0].prior_status == "MISSING_RUNTIME_JOB"
    assert history.latest_events[0].resulting_status == "ABANDONED"
    assert history.latest_events[0].affected_attempt_id == "attempt-missing-delivery-001"


def test_process_next_async_delivery_executes_document_ingestion_job_in_dedicated_mode(
    monkeypatch: MonkeyPatch,
) -> None:
    settings.async_cutover_state = "dedicated_workers_active"
    settings.async_queue_backend_mode = "redis"
    settings.async_queue_redis_url = "redis://localhost:6379/0"
    queue = get_test_async_delivery_queue()
    monkeypatch.setattr(
        "app.services.async_submission_shared.get_async_delivery_queue",
        lambda: queue,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.get_async_delivery_queue",
        lambda: queue,
    )

    submission = submit_retrieval_ingestion_job_async(
        job_id="ingjob_lotus_platform_rfcs_refresh_0069",
        caller_app="lotus-platform",
        correlation_id="corr-worker-fleet-ingestion-001",
    )

    result = process_next_async_delivery(worker_id="worker-a", timeout_seconds=0)
    detail = build_async_job_detail(job_id=submission.job_id or "")
    ingestion_detail = get_retrieval_ingestion_job_detail_or_raise(
        "ingjob_lotus_platform_rfcs_refresh_0069"
    )

    assert result is not None
    assert result.job_type == "document_ingestion"
    assert result.handled is True
    assert result.terminal_status == "COMPLETED"
    assert detail.job.status.value == "COMPLETED"
    assert ingestion_detail.job.status.value == "COMPLETED"


def test_run_dedicated_worker_loop_respects_max_cycles_when_idle(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []
    sleeps: list[float] = []

    def fake_process_next_async_delivery(*, worker_id: str, timeout_seconds: int) -> None:
        calls.append((worker_id, timeout_seconds))
        return None

    monkeypatch.setattr(
        "app.services.async_worker_fleet.process_next_async_delivery",
        fake_process_next_async_delivery,
    )
    monkeypatch.setattr(
        "app.services.async_worker_fleet.sleep", lambda seconds: sleeps.append(seconds)
    )

    run_dedicated_worker_loop(
        worker_id="worker-a",
        timeout_seconds=2,
        idle_sleep_seconds=0.1,
        max_cycles=3,
    )

    assert calls == [("worker-a", 2), ("worker-a", 2), ("worker-a", 2)]
    assert sleeps == [0.1, 0.1, 0.1]


def test_worker_main_runs_dedicated_loop(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    settings.async_worker_id = "lotus-ai-worker-7"
    settings.async_worker_queue_poll_seconds = 9
    monkeypatch.setattr(
        "app.worker_main.run_dedicated_worker_loop",
        lambda worker_id, timeout_seconds: captured.update(
            {"worker_id": worker_id, "timeout_seconds": timeout_seconds}
        ),
    )

    from app.worker_main import main

    main()

    assert captured == {"worker_id": "lotus-ai-worker-7", "timeout_seconds": 9}
