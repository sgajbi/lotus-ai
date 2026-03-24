from app.services.retrieval_governance_status import build_retrieval_governance_status


def test_retrieval_governance_status_reports_blocked_foundation_posture() -> None:
    status = build_retrieval_governance_status()

    assert status.service == "lotus-ai"
    assert status.governance_ready is False
    assert status.blocking_area_count == 3
    assert status.activation_readiness.activation_ready is False
    assert status.runbook_readiness.runbook_ready is False
    assert status.evidence_readiness.evidence_ready is False
    assert status.corpus_change_review_ready is False
    assert len(status.governance_summary) == 3
    assert "runtime-backed approval gate summary" in status.governance_summary[2]
