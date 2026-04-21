from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.contracts.evidence import ExecutionEvidenceDescriptor
from app.contracts.workflow_pack_runs import (
    WorkflowPackRunReviewState,
    WorkflowPackRunRuntimeState,
    WorkflowPackRunSupportabilityStatus,
)


class WorkflowPackTaskFlowStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class WorkflowPackTaskFlowStepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


class WorkflowPackTaskFlowCheckpointTransition(str, Enum):
    FLOW_CREATED = "FLOW_CREATED"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCEEDED = "STEP_SUCCEEDED"
    STEP_FAILED = "STEP_FAILED"
    INPUT_REQUESTED = "INPUT_REQUESTED"
    REVIEW_REQUESTED = "REVIEW_REQUESTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    FLOW_BLOCKED = "FLOW_BLOCKED"
    FLOW_RETRIED = "FLOW_RETRIED"
    FLOW_CANCELLED = "FLOW_CANCELLED"
    FLOW_EXPIRED = "FLOW_EXPIRED"
    FLOW_SUPERSEDED = "FLOW_SUPERSEDED"
    FLOW_COMPLETED = "FLOW_COMPLETED"
    DOMAIN_HANDOFF_RECORDED = "DOMAIN_HANDOFF_RECORDED"


class WorkflowPackTaskFlowBlockingConditionType(str, Enum):
    MISSING_INPUT = "MISSING_INPUT"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"
    DEGRADED_STORE = "DEGRADED_STORE"
    UNSUPPORTED_CONSUMER = "UNSUPPORTED_CONSUMER"
    DOMAIN_HANDOFF_FAILED = "DOMAIN_HANDOFF_FAILED"
    REPLACEMENT_LINEAGE_CONFLICT = "REPLACEMENT_LINEAGE_CONFLICT"


class WorkflowPackTaskFlowBlockingConditionStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    SUPERSEDED = "SUPERSEDED"


class WorkflowPackTaskFlowHandoffStatus(str, Enum):
    NOT_READY = "NOT_READY"
    READY_FOR_HANDOFF = "READY_FOR_HANDOFF"
    HANDED_OFF = "HANDED_OFF"
    FAILED = "FAILED"


class WorkflowPackTaskFlowStepDescriptor(BaseModel):
    step_id: str = Field(min_length=1, description="Stable step identifier inside the task flow.")
    name: str = Field(min_length=1, description="Human-readable step name.")
    status: WorkflowPackTaskFlowStepStatus = Field(description="Current step lifecycle posture.")
    run_refs: list[str] = Field(
        default_factory=list,
        description="Workflow-pack run identifiers produced or consumed by this step.",
    )
    review_refs: list[str] = Field(
        default_factory=list,
        description="Review-state identifiers or run ids used for review posture at this step.",
    )
    checkpoint_refs: list[str] = Field(
        default_factory=list,
        description="Checkpoint identifiers recorded for this step.",
    )
    blocking_condition_refs: list[str] = Field(
        default_factory=list,
        description="Blocking-condition identifiers currently attached to this step.",
    )


class WorkflowPackTaskFlowReplacementLineageDescriptor(BaseModel):
    superseded_run_id: str = Field(
        min_length=1,
        description="Older workflow-pack run superseded by a newer run.",
    )
    replacement_run_id: str = Field(
        min_length=1,
        description="Newer workflow-pack run replacing the superseded run.",
    )
    review_action_ref: str | None = Field(
        default=None,
        description="Review action or event reference that created the replacement lineage.",
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable reason for replacement lineage.",
    )

    @model_validator(mode="after")
    def _replacement_must_not_point_to_self(
        self,
    ) -> "WorkflowPackTaskFlowReplacementLineageDescriptor":
        if self.superseded_run_id == self.replacement_run_id:
            raise ValueError("replacement_run_id must differ from superseded_run_id")
        return self


class WorkflowPackTaskFlowBlockingConditionDescriptor(BaseModel):
    condition_id: str = Field(min_length=1, description="Stable blocking-condition identifier.")
    condition_type: WorkflowPackTaskFlowBlockingConditionType = Field(
        description="Governed blocking-condition type."
    )
    status: WorkflowPackTaskFlowBlockingConditionStatus = Field(
        description="Current blocking-condition posture."
    )
    owner: str = Field(
        min_length=1,
        description="Service, caller, or workflow actor expected to resolve the condition.",
    )
    message: str = Field(min_length=1, description="Human-readable blocking-condition summary.")
    evidence_refs: list[ExecutionEvidenceDescriptor] = Field(
        min_length=1,
        description="Evidence references proving the blocking condition.",
    )


