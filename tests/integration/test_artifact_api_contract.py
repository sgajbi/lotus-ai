from fastapi.testclient import TestClient

from app.config import settings
from app.services.artifact_store import reset_artifact_store_cache


def test_artifact_runtime_status_route(client: TestClient) -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.artifact_object_store_root = None
    reset_artifact_store_cache()

    response = client.get("/platform/artifacts/runtime-status")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "lotus-ai"
    assert body["metadata_store_mode"] == "memory"
    assert body["object_store_mode"] == "memory"
    assert body["metadata_store"]["status"] == "READY"
    assert body["object_store"]["status"] == "READY"
    assert "evaluation" in body["supported_domains"]
