from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.runtime_readiness import RuntimeReadinessStatus, StoreRuntimeStatusDescriptor


class ArtifactLifecycleStatus(str, Enum):
    HISTORICAL_STAGED = "historical_staged"
    RUNTIME_GENERATED = "runtime_generated"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ArtifactStorageBackend(str, Enum):
    MEMORY = "memory"
    FILESYSTEM = "filesystem"


class ArtifactDescriptor(BaseModel):
    artifact_id: str = Field(description="Stable artifact identifier.")
    domain: str = Field(description="Stable platform domain owning the artifact.")
    artifact_type: str = Field(description="Bounded artifact type within the owning domain.")
    source_object_kind: str = Field(
        description="Kind of runtime or historical object that owns the artifact."
    )
    source_object_id: str = Field(
        description="Stable identifier of the runtime or historical object that owns the artifact."
    )
    lifecycle_status: ArtifactLifecycleStatus = Field(
        description="Current lifecycle posture for the artifact."
    )
    retention_posture: str = Field(
        description="Retention posture such as active, retained_for_review, or archived."
    )
    media_type: str = Field(description="Media type for the stored payload.")
    byte_size: int = Field(description="Persisted payload size in bytes.")
    checksum_sha256: str = Field(description="SHA-256 checksum of the stored payload.")
    storage_backend: ArtifactStorageBackend = Field(
        description="Configured object-store backend holding the payload bytes."
    )
    storage_reference: str = Field(
        description="Opaque governed storage reference rather than a raw backend URL."
    )
    lineage_parent_artifact_id: str | None = Field(
        default=None,
        description="Optional predecessor artifact identifier when lineage is known.",
    )
    superseded_by_artifact_id: str | None = Field(
        default=None,
        description="Optional replacement artifact identifier when this artifact is superseded.",
    )
    created_at: str = Field(description="UTC timestamp when the artifact metadata was recorded.")
    created_by: str = Field(
        description="Bounded creation context such as worker, operator, or staged_registry."
    )


class ArtifactObjectStoreRuntimeStatusDescriptor(BaseModel):
    mode: str = Field(description="Configured object-store mode.")
    status: RuntimeReadinessStatus = Field(
        description="Current readiness status for the configured object-store mode."
    )
    root_configured: bool = Field(
        description="Whether a backing root path or equivalent configuration is present."
    )
    durable: bool = Field(
        description="Whether the configured object-store mode is durable across restart."
    )
    detail: str = Field(description="Human-readable explanation of the current object-store posture.")


class ArtifactRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the artifact runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    metadata_store_mode: str = Field(description="Configured artifact metadata store mode.")
    object_store_mode: str = Field(description="Configured artifact object-store mode.")
    metadata_store: StoreRuntimeStatusDescriptor = Field(
        description="Current runtime readiness for the artifact metadata store."
    )
    object_store: ArtifactObjectStoreRuntimeStatusDescriptor = Field(
        description="Current runtime readiness for the artifact payload store."
    )
    artifact_count: int = Field(
        description="Number of governed artifact metadata records currently stored."
    )
    supported_domains: list[str] = Field(
        description="Bounded list of platform domains intended to consume the artifact backbone."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current artifact backbone posture."
    )
