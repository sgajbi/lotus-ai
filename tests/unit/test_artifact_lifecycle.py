import pytest
from fastapi import HTTPException

from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.repositories.artifact_repository import ArtifactRecord
from app.services.artifact_lifecycle import archive_artifact
from app.services.artifact_store import get_artifact_repository


def test_archive_artifact_marks_lifecycle_and_retention_posture() -> None:
    repository = get_artifact_repository()
    repository.save_artifact(
        ArtifactRecord(
            artifact_id="artifact-archive-001",
            domain="async",
            artifact_type="job_terminal_output",
            source_object_kind="async_job",
            source_object_id="async-job-001",
            lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
            retention_posture="active",
            media_type="application/json",
            byte_size=10,
            checksum_sha256="c" * 64,
            storage_backend=ArtifactStorageBackend.MEMORY,
            storage_reference="memory://async/async-job-001.json",
            lineage_parent_artifact_id=None,
            superseded_by_artifact_id=None,
            created_at="2026-03-24T11:00:00Z",
            created_by="worker",
        )
    )

    archived = archive_artifact(artifact_id="artifact-archive-001")

    assert archived.lifecycle_status == ArtifactLifecycleStatus.ARCHIVED
    assert archived.retention_posture == "archived"
    assert repository.get_artifact(artifact_id="artifact-archive-001") == archived


def test_archive_artifact_raises_for_unknown_artifact() -> None:
    with pytest.raises(HTTPException) as exc_info:
        archive_artifact(artifact_id="missing-artifact")

    assert exc_info.value.status_code == 404
