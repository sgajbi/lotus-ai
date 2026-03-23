from pathlib import Path
from datetime import UTC, datetime

from _pytest.monkeypatch import MonkeyPatch

from app.config import settings
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.services.async_submission_service import submit_async_job
from app.services.async_worker_runtime import (
    claim_next_async_job,
    complete_async_job,
    fail_async_job,
    heartbeat_async_job,
    start_async_job,
)
from app.contracts.async_runtime import AsyncJobSubmissionRequest
from tests.support.migration_runner import upgrade_database_to_head


def test_async_worker_runtime_claim_start_and_complete_flow(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 12, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-001",
            payload_summary="Refresh retrieval documents.",
        )
    )

    claimed = claim_next_async_job(worker_id="worker-a")

    assert claimed is not None
    assert claimed.job.job_id == response.job_id
    assert claim_next_async_job(worker_id="worker-b") is None

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 12, 1, tzinfo=UTC),
    )
    start_async_job(job_id=response.job_id or "", worker_id="worker-a")
    heartbeat_async_job(job_id=response.job_id or "", worker_id="worker-a")
    complete_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        message="Retrieval indexing completed successfully.",
    )

    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.status.value == "COMPLETED"
    assert detail.active_lease is None
    assert len(detail.attempts) == 1
    assert detail.attempts[0].status == "COMPLETED"
    assert detail.attempts[0].worker_id == "worker-a"


def test_async_worker_runtime_retryable_failure_requeues_next_attempt(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 13, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-002",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim_next_async_job(worker_id="worker-a")

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 13, 2, tzinfo=UTC),
    )
    fail_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        failure_reason="TRANSIENT_TIMEOUT",
        retryable=True,
    )

    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.status.value == "QUEUED"
    assert detail.active_lease is None
    assert len(detail.attempts) == 2
    assert detail.attempts[0].status == "FAILED"
    assert detail.attempts[0].failure_reason == "TRANSIENT_TIMEOUT"
    assert detail.attempts[1].status == "QUEUED"


def test_async_worker_runtime_recovers_expired_lease_on_next_claim(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 14, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-003",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim_next_async_job(worker_id="worker-a")
    start_async_job(job_id=response.job_id or "", worker_id="worker-a")

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 14, 10, tzinfo=UTC),
    )
    recovered_claim = claim_next_async_job(worker_id="worker-b")

    assert recovered_claim is not None
    assert recovered_claim.job.job_id == response.job_id
    assert recovered_claim.attempt.attempt_number == 2

    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.status.value == "CLAIMED"
    assert detail.active_lease is not None
    assert detail.active_lease.worker_id == "worker-b"
    assert len(detail.attempts) == 2
    assert detail.attempts[0].status == "ABANDONED"
    assert detail.attempts[0].failure_reason == "LEASE_EXPIRED"
    assert detail.attempts[1].status == "CLAIMED"


def test_async_worker_runtime_recovery_survives_sql_store_reset(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-worker-recovery.db'}"
    upgrade_database_to_head(settings.database_url)

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 15, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-004",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim_next_async_job(worker_id="worker-a")
    start_async_job(job_id=response.job_id or "", worker_id="worker-a")

    reset_async_runtime_store_cache()

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 15, 10, tzinfo=UTC),
    )
    recovered_claim = claim_next_async_job(worker_id="worker-b")

    assert recovered_claim is not None
    assert recovered_claim.job.job_id == response.job_id
    assert recovered_claim.attempt.attempt_number == 2

    reset_async_runtime_store_cache()
    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.status.value == "CLAIMED"
    assert detail.active_lease is not None
    assert detail.active_lease.worker_id == "worker-b"
    assert len(detail.attempts) == 2
    assert detail.attempts[0].status == "ABANDONED"
    assert detail.attempts[0].failure_reason == "LEASE_EXPIRED"
    assert detail.attempts[1].status == "CLAIMED"
