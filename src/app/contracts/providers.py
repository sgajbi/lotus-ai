from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.access_control import AuthorizationDecision
from app.contracts.evals import EvaluationApprovalGateSummaryDescriptor


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
    LOCAL_OPENAI_COMPATIBLE = "local_openai_compatible"
    ENABLED = "enabled"


class ProviderAdapterKind(str, Enum):
    STUB = "STUB"
    OPENAI_LIVE = "OPENAI_LIVE"
    OPENAI_COMPATIBLE_LOCAL = "OPENAI_COMPATIBLE_LOCAL"
    OPENAI_EMBEDDINGS_LIVE = "OPENAI_EMBEDDINGS_LIVE"


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
    MODEL_NOT_CATALOGUED = "MODEL_NOT_CATALOGUED"
    MODEL_LIFECYCLE_INELIGIBLE = "MODEL_LIFECYCLE_INELIGIBLE"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
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


ROUTING_POLICY_FIXED_CONFIGURED_MODE = "fixed_configured_mode"
ROUTING_POLICY_VERSION_V1 = "v1"


class RoutingStrategy(str, Enum):
    FIXED = "FIXED"


class RoutingCandidateDescriptor(BaseModel):
    """One execution target the routing policy considered.

    A candidate with a null rejection_reason was eligible; the selected
    candidate is named on the decision. Rejection reasons reuse the bounded
    ProviderFailureCategory vocabulary - one failure vocabulary, no parallel
    enum to drift.
    """

    provider_id: str = Field(description="Provider identity of the candidate.")
    provider_mode: str = Field(description="Execution mode the candidate serves.")
    model_catalogue_entry_id: str | None = Field(
        default=None,
        description="Governed catalogue entry for the candidate, on live paths.",
    )
    model_revision: str | None = Field(
        default=None,
        description="Exact (or fallback) model revision of the candidate when known.",
    )
    rejection_reason: ProviderFailureCategory | None = Field(
        default=None,
        description="Bounded failure category when this candidate was rejected; null otherwise.",
    )


class RoutingDecisionDescriptor(BaseModel):
    """The recorded rationale for one execution's provider/model selection.

    Every execution attempt records exactly one decision: which policy decided,
    which candidates were considered, what was rejected and why, what was
    selected (or that everything was rejected), and when.
    """

    policy_id: str = Field(description="Routing policy that made this decision.")
    policy_version: str = Field(description="Version of the routing policy.")
    strategy: RoutingStrategy = Field(description="Routing strategy the policy applied.")
    candidates: list[RoutingCandidateDescriptor] = Field(
        description="Every candidate the policy considered for this execution.",
    )
    selected_provider_id: str | None = Field(
        default=None,
        description=(
            "Provider identity the execution was routed to; null when every candidate "
            "was rejected and the execution was refused."
        ),
    )
    selected_model_catalogue_entry_id: str | None = Field(
        default=None,
        description="Governed catalogue entry the execution was routed to, on live paths.",
    )
    decided_at: str = Field(description="Instant the routing decision was made (UTC).")
    selection_reason: str = Field(
        description="Human-readable statement of the selection or refusal.",
    )


class RoutingPostureCandidateDescriptor(BaseModel):
    provider_id: str | None = Field(
        default=None,
        description="Configured live provider identity; null when no live identity is set.",
    )
    provider_mode: str = Field(description="Configured provider execution mode.")
    model_catalogue_entry_id: str | None = Field(
        default=None,
        description="Governed catalogue entry the live identity resolves to, when configured.",
    )
    model_family: str | None = Field(default=None, description="Model family of the candidate.")
    model_revision: str | None = Field(
        default=None, description="Exact (or fallback) revision of the candidate."
    )
    revision_pinned: bool | None = Field(
        default=None, description="Whether the catalogue entry pins an exact revision."
    )
    lifecycle_state: str | None = Field(
        default=None, description="Lifecycle state of the catalogue entry."
    )


