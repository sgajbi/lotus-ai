from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.config import settings
from app.contracts.async_runtime import AsyncControlActionRequest, AsyncControlActionType
from app.contracts.async_runtime import AsyncJobSubmissionRequest
from app.repositories.async_runtime_repository import (
    AsyncRuntimeAttemptRecord as AsyncAttemptRecord,
    AsyncRuntimeClaimRecord,
    AsyncRuntimeJobRecord as AsyncJobRecord,
    AsyncRuntimeLeaseRecord,
)
from app.repositories.evaluation_runtime_repository import (
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
)
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_control import apply_async_control_action
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_runtime_execution import execute_runtime_backed_evaluation_run
from app.services.eval_run_service import build_evaluation_run_detail
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.async_submission_service import submit_async_job
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.evaluation_runtime_store import (
    get_evaluation_runtime_store,
    reset_evaluation_runtime_store_cache,
)
from tests.support.migration_runner import upgrade_database_to_head


def test_run_next_evaluation_execution_job_persists_attempts_case_results_and_verdict() -> None:
    submission = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-exec-001",
            triggered_by="operator-a",
        )
    )

    result = run_next_evaluation_execution_job(worker_id="worker-a")

    assert result is not None
    assert result.async_job_id == submission.async_job_id
    assert result.evaluation_run_id == submission.run_id
    assert result.verdict == "PASS"
    assert result.case_result_count == 2

    run_detail = build_evaluation_run_detail(run_id=submission.run_id or "")
    async_detail = build_async_job_detail(job_id=submission.async_job_id or "")

    assert run_detail.run.status.value == "COMPLETED"
    assert run_detail.attempts[0].status.value == "COMPLETED"
    assert run_detail.attempts[0].worker_id == "worker-a"
    assert run_detail.attempts[0].verdict is not None
    assert run_detail.attempts[0].verdict.value == "PASS"
    assert len(run_detail.case_results) == 2
    assert all(case.outcome.value == "PASS" for case in run_detail.case_results)
    assert async_detail.job.status.value == "COMPLETED"


def test_run_next_evaluation_execution_job_returns_none_when_no_jobs_are_available() -> None:
    assert run_next_evaluation_execution_job(worker_id="worker-a") is None


def test_run_next_evaluation_execution_job_does_not_claim_non_evaluation_jobs() -> None:
    submission = submit_async_job(
        AsyncJobSubmissionRequest(
            job_type="retrieval_indexing",
            target_id="retjob_lotus_platform_rfcs",
            caller_app="lotus-platform",
            correlation_id="corr-async-eval-worker-skip-001",
            payload_summary="Refresh retrieval documents.",
        )
    )

    result = run_next_evaluation_execution_job(worker_id="worker-a")
    detail = build_async_job_detail(job_id=submission.job_id or "")

    assert result is None
    assert detail.job.status.value == "QUEUED"


def test_run_next_evaluation_execution_job_survives_sql_store_reset(tmp_path: Path) -> None:
    settings.async_runtime_store_mode = "sqlalchemy"
    settings.evaluation_runtime_store_mode = "sqlalchemy"
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-eval-exec.db'}"
    upgrade_database_to_head(settings.database_url)

    submission = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-exec-sql-001",
            triggered_by="operator-a",
        )
    )

    run_next_evaluation_execution_job(worker_id="worker-a")
    reset_async_runtime_store_cache()
    reset_evaluation_runtime_store_cache()

    run_detail = build_evaluation_run_detail(run_id=submission.run_id or "")
    async_detail = build_async_job_detail(job_id=submission.async_job_id or "")

    assert run_detail.run.status.value == "COMPLETED"
    assert run_detail.attempts[0].status.value == "COMPLETED"
    assert len(run_detail.case_results) == 2
    assert all(case.outcome.value == "PASS" for case in run_detail.case_results)
    assert async_detail.job.status.value == "COMPLETED"


def test_evaluation_replay_preserves_prior_case_history_and_creates_new_attempt() -> None:
    submission = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-replay-001",
            triggered_by="operator-a",
        )
    )

    run_next_evaluation_execution_job(worker_id="worker-a")
    apply_async_control_action(
        AsyncControlActionRequest(
            job_id=submission.async_job_id or "",
            action_type=AsyncControlActionType.REPLAY_TERMINAL_JOB,
            requested_by="operator-a",
            approved_by="approver-a",
            reason="Replay runtime-backed evaluation after review.",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-b")

    run_detail = build_evaluation_run_detail(run_id=submission.run_id or "")
    async_detail = build_async_job_detail(job_id=submission.async_job_id or "")

    assert run_detail.run.status.value == "COMPLETED"
    assert len(run_detail.attempts) == 2
    assert run_detail.attempts[0].status.value == "COMPLETED"
    assert run_detail.attempts[1].status.value == "COMPLETED"
    assert len(run_detail.case_results) == 4
    assert len({case.case_result_id for case in run_detail.case_results}) == 4
    assert len({case.attempt_id for case in run_detail.case_results}) == 2
    assert async_detail.attempts[-1].status == "COMPLETED"


def test_run_next_evaluation_execution_job_marks_async_and_eval_attempt_failed_on_exception() -> (
    None
):
    submission = submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="provider_policy_examples",
            caller_app="lotus-platform",
            correlation_id="corr-eval-failure-001",
            triggered_by="operator-a",
        )
    )

    with patch(
        "app.services.eval_async_execution.execute_runtime_backed_evaluation_run",
        side_effect=RuntimeError("boom"),
    ):
        try:
            run_next_evaluation_execution_job(worker_id="worker-a")
        except RuntimeError as exc:
            assert str(exc) == "boom"
        else:
            raise AssertionError("Expected evaluation execution to raise RuntimeError.")

    run_detail = build_evaluation_run_detail(run_id=submission.run_id or "")
    async_detail = build_async_job_detail(job_id=submission.async_job_id or "")

    assert run_detail.run.status.value == "FAILED"
    assert run_detail.attempts[0].status.value == "FAILED"
    assert run_detail.attempts[0].failure_reason == "RuntimeError"
    assert async_detail.job.status.value == "FAILED"
    assert async_detail.attempts[-1].failure_reason == "RuntimeError"


