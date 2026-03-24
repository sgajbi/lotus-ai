from app.services.provider_runbook_readiness import build_provider_runbook_readiness


def test_provider_runbook_readiness_reports_operational_gaps() -> None:
    readiness = build_provider_runbook_readiness()

    assert readiness.service == "lotus-ai"
    assert readiness.runbook_ready is False
    assert readiness.required_item_count == 7
    assert readiness.completed_required_item_count == 1
    assert readiness.items[0].runbook_id == "provider_operational_runbook"
    assert readiness.items[1].status == "NOT_READY"
    assert readiness.items[3].runbook_id == "provider_spend_anomaly_response"
    assert readiness.items[5].runbook_id == "provider_degradation_and_circuit_response"
    assert readiness.items[6].status == "READY"
