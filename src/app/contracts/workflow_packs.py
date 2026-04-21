from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.access_control import AuthorizationDecision
from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunDescriptor,
    WorkflowPackRunProvenanceSummaryDescriptor,
    WorkflowPackRunReviewSummaryDescriptor,
)
from app.contracts.workflow_pack_queue_policies import (
    WorkflowPackQueueLane,
    WorkflowPackQueuePolicyDescriptor,
)


class WorkflowPackRegistrationStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    REGISTERED = "REGISTERED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    WITHDRAWN = "WITHDRAWN"
    RETIRED = "RETIRED"


class WorkflowPackActivationState(str, Enum):
    DARK = "DARK"
    PILOT = "PILOT"
    LIMITED_ACTIVE = "LIMITED_ACTIVE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


class WorkflowPackExecutionMode(str, Enum):
    SYNCHRONOUS = "SYNCHRONOUS"
    ASYNCHRONOUS = "ASYNCHRONOUS"
    REVIEW_GATED = "REVIEW_GATED"


class WorkflowPackQueueAttentionType(str, Enum):
    LANE_SATURATED = "LANE_SATURATED"
    QUEUE_ITEM_STALE = "QUEUE_ITEM_STALE"


class WorkflowPackCallerIdentityClass(str, Enum):
    INTERNAL_SERVICE = "INTERNAL_SERVICE"
    BANKER_PRODUCT = "BANKER_PRODUCT"
    OPERATOR_SUPPORT = "OPERATOR_SUPPORT"
    PLATFORM_AUTOMATION = "PLATFORM_AUTOMATION"


class WorkflowPackEnvironment(str, Enum):
    LOCAL = "LOCAL"
    DEVELOPMENT = "DEVELOPMENT"
    QA = "QA"
    UAT = "UAT"
    PRODUCTION = "PRODUCTION"


