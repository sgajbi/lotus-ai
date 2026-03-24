from fastapi.testclient import TestClient

from app.config import settings
from app.services.artifact_store import get_artifact_repository, reset_artifact_store_cache
from app.repositories.artifact_repository import ArtifactRecord
from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend


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


def test_artifact_catalog_and_governance_routes(client: TestClient) -> None:
    repository = get_artifact_repository()
    repository.save_artifact(
        ArtifactRecord(
            artifact_id="artifact-api-001",
            domain="observability",
            artifact_type="incident_bundle",
            source_object_kind="observability_domain_summary",
            source_object_id="provider",
            lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
            retention_posture="retained_for_review",
            media_type="application/json",
            byte_size=12,
            checksum_sha256="d" * 64,
            storage_backend=ArtifactStorageBackend.MEMORY,
            storage_reference="memory://observability/provider.json",
            lineage_parent_artifact_id=None,
            superseded_by_artifact_id=None,
            created_at="2026-03-24T12:00:00Z",
            created_by="observability_runtime",
        )
    )

    catalog_response = client.get("/platform/artifacts", params={"domain": "observability"})
    assert catalog_response.status_code == 200
    catalog_body = catalog_response.json()
    assert catalog_body["artifact_count"] == 1
    assert catalog_body["active_count"] == 1
    assert catalog_body["artifacts"][0]["artifact_id"] == "artifact-api-001"

    activation_response = client.get("/platform/artifacts/activation-readiness")
    assert activation_response.status_code == 200
    assert activation_response.json()["activation_ready"] is False

    runbook_response = client.get("/platform/artifacts/runbook-readiness")
    assert runbook_response.status_code == 200
    assert runbook_response.json()["runbook_ready"] is True

    governance_response = client.get("/platform/artifacts/governance-status")
    assert governance_response.status_code == 200
    governance_body = governance_response.json()
    assert governance_body["governance_ready"] is False
    assert governance_body["runtime_status"]["artifact_count"] >= 1
