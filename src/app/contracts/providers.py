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
    OPENAI = "openai"


class ProviderAdapterKind(str, Enum):
    STUB = "STUB"
    OPENAI_LIVE = "OPENAI_LIVE"


class ProviderFailureCategory(str, Enum):
    UNSUPPORTED_MODE = "UNSUPPORTED_MODE"
    LIVE_EXECUTION_NOT_ENABLED = "LIVE_EXECUTION_NOT_ENABLED"
    PROVIDER_NOT_REGISTERED = "PROVIDER_NOT_REGISTERED"
    INVALID_LIVE_CONFIGURATION = "INVALID_LIVE_CONFIGURATION"
    INVALID_QUOTA_CONFIGURATION = "INVALID_QUOTA_CONFIGURATION"
    INVALID_BUDGET_CONFIGURATION = "INVALID_BUDGET_CONFIGURATION"
    TASK_NOT_ALLOWLISTED = "TASK_NOT_ALLOWLISTED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_UPSTREAM_ERROR = "PROVIDER_UPSTREAM_ERROR"


class ProviderRolloutState(str, Enum):
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    STUB_DEFAULT = "STUB_DEFAULT"
    ALLOWLISTED_DISABLED = "ALLOWLISTED_DISABLED"
    CANARY_ENABLED = "CANARY_ENABLED"
    ROLLED_OUT = "ROLLED_OUT"


class ProviderCredentialStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    INVALID = "INVALID"


class ProviderQuotaScope(str, Enum):
    DEFAULT = "DEFAULT"
    TASK = "TASK"
    CALLER_APP = "CALLER_APP"
    TENANT = "TENANT"


class ProviderQuotaDescriptor(BaseModel):
    scope: ProviderQuotaScope = Field(
        description="Quota scope this policy entry applies to."
    )
    scope_key: str = Field(
        description="Stable identifier for the quota scope, or `global` for the default scope."
    )
    request_limit: int = Field(
        description="Maximum accepted live-provider execution requests allowed for this scope."
    )
    current_request_count: int = Field(
        description="Current in-process accepted request count observed for this scope."
    )
    remaining_request_count: int = Field(
        description="Remaining accepted request count before this scope is blocked."
    )
    notes: str = Field(description="Human-readable explanation of the quota scope semantics.")


class ProviderQuotaPolicyResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider quota policy view.")
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    quota_enforced: bool = Field(
        description="Whether live text-generation quota enforcement is currently enabled."
    )
    configuration_valid: bool = Field(
        description="Whether the configured provider quota posture is internally consistent."
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Human-readable findings describing the current provider quota posture.",
    )
    matching_order: list[ProviderQuotaScope] = Field(
        description="Ordered list of quota scopes evaluated for a live-provider execution request."
    )
    quotas: list[ProviderQuotaDescriptor] = Field(
        description="Configured live-provider quota entries and their current in-process usage."
    )


class ProviderBudgetState(str, Enum):
    NOT_ENFORCED = "NOT_ENFORCED"
    BELOW_SOFT_LIMIT = "BELOW_SOFT_LIMIT"
    SOFT_LIMIT_REACHED = "SOFT_LIMIT_REACHED"
    HARD_LIMIT_BLOCKED = "HARD_LIMIT_BLOCKED"
    INVALID = "INVALID"


class ProviderOperationsState(str, Enum):
    NORMAL = "NORMAL"
    OPERATIONS_INVALID = "OPERATIONS_INVALID"
    QUOTA_BLOCKED = "QUOTA_BLOCKED"
    BUDGET_SOFT_LIMIT = "BUDGET_SOFT_LIMIT"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    DEGRADED_UPSTREAM = "DEGRADED_UPSTREAM"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    ROLLOUT_BLOCKED = "ROLLOUT_BLOCKED"


class ProviderDegradationStatusDescriptor(BaseModel):
    status: str = Field(
        description="Current upstream degradation posture for the live provider path."
    )
    enforcement_enabled: bool = Field(
        description="Whether degraded-upstream and circuit-breaker controls are currently enabled."
    )
    configuration_valid: bool = Field(
        description="Whether degraded-upstream control configuration is internally consistent."
    )
    consecutive_failure_count: int = Field(
        description="Current consecutive live-provider failure count tracked by the degradation controller."
    )
    degraded_failure_count_threshold: int | None = Field(
        default=None,
        description="Configured consecutive-failure threshold for degraded-upstream posture, when enabled.",
    )
    circuit_open_failure_count_threshold: int | None = Field(
        default=None,
        description="Configured consecutive-failure threshold for circuit-open posture, when enabled.",
    )
    circuit_open_remaining_seconds: int | None = Field(
        default=None,
        description="Remaining circuit-open cooldown window in seconds, when the circuit is currently open.",
    )
    last_failure_category: ProviderFailureCategory | None = Field(
        default=None,
        description="Most recent live-provider failure category recorded by the degradation controller, when one exists.",
    )
    timeout_failure_count: int = Field(
        description="Count of tracked provider timeout failures in the current process lifetime."
    )
    rate_limited_failure_count: int = Field(
        description="Count of tracked provider rate-limit failures in the current process lifetime."
    )
    upstream_error_failure_count: int = Field(
        description="Count of tracked provider upstream-error failures in the current process lifetime."
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Human-readable findings describing upstream degradation posture.",
    )


class ProviderOperationsStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the provider operations runtime status view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    operations_state: ProviderOperationsState = Field(
        description="Current top-level provider operations state derived from rollout, quota, budget, and degradation posture."
    )
    runtime_execution_enabled: bool = Field(
        description="Whether live-provider execution is currently enabled for any provider path."
    )
    rollout_blocked: bool = Field(
        description="Whether provider operations remain blocked by rollout or configuration posture."
    )
    quota_policy: ProviderQuotaPolicyResponse = Field(
        description="Current live-provider quota posture."
    )
    budget_policy: ProviderBudgetPolicyResponse = Field(
        description="Current live-provider budget posture."
    )
    degradation_status: ProviderDegradationStatusDescriptor = Field(
        description="Current live-provider degradation posture."
    )
    blocking_reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable reasons why provider operations are currently blocked or degraded.",
    )
    summary: list[str] = Field(
        default_factory=list,
        description="Human-readable summary of the current provider operations posture.",
    )


class ProviderBudgetPolicyResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider budget policy view.")
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    budget_enforced: bool = Field(
        description="Whether live text-generation budget enforcement is currently enabled."
    )
    configuration_valid: bool = Field(
        description="Whether the configured provider budget posture is internally consistent."
    )
    budget_state: ProviderBudgetState = Field(
        description="Current provider budget state derived from configured limits and tracked spend."
    )
    current_spend_usd: float = Field(
        description="Current in-process tracked live-provider spend in USD."
    )
    soft_budget_usd: float | None = Field(
        default=None,
        description="Configured soft budget threshold in USD, when present.",
    )
    hard_budget_usd: float | None = Field(
        default=None,
        description="Configured hard budget threshold in USD, when present.",
    )
    remaining_budget_usd: float | None = Field(
        default=None,
        description="Remaining hard-budget capacity in USD, when a hard limit is configured.",
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Human-readable findings describing the current provider budget posture.",
    )
    usage_to_budget_notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes describing how tracked spend is compared against configured budget thresholds.",
    )