class WorkflowPackTaskFlowHandoffDescriptor(BaseModel):
    handoff_id: str = Field(min_length=1, description="Stable domain handoff identifier.")
    owner_service: str = Field(
        min_length=1,
        description="Domain service that owns the consequence-bearing handoff.",
    )
    status: WorkflowPackTaskFlowHandoffStatus = Field(description="Current handoff posture.")
    domain_ref: str | None = Field(
        default=None,
        description="Domain-owned workflow or object reference, when one has been created.",
    )
    evidence_refs: list[ExecutionEvidenceDescriptor] = Field(
        min_length=1,
        description="Evidence proving what was handed off or why handoff is blocked.",
    )


class WorkflowPackTaskFlowCheckpointDescriptor(BaseModel):
    checkpoint_id: str = Field(min_length=1, description="Stable checkpoint identifier.")
    task_flow_id: str = Field(
        min_length=1,
        description="Task-flow identifier this checkpoint belongs to.",
    )
    step_id: str = Field(min_length=1, description="Step identifier this checkpoint belongs to.")
    transition: WorkflowPackTaskFlowCheckpointTransition = Field(
        description="Governed transition recorded at this checkpoint."
    )
    actor: str = Field(min_length=1, description="Actor or subsystem that recorded the checkpoint.")
    recorded_at: str = Field(description="UTC timestamp when the checkpoint was recorded.")
    evidence_refs: list[ExecutionEvidenceDescriptor] = Field(
        min_length=1,
        description="Evidence references supporting this checkpoint.",
    )
    run_id: str | None = Field(
        default=None,
        description="Workflow-pack run identifier associated with this checkpoint, when applicable.",
    )
    review_ref: str | None = Field(
        default=None,
        description="Review-state reference associated with this checkpoint, when applicable.",
    )
    domain_handoff_ref: str | None = Field(
        default=None,
        description="Domain handoff reference associated with this checkpoint, when applicable.",
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable reason or decision summary for this checkpoint.",
    )
    degraded: bool = Field(
        default=False,
        description="Whether the checkpoint records degraded source posture.",
    )
    unsupported: bool = Field(
        default=False,
        description="Whether the checkpoint records unsupported consumer or transition posture.",
    )


