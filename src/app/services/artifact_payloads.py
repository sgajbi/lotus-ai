from __future__ import annotations

from uuid import uuid4

from app.config import settings
from app.contracts.artifacts import (
    ArtifactDescriptor,
    ArtifactLifecycleStatus,
    ArtifactStorageBackend,
)
from app.repositories.artifact_repository import ArtifactRecord
from app.services.artifact_object_store import StoredArtifactObject
from app.services.artifact_store import get_artifact_object_store, get_artifact_repository


def persist_json_artifact(
    *,
    domain: str,
    artifact_type: str,
    source_object_kind: str,
    source_object_id: str,
    created_at: str,
    created_by: str,
    payload_json: bytes,
    lifecycle_status: ArtifactLifecycleStatus = ArtifactLifecycleStatus.RUNTIME_GENERATED,
    retention_posture: str = "active",
    lineage_parent_artifact_id: str | None = None,
    superseded_by_artifact_id: str | None = None,
) -> ArtifactDescriptor:
    artifact_id = f"artifact_{domain}_{uuid4().hex[:16]}"
    object_key = (
        f"{domain}/{source_object_kind}/{source_object_id}/{artifact_id}.json"
    )
    stored_object = get_artifact_object_store().put_object(
        object_key=object_key,
        payload=payload_json,
        content_type="application/json",
    )
    record = ArtifactRecord(
        artifact_id=artifact_id,
        domain=domain,
        artifact_type=artifact_type,
        source_object_kind=source_object_kind,
        source_object_id=source_object_id,
        lifecycle_status=lifecycle_status,
        retention_posture=retention_posture,
        media_type=stored_object.content_type,
        byte_size=stored_object.byte_size,
        checksum_sha256=stored_object.checksum_sha256,
        storage_backend=_resolve_storage_backend(stored_object),
        storage_reference=f"{_resolve_storage_backend(stored_object).value}://{object_key}",
        lineage_parent_artifact_id=lineage_parent_artifact_id,
        superseded_by_artifact_id=superseded_by_artifact_id,
        created_at=created_at,
        created_by=created_by,
    )
    get_artifact_repository().save_artifact(record)
    return ArtifactDescriptor.model_validate(record.__dict__)


def load_artifact_descriptors(*, artifact_ids: list[str]) -> list[ArtifactDescriptor]:
    repository = get_artifact_repository()
    descriptors: list[ArtifactDescriptor] = []
    for artifact_id in artifact_ids:
        record = repository.get_artifact(artifact_id=artifact_id)
        if record is None:
            continue
        descriptors.append(ArtifactDescriptor.model_validate(record.__dict__))
    return descriptors


def _resolve_storage_backend(stored_object: StoredArtifactObject) -> ArtifactStorageBackend:
    if settings.artifact_object_store_mode == "memory":
        return ArtifactStorageBackend.MEMORY
    return ArtifactStorageBackend.FILESYSTEM
