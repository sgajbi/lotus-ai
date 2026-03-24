from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.repositories.artifact_repository import ArtifactRecord
from app.repositories.memory_artifact_repository import InMemoryArtifactRepository


def test_memory_artifact_repository_round_trips_records_in_created_order() -> None:
    repository = InMemoryArtifactRepository()
    older = ArtifactRecord(
        artifact_id="artifact-older",
        domain="evaluation",
        artifact_type="case_bundle",
        source_object_kind="evaluation_run",
        source_object_id="run-1",
        lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
        retention_posture="active",
        media_type="application/json",
        byte_size=120,
        checksum_sha256="a" * 64,
        storage_backend=ArtifactStorageBackend.MEMORY,
        storage_reference="memory://evaluation/run-1/case-bundle.json",
        lineage_parent_artifact_id=None,
        superseded_by_artifact_id=None,
        created_at="2026-03-24T09:00:00Z",
        created_by="worker",
    )
    newer = ArtifactRecord(
        artifact_id="artifact-newer",
        domain="async",
        artifact_type="job_output",
        source_object_kind="async_job",
        source_object_id="job-2",
        lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
        retention_posture="active",
        media_type="application/json",
        byte_size=200,
        checksum_sha256="b" * 64,
        storage_backend=ArtifactStorageBackend.MEMORY,
        storage_reference="memory://async/job-2/output.json",
        lineage_parent_artifact_id=None,
        superseded_by_artifact_id=None,
        created_at="2026-03-24T10:00:00Z",
        created_by="worker",
    )

    repository.save_artifact(newer)
    repository.save_artifact(older)

    assert [record.artifact_id for record in repository.list_artifacts()] == [
        "artifact-older",
        "artifact-newer",
    ]
    assert repository.get_artifact(artifact_id="artifact-older") == older
