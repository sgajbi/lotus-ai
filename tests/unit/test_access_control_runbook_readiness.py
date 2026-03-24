from app.services.access_control_runbook_readiness import build_access_control_runbook_readiness


def test_access_control_runbook_readiness_reports_required_items_ready() -> None:
    status = build_access_control_runbook_readiness()

    assert status.runbook_ready is True
    assert status.required_item_count == 5
    assert status.completed_required_item_count == 5
    assert status.items[0].runbook_id == "caller_onboarding_procedure"