class WorkflowPackTaskFlowDescriptor(BaseModel):
    task_flow_id: str = Field(min_length=1, description="Stable task-flow identifier.")
    workflow_pack_id: str = Field(min_length=1, description="Workflow-pack family identifier.")
    workflow_pack_version: str = Field(min_length=1, description="Workflow-pack version.")
    tenant_id: str | None = Field(
        default=None,
        description="Tenant identifier associated with the task flow, when known.",
    )
    caller: str = Field(min_length=1, description="Calling Lotus application or service.")
    desk_id: str | None = Field(
        default=None,
        description="Desk or rollout context associated with this task flow, when applicable.",
    )
    workflow_surface: str | None = Field(
        default=None,
        description="Named workflow surface associated with this task flow, when applicable.",
    )
    workflow_authority_owner: str = Field(
        min_length=1,
        description="Service boundary that retains consequence-bearing workflow authority.",
    )
    flow_status: WorkflowPackTaskFlowStatus = Field(
        description="Current task-flow lifecycle state."
    )
    current_step_id: str | None = Field(
        default=None,
        description="Current step identifier, when the flow has an active or waiting step.",
    )
    step_statuses: list[WorkflowPackTaskFlowStepDescriptor] = Field(
        min_length=1,
        description="Bounded step-state descriptors for this task flow.",
    )
    checkpoint_refs: list[str] = Field(
        default_factory=list,
        description="Checkpoint identifiers recorded for this task flow.",
    )
    run_refs: list[str] = Field(
        default_factory=list,
        description="Workflow-pack run identifiers linked to this task flow.",
    )
    review_refs: list[str] = Field(
        default_factory=list,
        description="Review-state references linked to this task flow.",
    )
    runtime_states: dict[str, WorkflowPackRunRuntimeState] = Field(
        default_factory=dict,
        description="Run-state snapshot by workflow-pack run id; does not replace the run ledger.",
    )
    review_states: dict[str, WorkflowPackRunReviewState] = Field(
        default_factory=dict,
        description="Review-state snapshot by review or run id; does not replace review contracts.",
    )
    replacement_lineage: list[WorkflowPackTaskFlowReplacementLineageDescriptor] = Field(
        default_factory=list,
        description="Explicit replacement lineage linked to this task flow.",
    )
    blocking_conditions: list[WorkflowPackTaskFlowBlockingConditionDescriptor] = Field(
        default_factory=list,
        description="Blocking conditions currently known for this task flow.",
    )
    handoff_refs: list[WorkflowPackTaskFlowHandoffDescriptor] = Field(
        default_factory=list,
        description="Domain handoff descriptors linked to this task flow.",
    )
    supportability_status: WorkflowPackRunSupportabilityStatus = Field(
        description="Shared supportability posture for this task flow."
    )
    created_at: str = Field(description="UTC timestamp when the task flow was created.")
    updated_at: str = Field(description="UTC timestamp when the task flow last changed.")
    expires_at: str | None = Field(
        default=None,
        description="UTC timestamp when the task flow expires, when applicable.",
    )
    authorization_evidence_ref: ExecutionEvidenceDescriptor = Field(
        description="Evidence proving registry/caller authorization was evaluated."
    )
    readiness_evidence_ref: ExecutionEvidenceDescriptor = Field(
        description="Evidence proving runtime and store readiness was evaluated."
    )

    @model_validator(mode="after")
    def _current_step_must_exist(self) -> "WorkflowPackTaskFlowDescriptor":
        step_ids = {step.step_id for step in self.step_statuses}
        if self.current_step_id is not None and self.current_step_id not in step_ids:
            raise ValueError("current_step_id must reference a declared step")
        if (
            self.flow_status
            in {
                WorkflowPackTaskFlowStatus.RUNNING,
                WorkflowPackTaskFlowStatus.WAITING_FOR_INPUT,
                WorkflowPackTaskFlowStatus.WAITING_FOR_REVIEW,
                WorkflowPackTaskFlowStatus.BLOCKED,
            }
            and self.current_step_id is None
        ):
            raise ValueError("active or waiting task flows require current_step_id")
        return self


class WorkflowPackTaskFlowCatalogResponse(BaseModel):
    service: str = Field(description="Service emitting the workflow-pack task-flow catalog.")
    phase: str = Field(description="Current lotus-ai delivery phase.")
    task_flow_store_mode: str = Field(description="Configured task-flow store mode.")
    task_flow_count: int = Field(description="Number of task flows returned after filtering.")
    active_count: int = Field(
        description="Returned task-flow count in active, waiting, or blocked posture."
    )
    waiting_for_review_count: int = Field(
        description="Returned task-flow count waiting for review."
    )
    blocked_count: int = Field(description="Returned task-flow count currently blocked.")
    terminal_count: int = Field(description="Returned task-flow count in terminal posture.")
    filters_applied: dict[str, object] = Field(
        description="Bounded filter set applied to the task-flow catalog."
    )
    task_flows: list[WorkflowPackTaskFlowDescriptor] = Field(
        description="Task-flow descriptors returned by the catalog query."
    )


class WorkflowPackTaskFlowDetailResponse(BaseModel):
    service: str = Field(description="Service emitting the workflow-pack task-flow detail.")
    phase: str = Field(description="Current lotus-ai delivery phase.")
    task_flow_store_mode: str = Field(description="Configured task-flow store mode.")
    task_flow: WorkflowPackTaskFlowDescriptor = Field(
        description="Task-flow descriptor for the requested task-flow id."
    )
    checkpoints: list[WorkflowPackTaskFlowCheckpointDescriptor] = Field(
        description="Recorded checkpoints for the requested task flow."
    )


class WorkflowPackTaskFlowCheckpointCatalogResponse(BaseModel):
    service: str = Field(description="Service emitting the task-flow checkpoint catalog.")
    phase: str = Field(description="Current lotus-ai delivery phase.")
    task_flow_store_mode: str = Field(description="Configured task-flow store mode.")
    task_flow_id: str = Field(description="Task-flow id used to load checkpoints.")
    checkpoint_count: int = Field(description="Number of checkpoints returned.")
    checkpoints: list[WorkflowPackTaskFlowCheckpointDescriptor] = Field(
        description="Recorded checkpoints for the requested task flow."
    )
