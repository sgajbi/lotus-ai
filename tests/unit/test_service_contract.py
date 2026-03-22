from fastapi.testclient import TestClient

from app.main import SERVICE_NAME, app


def test_service_name_is_lotus_prefixed() -> None:
    assert SERVICE_NAME.startswith("lotus-")


def test_root_contract_includes_delivery_phase() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["phase"] == "foundation"
