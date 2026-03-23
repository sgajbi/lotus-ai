from app.services.retrieval_evidence_readiness import build_retrieval_evidence_readiness
from app.contracts.evals import EvaluationRunSubmissionRequest
from app.services.eval_async_execution import run_next_evaluation_execution_job
from app.services.eval_run_submission_service import submit_evaluation_run


def test_retrieval_evidence_readiness_reports_foundation_evidence_gaps() -> None:
    readiness = build_retrieval_evidence_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.evidence_ready is False
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 0
    assert readiness.items[0].evidence_id == "retrieval_fixture_coverage_pack"
    assert readiness.items[1].status == "NOT_READY"
    assert readiness.approval_gate.domain_id == "retrieval_execution"
    assert readiness.approval_gate.evidence_state.value == "STAGED_ONLY"


def test_retrieval_evidence_readiness_prefers_runtime_backed_live_evidence() -> None:
    submit_evaluation_run(
        EvaluationRunSubmissionRequest(
            fixture_id="retrieval_citation_examples",
            caller_app="lotus-platform",
            correlation_id="corr-ret-evidence-001",
            triggered_by="operator-a",
        )
    )
    run_next_evaluation_execution_job(worker_id="worker-a")

    readiness = build_retrieval_evidence_readiness()

    assert readiness.approval_gate.evidence_state.value == "RUNTIME_PASS"
    assert readiness.items[0].status == "READY"
    assert readiness.items[1].status == "READY"
    assert readiness.items[2].status == "READY"
