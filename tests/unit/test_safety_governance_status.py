from app.services.safety_governance_status import build_safety_governance_status


def test_safety_governance_status_reports_blocked_foundation_posture() -> None:
    status = build_safety_governance_status()

    assert status.governance_ready is False
    # Issue #150 slice 2: active redaction removes one blocking area.
    assert status.blocking_area_count == 2
    assert status.runtime_status.runtime_redaction_active is True
    assert status.runbook_readiness.runbook_ready is False
    assert status.evidence_readiness.evidence_ready is False
    assert status.evidence_readiness.approval_gate.domain_id == "safety_enforcement"
