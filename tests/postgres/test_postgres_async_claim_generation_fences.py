"""Async worker generation fences on real PostgreSQL (issue #376).

The two repositories below own distinct engines and connection pools.  The
tests assert distinct PostgreSQL backend IDs before exercising a crash/reclaim
interleaving, so a local repository cache cannot masquerade as concurrency
evidence.  The stale worker deliberately reuses the *same worker id*; only
the immutable attempt generation distinguishes it from the reclaimed worker.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select, text

from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.db.models import ArtifactMetadataModel
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


def _next_attempt(job_id: str) -> AsyncRuntimeAttemptRecord:
    return AsyncRuntimeAttemptRecord(
        attempt_id=f"{job_id}_attempt_002",
        job_id=job_id,
        attempt_number=2,
        lifecycle_status="QUEUED",
        worker_id=None,
        claimed_at=None,
        heartbeat_at=None,
        started_at=None,
        completed_at=None,
        failure_reason=None,
        recorded_message="Retry queued after lease expiry recovery.",
    )


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
            next_attempt=_next_attempt(job_id),
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
