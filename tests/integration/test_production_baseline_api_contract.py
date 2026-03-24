from fastapi.testclient import TestClient


def test_production_baseline_runtime_status_route(client: TestClient) -> None:
    response = client.get("/platform/production-baseline/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["posture"] == "LOCAL_OR_DEMO_CAPABLE"
    assert body["production_ready"] is False
    assert body["dependency_count"] >= 6
    assert any(
        dependency["dependency_id"] == "database_backend"
        for dependency in body["dependencies"]
    )
