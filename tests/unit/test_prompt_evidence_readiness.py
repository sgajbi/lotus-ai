from app.services.prompt_evidence_readiness import build_prompt_evidence_readiness


def test_prompt_evidence_readiness_reports_foundation_evidence_gaps() -> None:
    readiness = build_prompt_evidence_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.evidence_ready is False
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 0
    assert readiness.items[0].evidence_id == "prompt_fixture_coverage_pack"
    assert readiness.items[1].status == "NOT_READY"
