from pathlib import Path

from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
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
