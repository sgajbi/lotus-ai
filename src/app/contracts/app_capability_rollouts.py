from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.capability_packs import CapabilityPackMaturityStage


class AppCapabilityRolloutStage(str, Enum):
    NOT_ONBOARDED = "NOT_ONBOARDED"
    INTEGRATION_IN_PROGRESS = "INTEGRATION_IN_PROGRESS"
    LIMITED_ROLLOUT = "LIMITED_ROLLOUT"
    ACTIVE_PRODUCTION = "ACTIVE_PRODUCTION"
    PAUSED_OR_ROLLED_BACK = "PAUSED_OR_ROLLED_BACK"
    RETIRED = "RETIRED"


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
    notes: str = Field(
        description="Human-readable explanation of the current transition posture."
    )


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


class AppCapabilityRolloutCatalogResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the app-capability rollout catalog."
    )
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
