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


class WorkflowPackRunRecoveryActionType(str, Enum):
    RETRY = "RETRY"
    REPLAY = "REPLAY"


class WorkflowPackRunFindingSeverity(str, Enum):
    INFO = "INFO"
    ACTION_REQUIRED = "ACTION_REQUIRED"


class WorkflowPackRunRecoveryLineageDescriptor(BaseModel):
    recovery_action_type: WorkflowPackRunRecoveryActionType = Field(
        description="Queue recovery action that produced this run."
    )
    source_queue_item_id: str = Field(
        description="Queue item whose retained request snapshot was used for recovery execution."
    )
    recovery_decision_event_id: str = Field(
        description="Queue event id that recorded the retry or replay decision."
    )
    recovery_attempt_number: int | None = Field(
        default=None,
        ge=1,
        description="Retry or replay attempt number recorded by queue recovery policy.",
    )
    source_workflow_pack_run_id: str | None = Field(
        default=None,
        description="Original workflow-pack run id when recoverable from structured run evidence.",
    )
    requested_by: str | None = Field(
        default=None,
        description="Operator, caller, or automation actor that requested recovery.",
    )
    evidence_ref: str | None = Field(
        default=None,
        description="Bounded evidence reference supporting the recovery execution.",
    )


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
    supportability_status: WorkflowPackRunSupportabilityStatus = Field(
        description="Shared supportability posture for the workflow-pack run."
    )
    allowed_review_actions: list[WorkflowPackRunReviewActionType] = Field(
        default_factory=list,
        description=(
            "Bounded ledger-level review actions currently compatible with the recorded run posture. "
            "These do not grant consequence-bearing workflow authority."
        ),
    )
    review_summary: WorkflowPackRunReviewSummaryDescriptor = Field(
        description=(
            "Bounded review-progression summary for the workflow-pack run so catalog consumers do "
            "not need raw event history to understand current review provenance."
        )
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
    replacement_run_id: str | None = Field(
        default=None,
        description="Replacement workflow-pack run identifier when the current run is revised or superseded.",
    )
    recovery_lineage: WorkflowPackRunRecoveryLineageDescriptor | None = Field(
        default=None,
        description="Bounded queue recovery lineage when this run was created by retry or replay.",
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


class WorkflowPackSourceEventType(str, Enum):
    AI_WORKFLOW_PACK_RUN_RECORDED = "AI_WORKFLOW_PACK_RUN_RECORDED"
    AI_WORKFLOW_PACK_REVIEW_STATE_UPDATED = "AI_WORKFLOW_PACK_REVIEW_STATE_UPDATED"
    AI_WORKFLOW_PACK_LINEAGE_UPDATED = "AI_WORKFLOW_PACK_LINEAGE_UPDATED"


class WorkflowPackSourceEventDescriptor(BaseModel):
    event_identity: str = Field(
        description=(
            "Stable source-event identity using "
            "source_system:source_type:source_id:content_hash_or_content_hash_unavailable."
        )
    )
    event_type: WorkflowPackSourceEventType = Field(
        description="AI-owned source-event type projected from the workflow-pack run ledger."
    )
    source_system: str = Field(description="Source system that owns the event.")
    source_type: str = Field(description="Source object type for the event.")
    source_id: str = Field(description="Source object identifier for the event.")
    content_hash: str = Field(
        description=(
            "Checksum for the bounded workflow-pack output artifact when available, otherwise "
            "content_hash_unavailable."
        )
    )
    portfolio_id: str | None = Field(
        default=None,
        description=(
            "Portfolio identifier extracted from bounded structured-output metadata when present. "
            "The source-event projection never reconstructs portfolio-memory facts."
        ),
    )
    run_id: str = Field(description="Workflow-pack run identifier that produced the source event.")
    pack_id: str = Field(description="Workflow-pack family identifier.")
    pack_version: str = Field(description="Workflow-pack version.")
    caller_app: str = Field(description="Calling Lotus application associated with the run.")
    tenant_id: str | None = Field(default=None, description="Tenant identifier when known.")
    workflow_surface: str | None = Field(
        default=None,
        description="Workflow surface associated with the run when known.",
    )
    workflow_authority_owner: str = Field(
        description="Service boundary retaining consequence-bearing workflow authority."
    )
    runtime_state: WorkflowPackRunRuntimeState = Field(
        description="Runtime state recorded for the workflow-pack run."
    )
    review_state: WorkflowPackRunReviewState = Field(
        description="Review-state posture recorded for the workflow-pack run."
    )
    supportability_status: WorkflowPackRunSupportabilityStatus = Field(
        description="Supportability posture derived from the workflow-pack run state."
    )
    portfolio_memory_status: str = Field(
        description="Whether bounded portfolio-memory lineage was supplied to the run."
    )
    portfolio_memory_content_hash: str = Field(
        description="Portfolio-memory context hash when supplied, otherwise an empty string."
    )
    event_ref_count: int = Field(
        description="Number of bounded source event references represented by the AI run output."
    )
    retention_policy: str = Field(description="Retention policy for the source-event projection.")
    redaction_policy: str = Field(description="Redaction posture for the source-event projection.")
    audit_policy: str = Field(description="Audit posture for the source-event projection.")
    access_classification: str = Field(
        description="Access classification for the source-event projection."
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="Bounded upstream source references used by the workflow-pack run.",
    )
    artifact_refs: list[ArtifactDescriptor] = Field(
        default_factory=list,
        description="Governed artifact references linked to the source event.",
    )
    evidence_descriptor_count: int = Field(
        description="Number of execution evidence descriptors linked to the source event."
    )
    recovery_lineage: WorkflowPackRunRecoveryLineageDescriptor | None = Field(
        default=None,
        description="Bounded queue recovery lineage when this source event came from retry or replay.",
    )
    recorded_at: str = Field(description="UTC timestamp when the source event was recorded.")


class WorkflowPackSourceEventCatalogResponse(BaseModel):
    service: str = Field(
        description="Service name emitting the workflow-pack source-event catalog."
    )
    version: str = Field(description="Current lotus-ai service version.")
    run_store_mode: str = Field(description="Configured workflow-pack run-store mode.")
    event_count: int = Field(description="Number of AI-owned source events returned.")
    filters_applied: dict[str, str | int] = Field(
        default_factory=dict,
        description="Bounded query filters applied while building the source-event catalog.",
    )
    ready_count: int = Field(
        description="Number of returned source events backed by ready workflow-pack run posture."
    )
    action_required_count: int = Field(
        description="Number of returned source events backed by action-required run posture."
    )
    historical_count: int = Field(
        description="Number of returned source events backed by historical run posture."
    )
    no_raw_payloads: bool = Field(
        description="Whether this source-event surface omits raw prompt, raw output, and raw portfolio-memory payloads."
    )
    source_authority_policy: str = Field(
        description="Source-authority policy enforced by the source-event projection."
    )
    events: list[WorkflowPackSourceEventDescriptor] = Field(
        description="AI-owned source events projected from workflow-pack run-ledger truth."
    )
    notes: list[str] = Field(
        description="Human-readable notes describing current source-event projection posture."
    )


class WorkflowPackRunSourceEventResponse(BaseModel):
    service: str = Field(description="Service name emitting workflow-pack run source events.")
    version: str = Field(description="Current lotus-ai service version.")
    run_store_mode: str = Field(description="Configured workflow-pack run-store mode.")
    run_id: str = Field(description="Workflow-pack run identifier.")
    event_count: int = Field(description="Number of source events projected for the run.")
    no_raw_payloads: bool = Field(
        description="Whether this source-event surface omits raw prompt, raw output, and raw portfolio-memory payloads."
    )
    source_authority_policy: str = Field(
        description="Source-authority policy enforced by the source-event projection."
    )
    events: list[WorkflowPackSourceEventDescriptor] = Field(
        description="AI-owned source events projected for the requested workflow-pack run."
    )
    notes: list[str] = Field(
        description="Human-readable notes describing the requested run source-event posture."
    )


class WorkflowPackRunCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the workflow-pack run catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    run_store_mode: str = Field(description="Configured workflow-pack run-store mode.")
    run_count: int = Field(description="Number of workflow-pack run records currently exposed.")
    filters_applied: dict[str, str | int] = Field(
        default_factory=dict,
        description="Bounded query filters applied while building the workflow-pack run catalog.",
    )
    awaiting_review_count: int = Field(
        description="Number of workflow-pack runs currently awaiting review."
    )
    completed_count: int = Field(
        description="Number of workflow-pack runs currently in completed runtime posture."
    )
    ready_count: int = Field(
        description="Number of returned workflow-pack runs currently in ready supportability posture."
    )
    action_required_count: int = Field(
        description="Number of returned workflow-pack runs currently in action-required supportability posture."
    )
    historical_count: int = Field(
        description="Number of returned workflow-pack runs currently in historical supportability posture."
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
    review: WorkflowPackRunConsumerReviewDescriptor = Field(
        description="Shared review-progression posture for the requested workflow-pack run."
    )
    provenance: WorkflowPackRunProvenanceSummaryDescriptor = Field(
        description="Bounded artifact and evidence linkage summary for the requested workflow-pack run."
    )
    supportability: WorkflowPackRunConsumerSupportabilityDescriptor = Field(
        description="Shared supportability posture for the requested workflow-pack run."
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


class WorkflowPackRunReviewSummaryDescriptor(BaseModel):
    latest_review_event_at: str | None = Field(
        default=None,
        description="UTC timestamp for the most recent recorded review-state transition, when available.",
    )
    latest_review_actor: str | None = Field(
        default=None,
        description="Actor recorded on the most recent review-state transition event, when available.",
    )
    review_transition_count: int = Field(
        description="Number of recorded review-state transition events currently linked to the run."
    )
    has_review_history: bool = Field(
        description="Whether any review-state transition has already been recorded for the run."
    )


class WorkflowPackRunConsumerReviewDescriptor(WorkflowPackRunReviewSummaryDescriptor):
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
    recovery_lineage: WorkflowPackRunRecoveryLineageDescriptor | None = Field(
        default=None,
        description="Bounded queue recovery lineage when this run was created by retry or replay.",
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


class WorkflowPackRunProvenanceSummaryDescriptor(BaseModel):
    artifact_ref_count: int = Field(
        description="Number of governed artifact refs currently linked to the run."
    )
    artifact_types: list[str] = Field(
        default_factory=list,
        description="Sorted distinct governed artifact types currently linked to the run.",
    )
    evidence_descriptor_count: int = Field(
        description="Number of execution evidence descriptors currently linked to the run."
    )
    evidence_types: list[str] = Field(
        default_factory=list,
        description="Sorted distinct evidence types currently linked to the run.",
    )


class WorkflowPackRunConsumerSupportabilityDescriptor(BaseModel):
    status: WorkflowPackRunSupportabilityStatus = Field(
        description="Shared supportability posture for the workflow-pack run."
    )
    review_pending: bool = Field(
        description="Whether the workflow-pack run still requires bounded human review."
    )
    superseded: bool = Field(
        description=(
            "Whether the workflow-pack run is now historical because a newer bounded draft posture "
            "or historical review state has superseded it."
        )
    )
    partial_output_visible: bool = Field(
        description="Whether the workflow-pack run still exposes partial output for bounded inspection."
    )
    summary_note: str = Field(
        description="Single consumer-facing summary note for the current workflow-pack supportability posture."
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
    provenance_summary: WorkflowPackRunProvenanceSummaryDescriptor = Field(
        description="Bounded artifact and evidence linkage summary for the workflow-pack run."
    )
    supportability: WorkflowPackRunConsumerSupportabilityDescriptor = Field(
        description="Consumer-facing supportability posture for the workflow-pack run."
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
        description=(
            "Whether the run is now historical because a newer bounded draft posture or "
            "historical review state has superseded it."
        )
    )
    partial_output_visible: bool = Field(
        description="Whether the run currently preserves some output despite not reaching a clean accepted terminal posture."
    )
    provenance: WorkflowPackRunProvenanceSummaryDescriptor = Field(
        description="Bounded artifact and evidence linkage summary for the workflow-pack run."
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
    latest_event_type: WorkflowPackRunEventType | None = Field(
        default=None,
        description="Event type recorded by the most recent workflow-pack run event, when available.",
    )
    latest_event_actor: str | None = Field(
        default=None,
        description="Actor recorded on the most recent workflow-pack run event, when available.",
    )
    latest_review_event_at: str | None = Field(
        default=None,
        description="UTC timestamp for the most recent recorded review-state transition, when available.",
    )
    latest_review_actor: str | None = Field(
        default=None,
        description="Actor recorded on the most recent review-state transition event, when available.",
    )
    review_transition_count: int = Field(
        description="Number of recorded review-state transition events currently linked to the run."
    )
    event_type_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Bounded per-event-type counts for the recorded workflow-pack run history.",
    )
    replacement_run_id: str | None = Field(
        default=None,
        description="Replacement workflow-pack run identifier when the current run is superseded or revised.",
    )
    recovery_lineage: WorkflowPackRunRecoveryLineageDescriptor | None = Field(
        default=None,
        description="Bounded queue recovery lineage when this run was created by retry or replay.",
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
