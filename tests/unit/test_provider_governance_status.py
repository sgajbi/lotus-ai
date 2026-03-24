from app.services.provider_governance_status import build_provider_governance_status


def test_provider_governance_status_reports_blocked_foundation_posture() -> None:
    status = build_provider_governance_status()

    assert status.service == "lotus-ai"
    assert status.governance_ready is False
    assert status.blocking_area_count == 3
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is False
    assert status.evidence_readiness.evidence_ready is False
    assert status.expansion_policy.bounded_expansion_enabled is True
    assert status.expansion_policy.expansion_blocked is False
    assert len(status.governance_summary) == 3
    assert "runtime-backed approval gate summary" in status.governance_summary[2]
