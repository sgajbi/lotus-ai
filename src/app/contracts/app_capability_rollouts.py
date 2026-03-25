from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.capability_packs import CapabilityPackMaturityStage
from app.contracts.capability_packs import (
    CapabilityPackAdoptionChecklistItem,
    CapabilityPackAdoptionCriterion,
)


class AppCapabilityRolloutStage(str, Enum):
    NOT_ONBOARDED = "NOT_ONBOARDED"
    INTEGRATION_IN_PROGRESS = "INTEGRATION_IN_PROGRESS"
    LIMITED_ROLLOUT = "LIMITED_ROLLOUT"
    ACTIVE_PRODUCTION = "ACTIVE_PRODUCTION"
    PAUSED_OR_ROLLED_BACK = "PAUSED_OR_ROLLED_BACK"
    RETIRED = "RETIRED"


class AppCapabilityEstateVisibilityState(str, Enum):
    BLOCKED = "BLOCKED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    RETIRED = "RETIRED"


class AppCapabilityRetirementScope(str, Enum):
    PAIRING_ONLY = "PAIRING_ONLY"
    PAIRING_WITH_GLOBAL_PACK_REVIEW = "PAIRING_WITH_GLOBAL_PACK_REVIEW"


class AppCapabilityRolloutDescriptor(BaseModel):
    downstream_app: str = Field(
        description="Downstream Lotus application represented by this app-capability rollout record."
    )
    capability_pack_id: str = Field(
        description="Capability-pack identifier represented by this rollout record."
    )
    capability_pack_family_id: str = Field(
        description="Capability-pack family identifier represented by this rollout record."
    )
    capability_pack_maturity_stage: CapabilityPackMaturityStage = Field(
        description="Current global capability-pack maturity stage, kept distinct from app-specific rollout stage."
    )
    rollout_stage: AppCapabilityRolloutStage = Field(
        description="Current app-specific rollout stage for the app-capability pairing."
    )
    currently_onboarded: bool = Field(
        description="Whether the app-capability pairing has moved beyond not-onboarded posture."
    )
    current_anchor_use_case_id: str | None = Field(
        default=None,
        description="Current implemented use-case anchor for the app-capability pairing, when one exists.",
    )
    rollout_review_surface: str = Field(
        description="Primary platform endpoint operators should use to review rollout truth for this pairing."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current app-capability rollout posture."
    )


class AppCapabilityOwnershipBoundary(BaseModel):
    owner: str = Field(description="Named owner for this app-capability rollout responsibility.")
    responsibility: str = Field(
        description="Bounded responsibility currently assigned to the named owner."
    )
    notes: str = Field(description="Human-readable explanation of the ownership boundary.")


class AppCapabilityEscalationItem(BaseModel):
    escalation_id: str = Field(description="Stable escalation or support-path identifier.")
    status: str = Field(description="Current posture for the escalation path.")
    notes: str = Field(description="Human-readable explanation of the escalation path.")


class AppCapabilityRolloutTransitionDescriptor(BaseModel):
    target_stage: AppCapabilityRolloutStage = Field(
        description="Target rollout stage represented by this transition descriptor."
    )
    allowed_now: bool = Field(
        description="Whether the represented transition is currently allowed for the pairing."
    )
    notes: str = Field(description="Human-readable explanation of the current transition posture.")


class AppCapabilityRolloutDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the app-capability rollout detail.")
    version: str = Field(description="Current lotus-ai service version.")
    record: AppCapabilityRolloutDescriptor = Field(
        description="Current rollout descriptor for the requested app-capability pairing."
    )
    ownership_boundaries: list[AppCapabilityOwnershipBoundary] = Field(
        description="Current ownership boundaries for the requested app-capability pairing."
    )
    escalation_paths: list[AppCapabilityEscalationItem] = Field(
        description="Current support and escalation posture for the requested app-capability pairing."
    )
    transition_targets: list[AppCapabilityRolloutTransitionDescriptor] = Field(
        description="Current allowed and blocked rollout transitions for the requested pairing."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the detailed app-capability rollout posture."
    )


class AppCapabilityRolloutGovernanceItem(BaseModel):
    item_id: str = Field(
        description="Stable governance item identifier for the app-capability pairing."
    )
    status: str = Field(description="Current posture for the governance item.")
    required_for_rollout: bool = Field(
        description="Whether the governance item must be satisfied before the pairing is rollout-ready."
    )
    notes: str = Field(description="Human-readable explanation of the governance item.")


class AppCapabilityRolloutGovernanceStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the app-capability rollout governance status."
    )
    version: str = Field(description="Current lotus-ai service version.")
    record: AppCapabilityRolloutDescriptor = Field(
        description="Current rollout descriptor for the requested app-capability pairing."
    )
    governance_ready: bool = Field(
        description="Whether the pairing currently has explicit ownership, escalation, and rollout-governance posture."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking the app-capability pairing."
    )
    ownership_boundaries: list[AppCapabilityOwnershipBoundary] = Field(
        description="Current ownership boundaries for the requested app-capability pairing."
    )
    escalation_paths: list[AppCapabilityEscalationItem] = Field(
        description="Current support and escalation posture for the requested app-capability pairing."
    )
    transition_targets: list[AppCapabilityRolloutTransitionDescriptor] = Field(
        description="Current allowed and blocked rollout transitions for the requested pairing."
    )
    items: list[AppCapabilityRolloutGovernanceItem] = Field(
        description="Governed ownership and rollout items for the requested pairing."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current app-capability governance posture."
    )


class AppCapabilityRolloutGovernanceSummaryItem(BaseModel):
    downstream_app: str = Field(
        description="Downstream application represented by the rollout-governance summary item."
    )
    capability_pack_id: str = Field(
        description="Capability-pack identifier represented by the rollout-governance summary item."
    )
    governance_ready: bool = Field(
        description="Whether the represented app-capability pairing currently satisfies its bounded governance posture."
    )
    rollout_stage: AppCapabilityRolloutStage = Field(
        description="Current rollout stage for the represented app-capability pairing."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking the represented pairing."
    )


class AppCapabilityRolloutCatalogGovernanceStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the app-capability rollout catalog governance view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether all currently modeled app-capability pairings satisfy bounded ownership and rollout governance posture."
    )
    ready_pairing_count: int = Field(
        description="Number of app-capability pairings currently satisfying bounded governance posture."
    )
    blocking_pairing_count: int = Field(
        description="Number of app-capability pairings currently blocked in governance review."
    )
    pairing_summaries: list[AppCapabilityRolloutGovernanceSummaryItem] = Field(
        description="Bounded governance summaries for currently modeled app-capability pairings."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of catalog-level app-capability rollout governance posture."
    )


class AppCapabilityOnboardingTemplateResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the app-capability onboarding template."
    )
    version: str = Field(description="Current lotus-ai service version.")
    template_id: str = Field(
        description="Stable identifier for the app-capability onboarding template."
    )
    downstream_app: str = Field(
        description="Downstream application represented by the onboarding template."
    )
    capability_pack_id: str = Field(
        description="Capability-pack identifier represented by the onboarding template."
    )
    current_rollout_stage: AppCapabilityRolloutStage = Field(
        description="Current app-specific rollout stage for the pairing."
    )
    based_on_pack_template_id: str = Field(
        description="Capability-pack adoption template currently reused by this app-capability onboarding template."
    )
    reference_use_case_template_id: str | None = Field(
        default=None,
        description="Reference use-case onboarding template currently reused by this app-capability onboarding template, when one exists.",
    )
    checklist: list[CapabilityPackAdoptionChecklistItem] = Field(
        description="Reusable onboarding checklist items for the app-capability pairing."
    )
    approval_criteria: list[CapabilityPackAdoptionCriterion] = Field(
        description="Reusable approval criteria for the app-capability pairing."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current app-capability onboarding posture."
    )


class AppCapabilityRolloutObservabilityItem(BaseModel):
    downstream_app: str = Field(
        description="Downstream application represented by the estate-observability summary item."
    )
    capability_pack_id: str = Field(
        description="Capability-pack identifier represented by the estate-observability summary item."
    )
    rollout_stage: AppCapabilityRolloutStage = Field(
        description="Current rollout stage for the represented app-capability pairing."
    )
    estate_visibility_state: AppCapabilityEstateVisibilityState = Field(
        description="Estate-wide visibility posture for the represented app-capability pairing."
    )
    governance_ready: bool = Field(
        description="Whether the represented app-capability pairing currently satisfies its bounded governance posture."
    )
    sampled_audit_record_count: int = Field(
        description="Number of bounded audit records currently sampled for the represented pairing."
    )
    sampled_async_job_count: int = Field(
        description="Number of bounded async job records currently sampled for the represented pairing."
    )
    incident_signal_count: int = Field(
        description="Number of sampled bounded incident-like signals currently associated with the represented pairing."
    )
    linked_endpoints: list[str] = Field(
        description="Linked operator-facing endpoints for reviewing this pairing's rollout and incident posture."
    )


class AppCapabilityRolloutObservabilitySummaryResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the app-capability rollout observability summary."
    )
    version: str = Field(description="Current lotus-ai service version.")
    observability_ready: bool = Field(
        description="Whether estate-wide rollout visibility is currently reviewable through bounded app-capability observability surfaces."
    )
    pairing_count: int = Field(
        description="Number of app-capability pairings currently summarized in the estate-observability view."
    )
    active_pairing_count: int = Field(
        description="Number of summarized pairings currently in active rollout visibility posture."
    )
    blocked_pairing_count: int = Field(
        description="Number of summarized pairings currently in blocked rollout visibility posture."
    )
    paused_pairing_count: int = Field(
        description="Number of summarized pairings currently in paused rollout visibility posture."
    )
    retired_pairing_count: int = Field(
        description="Number of summarized pairings currently in retired rollout visibility posture."
    )
    observed_pairing_count: int = Field(
        description="Number of summarized pairings with at least one bounded audit or async sample."
    )
    items: list[AppCapabilityRolloutObservabilityItem] = Field(
        description="Bounded estate-wide rollout observability items across current app-capability pairings."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current estate-wide app-capability rollout visibility posture."
    )


