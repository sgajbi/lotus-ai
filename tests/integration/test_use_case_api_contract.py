from fastapi.testclient import TestClient


def test_first_production_use_case_route(client: TestClient) -> None:
    response = client.get("/platform/use-cases/first-production-use-case")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["use_case_id"] == "lotus_performance.analytics_commentary.v1"
    assert body["downstream_app"] == "lotus-performance"
    assert body["task_id"] == "explain.v1"
    assert body["output_label"] == "EXPLANATION_ONLY"
    assert body["contract_hardened"] is True
    assert any(
        field["field_name"] == "metric_deltas" for field in body["downstream_contract_fields"]
    )
