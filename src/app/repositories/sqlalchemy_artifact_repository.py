from __future__ import annotations

from collections.abc import Sequence

from pathlib import Path

from sqlalchemy import delete, select

from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend
from app.db.models import ArtifactMetadataModel
from app.repositories.artifact_repository import ArtifactRecord, ArtifactRepository
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyArtifactRepository(SqlAlchemyRepositoryBase, ArtifactRepository):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_artifacts(self) -> list[ArtifactRecord]:
        with self._session_factory() as session:
            models = session.scalars(
                select(ArtifactMetadataModel).order_by(ArtifactMetadataModel.created_at)
            ).all()
            return [self._to_record(model) for model in models]

    def get_artifact(self, *, artifact_id: str) -> ArtifactRecord | None:
        with self._session_factory() as session:
            model = session.get(ArtifactMetadataModel, artifact_id)
            if model is None:
                return None
            return self._to_record(model)

    def delete_artifacts(self, artifact_ids: Sequence[str]) -> int:
        if not artifact_ids:
            return 0
        with self._session_factory() as session:
            result = session.execute(
                delete(ArtifactMetadataModel).where(
                    ArtifactMetadataModel.artifact_id.in_(list(artifact_ids))
                )
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def save_artifact(self, record: ArtifactRecord) -> None:
        model = ArtifactMetadataModel(
            artifact_id=record.artifact_id,
            domain=record.domain,
            artifact_type=record.artifact_type,
            source_object_kind=record.source_object_kind,
            source_object_id=record.source_object_id,
            lifecycle_status=record.lifecycle_status.value,
            retention_posture=record.retention_posture,
            media_type=record.media_type,
            byte_size=record.byte_size,
            checksum_sha256=record.checksum_sha256,
            storage_backend=record.storage_backend.value,
            storage_reference=record.storage_reference,
            lineage_parent_artifact_id=record.lineage_parent_artifact_id,
            superseded_by_artifact_id=record.superseded_by_artifact_id,
            created_at=record.created_at,
            created_by=record.created_by,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def _to_record(self, model: ArtifactMetadataModel) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=model.artifact_id,
            domain=model.domain,
            artifact_type=model.artifact_type,
            source_object_kind=model.source_object_kind,
            source_object_id=model.source_object_id,
            lifecycle_status=ArtifactLifecycleStatus(model.lifecycle_status),
            retention_posture=model.retention_posture,
            media_type=model.media_type,
            byte_size=model.byte_size,
            checksum_sha256=model.checksum_sha256,
            storage_backend=ArtifactStorageBackend(model.storage_backend),
            storage_reference=model.storage_reference,
            lineage_parent_artifact_id=model.lineage_parent_artifact_id,
            superseded_by_artifact_id=model.superseded_by_artifact_id,
            created_at=model.created_at,
            created_by=model.created_by,
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        prefix = "sqlite:///"
        if not self._database_url.startswith(prefix):
            return
        db_path = self._database_url.removeprefix(prefix)
        if db_path == ":memory:":
            return
        path = Path(db_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
