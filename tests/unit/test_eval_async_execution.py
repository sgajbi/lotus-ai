from pathlib import Path

from app.config import settings
from app.contracts.async_runtime import AsyncControlActionRequest, AsyncControlActionType
from app.contracts.async_runtime import AsyncJobSubmissionRequest
from app.services.async_job_service import build_async_job_detail
from app.services.async_runtime_control import apply_async_control_action
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_service import build_evaluation_run_detail
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.async_submission_service import submit_async_job
from app.services.async_runtime_store import reset_async_runtime_store_cache
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.evaluation_runtime_store import reset_evaluation_runtime_store_cache
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
