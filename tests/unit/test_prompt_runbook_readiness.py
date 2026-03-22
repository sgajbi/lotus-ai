from app.services.prompt_runbook_readiness import build_prompt_runbook_readiness


def test_prompt_runbook_readiness_reports_foundation_operational_gaps() -> None:
    readiness = build_prompt_runbook_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.runbook_ready is False
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 0
    assert readiness.items[0].runbook_id == "prompt_operational_runbook"
    assert readiness.items[1].status == "NOT_READY"