class AppCapabilityLifecycleItem(BaseModel):
    item_id: str = Field(
        description="Stable lifecycle-discipline item identifier for the app-capability pairing."
    )
    status: str = Field(description="Current posture for the lifecycle-discipline item.")
    required_for_retirement: bool = Field(
        description="Whether the lifecycle item must be satisfied before the pairing can be retired safely."
    )
    notes: str = Field(description="Human-readable explanation of the lifecycle-discipline item.")


class AppCapabilityRolloutLifecycleStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the app-capability rollout lifecycle status."
    )
    version: str = Field(description="Current lotus-ai service version.")
    record: AppCapabilityRolloutDescriptor = Field(
        description="Current rollout descriptor for the requested app-capability pairing."
    )
    lifecycle_ready: bool = Field(
        description="Whether the requested app-capability pairing currently satisfies bounded lifecycle-discipline posture."
    )
    retirement_ready_now: bool = Field(
        description="Whether the requested app-capability pairing currently has enough lifecycle discipline to be retired safely."
    )
    historical_traceability_ready: bool = Field(
        description="Whether traceability surfaces are in place to review the pairing after pause, rollback, or retirement."
    )
    retirement_scope: AppCapabilityRetirementScope = Field(
        description="Whether retiring the pairing is a pairing-only lifecycle action or should trigger broader capability-pack follow-on review."
    )
    retirement_rationale_summary: list[str] = Field(
        description="Bounded reasons and review notes that should be preserved when considering retirement of the pairing."
    )
    traceability_endpoints: list[str] = Field(
        description="Linked endpoints operators should use to inspect lifecycle history and retirement rationale for the pairing."
    )
    items: list[AppCapabilityLifecycleItem] = Field(
        description="Governed lifecycle-discipline items for the requested app-capability pairing."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current app-capability lifecycle posture."
    )


class AppCapabilityRolloutLifecycleSummaryItem(BaseModel):
    downstream_app: str = Field(
        description="Downstream application represented by the rollout-lifecycle summary item."
    )
    capability_pack_id: str = Field(
        description="Capability-pack identifier represented by the rollout-lifecycle summary item."
    )
    rollout_stage: AppCapabilityRolloutStage = Field(
        description="Current rollout stage for the represented app-capability pairing."
    )
    lifecycle_ready: bool = Field(
        description="Whether the represented app-capability pairing currently satisfies bounded lifecycle discipline."
    )
    retirement_ready_now: bool = Field(
        description="Whether the represented app-capability pairing could currently be retired safely."
    )
    historical_traceability_ready: bool = Field(
        description="Whether traceability surfaces are currently in place for the represented app-capability pairing."
    )
    retirement_scope: AppCapabilityRetirementScope = Field(
        description="Whether the represented pairing's retirement is pairing-only or should trigger broader capability-pack review."
    )


class AppCapabilityRolloutCatalogLifecycleStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the app-capability rollout catalog lifecycle view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    lifecycle_ready: bool = Field(
        description="Whether all currently modeled app-capability pairings satisfy bounded lifecycle-discipline posture."
    )
    ready_pairing_count: int = Field(
        description="Number of app-capability pairings currently satisfying lifecycle-discipline posture."
    )
    blocking_pairing_count: int = Field(
        description="Number of app-capability pairings currently blocked in lifecycle-discipline review."
    )
    pairing_summaries: list[AppCapabilityRolloutLifecycleSummaryItem] = Field(
        description="Bounded lifecycle-discipline summaries for currently modeled app-capability pairings."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of catalog-level app-capability lifecycle posture."
    )


class AppCapabilityRolloutCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the app-capability rollout catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    pairing_count: int = Field(
        description="Number of app-capability rollout records currently described."
    )
    onboarded_pairing_count: int = Field(
        description="Number of app-capability rollout records currently beyond not-onboarded posture."
    )
    active_pairing_count: int = Field(
        description="Number of app-capability rollout records currently in limited-rollout or active-production posture."
    )
    downstream_app_count: int = Field(
        description="Number of distinct downstream applications currently represented in the rollout catalog."
    )
    rollout_records: list[AppCapabilityRolloutDescriptor] = Field(
        description="Bounded app-capability rollout records currently modeled by lotus-ai."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of current app-capability rollout posture."
    )
