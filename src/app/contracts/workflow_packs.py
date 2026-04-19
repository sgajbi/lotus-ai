from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.tasks import TaskExecutionRequest, TaskExecutionResponse
from app.contracts.workflow_pack_runs import WorkflowPackRunDescriptor


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
    validation_rules: list[WorkflowPackValidationRuleDescriptor] = Field(
        description="Workflow-pack registration validation rules enforced for catalog entries."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current workflow-pack registry posture."
    )


class WorkflowPackRegistrationDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack registry detail.")
    version: str = Field(description="Current lotus-ai service version.")
    registration: WorkflowPackRegistrationDescriptor = Field(
        description="Workflow-pack registration record for the requested pack version."
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
