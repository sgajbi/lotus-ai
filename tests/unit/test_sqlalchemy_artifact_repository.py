from pathlib import Path

from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.repositories.artifact_repository import ArtifactRecord
from app.repositories.sqlalchemy_artifact_repository import SqlAlchemyArtifactRepository
from tests.support.migration_runner import upgrade_database_to_head


def test_sqlalchemy_artifact_repository_round_trips_metadata(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'lotus-ai-artifacts.db'}"
    upgrade_database_to_head(database_url)
    repository = SqlAlchemyArtifactRepository(database_url)
    record = ArtifactRecord(
        artifact_id="artifact-runtime-001",
        domain="observability",
        artifact_type="incident_bundle",
        source_object_kind="incident_review",
        source_object_id="incident-42",
        lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
        retention_posture="retained_for_review",
        media_type="application/json",
        byte_size=512,
        checksum_sha256="c" * 64,
        storage_backend=ArtifactStorageBackend.FILESYSTEM,
        storage_reference="filesystem://observability/incident-42.json",
        lineage_parent_artifact_id=None,
        superseded_by_artifact_id=None,
        created_at="2026-03-24T11:00:00Z",
        created_by="operator",
    )

    repository.save_artifact(record)

    assert repository.get_artifact(artifact_id=record.artifact_id) == record
    assert repository.list_artifacts() == [record]
