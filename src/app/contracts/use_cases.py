from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.tasks import OutputLabel, TaskCategory


class FirstUseCaseRolloutPosture(str, Enum):
    CONTRACT_DEFINED = "CONTRACT_DEFINED"


class FirstUseCaseOwnershipBoundary(BaseModel):
    owner: str = Field(description="Owning system or team for the boundary.")
    responsibility: str = Field(description="Bounded responsibility assigned to the owner.")


class FirstUseCaseContractField(BaseModel):
    field_name: str = Field(description="Stable structured input field name for the use case.")
    description: str = Field(description="Meaning of the field within the use-case contract.")


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
