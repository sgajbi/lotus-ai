from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.artifacts import ArtifactDescriptor
from app.contracts.evidence import ExecutionEvidenceDescriptor


class WorkflowPackRunRuntimeState(str, Enum):
    STAGED = "STAGED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class WorkflowPackRunReviewState(str, Enum):
    NOT_REVIEW_REQUIRED = "NOT_REVIEW_REQUIRED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    REVISED = "REVISED"
    SUPERSEDED = "SUPERSEDED"
    ABANDONED = "ABANDONED"


class WorkflowPackRunEventType(str, Enum):
    RUN_RECORDED = "RUN_RECORDED"
    REVIEW_STATE_UPDATED = "REVIEW_STATE_UPDATED"
    LINEAGE_UPDATED = "LINEAGE_UPDATED"


class WorkflowPackRunReviewActionType(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REVISE = "REVISE"
    SUPERSEDE = "SUPERSEDE"
    ABANDON = "ABANDON"


class WorkflowPackRunSupportabilityStatus(str, Enum):
    READY = "READY"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    HISTORICAL = "HISTORICAL"


class WorkflowPackRunFindingSeverity(str, Enum):
    INFO = "INFO"
    ACTION_REQUIRED = "ACTION_REQUIRED"


class WorkflowPackRunDescriptor(BaseModel):
    run_id: str = Field(description="Stable workflow-pack run identifier.")
    pack_id: str = Field(description="Workflow-pack family identifier.")
    pack_family: str = Field(description="Stable workflow-pack family grouping.")
    pack_version: str = Field(description="Workflow-pack version used for the run.")
    registration_ref: str = Field(
        description="Resolved workflow-pack registration reference used for the run."
    )
    task_id: str = Field(description="Lotus AI task identifier that produced the run.")
    request_id: str = Field(description="Stable lotus-ai request identifier for the run.")
    caller_app: str = Field(description="Calling Lotus application associated with the run.")
    correlation_id: str = Field(description="Caller-provided correlation identifier.")
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant identifier associated with the run.",
    )
    workflow_surface: str | None = Field(
        default=None,
        description="Named workflow surface associated with the run when one is known.",
    )
    workflow_authority_owner: str = Field(
        description="Service boundary that retains consequence-bearing workflow authority."
    )
    runtime_state: WorkflowPackRunRuntimeState = Field(
        description="Runtime execution state for the workflow-pack run."
    )
    review_state: WorkflowPackRunReviewState = Field(
        description="Review-state posture for the workflow-pack run."
    )
    allowed_review_actions: list[WorkflowPackRunReviewActionType] = Field(
        default_factory=list,
        description=(
            "Bounded ledger-level review actions currently compatible with the recorded run posture. "
            "These do not grant consequence-bearing workflow authority."
        ),
    )
    review_required: bool = Field(
        description="Whether the run is expected to enter a human-review flow."
    )
    provider_mode: str = Field(description="Provider mode recorded for the run.")
    stubbed: bool = Field(description="Whether the run was stub-backed.")
    output_preview: str = Field(description="Short preview of the generated workflow-pack output.")
    structured_output_keys: list[str] = Field(
        description="Sorted structured-output keys observed for the run."
    )
    evidence_descriptors: list[ExecutionEvidenceDescriptor] = Field(
        description="Reference-oriented execution evidence descriptors recorded for the run."
    )
    artifact_refs: list[ArtifactDescriptor] = Field(
        default_factory=list,
        description="Governed artifact references currently linked to the run.",
    )
    supersedes_run_id: str | None = Field(
        default=None,
        description="Prior workflow-pack run superseded by this run, when applicable.",
    )
    superseded_by_run_id: str | None = Field(
        default=None,
        description="Newer workflow-pack run that superseded this run, when applicable.",
    )
    created_at: str = Field(description="UTC timestamp when the run record was created.")
    completed_at: str | None = Field(
        default=None,
        description="UTC timestamp when the run reached its current terminal runtime state.",
    )
    last_updated_at: str = Field(description="UTC timestamp when the run record last changed.")


class WorkflowPackRunEventDescriptor(BaseModel):
    event_id: str = Field(description="Stable identifier for the workflow-pack run event.")
    run_id: str = Field(description="Workflow-pack run identifier affected by the event.")
    event_type: WorkflowPackRunEventType = Field(
        description="Type of workflow-pack run event that was recorded."
    )
    runtime_state: WorkflowPackRunRuntimeState = Field(
        description="Runtime state recorded at the time of the event."
    )
    review_state: WorkflowPackRunReviewState = Field(
        description="Review state recorded at the time of the event."
    )
    actor: str = Field(description="Actor or subsystem that recorded the event.")
    message: str = Field(description="Human-readable explanation of the event.")
    recorded_at: str = Field(description="UTC timestamp when the event was recorded.")


class WorkflowPackRunCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack run catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    run_store_mode: str = Field(description="Configured workflow-pack run-store mode.")
    run_count: int = Field(description="Number of workflow-pack run records currently exposed.")
    awaiting_review_count: int = Field(
        description="Number of workflow-pack runs currently awaiting review."
    )
    completed_count: int = Field(
        description="Number of workflow-pack runs currently in completed runtime posture."
    )
    latest_recorded_at: str | None = Field(
        default=None,
        description="Most recent run-record timestamp in the returned set.",
    )
    runs: list[WorkflowPackRunDescriptor] = Field(
        description="Workflow-pack run records available for operator inspection."
    )
    notes: list[str] = Field(
        description="Human-readable notes describing the current workflow-pack run-ledger posture."
    )


class WorkflowPackRunDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack run detail.")
    version: str = Field(description="Current lotus-ai service version.")
    run_store_mode: str = Field(description="Configured workflow-pack run-store mode.")
    run: WorkflowPackRunDescriptor = Field(
        description="Workflow-pack run record for the requested run identifier."
    )
    events: list[WorkflowPackRunEventDescriptor] = Field(
        description="Recorded workflow-pack run history for the requested run."
    )
    notes: list[str] = Field(
        description="Human-readable notes describing the current workflow-pack run detail posture."
    )


class WorkflowPackRunReviewActionRequest(BaseModel):
    action_type: WorkflowPackRunReviewActionType = Field(
        description="Requested review-state action for the workflow-pack run."
    )
    caller_app: str = Field(
        min_length=1,
        description="Caller application recording the review-state action.",
    )
    reviewed_by: str = Field(
        min_length=1,
        description="Reviewer or workflow actor recording the review-state action.",
    )
    reason: str = Field(
        min_length=1,
        description="Human-readable reason for the review-state action.",
    )
    replacement_run_id: str | None = Field(
        default=None,
        description="Replacement workflow-pack run identifier when the action creates revised or superseding lineage.",
    )


class WorkflowPackRunReviewActionResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the workflow-pack review action response."
    )
    version: str = Field(description="Current lotus-ai service version.")
    run: WorkflowPackRunDescriptor = Field(
        description="Workflow-pack run record after the review-state action completed."
    )
    events: list[WorkflowPackRunEventDescriptor] = Field(
        description="New workflow-pack run events recorded by the review-state action."
    )
    summary: list[str] = Field(
        description="Human-readable summary of the applied workflow-pack review-state action."
    )


class WorkflowPackRunConsumerRuntimeDescriptor(BaseModel):
    state: WorkflowPackRunRuntimeState = Field(
        description="Runtime execution posture for the workflow-pack run."
    )
    created_at: str = Field(description="UTC timestamp when the run record was created.")
    completed_at: str | None = Field(
        default=None,
        description="UTC timestamp when the run reached a terminal runtime posture, when available.",
    )
    last_updated_at: str = Field(description="UTC timestamp when the run record last changed.")
    provider_mode: str = Field(description="Provider mode recorded for the run.")
    stubbed: bool = Field(description="Whether the run was stub-backed.")


class WorkflowPackRunConsumerReviewDescriptor(BaseModel):
    required: bool = Field(
        description="Whether this workflow-pack run is expected to enter a review flow."
    )
    state: WorkflowPackRunReviewState = Field(
        description="Current review-state posture for the workflow-pack run."
    )
    allowed_actions: list[WorkflowPackRunReviewActionType] = Field(
        default_factory=list,
        description=(
            "Bounded ledger-compatible review actions currently accepted by lotus-ai for the run "
            "posture. These are not business-authority grants."
        ),
    )


class WorkflowPackRunConsumerLineageDescriptor(BaseModel):
    run_id: str = Field(description="Stable workflow-pack run identifier.")
    pack_id: str = Field(description="Workflow-pack family identifier.")
    pack_family: str = Field(description="Stable workflow-pack family grouping.")
    pack_version: str = Field(description="Workflow-pack version used for the run.")
    registration_ref: str = Field(
        description="Resolved workflow-pack registration reference used for the run."
    )
    task_id: str = Field(description="Lotus AI task identifier that produced the run.")
    request_id: str = Field(description="Stable lotus-ai request identifier for the run.")
    caller_app: str = Field(description="Calling Lotus application associated with the run.")
    correlation_id: str = Field(description="Caller-provided correlation identifier.")
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant identifier associated with the run.",
    )
    workflow_surface: str | None = Field(
        default=None,
        description="Named workflow surface associated with the run when one is known.",
    )
    workflow_authority_owner: str = Field(
        description="Service boundary that retains consequence-bearing workflow authority."
    )
    supersedes_run_id: str | None = Field(
        default=None,
        description="Prior workflow-pack run superseded by this run, when applicable.",
    )
    superseded_by_run_id: str | None = Field(
        default=None,
        description="Newer workflow-pack run that superseded this run, when applicable.",
    )


