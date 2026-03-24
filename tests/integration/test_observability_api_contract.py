from fastapi.testclient import TestClient


def test_observability_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/observability/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["domain_count"] == 6
    assert body["unavailable_domain_count"] == 0
    assert body["incident_evidence_supported_domain_count"] >= 1
    assert any(domain["domain_id"] == "provider" for domain in body["domains"])
    assert any(domain["domain_id"] == "safety" for domain in body["domains"])
    assert any(
        item["evidence_id"] == "safety_runtime_enforcement_state"
        for item in body["incident_evidence_items"]
    )


def test_observability_incident_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/incident-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["domain_count"] == 6
    assert any(summary["domain_id"] == "provider" for summary in body["summaries"])
    assert any(summary["domain_id"] == "retrieval" for summary in body["summaries"])
    assert any(summary["domain_id"] == "async" for summary in body["summaries"])
    assert any(summary["domain_id"] == "evaluation" for summary in body["summaries"])
    assert any(summary["domain_id"] == "prompt" for summary in body["summaries"])
    assert any(summary["domain_id"] == "safety" for summary in body["summaries"])


def test_provider_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/provider-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "provider"
    assert body["telemetry"]["incident_evidence_supported"] is True
    assert body["incident_evidence_items"][0]["evidence_id"] == "provider_operations_incident_state"


def test_evaluation_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/evaluation-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "evaluation"
    assert body["incident_evidence_items"][0]["evidence_id"] == "evaluation_approval_gate_state"


def test_prompt_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/prompt-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "prompt"
    assert body["incident_evidence_items"][0]["evidence_id"] == "prompt_rollout_approval_state"


def test_safety_observability_summary_route(client: TestClient) -> None:
    response = client.get("/platform/observability/safety-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["domain_id"] == "safety"
    assert body["incident_evidence_items"][0]["evidence_id"] == "safety_runtime_enforcement_state"
