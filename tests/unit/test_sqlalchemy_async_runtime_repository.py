from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeLeaseRecord,
)
from app.repositories.sqlalchemy_async_runtime_repository import (
    SqlAlchemyAsyncRuntimeRepository,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_async_runtime_repository_round_trip(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)

    repository.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="SUBMITTED",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="lotus-ai",
            correlation_id="corr-001",
            payload_summary="Refresh retrieval source lotus-ai-architecture",
            execution_path="durable_async_backbone",
            related_evaluation_run_id=None,
            latest_message="Job submitted for future durable execution.",
            attempt_count=1,
        )
    )
    repository.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="attempt-001",
            job_id="async-job-001",
            attempt_number=1,
            lifecycle_status="RUNNABLE",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Attempt recorded but not yet claimed.",
        )
    )
    repository.save_lease(
        AsyncRuntimeLeaseRecord(
            lease_id="lease-001",
            job_id="async-job-001",
            attempt_id="attempt-001",
            worker_id="worker-a",
            claimed_at="2026-03-23T00:01:00Z",
            heartbeat_at="2026-03-23T00:01:30Z",
            lease_expires_at="2026-03-23T00:06:30Z",
        )
    )

    job = repository.get_job(job_id="async-job-001")
    attempts = repository.list_attempts(job_id="async-job-001")
    lease = repository.get_active_lease(job_id="async-job-001")

    assert job is not None
    assert repository.list_jobs() == [job]
    assert job.job_type == "retrieval_indexing"
    assert len(attempts) == 1
    assert attempts[0].attempt_id == "attempt-001"
    assert lease is not None
    assert lease.worker_id == "worker-a"


def test_sqlalchemy_async_runtime_repository_returns_empty_results_for_unknown_records(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)

    assert repository.list_jobs() == []
    assert repository.get_job(job_id="missing") is None
    assert repository.list_attempts(job_id="missing") == []
    assert repository.list_leases() == []
    assert repository.get_active_lease(job_id="missing") is None
    assert repository.delete_lease(lease_id="missing") == 0


def test_sqlalchemy_async_runtime_repository_creates_parent_directory_for_sqlite_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "nested" / "db" / "lotus-ai-async-runtime.db"
    database_url = f"sqlite:///{db_path}"

    SqlAlchemyAsyncRuntimeRepository(database_url)

    assert db_path.parent.is_dir()


def test_sqlalchemy_async_runtime_repository_replaces_attempts_and_leases_cleanly(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)

    repository.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="attempt-001",
            job_id="async-job-001",
            attempt_number=1,
            lifecycle_status="RUNNABLE",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Attempt recorded.",
        )
    )
    repository.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="attempt-001",
            job_id="async-job-001",
            attempt_number=1,
            lifecycle_status="RUNNING",
            worker_id="worker-a",
            claimed_at="2026-03-23T00:01:00Z",
            heartbeat_at="2026-03-23T00:01:30Z",
            started_at="2026-03-23T00:01:00Z",
            completed_at=None,
            failure_reason=None,
            recorded_message="Attempt claimed by worker-a.",
        )
    )
    repository.save_lease(
        AsyncRuntimeLeaseRecord(
            lease_id="lease-001",
            job_id="async-job-001",
            attempt_id="attempt-001",
            worker_id="worker-a",
            claimed_at="2026-03-23T00:01:00Z",
            heartbeat_at="2026-03-23T00:01:30Z",
            lease_expires_at="2026-03-23T00:06:30Z",
        )
    )

    attempts = repository.list_attempts(job_id="async-job-001")

    assert len(attempts) == 1
    assert attempts[0].lifecycle_status == "RUNNING"
    assert repository.delete_lease(lease_id="lease-001") == 1
    assert repository.get_active_lease(job_id="async-job-001") is None


def test_sqlalchemy_async_runtime_repository_claims_next_runnable_job_once(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)
    repository.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="QUEUED",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="lotus-ai",
            correlation_id="corr-001",
            payload_summary="Refresh retrieval source lotus-ai-architecture",
            execution_path="durable_runtime_submission",
            related_evaluation_run_id=None,
            latest_message="Job queued for durable execution.",
            attempt_count=1,
        )
    )
    repository.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="attempt-001",
            job_id="async-job-001",
            attempt_number=1,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Attempt queued for worker claim.",
        )
    )

    claim = repository.claim_next_runnable_job(
        worker_id="worker-a",
        job_types=("retrieval_indexing",),
        claimed_at="2026-03-23T00:01:00Z",
        heartbeat_at="2026-03-23T00:01:00Z",
        lease_expires_at="2026-03-23T00:06:00Z",
        latest_message="Claimed by worker-a.",
        attempt_message="Attempt claimed by worker-a.",
    )

    assert claim is not None
    assert claim.job.lifecycle_status == "CLAIMED"
    assert claim.job.target_id == "retjob_lotus_platform_rfcs"
    assert claim.attempt.worker_id == "worker-a"
    assert claim.lease.worker_id == "worker-a"
    assert (
        repository.claim_next_runnable_job(
            worker_id="worker-b",
            job_types=("retrieval_indexing",),
            claimed_at="2026-03-23T00:02:00Z",
            heartbeat_at="2026-03-23T00:02:00Z",
            lease_expires_at="2026-03-23T00:07:00Z",
            latest_message="Claimed by worker-b.",
            attempt_message="Attempt claimed by worker-b.",
        )
        is None
    )


