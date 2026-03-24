from __future__ import annotations

from app.config import settings
from app.contracts.artifacts import (
    ArtifactObjectStoreRuntimeStatusDescriptor,
    ArtifactRuntimeStatusResponse,
)
from app.contracts.runtime_readiness import RuntimeReadinessStatus
from app.services.artifact_store import get_artifact_repository
from app.services.runtime_readiness import get_artifact_store_runtime_status

SUPPORTED_ARTIFACT_DOMAINS = ["evaluation", "async", "observability", "retrieval", "prompt"]
ACTIVE_ARTIFACT_DOMAINS = ["evaluation", "async", "observability"]


def build_artifact_runtime_status() -> ArtifactRuntimeStatusResponse:
    metadata_store = get_artifact_store_runtime_status()
    object_store = _build_artifact_object_store_runtime_status()
    artifact_count = _resolve_artifact_count(metadata_store.status)

    status_summary = [
        (
            "Artifact metadata remains relationally authoritative while payload bytes stay behind "
            "a governed object-store seam."
        ),
        (
            "Evaluation, async, and observability now emit governed runtime artifact refs while retrieval and prompt remain future consumers."
        ),
    ]
    if object_store.mode == "filesystem":
        status_summary.append(
            "Filesystem payload storage is active as a clearly labeled local or development fallback, not a production object-store posture."
        )

    return ArtifactRuntimeStatusResponse(
        service=settings.service_name,
        version=settings.service_version,
        metadata_store_mode=settings.artifact_store_mode,
        object_store_mode=settings.artifact_object_store_mode,
        metadata_store=metadata_store,
        object_store=object_store,
        artifact_count=artifact_count,
        supported_domains=SUPPORTED_ARTIFACT_DOMAINS,
        status_summary=status_summary,
    )


def _resolve_artifact_count(metadata_store_status: RuntimeReadinessStatus) -> int:
    if metadata_store_status is not RuntimeReadinessStatus.READY:
        return 0
    return len(get_artifact_repository().list_artifacts())


def _build_artifact_object_store_runtime_status() -> ArtifactObjectStoreRuntimeStatusDescriptor:
    if settings.artifact_object_store_mode == "memory":
        return ArtifactObjectStoreRuntimeStatusDescriptor(
            mode="memory",
            status=RuntimeReadinessStatus.READY,
            root_configured=False,
            durable=False,
            detail="In-memory artifact object store is active for local or foundation-phase development.",
        )
    if settings.artifact_object_store_mode == "filesystem":
        root_configured = bool(settings.artifact_object_store_root)
        if not root_configured:
            return ArtifactObjectStoreRuntimeStatusDescriptor(
                mode="filesystem",
                status=RuntimeReadinessStatus.CONFIGURATION_REQUIRED,
                root_configured=False,
                durable=True,
                detail="A filesystem root is required for the configured artifact object-store mode.",
            )
        return ArtifactObjectStoreRuntimeStatusDescriptor(
            mode="filesystem",
            status=RuntimeReadinessStatus.READY,
            root_configured=True,
            durable=True,
            detail="Filesystem-backed artifact payload storage is configured behind the governed object-store seam.",
        )
    return ArtifactObjectStoreRuntimeStatusDescriptor(
        mode=settings.artifact_object_store_mode,
        status=RuntimeReadinessStatus.UNAVAILABLE,
        root_configured=bool(settings.artifact_object_store_root),
        durable=False,
        detail="Configured artifact object-store mode is not supported by lotus-ai.",
    )
