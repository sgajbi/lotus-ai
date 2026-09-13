from pathlib import Path
from datetime import UTC, datetime
from dataclasses import replace

from _pytest.monkeypatch import MonkeyPatch
import pytest

from app.config import settings
from app.contracts.artifacts import ArtifactStorageBackend
from app.repositories.memory_async_runtime_repository import InMemoryAsyncRuntimeRepository
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord,
    AsyncRuntimeJobRecord,
)
from app.repositories.sqlalchemy_async_runtime_repository import SqlAlchemyAsyncRuntimeRepository
from fastapi import HTTPException
from app.services.eval_run_service import build_evaluation_run_detail
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_store import (
    get_async_runtime_store,
    reset_async_runtime_store_cache,
)
from app.services.async_submission_service import submit_async_job
from app.services.artifact_store import get_artifact_repository
from app.services.artifact_payloads import stage_json_artifact
from app.services.async_worker_runtime import (
    claim_next_async_job,
    complete_async_job,
    fail_async_job,
    heartbeat_async_job,
    recover_expired_async_jobs,
    start_async_job,
)
from app.contracts.evals import EvaluationRunSubmissionRequest
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
    start_async_job(
        job_id=response.job_id or "", worker_id="worker-a", attempt_id=claimed.attempt.attempt_id
    )
    heartbeat_async_job(
        job_id=response.job_id or "", worker_id="worker-a", attempt_id=claimed.attempt.attempt_id
    )
    complete_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        attempt_id=claimed.attempt.attempt_id,
        message="Retrieval indexing completed successfully.",
    )

    detail = build_async_job_detail(job_id=response.job_id or "")

    assert detail.job.status.value == "COMPLETED"
    assert detail.active_lease is None
    assert len(detail.attempts) == 1
    assert detail.attempts[0].status == "COMPLETED"
    assert detail.attempts[0].worker_id == "worker-a"
    assert len(detail.job.artifact_refs) == 1


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
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 13, 2, tzinfo=UTC),
    )
    fail_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        attempt_id=claim.attempt.attempt_id,
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


def test_async_worker_runtime_mints_monotonic_retry_and_recovery_generations(
    monkeypatch: MonkeyPatch,
) -> None:
    """The guarded counter, rather than a worker snapshot, owns successor ids."""

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 13, 30, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-monotonic-generations-001",
            payload_summary="Prove retry and recovery generations never reuse an attempt id.",
        )
    )
    first = claim_next_async_job(worker_id="worker-a")
    assert first is not None

    fail_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        attempt_id=first.attempt.attempt_id,
        failure_reason="TRANSIENT_TIMEOUT",
        retryable=True,
    )
    second = claim_next_async_job(worker_id="worker-a")
    assert second is not None and second.attempt.attempt_id.endswith("_attempt_002")

    fail_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        attempt_id=second.attempt.attempt_id,
        failure_reason="TRANSIENT_TIMEOUT",
        retryable=True,
    )
    third = claim_next_async_job(worker_id="worker-a")
    assert third is not None and third.attempt.attempt_id.endswith("_attempt_003")

    recovered = recover_expired_async_jobs(
        now=datetime(2026, 3, 23, 13, 36, tzinfo=UTC),
    )
    assert recovered == [response.job_id]
    detail = build_async_job_detail(job_id=response.job_id or "")
    persisted_job = get_async_runtime_store().get_job(job_id=response.job_id or "")
    assert persisted_job is not None and persisted_job.attempt_count == 4
    assert [(attempt.attempt_number, attempt.status) for attempt in detail.attempts] == [
        (1, "FAILED"),
        (2, "FAILED"),
        (3, "ABANDONED"),
        (4, "QUEUED"),
    ]
    assert detail.job.artifact_refs == []