class WorkflowPackEligibilityResult(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED_NOT_REGISTERED = "DENIED_NOT_REGISTERED"
    DENIED_NOT_ACTIVE = "DENIED_NOT_ACTIVE"
    DENIED_CALLER_SCOPE = "DENIED_CALLER_SCOPE"
    DENIED_ENVIRONMENT_SCOPE = "DENIED_ENVIRONMENT_SCOPE"
    DENIED_TENANT_SCOPE = "DENIED_TENANT_SCOPE"
    DENIED_SURFACE_SCOPE = "DENIED_SURFACE_SCOPE"
    DENIED_PAUSED = "DENIED_PAUSED"
    DENIED_RETIRED = "DENIED_RETIRED"
    DENIED_VALIDATION_STATUS = "DENIED_VALIDATION_STATUS"


class WorkflowPackControlActionType(str, Enum):
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    DEPRECATE = "DEPRECATE"
    RETIRE = "RETIRE"


class WorkflowPackDefinitionReferenceType(str, Enum):
    CONTRACT = "CONTRACT"
    SERVICE = "SERVICE"
    ROUTER = "ROUTER"
    TEST = "TEST"
    RFC = "RFC"
    UI_SURFACE = "UI_SURFACE"
    VALIDATION = "VALIDATION"


class WorkflowPackValidationRuleDescriptor(BaseModel):
    rule_id: str = Field(
        description="Stable workflow-pack registration validation rule identifier."
    )
    description: str = Field(
        description="Human-readable explanation of the registration validation rule."
    )


class WorkflowPackDefinitionReferenceDescriptor(BaseModel):
    reference_id: str = Field(
        description="Stable identifier for this workflow-pack definition reference."
    )
    repository: str = Field(description="Repository that contains the referenced artifact.")
    path: str = Field(description="Repository-relative path to the referenced artifact.")
    reference_type: WorkflowPackDefinitionReferenceType = Field(
        description="Artifact type represented by this workflow-pack definition reference."
    )
    required_for_registration: bool = Field(
        description="Whether this artifact is mandatory evidence for a truthful workflow-pack registration."
    )
    description: str = Field(
        description="Human-readable explanation of why this artifact matters for registration truth."
    )


class WorkflowPackExecutionBindingDescriptor(BaseModel):
    pack_id: str = Field(
        description="Workflow-pack family identifier bound for explicit execution."
    )
    version: str = Field(description="Workflow-pack version bound for explicit execution.")
    task_id: str = Field(
        description="Bounded lotus-ai task identifier used by the current explicit execution path."
    )
    default_workflow_surface: str = Field(
        description="Default workflow surface applied when the explicit execution request omits one."
    )
    required_payload_keys: list[str] = Field(
        description="Structured payload sections required by the current explicit execution binding."
    )


class WorkflowPackRegistrationDescriptor(BaseModel):
    pack_id: str = Field(description="Stable workflow-pack family identifier.")
    pack_family: str = Field(
        description="Stable family identifier grouping related workflow packs."
    )
    version: str = Field(description="Versioned executable contract for the workflow pack.")
    owner_repository: str = Field(
        description="Repository that owns the workflow-pack definition in code."
    )
    owner_service: str = Field(
        description="Service boundary that owns the workflow-pack definition contract."
    )
    truth_owner_services: list[str] = Field(
        description="Authoritative services this workflow pack is allowed to rely on for domain truth."
    )
    primary_use_case: str = Field(
        description="Primary bounded use case currently anchoring the workflow-pack family."
    )
    workflow_authority_owner: str = Field(
        description="Service or composition layer that owns consequence-bearing workflow authority."
    )
    default_execution_mode: WorkflowPackExecutionMode = Field(
        description="Default execution mode expected by the workflow-pack contract."
    )
    definition_ref: str = Field(
        description="Owning-repository reference pointing to the workflow-pack definition contract."
    )
    definition_refs: list["WorkflowPackDefinitionReferenceDescriptor"] = Field(
        description="Structured owner-artifact references grounding this workflow-pack registration in real Lotus repositories."
    )
    compatibility_contract_version: str = Field(
        description="Version of the shared workflow-pack compatibility contract this record satisfies."
    )
    registration_status: WorkflowPackRegistrationStatus = Field(
        description="Current control-plane registration posture for this workflow-pack version."
    )
    activation_state: WorkflowPackActivationState = Field(
        description="Current operational activation posture for this workflow-pack version."
    )
    registered_definition_digest: str = Field(
        description="Digest of the definition content registered into lotus-ai."
    )
    supported_callers: list[str] = Field(
        description="Caller applications currently eligible to request this workflow-pack version."
    )
    supported_identity_classes: list[WorkflowPackCallerIdentityClass] = Field(
        description="Bounded caller identity classes currently eligible for this workflow-pack version."
    )
    supported_environments: list[WorkflowPackEnvironment] = Field(
        description="Environments where this workflow-pack version may be activated."
    )
    tenant_scope: list[str] = Field(
        description="Explicit tenant or tenant-group scope when tenant-level activation narrowing applies."
    )
    surface_scope: list[str] = Field(
        description="Named workflow surfaces where this workflow-pack version may appear."
    )
    default_rollout_stage: str = Field(
        description="Default rollout stage currently modeled for the workflow-pack version."
    )
    pause_state: str = Field(
        description="Current emergency-pause posture for the workflow-pack version."
    )
    supersedes: str | None = Field(
        default=None,
        description="Older workflow-pack version superseded by this record, when applicable.",
    )
    superseded_by: str | None = Field(
        default=None,
        description="Newer workflow-pack version that supersedes this record, when applicable.",
    )
    registered_at: str = Field(description="UTC timestamp when the workflow-pack was registered.")
    registered_by: str = Field(
        description="Actor or automation identity that recorded the registration."
    )
    last_activated_at: str | None = Field(
        default=None,
        description="UTC timestamp when the activation state last moved into an executing posture.",
    )
    last_changed_at: str = Field(description="UTC timestamp when the registry record last changed.")
    status_summary: list[str] = Field(
        description="Human-readable summary of the current workflow-pack registration posture."
    )


class WorkflowPackRegistryCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack registry catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    registration_count: int = Field(
        description="Number of workflow-pack version registrations currently described."
    )
    registered_count: int = Field(
        description="Number of workflow-pack version registrations in REGISTERED posture."
    )
    production_eligible_count: int = Field(
        description="Number of workflow-pack version registrations whose declared environment scope includes production."
    )
    registrations: list[WorkflowPackRegistrationDescriptor] = Field(
        description="Workflow-pack registration records currently modeled by lotus-ai."
    )
    execution_bindings: list[WorkflowPackExecutionBindingDescriptor] = Field(
        description="Explicit workflow-pack execution bindings currently implemented by lotus-ai."
    )
    queue_policies: list[WorkflowPackQueuePolicyDescriptor] = Field(
        description="Explicit per-pack queue policies currently declared for executable workflow-pack versions."
    )
    validation_rules: list[WorkflowPackValidationRuleDescriptor] = Field(
        description="Workflow-pack registration validation rules enforced for catalog entries."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current workflow-pack registry posture."
    )


class WorkflowPackRuntimeStatusSummaryResponse(BaseModel):
    registration_count: int = Field(
        description="Number of workflow-pack version registrations currently described."
    )
    registered_count: int = Field(
        description="Number of workflow-pack version registrations in REGISTERED posture."
    )
    execution_binding_count: int = Field(
        description="Number of explicit workflow-pack execution bindings currently implemented by lotus-ai."
    )
    executable_registration_count: int = Field(
        description="Number of REGISTERED workflow-pack versions that also resolve through an explicit lotus-ai execution binding."
    )
    executable_review_required_count: int = Field(
        description="Number of explicitly executable workflow-pack versions whose default execution mode still requires human review."
    )
    executable_without_review_count: int = Field(
        description="Number of explicitly executable workflow-pack versions whose default execution mode does not require human review."
    )
    registered_without_execution_binding_count: int = Field(
        description="Number of REGISTERED workflow-pack versions that remain cataloged but are not yet executable through an explicit lotus-ai binding."
    )
    executable_registration_refs: list[str] = Field(
        description="Pack-version references currently both registered and explicitly executable through lotus-ai."
    )
    executable_review_required_refs: list[str] = Field(
        description="Executable pack-version references whose default execution mode still routes through a human-review gate."
    )
    executable_activity: list["WorkflowPackExecutableActivitySummaryResponse"] = Field(
        description="Per-pack activity summary for executable workflow-pack versions as observed through the bounded run ledger."
    )
    attention_queue: "WorkflowPackAttentionQueueSummaryResponse" = Field(
        description="Bounded estate-level queue of workflow-pack runs that currently require operator attention."
    )
    task_flow_attention: "WorkflowPackTaskFlowAttentionSummaryResponse" = Field(
        description="Bounded heartbeat-style attention summary for workflow-pack task flows."
    )
    queue_attention: "WorkflowPackQueueAttentionSummaryResponse" = Field(
        description="Bounded heartbeat-style attention summary for workflow-pack queue posture."
    )
    run_summary: "WorkflowPackRunRuntimeSummaryResponse" = Field(
        description="Estate-level workflow-pack run posture derived from the current bounded run ledger."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current workflow-pack runtime posture."
    )


class WorkflowPackRunRuntimeSummaryResponse(BaseModel):
    run_count: int = Field(
        description="Number of workflow-pack runs currently recorded in the ledger."
    )
    awaiting_review_count: int = Field(
        description="Number of workflow-pack runs currently awaiting human review."
    )
    accepted_count: int = Field(
        description="Number of workflow-pack runs currently accepted for bounded downstream use."
    )
    rejected_count: int = Field(
        description="Number of workflow-pack runs currently rejected by review-state posture."
    )
    abandoned_count: int = Field(
        description="Number of workflow-pack runs currently abandoned by review-state posture."
    )
    superseded_count: int = Field(
        description="Number of workflow-pack runs currently in revised or superseded historical posture."
    )
    failed_count: int = Field(
        description="Number of workflow-pack runs currently in failed runtime posture."
    )
    expired_count: int = Field(
        description="Number of workflow-pack runs currently in expired runtime posture."
    )
    action_required_count: int = Field(
        description="Number of workflow-pack runs currently in an estate-level posture that still requires operator attention."
    )
    latest_recorded_at: str | None = Field(
        default=None,
        description="Most recent workflow-pack run timestamp visible through the bounded ledger summary.",
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current workflow-pack run posture."
    )


class WorkflowPackExecutableActivitySummaryResponse(BaseModel):
    registration_ref: str = Field(
        description="Pack-version reference currently both registered and explicitly executable through lotus-ai."
    )
    pack_id: str = Field(description="Workflow-pack family identifier for the executable pack.")
    version: str = Field(description="Workflow-pack version for the executable pack.")
    run_count: int = Field(
        description="Number of ledgered workflow-pack runs recorded for this executable pack version."
    )
    awaiting_review_count: int = Field(
        description="Number of recorded runs for this executable pack version that are still awaiting review."
    )
    accepted_count: int = Field(
        description="Number of recorded runs for this executable pack version that are currently accepted."
    )
    ready_count: int = Field(
        description="Number of recorded runs for this executable pack version currently classified as supportable through the bounded ledger posture."
    )
    action_required_count: int = Field(
        description="Number of recorded runs for this executable pack version currently classified as requiring operator attention."
    )
    historical_count: int = Field(
        description="Number of recorded runs for this executable pack version currently classified as historical."
    )
    latest_action_required_run_id: str | None = Field(
        default=None,
        description="Most recent recorded workflow-pack run identifier for this executable pack version that still requires operator attention, when available.",
    )
    latest_action_required_recorded_at: str | None = Field(
        default=None,
        description="Most recent workflow-pack run timestamp for this executable pack version that still requires operator attention, when available.",
    )
    latest_action_required_review_summary: WorkflowPackRunReviewSummaryDescriptor | None = Field(
        default=None,
        description="Bounded review provenance for the most recent actionable run, when available.",
    )
    latest_action_required_provenance: WorkflowPackRunProvenanceSummaryDescriptor | None = Field(
        default=None,
        description="Bounded artifact and evidence linkage summary for the most recent actionable run, when available.",
    )
    latest_ready_run_id: str | None = Field(
        default=None,
        description="Most recent recorded workflow-pack run identifier for this executable pack version currently classified as ready, when available.",
    )
    latest_ready_recorded_at: str | None = Field(
        default=None,
        description="Most recent workflow-pack run timestamp for this executable pack version currently classified as ready, when available.",
    )
    latest_ready_review_summary: WorkflowPackRunReviewSummaryDescriptor | None = Field(
        default=None,
        description="Bounded review provenance for the most recent ready run, when available.",
    )
    latest_ready_provenance: WorkflowPackRunProvenanceSummaryDescriptor | None = Field(
        default=None,
        description="Bounded artifact and evidence linkage summary for the most recent ready run, when available.",
    )
    latest_run_id: str | None = Field(
        default=None,
        description="Most recent recorded workflow-pack run identifier for this executable pack version, when available.",
    )
    latest_recorded_at: str | None = Field(
        default=None,
        description="Most recent workflow-pack run timestamp for this executable pack version, when available.",
    )
    has_activity: bool = Field(
        description="Whether this executable pack version has any recorded workflow-pack run activity."
    )


class WorkflowPackAttentionQueueItemResponse(BaseModel):
    run_id: str = Field(description="Workflow-pack run identifier requiring operator attention.")
    registration_ref: str = Field(
        description="Pack-version reference associated with the actionable workflow-pack run."
    )
    pack_id: str = Field(description="Workflow-pack family identifier for the actionable run.")
    workflow_authority_owner: str = Field(
        description="Service boundary that retains consequence-bearing workflow authority for the run."
    )
    review_state: str = Field(description="Current review posture for the actionable run.")
    runtime_state: str = Field(description="Current runtime posture for the actionable run.")
    supportability_status: str = Field(
        description="Shared supportability classification currently causing the run to appear in the queue."
    )
    review_summary: WorkflowPackRunReviewSummaryDescriptor = Field(
        description="Bounded review provenance for the actionable workflow-pack run."
    )
    provenance: WorkflowPackRunProvenanceSummaryDescriptor = Field(
        description="Bounded artifact and evidence linkage summary for the actionable workflow-pack run."
    )
    created_at: str = Field(description="UTC timestamp when the actionable run was recorded.")


class WorkflowPackAttentionQueueSummaryResponse(BaseModel):
    queue_depth: int = Field(
        description="Total number of actionable workflow-pack runs currently awaiting operator attention across executable pack versions, even when the returned queue items are truncated by queue_limit."
    )
    queue_limit: int = Field(
        description="Maximum number of actionable workflow-pack runs returned in the bounded queue."
    )
    items: list[WorkflowPackAttentionQueueItemResponse] = Field(
        description="Most recent actionable workflow-pack runs across executable pack versions."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current workflow-pack operator-attention queue posture."
    )


class WorkflowPackTaskFlowAttentionItemResponse(BaseModel):
    task_flow_id: str = Field(description="Workflow-pack task-flow identifier requiring attention.")
    workflow_pack_id: str = Field(description="Workflow-pack family identifier for the task flow.")
    workflow_pack_version: str = Field(description="Workflow-pack version for the task flow.")
    flow_status: str = Field(description="Current task-flow lifecycle state.")
    supportability_status: str = Field(description="Current task-flow supportability posture.")
    current_step_id: str | None = Field(
        default=None,
        description="Current task-flow step identifier when the flow is active or waiting.",
    )
    run_refs: list[str] = Field(description="Workflow-pack run references linked to the task flow.")
    replacement_lineage_count: int = Field(
        description="Number of replacement-lineage edges linked to the task flow."
    )
    updated_at: str = Field(description="UTC timestamp when the task flow was last updated.")
    attention_reasons: list[str] = Field(
        description="Human-readable reasons why this task flow appears in the attention summary."
    )


class WorkflowPackTaskFlowAttentionSummaryResponse(BaseModel):
    heartbeat_status: str = Field(
        description="Heartbeat-style aggregate posture for task-flow attention."
    )
    attention_count: int = Field(
        description="Number of task flows currently requiring attention across the bounded task-flow catalog."
    )
    waiting_for_review_count: int = Field(
        description="Number of task flows currently waiting for review."
    )
    blocked_count: int = Field(description="Number of task flows currently blocked.")
    degraded_count: int = Field(
        description="Number of task flows with degraded or action-required supportability posture."
    )
    stale_count: int = Field(
        description="Number of active task flows whose updated timestamp exceeds the heartbeat stale threshold."
    )
    attention_limit: int = Field(description="Maximum number of attention items returned.")
    items: list[WorkflowPackTaskFlowAttentionItemResponse] = Field(
        description="Newest task-flow attention items up to the bounded attention limit."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of current task-flow attention posture."
    )


class WorkflowPackQueueAttentionItemResponse(BaseModel):
    attention_type: WorkflowPackQueueAttentionType = Field(
        description="Governed queue attention classification."
    )
    policy_id: str = Field(description="Queue policy identifier associated with the attention item.")
    workflow_pack_id: str = Field(description="Workflow-pack family identifier.")
    workflow_pack_version: str = Field(description="Workflow-pack version.")
    lane: WorkflowPackQueueLane = Field(description="Queue lane associated with the attention item.")
    queue_item_id: str | None = Field(
        default=None,
        description="Queue admission item identifier when attention is tied to one active item.",
    )
    active_count: int = Field(description="Current active admission count for the lane.")
    max_concurrent_runs_per_lane: int = Field(
        description="Configured concurrent admission limit for this lane."
    )
    admitted_at: str | None = Field(
        default=None,
        description="UTC timestamp when the queue item was admitted, when applicable.",
    )
    attention_reasons: list[str] = Field(
        description="Human-readable reasons why this queue posture requires attention."
    )


class WorkflowPackQueueAttentionSummaryResponse(BaseModel):
    heartbeat_status: str = Field(
        description="Heartbeat-style aggregate posture for queue attention."
    )
    attention_count: int = Field(
        description="Number of queue attention items currently requiring operator attention."
    )
    saturated_lane_count: int = Field(
        description="Number of queue lanes currently at or above their saturation attention threshold."
    )
    stale_item_count: int = Field(
        description="Number of active queue items older than their configured stale threshold."
    )
    active_admission_count: int = Field(
        description="Number of active queue admission leases in the source queue status."
    )
    queue_source_mode: str = Field(description="Queue source mode used for this attention summary.")
    attention_limit: int = Field(description="Maximum number of queue attention items returned.")
    items: list[WorkflowPackQueueAttentionItemResponse] = Field(
        description="Bounded queue attention items."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of current workflow-pack queue attention posture."
    )


class WorkflowPackRegistrationDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack registry detail.")
    version: str = Field(description="Current lotus-ai service version.")
    registration: WorkflowPackRegistrationDescriptor = Field(
        description="Workflow-pack registration record for the requested pack version."
    )
    execution_binding: WorkflowPackExecutionBindingDescriptor | None = Field(
        default=None,
        description="Explicit execution binding currently implemented for this workflow-pack version, when available.",
    )
    queue_policy: WorkflowPackQueuePolicyDescriptor | None = Field(
        default=None,
        description="Explicit queue policy for this workflow-pack version when the version is executable through lotus-ai.",
    )
    validation_rules: list[WorkflowPackValidationRuleDescriptor] = Field(
        description="Registration validation rules that apply to the requested workflow-pack version."
    )
    denied_without_registration: bool = Field(
        description="Whether lotus-ai should deny execution of this pack version if registry lookup fails."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current workflow-pack registration detail posture."
    )


class WorkflowPackEligibilityEvaluationRequest(BaseModel):
    pack_id: str = Field(description="Requested workflow-pack family identifier.")
    version: str = Field(description="Requested workflow-pack version.")
    caller_app: str = Field(description="Caller application requesting workflow-pack execution.")
    environment: WorkflowPackEnvironment = Field(
        description="Execution environment where the workflow-pack is being requested."
    )
    caller_identity_class: WorkflowPackCallerIdentityClass = Field(
        description="Bounded caller identity class requesting workflow-pack execution."
    )
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier when tenant-scoped activation applies.",
    )
    workflow_surface: str | None = Field(
        default=None,
        description="Named workflow surface where the pack is being requested.",
    )


class WorkflowPackEligibilityEvaluationResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack eligibility result.")
    version: str = Field(description="Current lotus-ai service version.")
    pack_id: str = Field(description="Requested workflow-pack family identifier.")
    requested_version: str = Field(description="Requested workflow-pack version.")
    eligibility_result: WorkflowPackEligibilityResult = Field(
        description="Explicit workflow-pack eligibility evaluation outcome."
    )
    allowed: bool = Field(description="Whether the requested workflow-pack execution is allowed.")
    evaluated_registration_ref: str | None = Field(
        default=None,
        description="Resolved workflow-pack registration reference when a registry record was found.",
    )
    caller_app: str = Field(description="Caller application evaluated by the workflow-pack policy.")
    environment: WorkflowPackEnvironment = Field(
        description="Environment evaluated by the workflow-pack policy."
    )
    caller_identity_class: WorkflowPackCallerIdentityClass = Field(
        description="Caller identity class evaluated by the workflow-pack policy."
    )
    tenant_scope_applied: bool = Field(
        description="Whether tenant-level scope was evaluated for this request."
    )
    workflow_surface_applied: bool = Field(
        description="Whether workflow-surface scope was evaluated for this request."
    )
    denial_reasons: list[str] = Field(
        description="Human-readable reasons explaining denied workflow-pack requests."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the workflow-pack eligibility decision."
    )


