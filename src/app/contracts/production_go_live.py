from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProductionGoLivePlatformState(str, Enum):
    TECHNICALLY_RUNNING = "TECHNICALLY_RUNNING"
    PRODUCTION_CAPABLE = "PRODUCTION_CAPABLE"
    PLATFORM_PRODUCTION_APPROVED = "PLATFORM_PRODUCTION_APPROVED"


class ProductionGoLiveUseCaseState(str, Enum):
    PRE_PROD_VALIDATION = "PRE_PROD_VALIDATION"
    LIMITED_ROLLOUT_ONLY = "LIMITED_ROLLOUT_ONLY"
    USE_CASE_PRODUCTION_APPROVED = "USE_CASE_PRODUCTION_APPROVED"


class ProductionGoLiveFreezeState(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ProductionGoLiveRollbackState(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    AVAILABLE = "AVAILABLE"
    RECOMMENDED = "RECOMMENDED"
    COMPLETED = "COMPLETED"


class ProductionGoLiveUseCaseApprovalState(str, Enum):
    PRE_PROD_VALIDATION = "PRE_PROD_VALIDATION"
    LIMITED_ROLLOUT_READY = "LIMITED_ROLLOUT_READY"
    PRODUCTION_BLOCKED = "PRODUCTION_BLOCKED"
    PRODUCTION_APPROVED = "PRODUCTION_APPROVED"


class ProductionGoLiveDomainStatus(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    INFORMATIONAL = "INFORMATIONAL"


class ProductionGoLiveDomainDescriptor(BaseModel):
    domain_id: str = Field(description="Stable production go-live approval domain identifier.")
    status: ProductionGoLiveDomainStatus = Field(
        description="Current production go-live posture for the approval domain."
    )
    required_for_platform_approval: bool = Field(
        description="Whether this approval domain must be approved before the platform can be treated as production-approved."
    )
    configured_mode: str = Field(
        description="Configured mode or rollout label currently associated with the approval domain."
    )
    review_surface: str = Field(
        description="Primary platform endpoint operators should use to review this approval domain."
    )
    detail: str = Field(
        description="Human-readable explanation of the current approval-domain posture."
    )


class ProductionGoLiveRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the production go-live runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    platform_state: ProductionGoLivePlatformState = Field(
        description="Current high-level platform production go-live state."
    )
    use_case_state: ProductionGoLiveUseCaseState = Field(
        description="Current high-level downstream use-case production go-live state."
    )
    technically_running: bool = Field(
        description="Whether the service is currently up and capable of serving bounded runtime traffic."
    )
    production_capable: bool = Field(
        description="Whether the runtime has crossed from local or demo posture into the RFC-0020 prod-shaped or production-ready baseline."
    )
    platform_production_approved: bool = Field(
        description="Whether the platform itself currently satisfies the bounded RFC-0022 platform approval posture."
    )
    use_case_production_approved: bool = Field(
        description="Whether the current named downstream use case is approved for active production traffic."
    )
    provider_freeze_state: ProductionGoLiveFreezeState = Field(
        description="Current production-only freeze posture for live-provider traffic."
    )
    provider_rollback_state: ProductionGoLiveRollbackState = Field(
        description="Current bounded rollback posture for live-provider traffic."
    )
    provider_rollback_target_state: str | None = Field(
        default=None,
        description="Bounded provider rollout state operators should target when rollback is required.",
    )
    approval_domain_count: int = Field(
        description="Number of production go-live approval domains included in this response."
    )
    blocked_domain_count: int = Field(
        description="Number of approval domains currently blocking platform production approval."
    )
    approval_domains: list[ProductionGoLiveDomainDescriptor] = Field(
        description="Bounded approval domains currently governing production go-live posture."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons the platform is not yet approved for production go-live."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current production go-live posture."
    )


class ProductionGoLiveActivationReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the production go-live activation-readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    runtime_status: ProductionGoLiveRuntimeStatusResponse = Field(
        description="Current runtime-backed production go-live posture."
    )
    provider_governance_ready: bool = Field(
        description="Whether provider governance is currently ready for production go-live review."
    )
    activation_ready: bool = Field(
        description="Whether platform production approval and live-provider production posture are both activatable without freeze or rollback blockers."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why production go-live activation remains blocked."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before production go-live can be treated as activatable."
    )


class ProductionGoLiveRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(
        description="Stable production go-live runbook readiness item identifier."
    )
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before production go-live activation."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class ProductionGoLiveRunbookReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the production go-live runbook-readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    runbook_ready: bool = Field(
        description="Whether production go-live operational runbook readiness is sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of production go-live runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required production go-live runbook items currently marked complete."
    )
    items: list[ProductionGoLiveRunbookReadinessItem] = Field(
        description="Governed production go-live operational runbook readiness items."
    )
    go_live_checklist: list[str] = Field(
        description="Short ordered operator checklist for final production go-live review."
    )


class ProductionGoLiveUseCaseApprovalItem(BaseModel):
    item_id: str = Field(description="Stable production go-live use-case approval item identifier.")
    status: str = Field(description="Current approval posture for the use-case criterion.")
    required_for_activation: bool = Field(
        description="Whether this criterion must be complete before the named use case can be treated as active-production-approved."
    )
    notes: str = Field(description="Human-readable explanation of the use-case approval criterion.")


class ProductionGoLiveUseCaseApprovalResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the production go-live use-case approval view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    use_case_id: str = Field(
        description="Stable identifier for the downstream use case under production approval review."
    )
    downstream_app: str = Field(description="Named downstream integration owner for the use case.")
    capability_pack_id: str = Field(
        description="Capability-pack identifier currently anchoring the downstream use case."
    )
    approval_state: ProductionGoLiveUseCaseApprovalState = Field(
        description="Current active-production approval posture for the named downstream use case."
    )
    limited_rollout_ready: bool = Field(
        description="Whether the named use case is currently governance-ready for bounded limited rollout."
    )
    active_production_ready: bool = Field(
        description="Whether the named use case is currently approved for active production traffic."
    )
    required_item_count: int = Field(
        description="Number of use-case production approval items currently required."
    )
    completed_required_item_count: int = Field(
        description="Number of required production approval items currently marked complete."
    )
    items: list[ProductionGoLiveUseCaseApprovalItem] = Field(
        description="Governed production-approval criteria for the named downstream use case."
    )
    status_summary: list[str] = Field(
        description="Short operator-facing summary of the current use-case production approval posture."
    )


class ProductionGoLiveGovernanceStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the production go-live governance status."
    )
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether production go-live governance is currently sufficient for approved live traffic."
    )
    runtime_status: ProductionGoLiveRuntimeStatusResponse = Field(
        description="Current runtime-backed production go-live posture."
    )
    activation_readiness: ProductionGoLiveActivationReadinessResponse = Field(
        description="Current activation-readiness posture for production go-live."
    )
    runbook_readiness: ProductionGoLiveRunbookReadinessResponse = Field(
        description="Current runbook-readiness posture for production go-live."
    )
    use_case_approval: ProductionGoLiveUseCaseApprovalResponse = Field(
        description="Current active-production approval posture for the named downstream use case."
    )
    provider_governance_ready: bool = Field(
        description="Whether provider governance is currently ready for approved live-provider traffic."
    )
    go_live_decision: str = Field(
        description="Short machine-readable go-live decision summarizing whether production traffic should remain blocked, stay limited-rollout-only, or be treated as approved."
    )
    blocking_area_count: int = Field(
        description="Number of top-level governance areas currently blocking production go-live."
    )
    governance_summary: list[str] = Field(
        description="Short operator-facing summary of current production go-live governance posture."
    )
