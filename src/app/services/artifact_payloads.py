from __future__ import annotations

from dataclasses import replace
import hashlib
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
    object_key = f"{domain}/{source_object_kind}/{source_object_id}/{artifact_id}.json"
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


def persist_or_reuse_json_artifact(
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
) -> ArtifactDescriptor:
    existing = _find_latest_active_artifact(
        domain=domain,
        artifact_type=artifact_type,
        source_object_kind=source_object_kind,
        source_object_id=source_object_id,
    )
    payload_checksum = hashlib.sha256(payload_json).hexdigest()
    if existing is not None:
        object_key = _parse_storage_reference(existing.storage_reference)
        stored_object = get_artifact_object_store().get_object(object_key=object_key)
        if stored_object is not None and stored_object.checksum_sha256 == payload_checksum:
            return ArtifactDescriptor.model_validate(existing.__dict__)

    created = persist_json_artifact(
        domain=domain,
        artifact_type=artifact_type,
        source_object_kind=source_object_kind,
        source_object_id=source_object_id,
        created_at=created_at,
        created_by=created_by,
        payload_json=payload_json,
        lifecycle_status=lifecycle_status,
        retention_posture=retention_posture,
        lineage_parent_artifact_id=existing.artifact_id if existing is not None else None,
    )
    if existing is not None:
        superseded = replace(
            existing,
            lifecycle_status=ArtifactLifecycleStatus.SUPERSEDED,
            superseded_by_artifact_id=created.artifact_id,
        )
        get_artifact_repository().save_artifact(superseded)
    return created


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


def _find_latest_active_artifact(
    *,
    domain: str,
    artifact_type: str,
    source_object_kind: str,
    source_object_id: str,
) -> ArtifactRecord | None:
    matches = [
        artifact
        for artifact in get_artifact_repository().list_artifacts()
        if artifact.domain == domain
        and artifact.artifact_type == artifact_type
        and artifact.source_object_kind == source_object_kind
        and artifact.source_object_id == source_object_id
        and artifact.superseded_by_artifact_id is None
    ]
    if not matches:
        return None
    return matches[-1]


def _parse_storage_reference(storage_reference: str) -> str:
    _, _, object_key = storage_reference.partition("://")
    return object_key