def test_async_completion_rechecks_expiry_after_staging_and_cleans_payload(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A payload staged before expiry is not publishable after expiry.

    The two post-claim instants model staging crossing the boundary: the
    durable transition receives its timestamp only after artifact staging.
    """

    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "artifact-payloads")
    instants = iter(
        [
            datetime(2026, 3, 23, 13, 30, tzinfo=UTC),
            datetime(2026, 3, 23, 13, 34, 59, tzinfo=UTC),
            datetime(2026, 3, 23, 13, 35, 1, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr("app.services.async_worker_runtime._utcnow", lambda: next(instants))
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-staging-expiry-001",
            payload_summary="Reject terminal metadata after a staged payload crosses lease expiry.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None

    with pytest.raises(HTTPException, match="no longer has an unexpired current claim") as error:
        complete_async_job(
            job_id=response.job_id or "",
            worker_id="worker-a",
            attempt_id=claim.attempt.attempt_id,
            message="This terminal result crossed its lease boundary.",
        )

    assert error.value.status_code == 409
    detail = build_async_job_detail(job_id=response.job_id or "")
    assert detail.job.status.value == "CLAIMED"
    assert detail.job.artifact_refs == []
    assert get_artifact_repository().list_artifacts() == []
    assert not [path for path in (tmp_path / "artifact-payloads").rglob("*") if path.is_file()]


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
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    start_async_job(
        job_id=response.job_id or "", worker_id="worker-a", attempt_id=claim.attempt.attempt_id
    )

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


def test_async_worker_runtime_recovery_skips_jobs_without_leases(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 18, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-005",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim_next_async_job(worker_id="worker-a")
    runtime_store = get_async_runtime_store()
    assert isinstance(runtime_store, InMemoryAsyncRuntimeRepository)
    runtime_store._leases_by_job.clear()

    recovered = claim_next_async_job(worker_id="worker-b")

    assert recovered is None
    detail = build_async_job_detail(job_id=response.job_id or "")
    assert detail.job.status.value == "CLAIMED"


def test_async_worker_runtime_recovery_skips_jobs_when_active_attempt_is_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 19, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-006",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    runtime_store = get_async_runtime_store()
    assert isinstance(runtime_store, InMemoryAsyncRuntimeRepository)
    runtime_store._attempts[response.job_id or ""] = []

    recovered = claim_next_async_job(worker_id="worker-b")

    assert recovered is None


def test_async_worker_runtime_rejects_missing_claim_at_the_transition_boundary() -> None:
    with pytest.raises(HTTPException) as exc_info:
        start_async_job(job_id="missing-job", worker_id="worker-a", attempt_id="missing-attempt")

    assert exc_info.value.status_code == 409
    assert "no longer has an unexpired current claim" in str(exc_info.value)


def test_async_worker_runtime_raises_when_job_is_not_leased_by_worker(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 20, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-007",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None

    with pytest.raises(HTTPException) as exc_info:
        start_async_job(
            job_id=response.job_id or "", worker_id="worker-b", attempt_id=claim.attempt.attempt_id
        )

    assert exc_info.value.status_code == 409
    assert "no longer has an unexpired current claim" in str(exc_info.value)


def test_async_worker_runtime_raises_when_active_attempt_is_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 21, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-008",
            payload_summary="Refresh retrieval documents.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    runtime_store = get_async_runtime_store()
    assert isinstance(runtime_store, InMemoryAsyncRuntimeRepository)
    runtime_store._attempts[response.job_id or ""] = []

    with pytest.raises(HTTPException) as exc_info:
        start_async_job(
            job_id=response.job_id or "", worker_id="worker-a", attempt_id=claim.attempt.attempt_id
        )

    assert exc_info.value.status_code == 409
    assert "no longer has an unexpired current claim" in str(exc_info.value)


def test_async_worker_runtime_rejects_expired_reused_worker_generation_and_artifact(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 23, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-generation-fence-001",
            payload_summary="Fence an expired reused worker generation.",
        )
    )
    first_claim = claim_next_async_job(worker_id="reused-worker")
    assert first_claim is not None
    start_async_job(
        job_id=response.job_id or "",
        worker_id="reused-worker",
        attempt_id=first_claim.attempt.attempt_id,
    )

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 23, 10, tzinfo=UTC),
    )
    recovered_claim = claim_next_async_job(worker_id="reused-worker")
    assert recovered_claim is not None
    assert recovered_claim.attempt.attempt_id != first_claim.attempt.attempt_id

    with pytest.raises(HTTPException) as heartbeat_error:
        heartbeat_async_job(
            job_id=response.job_id or "",
            worker_id="reused-worker",
            attempt_id=first_claim.attempt.attempt_id,
        )
    with pytest.raises(HTTPException) as completion_error:
        complete_async_job(
            job_id=response.job_id or "",
            worker_id="reused-worker",
            attempt_id=first_claim.attempt.attempt_id,
            message="Stale worker must not complete a recovered job.",
        )
    with pytest.raises(HTTPException) as failure_error:
        fail_async_job(
            job_id=response.job_id or "",
            worker_id="reused-worker",
            attempt_id=first_claim.attempt.attempt_id,
            failure_reason="STALE_WORKER",
            retryable=False,
        )

    assert all(
        error.value.status_code == 409
        for error in (heartbeat_error, completion_error, failure_error)
    )
    detail = build_async_job_detail(job_id=response.job_id or "")
    assert detail.job.status.value == "CLAIMED"
    assert detail.active_lease is not None
    assert detail.active_lease.attempt_id == recovered_claim.attempt.attempt_id
    assert detail.job.artifact_refs == []
    assert get_artifact_repository().list_artifacts() == []


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
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    start_async_job(
        job_id=response.job_id or "", worker_id="worker-a", attempt_id=claim.attempt.attempt_id
    )

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


def test_async_worker_runtime_sql_terminal_publication_persists_artifact_with_job(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.artifact_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-worker-terminal.db'}"
    upgrade_database_to_head(settings.database_url)
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 16, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-terminal-transaction-001",
            payload_summary="Persist terminal publication transactionally.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    start_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        attempt_id=claim.attempt.attempt_id,
    )
    complete_async_job(
        job_id=response.job_id or "",
        worker_id="worker-a",
        attempt_id=claim.attempt.attempt_id,
        message="Completed with durable terminal publication.",
    )

    reset_async_runtime_store_cache()
    detail = build_async_job_detail(job_id=response.job_id or "")
    assert detail.job.status.value == "COMPLETED"
    assert detail.active_lease is None
    assert len(detail.job.artifact_refs) == 1
    artifact_id = detail.job.artifact_refs[0].artifact_id
    assert get_artifact_repository().get_artifact(artifact_id=artifact_id) is not None


def test_sql_claim_transition_rejects_mismatched_and_expired_generations(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The repository, rather than a worker-side pre-read, rejects stale ownership."""
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-worker-generation.db'}"
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
            correlation_id="corr-async-worker-generation-rejection-001",
            payload_summary="Prove stale SQL claim rejection at the write boundary.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    repository = get_async_runtime_store()
    assert isinstance(repository, SqlAlchemyAsyncRuntimeRepository)

    rejected_inputs = (
        ("wrong-attempt", "2026-03-23T17:01:00+00:00"),
        (claim.attempt.attempt_id, "2026-03-23T17:06:00+00:00"),
    )
    for attempt_id, now in rejected_inputs:
        assert (
            repository.transition_current_claim(
                job_id=response.job_id or "",
                worker_id="worker-a",
                attempt_id=attempt_id,
                now=now,
                job_status="COMPLETED",
                job_message="A stale generation must not complete the job.",
                attempt_status="COMPLETED",
                attempt_message="Rejected stale terminal transition.",
                failure_reason=None,
                lease_expires_at=None,
                terminal_artifact=None,
            )
            is None
        )

    detail = build_async_job_detail(job_id=response.job_id or "")
    assert detail.job.status.value == "CLAIMED"
    assert detail.active_lease is not None
    assert detail.active_lease.attempt_id == claim.attempt.attempt_id


def test_sql_claim_transition_commits_retry_successor_with_failed_generation(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-worker-retry-transition.db'}"
    upgrade_database_to_head(settings.database_url)
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 18, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-retry-transition-001",
            payload_summary="Persist a failed generation and queued successor together.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    repository = get_async_runtime_store()
    assert isinstance(repository, SqlAlchemyAsyncRuntimeRepository)
    transition = repository.transition_current_claim(
        job_id=response.job_id or "",
        worker_id="worker-a",
        attempt_id=claim.attempt.attempt_id,
        now="2026-03-23T18:01:00+00:00",
        job_status="QUEUED",
        job_message="Retry queued after transient failure.",
        attempt_status="FAILED",
        attempt_message="Attempt failed and was requeued transactionally.",
        failure_reason="TRANSIENT_TIMEOUT",
        lease_expires_at=None,
        terminal_artifact=None,
        next_attempt_message="Retry queued after transient failure.",
    )

    assert transition is not None and transition.lease is None
    assert transition.next_attempt is not None
    assert transition.next_attempt.attempt_id == f"{response.job_id}_attempt_002"
    detail = build_async_job_detail(job_id=response.job_id or "")
    assert detail.job.status.value == "QUEUED"
    assert [(attempt.attempt_number, attempt.status) for attempt in detail.attempts] == [
        (1, "FAILED"),
        (2, "QUEUED"),
    ]
    second_claim = repository.claim_runnable_job_by_id(
        job_id=response.job_id or "",
        worker_id="worker-b",
        claimed_at="2026-03-23T18:02:00+00:00",
        heartbeat_at="2026-03-23T18:02:00+00:00",
        lease_expires_at="2026-03-23T18:03:00+00:00",
        latest_message="Retry generation claimed before expiry recovery.",
        attempt_message="Retry generation claimed before expiry recovery.",
    )
    assert second_claim is not None and second_claim.attempt.attempt_number == 2
    with pytest.raises(ValueError, match="fresh claim-transition timestamp"):
        repository.transition_current_claim(
            job_id=response.job_id or "",
            worker_id="worker-b",
            attempt_id=second_claim.attempt.attempt_id,
            now=None,
            job_status=None,
            job_message=None,
            attempt_status=None,
            attempt_message="Malformed transition must not invent a clock value.",
            failure_reason=None,
            lease_expires_at=None,
            terminal_artifact=None,
        )
    with pytest.raises(ValueError, match="fresh claim-recovery timestamp"):
        repository.recover_expired_claim(
            job_id=response.job_id or "",
            recovered_at=None,
            next_attempt_message="Malformed recovery must not invent a clock value.",
        )
    recovered = repository.recover_expired_claim(
        job_id=response.job_id or "",
        recovered_at="2026-03-23T18:04:00+00:00",
        next_attempt_message="Recovery queued a strictly newer generation.",
    )
    assert recovered is not None and recovered.next_attempt.attempt_number == 3
    recovered_detail = build_async_job_detail(job_id=response.job_id or "")
    assert [(attempt.attempt_number, attempt.status) for attempt in recovered_detail.attempts] == [
        (1, "FAILED"),
        (2, "ABANDONED"),
        (3, "QUEUED"),
    ]
    assert (
        repository.recover_expired_claim(
            job_id=response.job_id or "",
            recovered_at="2026-03-23T18:04:00+00:00",
            next_attempt_message="A missing lease cannot be recovered twice.",
        )
        is None
    )


def test_sql_recovery_rejects_unexpired_or_terminal_claim_state(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-async-worker-recovery-rejection.db'}"
    upgrade_database_to_head(settings.database_url)
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 19, 0, tzinfo=UTC),
    )
    response = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-recovery-rejection-001",
            payload_summary="Reject recovery outside a valid claim generation.",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    repository = get_async_runtime_store()
    assert isinstance(repository, SqlAlchemyAsyncRuntimeRepository)
    assert (
        repository.recover_expired_claim(
            job_id=response.job_id or "",
            recovered_at="2026-03-23T19:01:00+00:00",
            next_attempt_message="Recovery queued a successor generation.",
        )
        is None
    )

    job = repository.get_job(job_id=response.job_id or "")
    assert job is not None
    repository.save_job(replace(job, lifecycle_status="COMPLETED"))
    assert (
        repository.transition_current_claim(
            job_id=response.job_id or "",
            worker_id="worker-a",
            attempt_id=claim.attempt.attempt_id,
            now="2026-03-23T19:01:00+00:00",
            job_status="FAILED",
            job_message="A terminal job must reject a stale worker mutation.",
            attempt_status="FAILED",
            attempt_message="Rejected because the durable job state is terminal.",
            failure_reason="STALE_WORKER",
            lease_expires_at=None,
            terminal_artifact=None,
        )
        is None
    )


def test_stage_json_artifact_defers_metadata_for_filesystem_payloads(tmp_path: Path) -> None:
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "artifact-payloads")

    staged = stage_json_artifact(
        domain="async",
        artifact_type="claim-generation-proof",
        source_object_kind="async_job",
        source_object_id="job-staged-only",
        created_at="2026-03-23T19:00:00+00:00",
        created_by="worker-a",
        payload_json=b'{"proof":"staged"}',
    )

    assert staged.storage_backend == ArtifactStorageBackend.FILESYSTEM
    assert get_artifact_repository().get_artifact(artifact_id=staged.artifact_id) is None


