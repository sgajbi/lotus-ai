from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.runtime_readiness import StoreRuntimeStatusDescriptor


class AccessControlEnforcementState(str, Enum):
    REGISTRY_ONLY = "REGISTRY_ONLY"
    POLICY_RESOLUTION_READY = "POLICY_RESOLUTION_READY"
    DATA_PLANE_ENFORCED = "DATA_PLANE_ENFORCED"
    FULLY_ENFORCED = "FULLY_ENFORCED"


class TenantPolicyMode(str, Enum):
    OPTIONAL = "OPTIONAL"
    REQUIRED = "REQUIRED"
    RESTRICTED = "RESTRICTED"


class CallerLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class AuthorizationCapabilityType(str, Enum):
    TASK_EXECUTION = "task_execution"
    RETRIEVAL_EXECUTION = "retrieval_execution"
    LIVE_PROVIDER_EXECUTION = "live_provider_execution"
    ASYNC_CONTROL = "async_control"
    PROMPT_CONTROL = "prompt_control"
    PROVIDER_CONTROL = "provider_control"
    PLATFORM_READ = "platform_read"


class AuthorizationOutcome(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED_UNKNOWN_CALLER = "BLOCKED_UNKNOWN_CALLER"
    BLOCKED_CALLER_DISABLED = "BLOCKED_CALLER_DISABLED"
    BLOCKED_TASK_NOT_ALLOWED = "BLOCKED_TASK_NOT_ALLOWED"
    BLOCKED_RETRIEVAL_SOURCE_NOT_ALLOWED = "BLOCKED_RETRIEVAL_SOURCE_NOT_ALLOWED"
    BLOCKED_LIVE_PROVIDER_NOT_ALLOWED = "BLOCKED_LIVE_PROVIDER_NOT_ALLOWED"
    BLOCKED_ASYNC_CONTROL_NOT_ALLOWED = "BLOCKED_ASYNC_CONTROL_NOT_ALLOWED"
    BLOCKED_PROMPT_CONTROL_NOT_ALLOWED = "BLOCKED_PROMPT_CONTROL_NOT_ALLOWED"
    BLOCKED_PROVIDER_CONTROL_NOT_ALLOWED = "BLOCKED_PROVIDER_CONTROL_NOT_ALLOWED"
    BLOCKED_CALLER_IDENTITY_MISMATCH = "BLOCKED_CALLER_IDENTITY_MISMATCH"
    BLOCKED_TENANT_REQUIRED = "BLOCKED_TENANT_REQUIRED"
    BLOCKED_TENANT_NOT_ALLOWED = "BLOCKED_TENANT_NOT_ALLOWED"


class CallerPolicyDescriptor(BaseModel):
    caller_app: str = Field(description="Recognized caller application identifier.")
    lifecycle_status: CallerLifecycleStatus = Field(
        description="Current lifecycle posture for the caller registry entry."
    )
    description: str = Field(description="Human-readable description for the caller policy.")
    allowed_task_ids: list[str] = Field(
        default_factory=list,
        description="Task ids this caller is explicitly allowed to access when enforcement is active.",
    )
    allowed_retrieval_source_ids: list[str] = Field(
        default_factory=list,
        description="Retrieval sources this caller is explicitly allowed to access when enforcement is active.",
    )
    redaction_client_identifiers: list[str] = Field(
        default_factory=list,
        description="Caller-declared client identifiers the redaction engine removes from "
        "generated content as literal matches (issue #150); values never appear in findings.",
    )
    allow_live_provider: bool = Field(
        description="Whether this caller may use live provider execution when enforcement is active."
    )
    allow_async_control: bool = Field(
        description="Whether this caller may issue async control-plane actions when enforcement is active."
    )
    allow_prompt_control: bool = Field(
        description="Whether this caller may issue prompt control-plane actions when enforcement is active."
    )
    allow_provider_control: bool = Field(
        description="Whether this caller may issue provider control-plane actions when enforcement is active."
    )
    allow_audit_read_all_tenants: bool = Field(
        default=False,
        description="Whether this caller may inspect audit records across every tenant.",
    )
    tenant_policy_mode: TenantPolicyMode = Field(
        description="Whether tenant identity is optional, required, or restricted for this caller."
    )
    restricted_tenant_ids: list[str] = Field(
        default_factory=list,
        description="Explicit tenant ids allowed for this caller when tenant policy is restricted.",
    )


class AuthorizationDecision(BaseModel):
    caller_app: str = Field(description="Caller application evaluated by the access-control layer.")
    authenticated_caller_app: str | None = Field(
        default=None,
        description="Authenticated HTTP caller identity bound to this authorization decision, when present.",
    )
    caller_identity_source: str = Field(
        default="body_metadata_only",
        description="Source used to bind caller identity for this authorization decision.",
    )
    caller_identity_bound: bool = Field(
        default=False,
        description="Whether the request-declared caller matched an authenticated HTTP caller identity.",
    )
    capability_type: AuthorizationCapabilityType = Field(
        description="Capability class evaluated by the access-control layer."
    )
    outcome: AuthorizationOutcome = Field(
        description="Typed access-control outcome recorded for the evaluated request."
    )
    allowed: bool = Field(description="Whether the evaluated request was authorized.")
    tenant_policy_mode: TenantPolicyMode = Field(
        description="Tenant restriction mode used while resolving this authorization decision."
    )
    task_id: str | None = Field(
        default=None,
        description="Task identifier evaluated for authorization when the capability is task execution.",
    )
    requested_source_ids: list[str] = Field(
        default_factory=list,
        description="Caller-requested retrieval source filters considered during authorization.",
    )
    effective_source_ids: list[str] = Field(
        default_factory=list,
        description="Retrieval source filters authorized for execution after policy resolution.",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identity evaluated by the access-control layer when present.",
    )
    summary: str = Field(description="Human-readable explanation of the authorization outcome.")


class CallerPolicyCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the caller policy catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Configured caller policy store mode.")
    policy_count: int = Field(description="Number of caller policies returned in this response.")
    policies: list[CallerPolicyDescriptor] = Field(
        description="Recognized caller policies available to the access-control layer."
    )


class AccessControlRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the access-control runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Configured caller policy store mode.")
    store: StoreRuntimeStatusDescriptor = Field(
        description="Runtime readiness posture for the caller policy store."
    )
    enforcement_state: AccessControlEnforcementState = Field(
        description="Current access-control enforcement posture."
    )
    data_plane_enforced: bool = Field(
        description="Whether protected data-plane request paths are currently enforced through the caller policy registry."
    )
    control_plane_enforced: bool = Field(
        description="Whether protected control-plane action paths are currently enforced through the caller policy registry."
    )
    unknown_caller_policy: str = Field(
        description="Documented handling for unknown callers under the current posture."
    )
    tenant_isolation_active: bool = Field(
        description="Whether tenant restrictions are actively enforced by the runtime."
    )
    policy_count: int = Field(description="Number of recognized caller policies.")
    protected_surface_count: int = Field(
        description="Number of protected capability classes modeled by the caller policy registry."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of current access-control runtime posture."
    )


class AccessControlActivationReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the access-control activation readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    store_mode: str = Field(description="Configured caller policy store mode.")
    enforcement_state: AccessControlEnforcementState = Field(
        description="Current access-control enforcement posture."
    )
    activation_ready: bool = Field(
        description="Whether access-control posture is fully activatable as a durable shared-service control plane."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why access-control governance is not yet ready for fully durable activation."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before access-control rollout is fully ready."
    )


class AccessControlRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable access-control runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before full access-control activation."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class AccessControlRunbookReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the access-control runbook readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    runbook_ready: bool = Field(
        description="Whether access-control operational runbook readiness is sufficient for full activation."
    )
    required_item_count: int = Field(
        description="Number of access-control runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required access-control runbook items currently marked complete."
    )
    items: list[AccessControlRunbookReadinessItem] = Field(
        description="Governed access-control operational runbook readiness items."
    )


class AccessControlGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the access-control governance status.")
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether access-control governance is ready for enforced rollout."
    )
    store_mode: str = Field(description="Configured caller policy store mode.")
    enforcement_state: AccessControlEnforcementState = Field(
        description="Current access-control enforcement posture."
    )
    activation_readiness: AccessControlActivationReadinessResponse = Field(
        description="Current activation-readiness posture for access-control rollout."
    )
    runbook_readiness: AccessControlRunbookReadinessResponse = Field(
        description="Current runbook-readiness posture for access-control rollout."
    )
    policy_count: int = Field(description="Number of recognized caller policies.")
    tenant_restricted_policy_count: int = Field(
        description="Number of caller policies carrying explicit tenant restrictions."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking stronger enforcement posture."
    )
    governance_summary: list[str] = Field(
        description="Short operator-facing summary of current governance posture."
    )
