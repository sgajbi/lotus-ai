from app.services.prompt_governance_status import build_prompt_governance_status_summary


def test_prompt_governance_status_reports_blocked_foundation_posture() -> None:
    status = build_prompt_governance_status_summary()

    assert status.service == "lotus-ai"
    assert status.governance_ready is False
    assert status.blocking_area_count == 3
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is False
    assert status.evidence_readiness.evidence_ready is False
    assert len(status.governance_summary) == 3
    assert status.evidence_readiness.approval_gate.domain_id == "prompt_rollout"
