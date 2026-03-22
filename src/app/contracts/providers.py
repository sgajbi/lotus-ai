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


class ProviderExecutionMode(str, Enum):
    DISABLED = "disabled"
    STUB = "stub"


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


class ProviderPolicyDescriptor(BaseModel):
    capability: ProviderCapability = Field(
        description="Provider capability governed by the policy."
    )
    configured_mode: str = Field(description="Configured runtime mode for the capability.")
    allowed_modes: list[ProviderExecutionMode] = Field(
        description="Modes currently supported by lotus-ai for this capability."
    )
    selected_provider_id: str = Field(
        description="Provider identifier currently selected for this capability."
    )
    live_execution_enabled: bool = Field(
        description="Whether live execution is currently allowed for this capability."
    )
    rejection_behavior: str = Field(
        description="How lotus-ai should behave when the configured mode is unsupported."
    )


class ProviderPolicyResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider policy response.")
    version: str = Field(description="Current lotus-ai service version.")
    policies: list[ProviderPolicyDescriptor] = Field(
        description="Capability-specific provider execution policies."
    )


class ProviderExecutionRequest(BaseModel):
    task_id: str = Field(description="Bounded lotus-ai task identifier being executed.")
    caller_app: str = Field(description="Calling Lotus application or platform component.")
    prompt_version: str = Field(description="Resolved prompt version for this execution.")
    context_summary: str = Field(description="Short summary of caller-provided context.")
    context_payload: dict[str, object] = Field(
        default_factory=dict,
        description="Structured context payload curated by the calling Lotus application.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="Caller-provided source references attached to the execution request.",
    )


class ProviderExecutionResponse(BaseModel):
    provider_id: str = Field(description="Provider identifier selected for execution.")
    provider_mode: str = Field(description="Provider mode active during execution.")
    stubbed: bool = Field(description="Whether execution was handled by a stub provider path.")
    message: str = Field(description="Human-readable execution message returned by the provider.")
    structured_output: dict[str, object] = Field(
        default_factory=dict,
        description="Structured execution payload emitted by the provider layer.",
    )
