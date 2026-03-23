from app.services.safety_runbook_readiness import build_safety_runbook_readiness


def test_safety_runbook_readiness_reports_operational_gaps() -> None:
    readiness = build_safety_runbook_readiness()

    assert readiness.runbook_ready is False
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 3
    assert readiness.items[0].status == "READY"
    assert readiness.items[1].status == "READY"
    assert readiness.items[2].status == "READY"
    assert readiness.items[3].status == "FOUNDATION_DOCUMENTED"
