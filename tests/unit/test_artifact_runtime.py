from pathlib import Path

from app.config import settings
from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.repositories.artifact_repository import ArtifactRecord
from app.services.artifact_runtime import build_artifact_runtime_status
from app.services.artifact_store import get_artifact_repository, reset_artifact_store_cache
from tests.support.migration_runner import upgrade_database_to_head


def test_artifact_runtime_status_reports_memory_foundation_posture() -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "memory"
    settings.artifact_object_store_root = None
    reset_artifact_store_cache()

    status = build_artifact_runtime_status()

    assert status.metadata_store_mode == "memory"
    assert status.object_store_mode == "memory"
    assert status.metadata_store.status.value == "READY"
    assert status.object_store.durable is False
    assert status.artifact_count == 0
    assert "evaluation" in status.supported_domains
    assert "Evaluation, async, and observability" in status.status_summary[1]


def test_artifact_runtime_status_reports_sql_and_filesystem_posture(tmp_path: Path) -> None:
    settings.artifact_store_mode = "sqlalchemy"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = str(tmp_path / "artifact-objects")
    settings.database_url = f"sqlite:///{tmp_path / 'lotus-ai-artifact-runtime.db'}"
    upgrade_database_to_head(settings.database_url)
    reset_artifact_store_cache()

    get_artifact_repository().save_artifact(
        ArtifactRecord(
            artifact_id="artifact-001",
            domain="evaluation",
            artifact_type="case_bundle",
            source_object_kind="evaluation_run",
            source_object_id="run-abc",
            lifecycle_status=ArtifactLifecycleStatus.RUNTIME_GENERATED,
            retention_posture="active",
            media_type="application/json",
            byte_size=10,
            checksum_sha256="d" * 64,
            storage_backend=ArtifactStorageBackend.FILESYSTEM,
            storage_reference="filesystem://evaluation/run-abc/case-bundle.json",
            lineage_parent_artifact_id=None,
            superseded_by_artifact_id=None,
            created_at="2026-03-24T12:00:00Z",
            created_by="worker",
        )
    )

    status = build_artifact_runtime_status()

    assert status.metadata_store.status.value == "READY"
    assert status.object_store.status.value == "READY"
    assert status.object_store.durable is True
    assert status.artifact_count == 1


def test_artifact_runtime_status_reports_filesystem_configuration_required() -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "filesystem"
    settings.artifact_object_store_root = None
    reset_artifact_store_cache()

    status = build_artifact_runtime_status()

    assert status.metadata_store.status is RuntimeReadinessStatus.READY
    assert status.object_store.status is RuntimeReadinessStatus.CONFIGURATION_REQUIRED
    assert status.object_store.root_configured is False
    assert status.artifact_count == 0


def test_artifact_runtime_status_reports_unsupported_object_store_mode() -> None:
    settings.artifact_store_mode = "memory"
    settings.artifact_object_store_mode = "s3"
    settings.artifact_object_store_root = None
    reset_artifact_store_cache()

    status = build_artifact_runtime_status()

    assert status.object_store.status is RuntimeReadinessStatus.UNAVAILABLE
    assert status.object_store.durable is False
    assert "not supported" in status.object_store.detail
