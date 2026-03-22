from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProviderCapability(str, Enum):
    TEXT_GENERATION = "TEXT_GENERATION"
    EMBEDDINGS = "EMBEDDINGS"


class ProviderLifecycleStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


class ProviderDescriptor(BaseModel):
    provider_id: str = Field(description="Stable provider identifier within lotus-ai.")
    display_name: str = Field(description="Human-readable provider name.")
    capability: ProviderCapability = Field(
        description="Primary capability area exposed by the provider."
    )
    lifecycle_status: ProviderLifecycleStatus = Field(
        description="Current lifecycle state of the provider integration."
    )
    runtime_mode: str = Field(description="Configured runtime mode associated with the provider.")
    enabled_for_execution: bool = Field(
        description="Whether the provider is currently eligible for live execution."
    )
    source_reference: str = Field(
        description="Repository reference documenting the provider configuration."
    )
    notes: str = Field(description="Operational notes describing the current provider posture.")


class ProviderCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    embedding_provider_mode: str = Field(description="Configured embedding provider mode.")
    runtime_execution_enabled: bool = Field(
        description="Whether any provider is currently enabled for live execution."
    )
    providers: list[ProviderDescriptor] = Field(
        description="Governed provider catalog exposed by lotus-ai."
    )
