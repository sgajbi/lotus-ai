from __future__ import annotations

from app.repositories.evaluation_runtime_repository import (
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
)
from app.services.evaluation_runtime_store import get_evaluation_runtime_store


def queue_next_evaluation_attempt(*, run_id: str, reason_message: str) -> EvaluationRunAttemptRecord:
    store = get_evaluation_runtime_store()
    run = _get_run_or_raise(run_id=run_id)
    attempts = store.list_attempts(run_id=run_id)
    next_attempt_number = (attempts[-1].attempt_number + 1) if attempts else 1
    attempt = EvaluationRunAttemptRecord(
        attempt_id=f"{run_id}_attempt_{next_attempt_number:03d}",
        run_id=run_id,
        attempt_number=next_attempt_number,
        lifecycle_status="QUEUED",
        started_at=None,
        completed_at=None,
        worker_id=None,
        latest_message=reason_message,
        verdict=None,
        failure_reason=None,
    )
    store.save_attempt(attempt)
    store.save_run(
        EvaluationRunRecord(
            run_id=run.run_id,
            fixture_id=run.fixture_id,
            manifest_version=run.manifest_version,
            lifecycle_status="QUEUED",
            triggered_by=run.triggered_by,
            submitted_at=run.submitted_at,
            async_job_id=run.async_job_id,
            latest_message=reason_message,
            verdict=None,
            case_count=run.case_count,
        )
    )
    return attempt


def claim_active_evaluation_attempt(
    *,
    run_id: str,
    worker_id: str,
    reason_message: str,
) -> EvaluationRunAttemptRecord | None:
    store = get_evaluation_runtime_store()
    run = store.get_run(run_id=run_id)
    if run is None:
        return None
    attempt = _get_latest_active_attempt(run_id=run_id)
    if attempt is None:
        return None
    claimed = EvaluationRunAttemptRecord(
        attempt_id=attempt.attempt_id,
        run_id=attempt.run_id,
        attempt_number=attempt.attempt_number,
        lifecycle_status="CLAIMED",
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        worker_id=worker_id,
        latest_message=reason_message,
        verdict=None,
        failure_reason=None,
    )
    store.save_attempt(claimed)
    store.save_run(
        EvaluationRunRecord(
            run_id=run.run_id,
            fixture_id=run.fixture_id,
            manifest_version=run.manifest_version,
            lifecycle_status="QUEUED",
            triggered_by=run.triggered_by,
            submitted_at=run.submitted_at,
            async_job_id=run.async_job_id,
            latest_message=reason_message,
            verdict=None,
            case_count=run.case_count,
        )
    )
    return claimed


def abandon_active_evaluation_attempt(
    *,
    run_id: str,
    reason_message: str,
    failure_reason: str,
) -> EvaluationRunAttemptRecord | None:
    store = get_evaluation_runtime_store()
    run = store.get_run(run_id=run_id)
    if run is None:
        return None
    attempt = _get_latest_active_attempt(run_id=run_id)
    if attempt is None:
        return None
    abandoned = EvaluationRunAttemptRecord(
        attempt_id=attempt.attempt_id,
        run_id=attempt.run_id,
        attempt_number=attempt.attempt_number,
        lifecycle_status="ABANDONED",
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        worker_id=attempt.worker_id,
        latest_message=reason_message,
        verdict=None,
        failure_reason=failure_reason,
    )
    store.save_attempt(abandoned)
    store.save_run(
        EvaluationRunRecord(
            run_id=run.run_id,
            fixture_id=run.fixture_id,
            manifest_version=run.manifest_version,
            lifecycle_status="ABANDONED",
            triggered_by=run.triggered_by,
            submitted_at=run.submitted_at,
            async_job_id=run.async_job_id,
            latest_message=reason_message,
            verdict=None,
            case_count=run.case_count,
        )
    )
    return abandoned


def fail_active_evaluation_attempt(
    *,
    run_id: str,
    reason_message: str,
    failure_reason: str,
) -> EvaluationRunAttemptRecord | None:
    store = get_evaluation_runtime_store()
    run = store.get_run(run_id=run_id)
    if run is None:
        return None
    attempt = _get_latest_active_attempt(run_id=run_id)
    if attempt is None:
        return None
    failed = EvaluationRunAttemptRecord(
        attempt_id=attempt.attempt_id,
        run_id=attempt.run_id,
        attempt_number=attempt.attempt_number,
        lifecycle_status="FAILED",
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        worker_id=attempt.worker_id,
        latest_message=reason_message,
        verdict=None,
        failure_reason=failure_reason,
    )
    store.save_attempt(failed)
    store.save_run(
        EvaluationRunRecord(
            run_id=run.run_id,
            fixture_id=run.fixture_id,
            manifest_version=run.manifest_version,
            lifecycle_status="FAILED",
            triggered_by=run.triggered_by,
            submitted_at=run.submitted_at,
            async_job_id=run.async_job_id,
            latest_message=reason_message,
            verdict=None,
            case_count=run.case_count,
        )
    )
    return failed


def _get_latest_active_attempt(*, run_id: str) -> EvaluationRunAttemptRecord | None:
    attempts = get_evaluation_runtime_store().list_attempts(run_id=run_id)
    for attempt in reversed(attempts):
        if attempt.lifecycle_status in {"QUEUED", "CLAIMED", "RUNNING"}:
            return attempt
    return None


def _get_run_or_raise(*, run_id: str) -> EvaluationRunRecord:
    run = get_evaluation_runtime_store().get_run(run_id=run_id)
    if run is None:
        raise RuntimeError(f"Evaluation run '{run_id}' was not found in runtime state.")
    return run
