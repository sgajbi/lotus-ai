"""Provider catalog, policy and operator-profile read-model contracts.

Split from contracts/providers.py when the module budget fired (issue #244,
U1): the catalog/policy/profile read models are a cohesive family consumed by
their own services and routes, not by the execution path.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.contracts.providers import (
    ProviderAdapterKind,
    ProviderCapability,
    ProviderConfigurationStatusDescriptor,
    ProviderExecutionMode,
    ProviderExpansionPolicyDescriptor,
    ProviderFailureCategory,
    ProviderLifecycleStatus,
)


class ProviderDescriptor(BaseModel):
    provider_id: str = Field(description="Stable provider identifier within lotus-ai.")
    display_name: str = Field(description="Human-readable provider name.")
    capability: ProviderCapability = Field(
        description="Primary capability area exposed by the provider."
    )
    adapter_kind: ProviderAdapterKind = Field(
        description="Kind of provider adapter currently registered for this provider path."
    )
    lifecycle_status: ProviderLifecycleStatus = Field(
        description="Current lifecycle state of the provider integration."
    )
    runtime_mode: str = Field(description="Configured runtime mode associated with the provider.")
    enabled_for_execution: bool = Field(
        description="Whether the provider is currently eligible for live execution."
    )
    failure_category_on_use: ProviderFailureCategory | None = Field(
        default=None,
        description="Failure category expected if this provider path is selected before it is enabled.",
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
    text_generation_configuration: ProviderConfigurationStatusDescriptor = Field(
        description="Current rollout and configuration posture for future live text-generation activation."
    )
    embedding_configuration: ProviderConfigurationStatusDescriptor = Field(
        description="Current rollout and configuration posture for future live embedding-provider activation."
    )
    runtime_execution_enabled: bool = Field(
        description="Whether any provider is currently enabled for live execution."
    )
    text_generation_runtime_execution_enabled: bool = Field(
        description="Whether any text-generation provider path is currently enabled for live execution."
    )
    embedding_runtime_execution_enabled: bool = Field(
        description="Whether any embedding provider path is currently enabled for live execution."
    )
    expansion_policy: ProviderExpansionPolicyDescriptor = Field(
        description="Bounded provider-expansion policy describing current provider breadth and future governed slots."
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
    selected_adapter_kind: ProviderAdapterKind = Field(
        description="Registered adapter kind currently selected for this capability."
    )
    live_execution_enabled: bool = Field(
        description="Whether live execution is currently allowed for this capability."
    )
    rejection_category: ProviderFailureCategory = Field(
        description="Structured failure category used when the configured mode is rejected."
    )
    rejection_behavior: str = Field(
        description="How lotus-ai should behave when the configured mode is unsupported."
    )


class ProviderPolicyResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider policy response.")
    version: str = Field(description="Current lotus-ai service version.")
    text_generation_configuration: ProviderConfigurationStatusDescriptor = Field(
        description="Current rollout and configuration posture for future live text-generation activation."
    )
    embedding_configuration: ProviderConfigurationStatusDescriptor = Field(
        description="Current rollout and configuration posture for future live embedding-provider activation."
    )
    expansion_policy: ProviderExpansionPolicyDescriptor = Field(
        description="Bounded provider-expansion policy describing how later providers are reviewed without widening execution semantics prematurely."
    )
    policies: list[ProviderPolicyDescriptor] = Field(
        description="Capability-specific provider execution policies."
    )


class ProviderOperatorProfileDescriptor(BaseModel):
    profile_id: str = Field(description="Stable operator-facing provider profile identifier.")
    display_name: str = Field(description="Operator-facing label for the provider profile.")
    provider_mode: str = Field(description="Provider mode activated by this profile.")
    provider_id: str | None = Field(
        default=None,
        description="Expected provider identifier for this profile when one is configured.",
    )
    api_base_class: str = Field(
        description="High-level endpoint class for this profile, such as managed_openai or local_openai_compatible."
    )
    docker_profile: str | None = Field(
        default=None,
        description="Optional Docker Compose profile name associated with this operator profile.",
    )
    use_case: str = Field(
        description="Human-readable explanation of when operators should choose this profile."
    )
    required_settings: list[str] = Field(
        default_factory=list,
        description="Configuration settings that must be present for this profile to operate correctly.",
    )
    verification_surfaces: list[str] = Field(
        default_factory=list,
        description="Primary inspection surfaces operators should use to verify this profile.",
    )


class ProviderOperatorProfileResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider operator profile view.")
    version: str = Field(description="Current lotus-ai service version.")
    selected_profile_id: str = Field(
        description="Operator profile currently implied by the active provider configuration."
    )
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    current_provider_id: str | None = Field(
        default=None,
        description="Configured current provider id for the active text-generation path.",
    )
    current_model_id: str | None = Field(
        default=None,
        description="Configured current model id for the active text-generation path.",
    )
    live_execution_enabled: bool = Field(
        description="Whether the current provider profile is presently enabled for live execution."
    )
    current_readiness_note: str = Field(
        description="Single operator-facing note describing the current active provider posture."
    )
    switching_steps: list[str] = Field(
        default_factory=list,
        description="Ordered operator steps to switch and verify the active provider profile.",
    )
    profiles: list[ProviderOperatorProfileDescriptor] = Field(
        description="Supported provider operator profiles exposed by lotus-ai."
    )
