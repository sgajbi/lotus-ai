from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.runtime_readiness import StoreRuntimeStatusDescriptor


class AccessControlEnforcementState(str, Enum):
    DOCUMENTARY_ONLY = "DOCUMENTARY_ONLY"
    POLICY_RESOLUTION_READY = "POLICY_RESOLUTION_READY"
    ENFORCED = "ENFORCED"


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


class AuthorizationOutcome(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED_UNKNOWN_CALLER = "BLOCKED_UNKNOWN_CALLER"
    BLOCKED_CALLER_DISABLED = "BLOCKED_CALLER_DISABLED"
    BLOCKED_TASK_NOT_ALLOWED = "BLOCKED_TASK_NOT_ALLOWED"
    BLOCKED_RETRIEVAL_SOURCE_NOT_ALLOWED = "BLOCKED_RETRIEVAL_SOURCE_NOT_ALLOWED"
    BLOCKED_LIVE_PROVIDER_NOT_ALLOWED = "BLOCKED_LIVE_PROVIDER_NOT_ALLOWED"
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
    tenant_policy_mode: TenantPolicyMode = Field(
        description="Whether tenant identity is optional, required, or restricted for this caller."
    )
    restricted_tenant_ids: list[str] = Field(
        default_factory=list,
        description="Explicit tenant ids allowed for this caller when tenant policy is restricted.",
    )


class AuthorizationDecision(BaseModel):
    caller_app: str = Field(description="Caller application evaluated by the access-control layer.")
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
