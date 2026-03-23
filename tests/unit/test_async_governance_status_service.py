from app.services.async_governance_status_service import build_async_governance_status


def test_async_governance_status_reports_blocked_foundation_posture() -> None:
    status = build_async_governance_status()

    assert status.service == "lotus-ai"
    assert status.governance_ready is False
    assert status.blocking_area_count == 2
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is False
    assert len(status.governance_summary) == 2
    assert "evaluation execution are active" in status.governance_summary[0]
