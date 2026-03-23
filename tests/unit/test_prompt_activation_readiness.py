from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.prompt_activation_readiness import build_prompt_activation_readiness


def test_prompt_activation_readiness_reports_foundation_blockers() -> None:
    readiness = build_prompt_activation_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.prompt_store_mode == "memory"
    assert readiness.management_mode == "SEEDED_MEMORY"
    assert readiness.activation_ready is False
    assert len(readiness.blocking_findings) == 4
    assert "Runtime-backed prompt approval evidence" in readiness.blocking_findings[0]
    assert len(readiness.activation_path) == 4


def test_prompt_activation_readiness_remains_blocked_even_after_prompt_eval_pass() -> None:
    for fixture_id in ("prompt_promotion_examples", "prompt_rollback_examples"):
        submit_evaluation_run(
            EvaluationRunSubmissionRequest(
                fixture_id=fixture_id,
                caller_app="lotus-platform",
                correlation_id=f"corr-{fixture_id}",
                triggered_by="operator-a",
            )
        )
        run_next_evaluation_execution_job(worker_id="worker-a")

    readiness = build_prompt_activation_readiness()

    assert readiness.activation_ready is False
    assert len(readiness.blocking_findings) == 3
