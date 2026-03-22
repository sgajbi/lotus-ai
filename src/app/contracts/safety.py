from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.tasks import OutputLabel


class SafetyControlStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"
    ENFORCED = "ENFORCED"


class RedactionPosture(str, Enum):
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    MINIMIZATION_REQUIRED = "MINIMIZATION_REQUIRED"


class SafetyControlDescriptor(BaseModel):
    control_id: str = Field(description="Stable safety control identifier.")
    status: SafetyControlStatus = Field(description="Current enforcement status of the control.")
    description: str = Field(description="Human-readable description of the safety control.")


class TaskSafetyDescriptor(BaseModel):
    task_id: str = Field(description="Bounded lotus-ai task identifier.")
    output_label: OutputLabel = Field(description="Output label associated with the task.")
    redaction_posture: RedactionPosture = Field(
        description="Declared redaction and minimization posture for the task."
    )
    response_labeling_required: bool = Field(
        description="Whether response labeling is mandatory for the task."
    )
    intended_use_notes: str = Field(
        description="Human-readable intended-use guidance for the task output."
    )


class SafetyPolicyResponse(BaseModel):
    service: str = Field(description="Service name emitting the safety policy response.")
    version: str = Field(description="Current lotus-ai service version.")
    safety_mode: str = Field(description="Configured safety mode for lotus-ai.")
    controls: list[SafetyControlDescriptor] = Field(
        description="Cross-cutting safety controls known to lotus-ai."
    )
    task_policies: list[TaskSafetyDescriptor] = Field(
        description="Task-level safety posture for bounded lotus-ai capabilities."
    )
