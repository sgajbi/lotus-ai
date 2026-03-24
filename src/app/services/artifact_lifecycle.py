from __future__ import annotations

from dataclasses import replace

from fastapi import HTTPException, status

from app.contracts.artifacts import ArtifactLifecycleStatus
from app.repositories.artifact_repository import ArtifactRecord
from app.services.artifact_store import get_artifact_repository


def archive_artifact(*, artifact_id: str) -> ArtifactRecord:
    repository = get_artifact_repository()
    record = repository.get_artifact(artifact_id=artifact_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_id}' was not found.",
        )
    archived = replace(
        record,
        lifecycle_status=ArtifactLifecycleStatus.ARCHIVED,
        retention_posture="archived",
    )
    repository.save_artifact(archived)
    return archived
