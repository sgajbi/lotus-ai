from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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


class WorkflowPackValidationRuleDescriptor(BaseModel):
    rule_id: str = Field(description="Stable workflow-pack registration validation rule identifier.")
    description: str = Field(
        description="Human-readable explanation of the registration validation rule."
    )


class WorkflowPackRegistrationDescriptor(BaseModel):
    pack_id: str = Field(description="Stable workflow-pack family identifier.")
    pack_family: str = Field(description="Stable family identifier grouping related workflow packs.")
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
    last_changed_at: str = Field(
        description="UTC timestamp when the registry record last changed."
    )
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