def test_execute_runtime_backed_evaluation_run_rejects_missing_run() -> None:
    with pytest.raises(HTTPException, match="was not found"):
        execute_runtime_backed_evaluation_run(
            run_id="missing-run",
            worker_id="worker-a",
        )


def test_execute_runtime_backed_evaluation_run_rejects_without_active_attempt() -> None:
    store = get_evaluation_runtime_store()
    store.save_run(
        EvaluationRunRecord(
            run_id="evalrun_no_attempt",
            fixture_id="provider_policy_examples",
            manifest_version="foundation.v1",
            lifecycle_status="QUEUED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T00:00:00Z",
            async_job_id="asyncjob_no_attempt",
            latest_message="Queued without attempt.",
            verdict=None,
            case_count=2,
        )
    )

    with pytest.raises(HTTPException, match="has no queued runtime attempt"):
        execute_runtime_backed_evaluation_run(
            run_id="evalrun_no_attempt",
            worker_id="worker-a",
        )


def test_execute_runtime_backed_evaluation_run_rejects_staged_only_fixture_family() -> None:
    store = get_evaluation_runtime_store()
    store.save_run(
        EvaluationRunRecord(
            run_id="evalrun_staged_only",
            fixture_id="explanation_task_examples",
            manifest_version="foundation.v1",
            lifecycle_status="QUEUED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T00:00:00Z",
            async_job_id="asyncjob_staged_only",
            latest_message="Queued staged-only fixture.",
            verdict=None,
            case_count=1,
        )
    )
    store.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id="evalrun_staged_only_attempt_001",
            run_id="evalrun_staged_only",
            attempt_number=1,
            lifecycle_status="QUEUED",
            started_at=None,
            completed_at=None,
            worker_id=None,
            latest_message="Queued.",
            verdict=None,
            failure_reason=None,
        )
    )

    with pytest.raises(HTTPException, match="is not executable in runtime-backed mode"):
        execute_runtime_backed_evaluation_run(
            run_id="evalrun_staged_only",
            worker_id="worker-a",
        )


def test_run_next_evaluation_execution_job_fails_unsupported_claim() -> None:
    with (
        patch(
            "app.services.eval_async_execution.claim_next_async_job_for_types",
            return_value=AsyncRuntimeClaimRecord(
                job=AsyncJobRecord(
                    job_id="async-job-unsupported-eval",
                    job_type="retrieval_indexing",
                    target_id="retjob_lotus_platform_rfcs",
                    lifecycle_status="CLAIMED",
                    submitted_at="2026-03-23T00:00:00Z",
                    caller_app="lotus-platform",
                    correlation_id="corr-eval-unsupported-claim",
                    payload_summary="Wrong job type claimed.",
                    execution_path="durable_runtime_worker_execution",
                    related_evaluation_run_id=None,
                    latest_message="Claimed.",
                    attempt_count=1,
                ),
                attempt=AsyncAttemptRecord(
                    attempt_id="async-job-unsupported-eval_attempt_001",
                    job_id="async-job-unsupported-eval",
                    attempt_number=1,
                    lifecycle_status="CLAIMED",
                    worker_id="worker-a",
                    claimed_at="2026-03-23T00:01:00Z",
                    heartbeat_at="2026-03-23T00:01:00Z",
                    started_at=None,
                    completed_at=None,
                    failure_reason=None,
                    recorded_message="Claimed.",
                ),
                lease=AsyncRuntimeLeaseRecord(
                    lease_id="lease-unsupported-eval",
                    job_id="async-job-unsupported-eval",
                    attempt_id="async-job-unsupported-eval_attempt_001",
                    worker_id="worker-a",
                    claimed_at="2026-03-23T00:01:00Z",
                    heartbeat_at="2026-03-23T00:01:00Z",
                    lease_expires_at="2026-03-23T00:06:00Z",
                ),
            ),
        ),
        patch("app.services.eval_async_execution.fail_async_job") as fail_async_job,
    ):
        result = run_next_evaluation_execution_job(worker_id="worker-a")

    assert result is None
    fail_async_job.assert_called_once()
    assert fail_async_job.call_args.kwargs["failure_reason"] == "UNSUPPORTED_ASYNC_JOB_TYPE"
