from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run
from app.services.prompt_evidence_readiness import build_prompt_evidence_readiness


def test_prompt_evidence_readiness_reports_foundation_evidence_gaps() -> None:
    readiness = build_prompt_evidence_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.evidence_ready is False
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 2
    assert readiness.items[0].evidence_id == "prompt_fixture_coverage_pack"
    assert readiness.items[1].status == "FOUNDATION_STAGED"
    assert readiness.approval_gate.domain_id == "prompt_rollout"
    assert readiness.approval_gate.evidence_state.value == "STAGED_ONLY"


def test_prompt_evidence_readiness_reports_runtime_pass_when_prompt_fixtures_pass() -> None:
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

    readiness = build_prompt_evidence_readiness()

    assert readiness.evidence_ready is True
    assert readiness.completed_required_item_count == 4
    assert readiness.items[1].status == "READY"
    assert readiness.items[3].status == "READY"
    assert readiness.approval_gate.evidence_state.value == "RUNTIME_PASS"
