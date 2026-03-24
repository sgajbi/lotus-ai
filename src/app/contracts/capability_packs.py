from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.evals import (
    EvaluationApprovalEvidenceState,
    EvaluationApprovalGateSummaryDescriptor,
)
from app.contracts.tasks import OutputLabel


class CapabilityPackMaturityStage(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    REUSABLE = "REUSABLE"
    APPROVED = "APPROVED"


class CapabilityPackFamilyKind(str, Enum):
    COMMENTARY = "COMMENTARY"
    EXPLANATION = "EXPLANATION"


class CapabilityPackDescriptor(BaseModel):
    pack_id: str = Field(description="Stable identifier for the app-facing capability pack.")
    family_id: str = Field(description="Stable family identifier grouping related packs.")
    family_kind: CapabilityPackFamilyKind = Field(
        description="Primary product family kind represented by the capability pack."
    )
    maturity_stage: CapabilityPackMaturityStage = Field(
        description="Current product-maturity stage for the capability pack."
    )
    primary_task_id: str = Field(
        description="Bounded lotus-ai task currently used as the primary runtime backbone for the pack."
    )
    output_label: OutputLabel = Field(
        description="Expected output label for the pack's bounded response family."
    )
    current_anchor_use_case_id: str | None = Field(
        default=None,
        description="Current implemented use case used as the nearest runtime anchor for this pack, when present.",
    )
    reusable_across_apps: bool = Field(
        description="Whether the pack is currently considered reusable across multiple Lotus applications."
    )
    intended_downstream_patterns: list[str] = Field(
        description="Kinds of downstream integration patterns this pack is intended to support."
    )
    governance_surface_ids: list[str] = Field(
        description="Primary platform surfaces used to review this pack's readiness and governance posture."
    )
    adoption_template_endpoint: str = Field(
        description="Primary platform endpoint downstream teams should use to inspect the pack-oriented adoption template."
    )
    quality_gate_domain_id: str = Field(
        description="Named evaluation approval-gate domain currently used to assess this capability pack."
    )
    quality_gate_ready: bool = Field(
        description="Whether the capability pack currently has sufficient runtime-backed quality evidence."
    )
    quality_evidence_state: EvaluationApprovalEvidenceState = Field(
        description="Current runtime-backed quality evidence posture for the capability pack."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current capability-pack posture."
    )


class CapabilityPackQualityExpectation(BaseModel):
    expectation_id: str = Field(description="Stable identifier for the pack quality expectation.")
    description: str = Field(description="Human-readable product quality expectation for the pack.")


class CapabilityPackUnsupportedInputBehavior(BaseModel):
    behavior_id: str = Field(
        description="Stable identifier for unsupported or incomplete input behavior."
    )
    description: str = Field(
        description="Human-readable explanation of how the pack should behave on unsupported input."
    )


class CapabilityPackCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the capability-pack catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    pack_count: int = Field(
        description="Number of app-facing capability packs currently described."
    )
    reusable_pack_count: int = Field(
        description="Number of capability packs currently considered reusable across multiple apps."
    )
    approved_pack_count: int = Field(
        description="Number of capability packs currently considered approved."
    )
    packs: list[CapabilityPackDescriptor] = Field(
        description="Bounded app-facing capability packs currently described by lotus-ai."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current capability-pack catalog posture."
    )


class CapabilityPackDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the capability-pack detail.")
    version: str = Field(description="Current lotus-ai service version.")
    pack: CapabilityPackDescriptor = Field(
        description="Bounded descriptor for the requested capability pack."
    )
    quality_expectations: list[CapabilityPackQualityExpectation] = Field(
        description="Pack-specific quality expectations for grounded and supportable output."
    )
    unsupported_input_behaviors: list[CapabilityPackUnsupportedInputBehavior] = Field(
        description="Pack-specific unsupported or incomplete input handling expectations."
    )
    approval_gate: EvaluationApprovalGateSummaryDescriptor = Field(
        description="Runtime-backed evaluation approval-gate summary for this capability pack."
    )
    non_goals: list[str] = Field(
        description="Explicit behaviors this capability pack does not authorize."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current capability-pack detail posture."
    )


class CapabilityPackActivationReadinessItem(BaseModel):
    item_id: str = Field(description="Stable capability-pack activation readiness item identifier.")
    status: str = Field(description="Current activation-readiness posture for the item.")
    required_for_activation: bool = Field(
        description="Whether this item must be complete before the pack is activation-ready."
    )
    notes: str = Field(description="Human-readable explanation of the activation requirement.")


class CapabilityPackActivationReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the capability-pack activation view.")
    version: str = Field(description="Current lotus-ai service version.")
    pack_id: str = Field(description="Stable capability-pack identifier under review.")
    activation_ready: bool = Field(
        description="Whether the capability pack currently meets its bounded activation requirements."
    )
    required_item_count: int = Field(
        description="Number of activation-readiness items currently required for the pack."
    )
    completed_required_item_count: int = Field(
        description="Number of required activation-readiness items currently marked complete."
    )
    items: list[CapabilityPackActivationReadinessItem] = Field(
        description="Governed activation-readiness items for the capability pack."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current capability-pack activation posture."
    )


class CapabilityPackRunbookReadinessItem(BaseModel):
    item_id: str = Field(description="Stable capability-pack runbook-readiness item identifier.")
    status: str = Field(description="Current runbook-readiness posture for the item.")
    required_for_activation: bool = Field(
        description="Whether this item must be complete before the pack is operationally ready."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class CapabilityPackRunbookReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the capability-pack runbook view.")
    version: str = Field(description="Current lotus-ai service version.")
    pack_id: str = Field(description="Stable capability-pack identifier under review.")
    runbook_ready: bool = Field(
        description="Whether the capability pack currently meets its bounded runbook requirements."
    )
    required_item_count: int = Field(
        description="Number of runbook-readiness items currently required for the pack."
    )
    completed_required_item_count: int = Field(
        description="Number of required runbook-readiness items currently marked complete."
    )
    items: list[CapabilityPackRunbookReadinessItem] = Field(
        description="Governed runbook-readiness items for the capability pack."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current capability-pack runbook posture."
    )


class CapabilityPackObservabilitySummaryResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the capability-pack observability view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    pack_id: str = Field(description="Stable capability-pack identifier under review.")
    observability_ready: bool = Field(
        description="Whether the bounded observability and support-review surface for the pack is available."
    )
    sampled_audit_record_count: int = Field(
        description="Number of bounded recent audit records currently associated with the pack."
    )
    sampled_async_job_count: int = Field(
        description="Number of bounded async jobs currently associated with the pack."
    )
    incident_signal_count: int = Field(
        description="Number of bounded recent incident signals currently associated with the pack."
    )
    observed_caller_apps: list[str] = Field(
        description="Caller applications observed in the bounded recent pack sample."
    )
    linked_endpoints: list[str] = Field(
        description="Existing platform endpoints used to inspect pack usage, evidence, or support posture."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current capability-pack observability posture."
    )


class CapabilityPackGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the capability-pack governance view.")
    version: str = Field(description="Current lotus-ai service version.")
    pack_id: str = Field(description="Stable capability-pack identifier under review.")
    governance_ready: bool = Field(
        description="Whether the capability pack currently satisfies activation, runbook, and observability governance posture."
    )
    activation_readiness: CapabilityPackActivationReadinessResponse = Field(
        description="Current bounded activation-readiness posture for the capability pack."
    )
    runbook_readiness: CapabilityPackRunbookReadinessResponse = Field(
        description="Current bounded runbook-readiness posture for the capability pack."
    )
    observability: CapabilityPackObservabilitySummaryResponse = Field(
        description="Current bounded observability and support-review posture for the capability pack."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking the capability pack."
    )
    governance_summary: list[str] = Field(
        description="Human-readable summary of the current capability-pack governance posture."
    )


class CapabilityPackGovernanceSummaryItem(BaseModel):
    pack_id: str = Field(
        description="Stable capability-pack identifier represented in the summary."
    )
    governance_ready: bool = Field(
        description="Whether the represented pack currently satisfies bounded governance posture."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking the represented pack."
    )
    quality_evidence_state: EvaluationApprovalEvidenceState = Field(
        description="Current runtime-backed quality evidence posture for the represented pack."
    )


class CapabilityPackCatalogGovernanceStatusResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the capability-pack catalog governance view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    governance_ready: bool = Field(
        description="Whether all currently modeled capability packs satisfy their bounded governance posture."
    )
    ready_pack_count: int = Field(
        description="Number of currently modeled packs whose bounded governance posture is ready."
    )
    blocking_pack_count: int = Field(
        description="Number of currently modeled packs still blocked in governance review."
    )
    pack_summaries: list[CapabilityPackGovernanceSummaryItem] = Field(
        description="Bounded per-pack governance summaries for the current catalog."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current catalog-level capability-pack governance posture."
    )


class CapabilityPackAdoptionChecklistItem(BaseModel):
    checklist_id: str = Field(description="Stable pack-adoption checklist item identifier.")
    phase: str = Field(description="Onboarding phase where this pack-adoption item applies.")
    required: bool = Field(
        description="Whether this checklist item is required before pack-oriented onboarding."
    )
    notes: str = Field(description="Human-readable guidance for the pack-adoption item.")


class CapabilityPackAdoptionCriterion(BaseModel):
    criterion_id: str = Field(description="Stable pack-adoption approval criterion identifier.")
    criterion_name: str = Field(description="Short name for the pack-adoption criterion.")
    evaluation_surface: str = Field(
        description="Primary platform endpoint used to review this pack-adoption criterion."
    )
    pass_condition: str = Field(
        description="Human-readable condition that must hold before the criterion is treated as satisfied."
    )


class CapabilityPackAdoptionTemplateResponse(BaseModel):
    service: str = Field(description="Service name emitting the capability-pack adoption template.")
    version: str = Field(description="Current lotus-ai service version.")
    template_id: str = Field(
        description="Stable identifier for the pack-oriented adoption template."
    )
    pack_id: str = Field(description="Capability-pack identifier this template is anchored to.")
    current_reference_use_case_id: str | None = Field(
        default=None,
        description="Currently implemented use case anchoring this pack template, when one exists.",
    )
    downstream_patterns: list[str] = Field(
        description="Kinds of downstream application patterns this pack template is intended to support."
    )
    recommended_caller_apps: list[str] = Field(
        description="Caller applications or app categories most immediately suitable for the pack."
    )
    checklist: list[CapabilityPackAdoptionChecklistItem] = Field(
        description="Reusable pack-oriented onboarding checklist items."
    )
    approval_criteria: list[CapabilityPackAdoptionCriterion] = Field(
        description="Reusable pack-oriented approval criteria."
    )
    lessons_learned: list[str] = Field(
        description="Captured lessons for later downstream teams adopting this pack."
    )
    non_goals: list[str] = Field(
        description="Explicit behaviors this pack-oriented adoption template does not authorize."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current pack-oriented adoption posture."
    )
