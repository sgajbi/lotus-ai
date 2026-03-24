from fastapi.testclient import TestClient


def test_production_go_live_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/production-go-live/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["platform_state"] == "TECHNICALLY_RUNNING"
    assert body["use_case_state"] == "PRE_PROD_VALIDATION"
    assert body["technically_running"] is True
    assert body["production_capable"] is False
    assert body["platform_production_approved"] is False
    assert body["use_case_production_approved"] is False
    assert any(
        domain["domain_id"] == "managed_secret_posture" for domain in body["approval_domains"]
    )
    assert any(
        domain["domain_id"] == "managed_object_storage" for domain in body["approval_domains"]
    )
    assert any(
        domain["domain_id"] == "managed_object_storage"
        and domain["review_surface"] == "/platform/artifacts/governance-status"
        for domain in body["approval_domains"]
    )
    assert body["provider_freeze_state"] == "NOT_APPLICABLE"
    assert body["provider_rollback_state"] == "NOT_APPLICABLE"


def test_production_go_live_governance_routes(client: TestClient) -> None:
    activation_response = client.get("/platform/production-go-live/activation-readiness")
    use_case_response = client.get("/platform/production-go-live/use-case-approval")
    runbook_response = client.get("/platform/production-go-live/runbook-readiness")
    governance_response = client.get("/platform/production-go-live/governance-status")

    assert activation_response.status_code == 200
    assert use_case_response.status_code == 200
    assert runbook_response.status_code == 200
    assert governance_response.status_code == 200

    assert "runtime_status" in activation_response.json()
    assert "approval_state" in use_case_response.json()
    assert "items" in runbook_response.json()
    assert "go_live_checklist" in runbook_response.json()
    assert "activation_readiness" in governance_response.json()
    assert "use_case_approval" in governance_response.json()
    assert governance_response.json()["go_live_decision"] == "BLOCKED"
