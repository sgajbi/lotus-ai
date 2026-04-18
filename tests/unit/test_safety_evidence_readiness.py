from _pytest.monkeypatch import MonkeyPatch

from app.contracts.evals import (
    EvaluationApprovalEvidenceState,
    EvaluationApprovalGateSummaryDescriptor,
)
from app.services.safety_evidence_readiness import build_safety_evidence_readiness


def test_safety_evidence_readiness_reports_staged_only_until_runtime_runs_exist() -> None:
    readiness = build_safety_evidence_readiness()

    assert readiness.evidence_ready is False
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 3
    assert readiness.approval_gate.domain_id == "safety_enforcement"
    assert readiness.approval_gate.evidence_state.value == "STAGED_ONLY"
    assert readiness.items[0].status == "READY"
    assert readiness.items[1].status == "READY"
    assert readiness.items[2].status == "FOUNDATION_STAGED"
    assert readiness.items[3].status == "READY"


def test_safety_evidence_readiness_reports_runtime_failure_state(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.safety_evidence_readiness.build_safety_approval_gate_summary",
        lambda: EvaluationApprovalGateSummaryDescriptor(
            domain_id="safety_enforcement",
            domain_label="Safety enforcement",
            approval_ready=False,
            evidence_state=EvaluationApprovalEvidenceState.RUNTIME_FAIL,
            required_fixture_count=2,
            runtime_backed_fixture_count=2,
            latest_runtime_run_id="eval_safety_fail",
            latest_runtime_recorded_at="2026-04-18T00:00:00Z",
            latest_historical_baseline_run_id="hist_safety",
            fixture_summaries=[],
            notes=["runtime fail"],
        ),
    )

    readiness = build_safety_evidence_readiness()

    assert readiness.evidence_ready is False
    assert readiness.items[2].status == "FAILED"
    assert "failing result" in readiness.items[2].notes


def test_safety_evidence_readiness_reports_not_ready_when_no_runtime_evidence_exists(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.safety_evidence_readiness.build_safety_approval_gate_summary",
        lambda: EvaluationApprovalGateSummaryDescriptor(
            domain_id="safety_enforcement",
            domain_label="Safety enforcement",
            approval_ready=False,
            evidence_state=EvaluationApprovalEvidenceState.NO_EVIDENCE,
            required_fixture_count=2,
            runtime_backed_fixture_count=0,
            latest_runtime_run_id=None,
            latest_runtime_recorded_at=None,
            latest_historical_baseline_run_id="hist_safety",
            fixture_summaries=[],
            notes=["no evidence"],
        ),
    )

    readiness = build_safety_evidence_readiness()

    assert readiness.evidence_ready is False
    assert readiness.items[2].status == "NOT_READY"
    assert "No runtime-backed safety evidence" in readiness.items[2].notes