class RoutingPostureResponse(BaseModel):
    service: str = Field(description="Service name emitting the routing posture.")
    version: str = Field(description="Current lotus-ai service version.")
    policy_id: str = Field(description="Routing policy currently in force.")
    policy_version: str = Field(description="Version of the routing policy.")
    strategy: RoutingStrategy = Field(description="Routing strategy the policy applies.")
    candidate: RoutingPostureCandidateDescriptor = Field(
        description="The single candidate the fixed policy would consider right now.",
    )
    degradation: "ProviderDegradationStatusDescriptor" = Field(
        description="Current circuit-breaker posture for the live provider path.",
    )
    quota_enforced: bool = Field(description="Whether live-text quota enforcement is on.")
    budget_enforced: bool = Field(description="Whether live-text budget enforcement is on.")
    enforcing_kill_switch_count: int = Field(
        ge=0,
        description="Currently enforcing kill-switch activations (any scope).",
    )
    notes: list[str] = Field(description="Boundary statements this posture ships with.")


class ProviderCredentialStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    INVALID = "INVALID"


class ProviderQuotaScope(str, Enum):
    DEFAULT = "DEFAULT"
    TASK = "TASK"
    CALLER_APP = "CALLER_APP"
    TENANT = "TENANT"


class ProviderOperationsControlActionType(str, Enum):
    RESET_ALL_QUOTAS = "RESET_ALL_QUOTAS"
    RESET_QUOTA_SCOPE = "RESET_QUOTA_SCOPE"
    RESET_BUDGET = "RESET_BUDGET"
    RESET_DEGRADATION = "RESET_DEGRADATION"
    RESET_ALL_PROVIDER_OPERATIONS = "RESET_ALL_PROVIDER_OPERATIONS"


class ProviderQuotaDescriptor(BaseModel):
    scope: ProviderQuotaScope = Field(description="Quota scope this policy entry applies to.")
    scope_key: str = Field(
        description="Stable identifier for the quota scope, or `global` for the default scope."
    )
    request_limit: int = Field(
        description="Maximum accepted live-provider execution requests allowed for this scope."
    )
    current_request_count: int = Field(
        description="Current tracked accepted request count observed for this scope."
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
        description="Configured live-provider quota entries and their current tracked usage."
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
        description="Count of tracked provider timeout failures in the current durable degradation state."
    )
    rate_limited_failure_count: int = Field(
        description="Count of tracked provider rate-limit failures in the current durable degradation state."
    )
    upstream_error_failure_count: int = Field(
        description="Count of tracked provider upstream-error failures in the current durable degradation state."
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
    expansion_policy: ProviderExpansionPolicyDescriptor = Field(
        description="Bounded provider-expansion policy as it relates to current provider operations posture."
    )
    blocking_reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable reasons why provider operations are currently blocked or degraded.",
    )
    summary: list[str] = Field(
        default_factory=list,
        description="Human-readable summary of the current provider operations posture.",
    )


class ProviderOperationsControlEventDescriptor(BaseModel):
    event_id: str = Field(
        description="Stable identifier for the recorded provider-operations action."
    )
    action_type: ProviderOperationsControlActionType = Field(
        description="Type of provider-operations control action that was recorded."
    )
    scope: ProviderQuotaScope | None = Field(
        default=None,
        description="Quota scope targeted by the action when the action resets a specific quota scope.",
    )
    scope_key: str | None = Field(
        default=None,
        description="Scope key targeted by the action when applicable.",
    )
    reason: str = Field(description="Operator-provided reason for the provider-operations action.")
    requested_by: str = Field(description="Operator or system identity that requested the action.")
    approved_by: str = Field(description="Approver identity recorded for the action.")
    affected_record_count: int = Field(
        description="Number of provider-operations state records affected by the action."
    )
    authorization: AuthorizationDecision = Field(
        description="Typed caller-authorization decision recorded for the provider control action."
    )
    recorded_at: str = Field(description="Timestamp when the action was recorded.")


class ProviderOperationsControlHistoryResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the provider-operations control history view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    control_plane_store_mode: str = Field(
        description="Configured provider-operations store mode backing control-plane truth."
    )
    reset_actions_supported: bool = Field(
        description="Whether governed provider-operations reset actions are currently supported."
    )
    supported_action_types: list[ProviderOperationsControlActionType] = Field(
        description="Supported provider-operations control action types."
    )
    latest_events: list[ProviderOperationsControlEventDescriptor] = Field(
        default_factory=list,
        description="Most recent recorded provider-operations control-plane actions.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes describing reset and rollover semantics for the provider control plane.",
    )


class ProviderOperationsControlActionRequest(BaseModel):
    action_type: ProviderOperationsControlActionType = Field(
        description="Requested provider-operations control action."
    )
    caller_app: str = Field(
        min_length=1,
        description="Caller application identity authorized to issue the provider-operations action.",
    )
    scope: ProviderQuotaScope | None = Field(
        default=None,
        description="Quota scope targeted by the action when resetting one quota scope.",
    )
    scope_key: str | None = Field(
        default=None,
        description="Quota scope key targeted by the action when resetting one quota scope.",
    )
    requested_by: str = Field(
        min_length=1,
        description="Operator or system identity requesting the provider-operations action.",
    )
    approved_by: str = Field(
        min_length=1,
        description="Approver identity authorizing the provider-operations action.",
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable reason for the provider-operations action.",
    )


class ProviderOperationsControlActionResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the provider-operations control action response."
    )
    version: str = Field(description="Current lotus-ai service version.")
    provider_mode: str = Field(description="Configured text-generation provider mode.")
    event: ProviderOperationsControlEventDescriptor = Field(
        description="Recorded provider-operations control-plane event."
    )
    summary: list[str] = Field(
        default_factory=list,
        description="Human-readable summary of the applied provider-operations action.",
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
    current_spend_usd: float = Field(description="Current tracked live-provider spend in USD.")
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
    capability: ProviderCapability = Field(
        description="Provider capability whose rollout and configuration posture is being described."
    )
    rollout_state: ProviderRolloutState = Field(
        description="Current governed rollout posture for this provider capability."
    )
    configured_live_provider_id: str | None = Field(
        default=None,
        description="Allowlisted or configured live provider identifier for this capability, when present.",
    )
    configured_live_model_id: str | None = Field(
        default=None,
        description="Allowlisted or configured live model identifier for this capability, when present.",
    )
    allowlisted_task_ids: list[str] = Field(
        default_factory=list,
        description="Bounded task identifiers currently allowlisted for future activation, when this capability is task-scoped.",
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


class ProviderExpansionRuleDescriptor(BaseModel):
    capability: ProviderCapability = Field(
        description="Provider capability governed by this bounded expansion rule."
    )
    registered_provider_ids: list[str] = Field(
        description="Currently registered provider identifiers for this capability."
    )
    live_capable_provider_ids: list[str] = Field(
        description="Registered provider identifiers that expose a non-stub live-capable adapter for this capability."
    )
    max_governed_provider_count: int = Field(
        description="Maximum bounded provider count currently approved for this capability."
    )
    available_expansion_slots: int = Field(
        description="Remaining bounded expansion slots available before this capability exceeds the approved provider-breadth model."
    )
    expansion_ready: bool = Field(
        description="Whether this capability remains within the bounded provider-expansion policy."
    )
    requirements: list[str] = Field(
        default_factory=list,
        description="Explicit governance requirements that any additional provider must satisfy before activation.",
    )
    notes: str = Field(
        description="Human-readable explanation of the bounded provider-breadth posture for this capability."
    )


class ProviderExpansionPolicyDescriptor(BaseModel):
    bounded_expansion_enabled: bool = Field(
        description="Whether lotus-ai now exposes an explicit bounded provider-expansion model."
    )
    expansion_blocked: bool = Field(
        description="Whether the current registered provider breadth violates or exhausts the bounded expansion policy."
    )
    findings: list[str] = Field(
        default_factory=list,
        description="Human-readable findings describing the current bounded provider-expansion posture.",
    )
    capability_rules: list[ProviderExpansionRuleDescriptor] = Field(
        description="Capability-specific bounded provider expansion rules."
    )


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
    temperature: float = Field(
        default=0.0,
        ge=0,
        description="Explicit sampling temperature sent to the provider (issue #151).",
    )
    top_p: float | None = Field(
        default=None,
        gt=0,
        le=1,
        description="Explicit nucleus-sampling bound; omitted from the provider call when null.",
    )
    seed: int | None = Field(
        default=None,
        description="Sampling seed where the provider supports it; omitted when null.",
    )


class EmbeddingExecutionRequest(BaseModel):
    caller_app: str = Field(description="Calling Lotus application or platform component.")
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant or environment ownership marker for the embedding request.",
    )
    corpus_id: str | None = Field(
        default=None,
        description="Optional bounded corpus identifier associated with the embedding request.",
    )
    content: str = Field(description="Bounded text content to convert into an embedding.")
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Structured metadata describing the bounded embedding request context.",
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
    model_version: str | None = Field(
        default=None,
        description="Governed model release or deployment version used for provider execution.",
    )
    model_catalogue_entry_id: str | None = Field(
        default=None,
        description=(
            "Governed model-catalogue entry this execution was bound to, on live provider paths."
        ),
    )
    model_revision_pinned: bool | None = Field(
        default=None,
        description=(
            "Whether the bound catalogue entry pins an exact model revision "
            "(False means the family/tag fallback identity executed)."
        ),
    )
    routing_decision: RoutingDecisionDescriptor | None = Field(
        default=None,
        description=(
            "Recorded routing rationale for this execution: policy, considered candidates, "
            "selection and reason. Stamped by the provider gateway."
        ),
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


class EmbeddingExecutionResponse(BaseModel):
    provider_id: str = Field(description="Provider identifier selected for embedding execution.")
    provider_mode: str = Field(description="Provider mode active during embedding execution.")
    adapter_kind: ProviderAdapterKind | None = Field(
        default=None,
        description="Registered adapter kind that handled the embedding request, when applicable.",
    )
    failure_category: ProviderFailureCategory | None = Field(
        default=None,
        description="Structured provider failure category when embedding execution is rejected or degraded.",
    )
    model_id: str | None = Field(
        default=None,
        description="Embedding model identifier used for execution when one is available.",
    )
    stubbed: bool = Field(
        description="Whether embedding execution was handled by a stub provider path."
    )
    vector_dimension: int | None = Field(
        default=None,
        description="Dimension of the returned embedding vector, when execution succeeded.",
    )
    embedding: list[float] = Field(
        default_factory=list,
        description="Embedding vector returned by the provider layer when execution succeeded.",
    )
    message: str = Field(
        description="Human-readable embedding execution message returned by the provider layer."
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
    embedding_configuration: ProviderConfigurationStatusDescriptor = Field(
        description="Current rollout and configuration posture for future live embedding-provider activation."
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
    approval_gate: EvaluationApprovalGateSummaryDescriptor = Field(
        description="Runtime-backed approval evidence summary for the provider rollout domain."
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
    expansion_policy: ProviderExpansionPolicyDescriptor = Field(
        description="Bounded provider-expansion policy describing whether later provider breadth can be reviewed without weakening governance clarity."
    )
    blocking_area_count: int = Field(
        description="Number of top-level provider governance areas currently blocking activation."
    )
    governance_summary: list[str] = Field(
        description="Human-readable summary of the current provider governance posture."
    )
