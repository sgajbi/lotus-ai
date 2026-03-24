from fastapi.testclient import TestClient

from app.config import settings


def test_platform_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert "deployment_split" in body
    assert "production_baseline" in body
    assert "production_baseline_governance" in body


def test_deployment_split_runtime_status_route(client: TestClient) -> None:
    settings.deployment_split_stage = "unified"
    response = client.get("/platform/deployment-split/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["configured_stage"] == "UNIFIED"
    assert body["effective_stage"] == "UNIFIED"
    assert body["plane_count"] == 3
    assert body["route_count"] == 4
    assert any(route["route_id"] == "retrieval_search_execution" for route in body["routes"])
    assert any(plane["plane_id"] == "runtime" for plane in body["planes"])


def test_deployment_split_governance_routes(client: TestClient) -> None:
    activation_response = client.get("/platform/deployment-split/activation-readiness")
    runbook_response = client.get("/platform/deployment-split/runbook-readiness")
    governance_response = client.get("/platform/deployment-split/governance-status")

    assert activation_response.status_code == 200
    assert runbook_response.status_code == 200
    assert governance_response.status_code == 200

    activation_body = activation_response.json()
    runbook_body = runbook_response.json()
    governance_body = governance_response.json()

    assert activation_body["service"] == "lotus-ai"
    assert "activation_ready" in activation_body
    assert runbook_body["runbook_ready"] is True
    assert runbook_body["required_item_count"] >= 1
    assert governance_body["runtime_status"]["service"] == "lotus-ai"
    assert "activation_readiness" in governance_body
    assert "runbook_readiness" in governance_body


def test_production_baseline_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/production-baseline/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["posture"] == "LOCAL_OR_DEMO_CAPABLE"
    assert body["production_ready"] is False
    assert body["dependency_count"] >= 6
    assert any(
        dependency["dependency_id"] == "database_backend" for dependency in body["dependencies"]
    )


def test_production_baseline_governance_routes(client: TestClient) -> None:
    activation_response = client.get("/platform/production-baseline/activation-readiness")
    runbook_response = client.get("/platform/production-baseline/runbook-readiness")
    governance_response = client.get("/platform/production-baseline/governance-status")

    assert activation_response.status_code == 200
    assert runbook_response.status_code == 200
    assert governance_response.status_code == 200

    activation_body = activation_response.json()
    runbook_body = runbook_response.json()
    governance_body = governance_response.json()

    assert activation_body["service"] == "lotus-ai"
    assert "activation_ready" in activation_body
    assert runbook_body["runbook_ready"] is True
    assert runbook_body["required_item_count"] >= 1
    assert governance_body["runtime_status"]["service"] == "lotus-ai"
    assert "activation_readiness" in governance_body
    assert "runbook_readiness" in governance_body
