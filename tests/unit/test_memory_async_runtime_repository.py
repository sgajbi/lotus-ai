from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
    AsyncRuntimeControlEventRecord,
    AsyncRuntimeLeaseRecord,
)
from app.repositories.memory_async_runtime_repository import InMemoryAsyncRuntimeRepository


def test_memory_async_runtime_repository_round_trip() -> None:
    repository = InMemoryAsyncRuntimeRepository()

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


def test_memory_async_runtime_repository_returns_empty_results_for_unknown_records() -> None:
    repository = InMemoryAsyncRuntimeRepository()

    assert repository.list_jobs() == []
    assert repository.get_job(job_id="missing") is None
    assert repository.list_attempts(job_id="missing") == []
    assert repository.list_leases() == []
    assert repository.get_active_lease(job_id="missing") is None
    assert repository.delete_lease(lease_id="missing") == 0


def test_memory_async_runtime_repository_replaces_attempts_and_leases_cleanly() -> None:
    repository = InMemoryAsyncRuntimeRepository()

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


def test_memory_async_runtime_repository_claims_next_runnable_job_once() -> None:
    repository = InMemoryAsyncRuntimeRepository()
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
    assert repository.claim_next_runnable_job(
        worker_id="worker-b",
        claimed_at="2026-03-23T00:02:00Z",
        heartbeat_at="2026-03-23T00:02:00Z",
        lease_expires_at="2026-03-23T00:07:00Z",
        latest_message="Claimed by worker-b.",
        attempt_message="Attempt claimed by worker-b.",
    ) is None


def test_memory_async_runtime_repository_round_trips_control_events() -> None:
    repository = InMemoryAsyncRuntimeRepository()
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
