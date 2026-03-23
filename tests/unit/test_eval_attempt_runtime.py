from app.repositories.evaluation_runtime_repository import (
    EvaluationRunAttemptRecord,
    EvaluationRunRecord,
)
from app.services.eval_attempt_runtime import (
    abandon_active_evaluation_attempt,
    claim_active_evaluation_attempt,
    fail_active_evaluation_attempt,
    queue_next_evaluation_attempt,
)
from app.services.evaluation_runtime_store import get_evaluation_runtime_store


def test_queue_next_evaluation_attempt_raises_for_missing_run() -> None:
    try:
        queue_next_evaluation_attempt(
            run_id="missing-run",
            reason_message="Queue missing run.",
        )
    except RuntimeError as exc:
        assert "missing-run" in str(exc)
    else:
        raise AssertionError("Expected missing runtime evaluation run to raise.")


def test_claim_abandon_and_fail_active_attempt_return_none_when_run_missing() -> None:
    assert (
        claim_active_evaluation_attempt(
            run_id="missing-run",
            worker_id="worker-a",
            reason_message="Claim missing run.",
        )
        is None
    )
    assert (
        abandon_active_evaluation_attempt(
            run_id="missing-run",
            reason_message="Abandon missing run.",
            failure_reason="MISSING_RUN",
        )
        is None
    )
    assert (
        fail_active_evaluation_attempt(
            run_id="missing-run",
            reason_message="Fail missing run.",
            failure_reason="MISSING_RUN",
        )
        is None
    )


def test_claim_abandon_and_fail_active_attempt_return_none_without_active_attempt() -> None:
    store = get_evaluation_runtime_store()
    store.save_run(
        EvaluationRunRecord(
            run_id="evalrun_terminal_only",
            fixture_id="provider_policy_examples",
            manifest_version="foundation.v1",
            lifecycle_status="COMPLETED",
            triggered_by="operator-a",
            submitted_at="2026-03-23T00:00:00Z",
            async_job_id="asyncjob_terminal_only",
            latest_message="Completed already.",
            verdict="PASS",
            case_count=2,
        )
    )
    store.save_attempt(
        EvaluationRunAttemptRecord(
            attempt_id="evalrun_terminal_only_attempt_001",
            run_id="evalrun_terminal_only",
            attempt_number=1,
            lifecycle_status="COMPLETED",
            started_at="2026-03-23T00:01:00Z",
            completed_at="2026-03-23T00:02:00Z",
            worker_id="worker-a",
            latest_message="Completed already.",
            verdict="PASS",
            failure_reason=None,
        )
    )

    assert (
        claim_active_evaluation_attempt(
            run_id="evalrun_terminal_only",
            worker_id="worker-b",
            reason_message="Claim terminal run.",
        )
        is None
    )
    assert (
        abandon_active_evaluation_attempt(
            run_id="evalrun_terminal_only",
            reason_message="Abandon terminal run.",
            failure_reason="NOT_ACTIVE",
        )
        is None
    )
    assert (
        fail_active_evaluation_attempt(
            run_id="evalrun_terminal_only",
            reason_message="Fail terminal run.",
            failure_reason="NOT_ACTIVE",
        )
        is None
    )