def test_memory_recovery_rejects_unexpired_claim_state() -> None:
    repository = InMemoryAsyncRuntimeRepository()
    job_id = "asyncjob_memory_recovery_generation"
    repository.save_job(
        AsyncRuntimeJobRecord(
            job_id=job_id,
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            lifecycle_status="QUEUED",
            submitted_at="2026-03-23T20:00:00+00:00",
            caller_app="lotus-platform",
            correlation_id="corr-memory-recovery-generation-001",
            payload_summary="Prove in-memory recovery preserves generation rules.",
            execution_path="dedicated_worker",
            related_evaluation_run_id=None,
            latest_message="Queued.",
            attempt_count=1,
            artifact_ids=[],
            tenant_id=None,
        )
    )
    repository.save_attempt(
        AsyncRuntimeAttemptRecord(
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
            recorded_message="Queued.",
        )
    )
    claim = repository.claim_runnable_job_by_id(
        job_id=job_id,
        worker_id="worker-a",
        claimed_at="2026-03-23T20:00:00+00:00",
        heartbeat_at="2026-03-23T20:00:00+00:00",
        lease_expires_at="2026-03-23T20:05:00+00:00",
        latest_message="Claimed.",
        attempt_message="Claimed.",
    )
    assert claim is not None
    with pytest.raises(ValueError, match="fresh claim-transition timestamp"):
        repository.transition_current_claim(
            job_id=job_id,
            worker_id="worker-a",
            attempt_id=claim.attempt.attempt_id,
            now=None,
            job_status=None,
            job_message=None,
            attempt_status=None,
            attempt_message="Malformed transition must not invent a clock value.",
            failure_reason=None,
            lease_expires_at=None,
            terminal_artifact=None,
        )
    with pytest.raises(ValueError, match="fresh claim-recovery timestamp"):
        repository.recover_expired_claim(
            job_id=job_id,
            recovered_at=None,
            next_attempt_message="Malformed recovery must not invent a clock value.",
        )
    assert (
        repository.recover_expired_claim(
            job_id=job_id,
            recovered_at="2026-03-23T20:01:00+00:00",
            next_attempt_message="Recovery queued a successor generation.",
        )
        is None
    )


def test_async_worker_runtime_recovery_updates_evaluation_attempt_history(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 22, 0, tzinfo=UTC),
    )
    submission = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-async-worker-eval-001",
            triggered_by="operator-a",
        )
    )
    claim = claim_next_async_job(worker_id="worker-a")
    assert claim is not None
    start_async_job(
        job_id=submission.async_job_id or "",
        worker_id="worker-a",
        attempt_id=claim.attempt.attempt_id,
    )

    monkeypatch.setattr(
        "app.services.async_worker_runtime._utcnow",
        lambda: datetime(2026, 3, 23, 22, 10, tzinfo=UTC),
    )
    recovered_claim = claim_next_async_job(worker_id="worker-b")

    assert recovered_claim is not None
    detail = build_evaluation_run_detail(run_id=submission.run_id or "")
    assert detail.run.status.value == "QUEUED"
    assert len(detail.attempts) == 2
    assert detail.attempts[0].status.value == "ABANDONED"
    assert detail.attempts[0].failure_reason == "LEASE_EXPIRED"
    assert detail.attempts[1].status.value == "CLAIMED"
    assert detail.attempts[1].worker_id == "worker-b"
