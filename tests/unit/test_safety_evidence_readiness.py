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
