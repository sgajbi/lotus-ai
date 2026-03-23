from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SafetyControlStatus(str, Enum):
    DOCUMENTED = "DOCUMENTED"
    ENFORCED = "ENFORCED"


class RedactionPosture(str, Enum):
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    MINIMIZATION_REQUIRED = "MINIMIZATION_REQUIRED"


class SafetyExecutionDisposition(str, Enum):
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    ENFORCED_PASSTHROUGH = "ENFORCED_PASSTHROUGH"
    ENFORCED_REDACTED = "ENFORCED_REDACTED"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"


class SafetyControlExecutionState(str, Enum):
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    ENFORCED = "ENFORCED"


class SafetyControlDescriptor(BaseModel):
    control_id: str = Field(description="Stable safety control identifier.")
    status: SafetyControlStatus = Field(description="Current enforcement status of the control.")
    description: str = Field(description="Human-readable description of the safety control.")


class SafetyControlExecutionResult(BaseModel):
    control_id: str = Field(description="Stable safety control identifier.")
    execution_state: SafetyControlExecutionState = Field(
        description="How the control participated in the execution."
    )
    summary: str = Field(description="Human-readable explanation of the control execution state.")


class TaskSafetyDescriptor(BaseModel):
    task_id: str = Field(description="Bounded lotus-ai task identifier.")
    output_label: str = Field(description="Output label associated with the task.")
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


class SafetyRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the safety runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    safety_mode: str = Field(description="Configured lotus-ai safety mode.")
    runtime_redaction_active: bool = Field(
        description="Whether any runtime redaction engine is currently active."
    )
    runtime_redaction_disposition: SafetyExecutionDisposition = Field(
        description="Current runtime safety disposition for redaction-requiring outputs."
    )
    enforced_control_ids: list[str] = Field(
        description="Safety controls currently enforced at runtime."
    )
    documented_only_control_ids: list[str] = Field(
        description="Safety controls that are documented but not runtime-enforced yet."
    )
    supported_execution_dispositions: list[SafetyExecutionDisposition] = Field(
        description="Safety execution dispositions the current runtime can truthfully emit."
    )
    task_policy_count: int = Field(description="Number of task-level safety policies exposed.")


class SafetyExecutionOutcome(BaseModel):
    safety_mode: str = Field(
        description="Configured lotus-ai safety mode applied to the execution."
    )
    output_label: str = Field(description="Output label attached to the executed task.")
    redaction_posture: RedactionPosture = Field(
        description="Redaction posture associated with the executed task."
    )
    disposition: SafetyExecutionDisposition = Field(
        description="Resolved runtime safety disposition for the execution."
    )
    runtime_redaction_active: bool = Field(
        description="Whether runtime redaction enforcement was active for the execution."
    )
    enforced_controls: list[str] = Field(
        description="Stable identifiers for safety controls enforced for the execution."
    )
    control_results: list[SafetyControlExecutionResult] = Field(
        description="Typed per-control execution results for the execution."
    )
    decision_summary: str = Field(
        description="Human-readable explanation of the resolved safety decision."
    )