class WorkflowPackControlEventDescriptor(BaseModel):
    event_id: str = Field(description="Stable identifier for the workflow-pack control action.")
    pack_id: str = Field(description="Workflow-pack family identifier affected by the action.")
    version: str = Field(description="Workflow-pack version affected by the action.")
    action_type: WorkflowPackControlActionType = Field(
        description="Type of workflow-pack control action that was recorded."
    )
    requested_by: str = Field(description="Operator or system identity requesting the action.")
    approved_by: str = Field(description="Approver identity recorded for the action.")
    reason: str = Field(description="Human-readable reason for the workflow-pack control action.")
    prior_registration_status: WorkflowPackRegistrationStatus = Field(
        description="Registration status before the workflow-pack control action ran."
    )
    resulting_registration_status: WorkflowPackRegistrationStatus = Field(
        description="Registration status after the workflow-pack control action completed."
    )
    prior_activation_state: WorkflowPackActivationState = Field(
        description="Activation state before the workflow-pack control action ran."
    )
    resulting_activation_state: WorkflowPackActivationState = Field(
        description="Activation state after the workflow-pack control action completed."
    )
    caller_app: str = Field(
        description="Caller application issuing the workflow-pack control action."
    )
    authorization: AuthorizationDecision = Field(
        description="Caller-policy authorization decision recorded for the workflow-pack control action."
    )
    recorded_at: str = Field(
        description="UTC timestamp when the workflow-pack control action was recorded."
    )


class WorkflowPackControlHistoryResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack control history.")
    version: str = Field(description="Current lotus-ai service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    control_plane_store_mode: str = Field(
        description="Current workflow-pack control-plane store mode."
    )
    supported_action_types: list[WorkflowPackControlActionType] = Field(
        description="Supported workflow-pack control action types."
    )
    latest_events: list[WorkflowPackControlEventDescriptor] = Field(
        description="Most recent workflow-pack control-plane events."
    )
    notes: list[str] = Field(
        description="Human-readable notes describing workflow-pack control-plane durability and scope."
    )


class WorkflowPackControlActionRequest(BaseModel):
    pack_id: str = Field(description="Workflow-pack family identifier targeted by the action.")
    version: str = Field(description="Workflow-pack version targeted by the action.")
    action_type: WorkflowPackControlActionType = Field(
        description="Requested workflow-pack control action."
    )
    caller_app: str = Field(
        min_length=1,
        description="Caller application issuing the workflow-pack control action.",
    )
    requested_by: str = Field(
        min_length=1,
        description="Operator or system identity requesting the action.",
    )
    approved_by: str = Field(
        min_length=1,
        description="Approver identity authorizing the action.",
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable reason for the workflow-pack control action.",
    )


class WorkflowPackControlActionResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the workflow-pack control action response."
    )
    version: str = Field(description="Current lotus-ai service version.")
    event: WorkflowPackControlEventDescriptor = Field(
        description="Recorded workflow-pack control-plane event."
    )
    registration: WorkflowPackRegistrationDescriptor = Field(
        description="Workflow-pack registration state after the control action completed."
    )
    summary: list[str] = Field(
        description="Human-readable summary of the applied workflow-pack control action."
    )


