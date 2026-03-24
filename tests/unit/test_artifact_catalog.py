from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.repositories.artifact_repository import ArtifactRecord
from app.services.artifact_catalog import build_artifact_catalog
from app.services.artifact_store import get_artifact_repository


def test_artifact_catalog_summarizes_lifecycle_counts_and_filters_domain() -> None:
    repository = get_artifact_repository()
    repository.save_artifact(
        ArtifactRecord(
            artifact_id="artifact-eval-001",
            domain="evaluation",
            artifact_type="case_bundle",
            source_object_kind="evaluation_case_result",
            source_object_id="evalcase_001",
            lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
            retention_posture="active",
            media_type="application/json",
            byte_size=10,
            checksum_sha256="a" * 64,
            storage_backend=ArtifactStorageBackend.MEMORY,
            storage_reference="memory://evaluation/evalcase_001.json",
            lineage_parent_artifact_id=None,
            superseded_by_artifact_id=None,
            created_at="2026-03-24T10:00:00Z",
            created_by="worker",
        )
    )
    repository.save_artifact(
        ArtifactRecord(
            artifact_id="artifact-obs-001",
            domain="observability",
            artifact_type="incident_bundle",
            source_object_kind="observability_domain_summary",
            source_object_id="provider",
            lifecycle_status=ArtifactLifecycleStatus.SUPERSEDED,
            retention_posture="retained_for_review",
            media_type="application/json",
            byte_size=20,
            checksum_sha256="b" * 64,
            storage_backend=ArtifactStorageBackend.MEMORY,
            storage_reference="memory://observability/provider.json",
            lineage_parent_artifact_id=None,
            superseded_by_artifact_id="artifact-obs-002",
            created_at="2026-03-24T10:01:00Z",
            created_by="observability_runtime",
        )
    )

    catalog = build_artifact_catalog(limit=50, domain="evaluation")

    assert catalog.artifact_count == 1
    assert catalog.active_count == 1
    assert catalog.superseded_count == 0
    assert catalog.archived_count == 0
    assert catalog.historical_staged_count == 0
    assert catalog.artifacts[0].artifact_id == "artifact-eval-001"