class ProviderConfigurationStatusDescriptor(BaseModel):
    rollout_state: ProviderRolloutState = Field(
        description="Current governed rollout posture for live text-generation provider activation."
    )
    configured_live_provider_id: str | None = Field(
        default=None,
        description="Allowlisted live provider identifier configured for future activation, when present.",
    )
    configured_live_model_id: str | None = Field(
        default=None,
        description="Allowlisted live model identifier configured for future activation, when present.",
    )
    allowlisted_task_ids: list[str] = Field(
        default_factory=list,
        description="Bounded task identifiers currently allowlisted for future live text-generation execution.",
    )
    credential_status: ProviderCredentialStatus = Field(
        description="Current credential posture for the configured live provider path."
    )
    configuration_valid: bool = Field(
        description="Whether the configured rollout and live provider settings are internally consistent."
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Human-readable findings describing configuration and rollout posture.",
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
    policies: list[ProviderPolicyDescriptor] = Field(
        description="Capability-specific provider execution policies."
    )


class ProviderExecutionRequest(BaseModel):
    task_id: str = Field(description="Bounded lotus-ai task identifier being executed.")
    caller_app: str = Field(description="Calling Lotus application or platform component.")
    requested_by: str | None = Field(
        default=None,
        description="Optional human or system identity associated with the provider request.",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant or environment ownership marker for the provider request.",
    )
    prompt_version: str = Field(description="Resolved prompt version for this execution.")
    system_instructions: str = Field(
        description="Resolved system instructions for the executing task prompt."
    )
    output_contract_notes: str = Field(
        description="Resolved output-contract notes constraining live provider behavior."
    )
    output_label: str = Field(description="Resolved output label for the executing task.")
    safety_mode: str = Field(description="Resolved safety mode for the executing task.")
    redaction_posture: str = Field(description="Resolved redaction posture for the executing task.")
    context_summary: str = Field(description="Short summary of caller-provided context.")
    context_payload: dict[str, object] = Field(
        default_factory=dict,
        description="Structured context payload curated by the calling Lotus application.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="Caller-provided source references attached to the execution request.",
    )
    timeout_ms: int = Field(
        description="Bounded provider timeout budget for this execution request."
    )
    retry_limit: int = Field(
        description="Maximum bounded retry count allowed for this execution request."
    )
    max_output_tokens: int = Field(
        description="Maximum bounded output-token budget allowed for this execution request."
    )


class ProviderExecutionResponse(BaseModel):
    provider_id: str = Field(description="Provider identifier selected for execution.")
    provider_mode: str = Field(description="Provider mode active during execution.")
    adapter_kind: ProviderAdapterKind | None = Field(
        default=None,
        description="Registered provider adapter kind that handled the execution, when applicable.",
    )
    failure_category: ProviderFailureCategory | None = Field(
        default=None,
        description="Structured provider failure category when execution is rejected or degraded.",
    )
    timeout_ms: int | None = Field(
        default=None,
        description="Provider timeout budget applied to this execution, when applicable.",
    )
    retry_count: int | None = Field(
        default=None,
        description="Actual retry count used while executing this provider path, when applicable.",
    )
    max_output_tokens: int | None = Field(
        default=None,
        description="Output-token budget applied to this execution, when applicable.",
    )
    model_id: str | None = Field(
        default=None,
        description="Model identifier used for provider execution when one is available.",
    )
    provider_request_id: str | None = Field(
        default=None,
        description="Upstream provider request identifier when one is available.",
    )
    input_tokens: int | None = Field(
        default=None,
        description="Input-token count reported by the provider when available.",
    )
    output_tokens: int | None = Field(
        default=None,
        description="Output-token count reported by the provider when available.",
    )
    total_tokens: int | None = Field(
        default=None,
        description="Total token count reported by the provider when available.",
    )
    estimated_cost_usd: float | None = Field(
        default=None,
        description="Estimated USD cost for the provider execution when rate-card data is configured.",
    )
    stubbed: bool = Field(description="Whether execution was handled by a stub provider path.")
    message: str = Field(description="Human-readable execution message returned by the provider.")
    structured_output: dict[str, object] = Field(
        default_factory=dict,
        description="Structured execution payload emitted by the provider layer.",
    )


class ProviderActivationReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the provider activation readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    embedding_provider_mode: str = Field(description="Configured embedding provider mode.")
    text_generation_configuration: ProviderConfigurationStatusDescriptor = Field(
        description="Current rollout and configuration posture for future live text-generation activation."
    )
    activation_ready: bool = Field(
        description="Whether provider execution is currently ready for live activation."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why provider execution is not yet activatable."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before live provider execution can be enabled."
    )


class ProviderRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable provider runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before live provider activation."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class ProviderRunbookReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider runbook readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    runbook_ready: bool = Field(
        description="Whether provider operational runbook readiness is currently sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of provider runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required provider runbook items currently marked complete."
    )
    items: list[ProviderRunbookReadinessItem] = Field(
        description="Governed provider operational runbook readiness items."
    )


class ProviderEvidenceReadinessItem(BaseModel):
    evidence_id: str = Field(description="Stable provider evidence-readiness item identifier.")
    status: str = Field(description="Current readiness posture for the evidence requirement.")
    required_for_activation: bool = Field(
        description="Whether this evidence item must be complete before live provider activation."
    )
    notes: str = Field(description="Human-readable explanation of the evidence requirement.")


class ProviderEvidenceReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider evidence readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    evidence_ready: bool = Field(
        description="Whether provider evidence posture is currently sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of provider evidence items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required provider evidence items currently marked complete."
    )
    items: list[ProviderEvidenceReadinessItem] = Field(
        description="Governed provider evidence-readiness items."
    )


class ProviderGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the provider governance status view.")
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether provider governance posture is currently sufficient for live activation."
    )
    activation_readiness: ProviderActivationReadinessResponse = Field(
        description="Technical activation-readiness summary for provider execution."
    )
    runbook_readiness: ProviderRunbookReadinessResponse = Field(
        description="Operational runbook-readiness summary for provider execution."
    )
    evidence_readiness: ProviderEvidenceReadinessResponse = Field(
        description="Evaluation and audit evidence-readiness summary for provider execution."
    )
    blocking_area_count: int = Field(
        description="Number of top-level provider governance areas currently blocking activation."
    )
    governance_summary: list[str] = Field(
        description="Human-readable summary of the current provider governance posture."
    )
