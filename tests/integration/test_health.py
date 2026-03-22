from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoints() -> None:
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200


def test_correlation_header_propagation() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Correlation-Id": "corr-123"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-123"


def test_platform_capabilities_contract() -> None:
    client = TestClient(app)
    response = client.get("/platform/capabilities")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["phase"] == "foundation"
    assert any(task["task_id"] == "explain.v1" for task in body["tasks"])
