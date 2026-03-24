from app.services.async_runbook_readiness_service import build_async_runbook_readiness


def test_async_runbook_readiness_reports_operational_gaps() -> None:
    readiness = build_async_runbook_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.runbook_ready is False
    assert readiness.required_item_count == 4
    assert readiness.completed_required_item_count == 0
    assert readiness.items[0].runbook_id == "async_operational_runbook"
    assert readiness.items[0].status == "PARTIALLY_COMPLETE"
    assert readiness.items[2].status == "PARTIALLY_COMPLETE"
    assert readiness.items[1].status == "NOT_READY"
