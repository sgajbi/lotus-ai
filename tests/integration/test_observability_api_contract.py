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
    assert any(item["evidence_id"] == "safety_audit_evidence_pack" for item in body["incident_evidence_items"])
