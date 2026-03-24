from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.evals import EvaluationApprovalGateSummaryDescriptor
from app.contracts.tasks import OutputLabel, TaskCategory


class FirstUseCaseRolloutPosture(str, Enum):
    CONTRACT_DEFINED = "CONTRACT_DEFINED"


class FirstUseCaseOperationalPosture(str, Enum):
    CONTRACT_DEFINED = "CONTRACT_DEFINED"
    LIMITED_ROLLOUT_BLOCKED = "LIMITED_ROLLOUT_BLOCKED"
    LIMITED_ROLLOUT_READY = "LIMITED_ROLLOUT_READY"


class FirstUseCaseOwnershipBoundary(BaseModel):
    owner: str = Field(description="Owning system or team for the boundary.")
    responsibility: str = Field(description="Bounded responsibility assigned to the owner.")


class FirstUseCaseContractField(BaseModel):
    field_name: str = Field(description="Stable structured input field name for the use case.")
    description: str = Field(description="Meaning of the field within the use-case contract.")


class FirstUseCaseReadinessItem(BaseModel):
    evidence_id: str = Field(description="Stable first-use-case readiness item identifier.")
    status: str = Field(description="Current readiness posture for this use-case requirement.")
    required_for_activation: bool = Field(
        description="Whether this readiness item must be complete before the first use case is treated as rollout-ready."
    )
    notes: str = Field(description="Human-readable explanation of the readiness item.")


class FirstUseCaseReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the first-use-case readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    use_case_id: str = Field(description="Stable identifier for the selected first use case.")
    downstream_app: str = Field(description="Named downstream integration owner for the use case.")
    readiness_ready: bool = Field(
        description="Whether the bounded first use case currently has sufficient technical evidence for limited governed onboarding."
    )
    required_item_count: int = Field(
        description="Number of first-use-case readiness items currently required."
    )
    completed_required_item_count: int = Field(
        description="Number of required first-use-case readiness items currently marked complete."
    )
    approval_gate: EvaluationApprovalGateSummaryDescriptor = Field(
        description="Runtime-backed evaluation approval-gate summary for the selected first use case."
    )
    items: list[FirstUseCaseReadinessItem] = Field(
        description="Governed readiness items for the selected first use case."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current first-use-case readiness posture."
    )


class FirstUseCaseRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable first-use-case runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before limited rollout."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class FirstUseCaseRunbookReadinessResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the first-use-case runbook readiness view."
    )
    version: str = Field(description="Current lotus-ai service version.")
    use_case_id: str = Field(description="Stable identifier for the selected first use case.")
    downstream_app: str = Field(description="Named downstream integration owner for the use case.")
    runbook_ready: bool = Field(
        description="Whether limited-rollout operational runbook readiness is sufficient for the first use case."
    )
    required_item_count: int = Field(
        description="Number of runbook items currently required before limited rollout."
    )
    completed_required_item_count: int = Field(
        description="Number of required runbook items currently marked complete."
    )
    items: list[FirstUseCaseRunbookReadinessItem] = Field(
        description="Governed runbook readiness items for the first production use case."
    )


class FirstUseCaseGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the first-use-case governance status.")
    version: str = Field(description="Current lotus-ai service version.")
    use_case_id: str = Field(description="Stable identifier for the selected first use case.")
    downstream_app: str = Field(description="Named downstream integration owner for the use case.")
    operational_posture: FirstUseCaseOperationalPosture = Field(
        description="Current bounded rollout posture for the first production use case."
    )
    governance_ready: bool = Field(
        description="Whether the first use case is ready for limited governed rollout."
    )
    readiness: FirstUseCaseReadinessResponse = Field(
        description="Current technical and runtime-backed readiness posture for the first use case."
    )
    runbook_readiness: FirstUseCaseRunbookReadinessResponse = Field(
        description="Current operational runbook readiness posture for the first use case."
    )
    blocking_area_count: int = Field(
        description="Number of governance areas currently blocking limited rollout."
    )
    governance_summary: list[str] = Field(
        description="Short operator-facing summary of the current first-use-case governance posture."
    )


class FirstUseCaseRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the first-use-case contract status.")
    version: str = Field(description="Current lotus-ai service version.")
    use_case_id: str = Field(description="Stable identifier for the selected first use case.")
    downstream_app: str = Field(description="Named downstream integration owner for the use case.")
    task_id: str = Field(description="Bounded lotus-ai task used by the first use case.")
    task_category: TaskCategory = Field(
        description="Task category used by the first production-oriented use case."
    )
    output_label: OutputLabel = Field(
        description="Expected output label for the selected first use case."
    )
    rollout_posture: FirstUseCaseRolloutPosture = Field(
        description="Current rollout posture for the first use-case onboarding contract."
    )
    contract_hardened: bool = Field(
        description="Whether the first-use-case request and ownership contract are explicitly defined."
    )
    downstream_contract_fields: list[FirstUseCaseContractField] = Field(
        description="Bounded structured fields expected from the downstream integration."
    )
    ownership_boundaries: list[FirstUseCaseOwnershipBoundary] = Field(
        description="Explicit ownership boundaries between lotus-ai and the downstream app."
    )
    dependency_summary: list[str] = Field(
        description="Runtime dependencies intentionally relied on by the first-use-case contract."
    )
    non_goals: list[str] = Field(
        description="Explicit behaviors that remain out of scope for the first-use-case contract."
    )
    status_summary: list[str] = Field(
        description="Human-readable summary of the current first-use-case onboarding posture."
    )
