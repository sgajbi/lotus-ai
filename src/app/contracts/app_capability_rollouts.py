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
