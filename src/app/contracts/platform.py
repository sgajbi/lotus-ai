from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RuntimeReadinessStatus(str, Enum):
    READY = "READY"
    CONFIGURATION_REQUIRED = "CONFIGURATION_REQUIRED"
    MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


class StoreRuntimeStatusDescriptor(BaseModel):
    mode: str = Field(description="Configured store mode for the runtime component.")
    status: RuntimeReadinessStatus = Field(description="Current readiness status for the store.")
    database_configured: bool = Field(
        description="Whether a database URL is configured for this store."
    )
    detail: str = Field(description="Human-readable explanation of the current readiness status.")


class PlatformRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the platform runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    provider_mode: str = Field(description="Current model provider execution mode.")
    retrieval_mode: str = Field(description="Current retrieval execution mode.")
    embedding_provider_mode: str = Field(description="Current embedding provider mode.")
    safety_mode: str = Field(description="Current safety policy mode.")
    audit_store: StoreRuntimeStatusDescriptor = Field(
        description="Current audit persistence runtime posture."
    )
    retrieval_store: StoreRuntimeStatusDescriptor = Field(
        description="Current retrieval metadata runtime posture."
    )
    database_configured: bool = Field(
        description="Whether a database URL is configured for durable runtime components."
    )
    prompt_count: int = Field(description="Number of registered prompt definitions.")
    capability_count: int = Field(description="Number of bounded capabilities exposed by lotus-ai.")
    vector_store: str = Field(description="Current or planned vector-store strategy label.")
    migration_contract_enforced: bool = Field(
        description="Whether lotus-ai requires migration-managed relational schema changes."
    )