class WorkflowPackExecutionRequest(BaseModel):
    pack_id: str = Field(description="Workflow-pack family identifier to execute.")
    version: str = Field(description="Workflow-pack version to execute.")
    environment: WorkflowPackEnvironment = Field(
        description="Execution environment where the workflow pack is being requested."
    )
    caller_identity_class: WorkflowPackCallerIdentityClass = Field(
        description="Bounded caller identity class requesting workflow-pack execution."
    )
    workflow_surface: str | None = Field(
        default=None,
        description="Named workflow surface requesting the workflow-pack execution.",
    )
    queue_lane: WorkflowPackQueueLane | None = Field(
        default=None,
        description="Optional governed queue lane requested for this explicit workflow-pack execution. Omit to use the pack policy default lane.",
    )
    task_request: TaskExecutionRequest = Field(
        description=(
            "Bounded lotus-ai task request that carries the structured execution context for the "
            "workflow pack."
        )
    )


class WorkflowPackExecutionResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack execution response.")
    version: str = Field(description="Current lotus-ai service version.")
    eligibility: WorkflowPackEligibilityEvaluationResponse = Field(
        description="Eligibility decision applied before the workflow-pack execution ran."
    )
    execution: TaskExecutionResponse = Field(
        description="Bounded task execution response emitted by the workflow-pack execution path."
    )
    workflow_pack_run: WorkflowPackRunDescriptor = Field(
        description="Workflow-pack run recorded for the explicit execution request."
    )
    summary: list[str] = Field(
        description="Human-readable summary of the explicit workflow-pack execution posture."
    )
