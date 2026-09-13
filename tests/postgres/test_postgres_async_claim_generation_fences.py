"""Async worker generation fences on real PostgreSQL (issue #376).

The two repositories below own distinct engines and connection pools.  The
tests assert distinct PostgreSQL backend IDs before exercising a crash/reclaim
interleaving, so a local repository cache cannot masquerade as concurrency
evidence.  The stale worker deliberately reuses the *same worker id*; only
the immutable attempt generation distinguishes it from the reclaimed worker.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.db.models import ArtifactMetadataModel, AsyncWorkerLeaseModel
from app.repositories.artifact_repository import ArtifactRecord
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.repositories.sqlalchemy_async_runtime_repository import (
    SqlAlchemyAsyncRuntimeRepository,
)

_T0 = "2026-09-13T00:00:00Z"
_T1 = "2026-09-13T00:05:01Z"
_T2 = "2026-09-13T00:05:02Z"


def _two_sessions(
    database_url: str,
) -> tuple[SqlAlchemyAsyncRuntimeRepository, SqlAlchemyAsyncRuntimeRepository]:
    return (
        SqlAlchemyAsyncRuntimeRepository(database_url),
        SqlAlchemyAsyncRuntimeRepository(database_url),
    )


def _race(*calls: Callable[[], object]) -> list[object]:
    """Run operations in separate threads, retaining separate repository pools."""

    barrier = Barrier(len(calls), timeout=10)

    def run(call: Callable[[], object]) -> object:
        barrier.wait()
        return call()

    with ThreadPoolExecutor(max_workers=len(calls)) as pool:
        return list(pool.map(run, calls))


def _seed_queued_job(
    repository: SqlAlchemyAsyncRuntimeRepository, job_id: str
) -> AsyncRuntimeAttemptRecord:
    repository.save_job(
        AsyncRuntimeJobRecord(
            job_id=job_id,
            job_type="retrieval_indexing",
            target_id="retjob_pg_claim_fence",
            lifecycle_status="QUEUED",
            submitted_at=_T0,
            caller_app="lotus-platform",
            correlation_id=f"corr-{job_id}",
            payload_summary="PostgreSQL immutable claim-generation proof.",
            execution_path="dedicated_worker",
            related_evaluation_run_id=None,
            latest_message="Queued for PostgreSQL fence proof.",
            attempt_count=1,
            artifact_ids=[],
            tenant_id="tenant-pg-fence",
        )
    )
    attempt = AsyncRuntimeAttemptRecord(
        attempt_id=f"{job_id}_attempt_001",
        job_id=job_id,
        attempt_number=1,
        lifecycle_status="QUEUED",
        worker_id=None,
        claimed_at=None,
        heartbeat_at=None,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        recorded_message="Queued for PostgreSQL fence proof.",
    )
    repository.save_attempt(attempt)
    return attempt


def _terminal_artifact(job_id: str) -> ArtifactRecord:
    artifact_id = f"artifact_async_pg_fence_{uuid4().hex}"
    return ArtifactRecord(
        artifact_id=artifact_id,
        domain="async",
        artifact_type="job_terminal_output",
        source_object_kind="async_job",
        source_object_id=job_id,
        lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
        retention_posture="active",
        media_type="application/json",
        byte_size=2,
        checksum_sha256="a" * 64,
        storage_backend=ArtifactStorageBackend.MEMORY,
        storage_reference=f"memory://async/async_job/{job_id}/{artifact_id}.json",
        lineage_parent_artifact_id=None,
        superseded_by_artifact_id=None,
        created_at=_T2,
        created_by="reused-worker",
        tenant_id="tenant-pg-fence",
    )


def test_async_claim_fence_uses_independent_read_committed_sessions(
    postgres_database_url: str,
) -> None:
    session_a, session_b = _two_sessions(postgres_database_url)
    backend_ids: list[int] = []
    isolation_levels: list[str] = []
    for repository in (session_a, session_b):
        with repository._session_factory() as session:
            backend_ids.append(session.execute(text("SELECT pg_backend_pid()")).scalar_one())
            isolation_levels.append(
                session.execute(text("SHOW transaction_isolation")).scalar_one()
            )
    assert backend_ids[0] != backend_ids[1]
    assert isolation_levels == ["read committed", "read committed"]


def test_stale_reused_worker_cannot_publish_terminal_artifact_after_crash_recovery(
    postgres_database_url: str,
) -> None:
    """A restarted worker with the same id cannot write attempt one after
    recovery minted and leased attempt two. The rejected transition leaves no
    terminal artifact metadata, not merely no job artifact reference.
    """

    stale_session, recovery_session = _two_sessions(postgres_database_url)
    job_id = f"asyncjob_pg_generation_{uuid4().hex}"
    first_attempt = _seed_queued_job(stale_session, job_id)
    claimed = stale_session.claim_runnable_job_by_id(
        job_id=job_id,
        worker_id="reused-worker",
        claimed_at=_T0,
        heartbeat_at=_T0,
        lease_expires_at="2026-09-13T00:05:00Z",
        latest_message="Worker began execution before crashing.",
        attempt_message="Attempt one claimed before crash.",
    )
    assert claimed is not None and claimed.attempt.attempt_id == first_attempt.attempt_id
    assert (
        recovery_session.recover_expired_claim(
            job_id=job_id,
            recovered_at=_T1,
            next_attempt_message="Retry queued after lease expiry recovery.",
        )
        is not None
    )
    reclaimed = recovery_session.claim_runnable_job_by_id(
        job_id=job_id,
        worker_id="reused-worker",
        claimed_at=_T1,
        heartbeat_at=_T1,
        lease_expires_at="2026-09-13T00:10:01Z",
        latest_message="Restarted worker owns generation two.",
        attempt_message="Attempt two claimed after recovery.",
    )
    assert reclaimed is not None
    assert reclaimed.attempt.attempt_id != first_attempt.attempt_id

    assert (
        stale_session.transition_current_claim(
            job_id=job_id,
            worker_id="reused-worker",
            attempt_id=first_attempt.attempt_id,
            now=_T2,
            job_status="RUNNING",
            job_message="Stale start must be rejected.",
            attempt_status="RUNNING",
            attempt_message="Stale start must be rejected.",
            failure_reason=None,
            lease_expires_at=None,
            terminal_artifact=None,
        )
        is None
    )

    assert (
        stale_session.transition_current_claim(
            job_id=job_id,
            worker_id="reused-worker",
            attempt_id=first_attempt.attempt_id,
            now=_T2,
            job_status=None,
            job_message=None,
            attempt_status=None,
            attempt_message="Stale heartbeat must be rejected.",
            failure_reason=None,
            lease_expires_at="2026-09-13T00:10:02Z",
            terminal_artifact=None,
        )
        is None
    )
    assert (
        stale_session.transition_current_claim(
            job_id=job_id,
            worker_id="reused-worker",
            attempt_id=first_attempt.attempt_id,
            now=_T2,
            job_status="FAILED",
            job_message="Stale failure must be rejected.",
            attempt_status="FAILED",
            attempt_message="Stale failure must be rejected.",
            failure_reason="STALE_WORKER",
            lease_expires_at=None,
            terminal_artifact=None,
        )
        is None
    )
    stale_artifact = _terminal_artifact(job_id)
    assert (
        stale_session.transition_current_claim(
            job_id=job_id,
            worker_id="reused-worker",
            attempt_id=first_attempt.attempt_id,
            now=_T2,
            job_status="COMPLETED",
            job_message="Stale completion must be rejected.",
            attempt_status="COMPLETED",
            attempt_message="Stale completion must be rejected.",
            failure_reason=None,
            lease_expires_at=None,
            terminal_artifact=stale_artifact,
        )
        is None
    )

    job = recovery_session.get_job(job_id=job_id)
    lease = recovery_session.get_active_lease(job_id=job_id)
    attempts = recovery_session.list_attempts(job_id=job_id)
    assert job is not None and job.lifecycle_status == "CLAIMED" and job.artifact_ids == []
    assert lease is not None and lease.attempt_id == reclaimed.attempt.attempt_id
    assert [attempt.lifecycle_status for attempt in attempts] == ["ABANDONED", "CLAIMED"]
    with recovery_session._session_factory() as session:
        assert (
            session.scalar(
                select(ArtifactMetadataModel.artifact_id).where(
                    ArtifactMetadataModel.artifact_id == stale_artifact.artifact_id
                )
            )
            is None
        )


def test_current_generation_commits_terminal_job_and_artifact_metadata_together(
    postgres_database_url: str,
) -> None:
    repository, verifier = _two_sessions(postgres_database_url)
    job_id = f"asyncjob_pg_terminal_{uuid4().hex}"
    first_attempt = _seed_queued_job(repository, job_id)
    claim = repository.claim_runnable_job_by_id(
        job_id=job_id,
        worker_id="worker-a",
        claimed_at=_T0,
        heartbeat_at=_T0,
        lease_expires_at="2026-09-13T00:10:00Z",
        latest_message="Claimed for terminal publication proof.",
        attempt_message="Claimed for terminal publication proof.",
    )
    assert claim is not None
    artifact = _terminal_artifact(job_id)
    completed = repository.transition_current_claim(
        job_id=job_id,
        worker_id="worker-a",
        attempt_id=first_attempt.attempt_id,
        now=_T1,
        job_status="COMPLETED",
        job_message="Completed with fenced artifact publication.",
        attempt_status="COMPLETED",
        attempt_message="Completed with fenced artifact publication.",
        failure_reason=None,
        lease_expires_at=None,
        terminal_artifact=artifact,
    )
    assert completed is not None and completed.lease is None
    job = verifier.get_job(job_id=job_id)
    assert job is not None and job.lifecycle_status == "COMPLETED"
    assert job.artifact_ids == [artifact.artifact_id]
    assert verifier.get_active_lease(job_id=job_id) is None
    with verifier._session_factory() as session:
        persisted = session.get(ArtifactMetadataModel, artifact.artifact_id)
        assert persisted is not None and persisted.source_object_id == job_id


def test_retry_generations_are_monotonic_through_recovery_on_postgresql(
    postgres_database_url: str,
) -> None:
    """A locked counter produces 001 -> 002 -> 003, then recovery -> 004."""

    writer, verifier = _two_sessions(postgres_database_url)
    job_id = f"asyncjob_pg_monotonic_{uuid4().hex}"
    first = _seed_queued_job(writer, job_id)
    claim_one = writer.claim_runnable_job_by_id(
        job_id=job_id,
        worker_id="worker-a",
        claimed_at=_T0,
        heartbeat_at=_T0,
        lease_expires_at="2026-09-13T00:02:00Z",
        latest_message="Generation one claimed.",
        attempt_message="Generation one claimed.",
    )
    assert claim_one is not None
    retry_one = writer.transition_current_claim(
        job_id=job_id,
        worker_id="worker-a",
        attempt_id=first.attempt_id,
        now="2026-09-13T00:01:00Z",
        job_status="QUEUED",
        job_message="Retry two queued.",
        attempt_status="FAILED",
        attempt_message="Generation one retryable failure.",
        failure_reason="TRANSIENT_TIMEOUT",
        lease_expires_at=None,
        terminal_artifact=None,
        next_attempt_message="Retry two queued.",
    )
    assert retry_one is not None and retry_one.next_attempt is not None
    assert retry_one.next_attempt.attempt_id == f"{job_id}_attempt_002"
    claim_two = writer.claim_runnable_job_by_id(
        job_id=job_id,
        worker_id="worker-a",
        claimed_at="2026-09-13T00:02:00Z",
        heartbeat_at="2026-09-13T00:02:00Z",
        lease_expires_at="2026-09-13T00:04:00Z",
        latest_message="Generation two claimed.",
        attempt_message="Generation two claimed.",
    )
    assert claim_two is not None
    retry_two = writer.transition_current_claim(
        job_id=job_id,
        worker_id="worker-a",
        attempt_id=claim_two.attempt.attempt_id,
        now="2026-09-13T00:03:00Z",
        job_status="QUEUED",
        job_message="Retry three queued.",
        attempt_status="FAILED",
        attempt_message="Generation two retryable failure.",
        failure_reason="TRANSIENT_TIMEOUT",
        lease_expires_at=None,
        terminal_artifact=None,
        next_attempt_message="Retry three queued.",
    )
    assert retry_two is not None and retry_two.next_attempt is not None
    assert retry_two.next_attempt.attempt_id == f"{job_id}_attempt_003"
    claim_three = writer.claim_runnable_job_by_id(
        job_id=job_id,
        worker_id="worker-a",
        claimed_at="2026-09-13T00:04:00Z",
        heartbeat_at="2026-09-13T00:04:00Z",
        lease_expires_at="2026-09-13T00:05:00Z",
        latest_message="Generation three claimed.",
        attempt_message="Generation three claimed.",
    )
    assert claim_three is not None
    recovery = verifier.recover_expired_claim(
        job_id=job_id,
        recovered_at=_T1,
        next_attempt_message="Recovery queued generation four.",
    )
    assert recovery is not None and recovery.next_attempt.attempt_id == f"{job_id}_attempt_004"
    job = verifier.get_job(job_id=job_id)
    attempts = verifier.list_attempts(job_id=job_id)
    assert job is not None and job.attempt_count == 4
    assert [(attempt.attempt_number, attempt.lifecycle_status) for attempt in attempts] == [
        (1, "FAILED"),
        (2, "FAILED"),
        (3, "ABANDONED"),
        (4, "QUEUED"),
    ]


def test_simultaneous_postgresql_claimers_admit_exactly_one_current_generation(
    postgres_database_url: str,
) -> None:
    """Two independent PostgreSQL sessions cannot both claim one queued attempt."""

    claimant_a, claimant_b = _two_sessions(postgres_database_url)
    job_id = f"asyncjob_pg_simultaneous_{uuid4().hex}"
    _seed_queued_job(claimant_a, job_id)
    outcomes = _race(
        lambda: claimant_a.claim_runnable_job_by_id(
            job_id=job_id,
            worker_id="worker-a",
            claimed_at=_T0,
            heartbeat_at=_T0,
            lease_expires_at="2026-09-13T00:05:00Z",
            latest_message="Worker A attempted claim.",
            attempt_message="Worker A attempted claim.",
        ),
        lambda: claimant_b.claim_runnable_job_by_id(
            job_id=job_id,
            worker_id="worker-b",
            claimed_at=_T0,
            heartbeat_at=_T0,
            lease_expires_at="2026-09-13T00:05:00Z",
            latest_message="Worker B attempted claim.",
            attempt_message="Worker B attempted claim.",
        ),
    )
    winners = [outcome for outcome in outcomes if outcome is not None]
    assert len(winners) == 1
    job = claimant_a.get_job(job_id=job_id)
    lease = claimant_a.get_active_lease(job_id=job_id)
    assert job is not None and job.lifecycle_status == "CLAIMED"
    assert lease is not None and lease.worker_id in {"worker-a", "worker-b"}


def test_postgresql_completion_and_expiry_recovery_admit_one_durable_outcome(
    postgres_database_url: str,
) -> None:
    """Completion and recovery race one lease; the loser publishes no mixed state."""

    completer, recoverer = _two_sessions(postgres_database_url)
    job_id = f"asyncjob_pg_complete_recover_{uuid4().hex}"
    first = _seed_queued_job(completer, job_id)
    assert (
        completer.claim_runnable_job_by_id(
            job_id=job_id,
            worker_id="worker-a",
            claimed_at=_T0,
            heartbeat_at=_T0,
            lease_expires_at="2026-09-13T00:05:00Z",
            latest_message="Claimed for completion-versus-recovery proof.",
            attempt_message="Claimed for completion-versus-recovery proof.",
        )
        is not None
    )
    artifact = _terminal_artifact(job_id)
    outcomes = _race(
        lambda: completer.transition_current_claim(
            job_id=job_id,
            worker_id="worker-a",
            attempt_id=first.attempt_id,
            now="2026-09-13T00:04:59Z",
            job_status="COMPLETED",
            job_message="Completion raced expiry recovery.",
            attempt_status="COMPLETED",
            attempt_message="Completion raced expiry recovery.",
            failure_reason=None,
            lease_expires_at=None,
            terminal_artifact=artifact,
        ),
        lambda: recoverer.recover_expired_claim(
            job_id=job_id,
            recovered_at=_T1,
            next_attempt_message="Recovery raced completion.",
        ),
    )
    assert sum(outcome is not None for outcome in outcomes) == 1

    job = completer.get_job(job_id=job_id)
    attempts = completer.list_attempts(job_id=job_id)
    assert job is not None
    assert completer.get_active_lease(job_id=job_id) is None
    with completer._session_factory() as session:
        persisted_artifact = session.get(ArtifactMetadataModel, artifact.artifact_id)
    if job.lifecycle_status == "COMPLETED":
        assert job.artifact_ids == [artifact.artifact_id]
        assert [attempt.lifecycle_status for attempt in attempts] == ["COMPLETED"]
        assert persisted_artifact is not None
    else:
        assert job.lifecycle_status == "QUEUED" and job.artifact_ids == []
        assert [(attempt.attempt_number, attempt.lifecycle_status) for attempt in attempts] == [
            (1, "ABANDONED"),
            (2, "QUEUED"),
        ]
        assert persisted_artifact is None


def test_postgresql_lock_wait_rechecks_expiry_before_terminal_publication(
    postgres_database_url: str,
) -> None:
    """The completion timestamp is sampled after a held lease-row lock releases."""

    writer, blocked_writer = _two_sessions(postgres_database_url)
    job_id = f"asyncjob_pg_lock_expiry_{uuid4().hex}"
    first = _seed_queued_job(writer, job_id)
    assert (
        writer.claim_runnable_job_by_id(
            job_id=job_id,
            worker_id="worker-a",
            claimed_at=_T0,
            heartbeat_at=_T0,
            lease_expires_at="2026-09-13T00:05:00Z",
            latest_message="Claimed for expiry-boundary proof.",
            attempt_message="Claimed for expiry-boundary proof.",
        )
        is not None
    )
    artifact = _terminal_artifact(job_id)
    lock_acquired = Event()
    fresh_time_sampled = Event()
    release_lock = Event()

    def hold_lease_lock() -> None:
        with writer._session_factory.begin() as session:
            session.scalars(
                select(AsyncWorkerLeaseModel)
                .where(AsyncWorkerLeaseModel.job_id == job_id)
                .with_for_update()
            ).one()
            lock_acquired.set()
            assert release_lock.wait(timeout=10)

    def expire_after_lock() -> str:
        fresh_time_sampled.set()
        return _T1

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(hold_lease_lock)
        assert lock_acquired.wait(timeout=10)
        blocked = pool.submit(
            blocked_writer.transition_current_claim,
            job_id=job_id,
            worker_id="worker-a",
            attempt_id=first.attempt_id,
            now=None,
            job_status="COMPLETED",
            job_message="Must not publish after expiry.",
            attempt_status="COMPLETED",
            attempt_message="Must not publish after expiry.",
            failure_reason=None,
            lease_expires_at=None,
            terminal_artifact=artifact,
            now_factory=expire_after_lock,
        )
        assert not fresh_time_sampled.wait(timeout=0.2)
        release_lock.set()
        assert holder.result(timeout=10) is None
        assert blocked.result(timeout=10) is None

    job = writer.get_job(job_id=job_id)
    lease = writer.get_active_lease(job_id=job_id)
    assert job is not None and job.lifecycle_status == "CLAIMED" and job.artifact_ids == []
    assert lease is not None and lease.attempt_id == first.attempt_id
    with writer._session_factory() as session:
        assert session.get(ArtifactMetadataModel, artifact.artifact_id) is None


def test_postgresql_terminal_artifact_failure_rolls_back_job_metadata_together(
    postgres_database_url: str,
) -> None:
    """A failed artifact insert cannot commit terminal job or attempt state alone."""

    repository, verifier = _two_sessions(postgres_database_url)
    job_id = f"asyncjob_pg_terminal_rollback_{uuid4().hex}"
    first = _seed_queued_job(repository, job_id)
    assert (
        repository.claim_runnable_job_by_id(
            job_id=job_id,
            worker_id="worker-a",
            claimed_at=_T0,
            heartbeat_at=_T0,
            lease_expires_at="2026-09-13T00:10:00Z",
            latest_message="Claimed for rollback proof.",
            attempt_message="Claimed for rollback proof.",
        )
        is not None
    )
    collision = _terminal_artifact("another-async-job")
    with repository._session_factory.begin() as session:
        session.add(repository._artifact_metadata_model(collision))

    with pytest.raises(IntegrityError):
        repository.transition_current_claim(
            job_id=job_id,
            worker_id="worker-a",
            attempt_id=first.attempt_id,
            now=_T1,
            job_status="COMPLETED",
            job_message="Must roll back if terminal artifact persistence fails.",
            attempt_status="COMPLETED",
            attempt_message="Must roll back if terminal artifact persistence fails.",
            failure_reason=None,
            lease_expires_at=None,
            terminal_artifact=collision,
        )

    job = verifier.get_job(job_id=job_id)
    attempt = verifier.get_attempt(attempt_id=first.attempt_id)
    lease = verifier.get_active_lease(job_id=job_id)
    assert job is not None and job.lifecycle_status == "CLAIMED" and job.artifact_ids == []
    assert attempt is not None and attempt.lifecycle_status == "CLAIMED"
    assert lease is not None and lease.attempt_id == first.attempt_id
    with verifier._session_factory() as session:
        persisted = session.get(ArtifactMetadataModel, collision.artifact_id)
        assert persisted is not None and persisted.source_object_id == "another-async-job"
