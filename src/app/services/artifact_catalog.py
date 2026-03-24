from __future__ import annotations

from app.config import settings
from app.contracts.artifacts import (
    ArtifactCatalogResponse,
    ArtifactDescriptor,
    ArtifactLifecycleStatus,
)
from app.services.artifact_store import get_artifact_repository
from app.services.runtime_readiness import get_artifact_store_runtime_status


def build_artifact_catalog(*, limit: int = 100, domain: str | None = None) -> ArtifactCatalogResponse:
    artifacts = _load_artifacts(limit=limit, domain=domain)
    return ArtifactCatalogResponse(
        service=settings.service_name,
        version=settings.service_version,
        artifact_count=len(artifacts),
        active_count=sum(
            1
            for artifact in artifacts
            if artifact.lifecycle_status == ArtifactLifecycleStatus.RUNTIME_GENERATED
        ),
        superseded_count=sum(
            1
            for artifact in artifacts
            if artifact.lifecycle_status == ArtifactLifecycleStatus.SUPERSEDED
        ),
        archived_count=sum(
            1 for artifact in artifacts if artifact.lifecycle_status == ArtifactLifecycleStatus.ARCHIVED
        ),
        historical_staged_count=sum(
            1
            for artifact in artifacts
            if artifact.lifecycle_status == ArtifactLifecycleStatus.HISTORICAL_STAGED
        ),
        artifacts=artifacts,
        status_summary=[
            "Artifact catalog is descriptor-first and bounded; it does not expose raw payload bytes or backend URLs.",
            (
                f"{len(artifacts)} artifact descriptor(s) currently match the bounded catalog filter."
                if artifacts
                else "No artifact descriptors currently match the bounded catalog filter."
            ),
        ],
    )


def _load_artifacts(*, limit: int, domain: str | None) -> list[ArtifactDescriptor]:
    runtime_status = get_artifact_store_runtime_status()
    if runtime_status.status.value != "READY":
        return []
    records = get_artifact_repository().list_artifacts()
    if domain is not None:
        records = [record for record in records if record.domain == domain]
    bounded = list(reversed(records))[:limit]
    return [ArtifactDescriptor.model_validate(record.__dict__) for record in bounded]
