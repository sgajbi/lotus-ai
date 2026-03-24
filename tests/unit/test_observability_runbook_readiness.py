from app.services.observability_runbook_readiness import build_observability_runbook_readiness


def test_observability_runbook_readiness_reports_required_items_complete() -> None:
    readiness = build_observability_runbook_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.runbook_ready is True
    assert readiness.required_item_count == 3
    assert readiness.completed_required_item_count == 3
    assert readiness.items[0].runbook_id == "observability_operational_review"
    assert readiness.items[1].status == "READY"
    assert readiness.items[3].required_for_activation is False