class WorkflowPackRunConsumerProvenanceDescriptor(BaseModel):
    output_preview: str = Field(description="Short preview of the generated workflow-pack output.")
    structured_output_keys: list[str] = Field(
        description="Sorted structured-output keys observed for the run."
    )
    evidence_descriptors: list[ExecutionEvidenceDescriptor] = Field(
        description="Reference-oriented execution evidence descriptors recorded for the run."
    )
    artifact_refs: list[ArtifactDescriptor] = Field(
        default_factory=list,
        description="Governed artifact references currently linked to the run.",
    )


class WorkflowPackRunConsumerViewResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack consumer view.")
    version: str = Field(description="Current lotus-ai service version.")
    run_store_mode: str = Field(description="Configured workflow-pack run-store mode.")
    runtime: WorkflowPackRunConsumerRuntimeDescriptor = Field(
        description="Consumer-facing runtime posture for the workflow-pack run."
    )
    review: WorkflowPackRunConsumerReviewDescriptor = Field(
        description="Consumer-facing review posture for the workflow-pack run."
    )
    lineage: WorkflowPackRunConsumerLineageDescriptor = Field(
        description="Consumer-facing lineage and ownership identity for the workflow-pack run."
    )
    provenance: WorkflowPackRunConsumerProvenanceDescriptor = Field(
        description="Consumer-facing provenance and output summary for the workflow-pack run."
    )
    notes: list[str] = Field(
        description="Human-readable notes describing the bounded consumer-contract posture."
    )


class WorkflowPackRunSupportabilityFinding(BaseModel):
    finding_id: str = Field(description="Stable supportability finding identifier.")
    severity: WorkflowPackRunFindingSeverity = Field(
        description="Operator-facing severity for the supportability finding."
    )
    summary: str = Field(description="Short human-readable summary of the finding.")
    detail: str = Field(description="Expanded operator-facing explanation of the finding.")


class WorkflowPackRunOperatorProfileResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack operator profile.")
    version: str = Field(description="Current lotus-ai service version.")
    run_store_mode: str = Field(description="Configured workflow-pack run-store mode.")
    run_id: str = Field(description="Stable workflow-pack run identifier.")
    pack_id: str = Field(description="Workflow-pack family identifier.")
    registration_ref: str = Field(
        description="Resolved workflow-pack registration reference used for the run."
    )
    runtime_state: WorkflowPackRunRuntimeState = Field(
        description="Current runtime posture for the workflow-pack run."
    )
    review_state: WorkflowPackRunReviewState = Field(
        description="Current review posture for the workflow-pack run."
    )
    workflow_authority_owner: str = Field(
        description="Service boundary that retains consequence-bearing workflow authority."
    )
    supportability_status: WorkflowPackRunSupportabilityStatus = Field(
        description="Overall operator-facing supportability posture for the run."
    )
    review_pending: bool = Field(
        description="Whether the run still requires human review before downstream use."
    )
    failed: bool = Field(description="Whether the run is currently in failed runtime posture.")
    expired: bool = Field(description="Whether the run is currently in expired runtime posture.")
    superseded: bool = Field(
        description="Whether the run is now historical because a newer replacement run exists."
    )
    partial_output_visible: bool = Field(
        description="Whether the run currently preserves some output despite not reaching a clean accepted terminal posture."
    )
    artifact_ref_count: int = Field(
        description="Number of governed artifact refs currently linked to the run."
    )
    evidence_descriptor_count: int = Field(
        description="Number of evidence descriptors currently linked to the run."
    )
    history_event_count: int = Field(
        description="Number of recorded workflow-pack run events currently linked to the run."
    )
    latest_event_at: str | None = Field(
        default=None,
        description="UTC timestamp for the most recent recorded workflow-pack run event.",
    )
    replacement_run_id: str | None = Field(
        default=None,
        description="Replacement workflow-pack run identifier when the current run is superseded or revised.",
    )
    current_summary_note: str = Field(
        description="Single operator-facing note summarizing the current run posture."
    )
    findings: list[WorkflowPackRunSupportabilityFinding] = Field(
        default_factory=list,
        description="Supportability findings operators should use when diagnosing or triaging the run.",
    )
    inspection_surfaces: list[str] = Field(
        default_factory=list,
        description="Primary workflow-pack inspection routes operators should use for this run.",
    )
    inspection_steps: list[str] = Field(
        default_factory=list,
        description="Ordered operator steps for diagnosing or escalating this run.",
    )
