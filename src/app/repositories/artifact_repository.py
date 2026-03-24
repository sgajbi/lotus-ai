from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.contracts.artifacts import ArtifactLifecycleStatus, ArtifactStorageBackend


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    domain: str
    artifact_type: str
    source_object_kind: str
    source_object_id: str
    lifecycle_status: ArtifactLifecycleStatus
    retention_posture: str
    media_type: str
    byte_size: int
    checksum_sha256: str
    storage_backend: ArtifactStorageBackend
    storage_reference: str
    lineage_parent_artifact_id: str | None
    superseded_by_artifact_id: str | None
    created_at: str
    created_by: str


class ArtifactRepository(Protocol):
    def list_artifacts(self) -> list[ArtifactRecord]:
        """List all persisted artifact metadata records."""

    def get_artifact(self, *, artifact_id: str) -> ArtifactRecord | None:
        """Fetch one persisted artifact metadata record."""

    def save_artifact(self, record: ArtifactRecord) -> None:
        """Persist one artifact metadata record."""
