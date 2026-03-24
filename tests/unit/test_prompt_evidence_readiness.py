from app.contracts.evals import EvaluationApprovalEvidenceState
from app.repositories.evaluation_runtime_repository import EvaluationRunRecord
from app.services.evaluation_runtime_store import get_evaluation_runtime_store
from app.services.prompt_evidence_readiness import (
    _approval_gate_status,
    build_prompt_evidence_readiness,
)


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
        get_evaluation_runtime_store().save_run(
            EvaluationRunRecord(
                run_id=f"runtime_prompt_evidence_{fixture_id}",
                fixture_id=fixture_id,
                manifest_version="foundation.v1",
                lifecycle_status="COMPLETED",
                triggered_by="operator-a",
                submitted_at="2026-03-24T09:00:00Z",
                async_job_id=f"async_prompt_evidence_{fixture_id}",
                latest_message="Prompt rollout approval fixture passed.",
                verdict="PASS",
                case_count=1,
            )
        )

    readiness = build_prompt_evidence_readiness()

    assert readiness.evidence_ready is True
    assert readiness.completed_required_item_count == 4
    assert readiness.items[1].status == "READY"
    assert readiness.items[3].status == "READY"
    assert readiness.approval_gate.evidence_state.value == "RUNTIME_PASS"


def test_prompt_evidence_readiness_maps_all_runtime_approval_states() -> None:
    assert (
        _approval_gate_status(EvaluationApprovalEvidenceState.RUNTIME_IN_PROGRESS) == "IN_PROGRESS"
    )
    assert _approval_gate_status(EvaluationApprovalEvidenceState.RUNTIME_PARTIAL) == "PARTIAL"
    assert _approval_gate_status(EvaluationApprovalEvidenceState.RUNTIME_FAIL) == "FAILED"
    assert _approval_gate_status(EvaluationApprovalEvidenceState.RUNTIME_STALE) == "STALE"
    assert _approval_gate_status(EvaluationApprovalEvidenceState.STAGED_ONLY) == "FOUNDATION_STAGED"
    assert _approval_gate_status(EvaluationApprovalEvidenceState.NO_EVIDENCE) == "NOT_READY"