def test_sqlalchemy_async_runtime_repository_round_trips_control_events(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)
    repository.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="FAILED",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="lotus-ai",
            correlation_id="corr-001",
            payload_summary="Refresh retrieval source lotus-ai-architecture",
            execution_path="durable_runtime_worker_execution",
            related_evaluation_run_id=None,
            latest_message="Job failed terminally.",
            attempt_count=1,
        )
    )
    repository.save_control_event(
        AsyncRuntimeControlEventRecord(
            event_id="event-001",
            job_id="async-job-001",
            action_type="RETRY_FAILED_JOB",
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Retry after review.",
            prior_status="FAILED",
            resulting_status="QUEUED",
            affected_attempt_id="attempt-002",
            recorded_at="2026-03-23T18:00:00Z",
        )
    )

    events = repository.list_control_events()

    assert len(events) == 1
    assert events[0].action_type == "RETRY_FAILED_JOB"
    assert events[0].affected_attempt_id == "attempt-002"


def test_sqlalchemy_async_runtime_repository_claims_specific_runnable_job_by_id(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)
    repository.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-claim-by-id",
            job_type="evaluation_execution",
            target_id="provider_runtime_examples",
            lifecycle_status="QUEUED",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="lotus-ai",
            correlation_id="corr-claim-by-id",
            payload_summary="Run evaluation execution.",
            execution_path="durable_runtime_submission",
            related_evaluation_run_id="evalrun_001",
            latest_message="Queued for dedicated worker execution.",
            attempt_count=1,
        )
    )
    repository.save_attempt(
        AsyncRuntimeAttemptRecord(
            attempt_id="attempt-claim-by-id-001",
            job_id="async-job-claim-by-id",
            attempt_number=1,
            lifecycle_status="QUEUED",
            worker_id=None,
            claimed_at=None,
            heartbeat_at=None,
            started_at=None,
            completed_at=None,
            failure_reason=None,
            recorded_message="Queued for worker claim.",
        )
    )

    claim = repository.claim_runnable_job_by_id(
        job_id="async-job-claim-by-id",
        worker_id="worker-a",
        claimed_at="2026-03-23T00:01:00Z",
        heartbeat_at="2026-03-23T00:01:00Z",
        lease_expires_at="2026-03-23T00:06:00Z",
        latest_message="Claimed by worker-a.",
        attempt_message="Attempt claimed by worker-a.",
    )

    assert claim is not None
    assert claim.job.job_id == "async-job-claim-by-id"
    assert claim.attempt.worker_id == "worker-a"
    assert claim.lease.worker_id == "worker-a"


def test_sqlalchemy_async_runtime_repository_returns_none_for_unknown_attempt(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)

    assert repository.get_attempt(attempt_id="missing-attempt") is None


def test_sqlalchemy_async_runtime_repository_claim_returns_none_without_attempt(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-runtime.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyAsyncRuntimeRepository(database_url)
    repository.save_job(
        AsyncRuntimeJobRecord(
            job_id="async-job-001",
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="QUEUED",
            submitted_at="2026-03-23T00:00:00Z",
            caller_app="lotus-ai",
            correlation_id="corr-001",
            payload_summary="Refresh retrieval source lotus-ai-architecture",
            execution_path="durable_runtime_submission",
            related_evaluation_run_id=None,
            latest_message="Queued without attempts.",
            attempt_count=0,
        )
    )

    assert (
        repository.claim_next_runnable_job(
            worker_id="worker-a",
            job_types=("retrieval_indexing",),
            claimed_at="2026-03-23T00:01:00Z",
            heartbeat_at="2026-03-23T00:01:00Z",
            lease_expires_at="2026-03-23T00:06:00Z",
            latest_message="Claimed by worker-a.",
            attempt_message="Attempt claimed by worker-a.",
        )
        is None
    )


def test_sqlalchemy_async_runtime_repository_ensure_sqlite_directory_skips_memory_and_non_sqlite(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    SqlAlchemyAsyncRuntimeRepository("sqlite:///:memory:")
    relative_path = tmp_path / "relative" / "lotus-ai-async-runtime.db"
    SqlAlchemyAsyncRuntimeRepository(f"sqlite:///{relative_path}")
    assert relative_path.parent.is_dir()
    monkeypatch.setattr(
        "app.repositories.sqlalchemy_async_runtime_repository.create_engine",
        lambda database_url, future=True: object(),
    )
    SqlAlchemyAsyncRuntimeRepository("postgresql://user:pass@localhost/lotus")
