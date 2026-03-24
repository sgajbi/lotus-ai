from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.contracts.access_control import AuthorizationDecision
from app.contracts.artifacts import ArtifactDescriptor


class AsyncQueueMode(str, Enum):
    DISABLED = "DISABLED"
    SHADOW = "SHADOW"
    ACTIVE = "ACTIVE"


class AsyncWorkerMode(str, Enum):
    IN_PROCESS_ONLY = "IN_PROCESS_ONLY"
    DEDICATED = "DEDICATED"
    DEGRADED_FALLBACK = "DEGRADED_FALLBACK"


class AsyncCutoverState(str, Enum):
    IN_PROCESS_ONLY = "in_process_only"
    QUEUE_DELIVERY_SHADOW = "queue_delivery_shadow"
    DEDICATED_WORKERS_ACTIVE = "dedicated_workers_active"
    DEGRADED_FALLBACK = "degraded_fallback"


class AsyncJobStatus(str, Enum):
    STAGED = "STAGED"
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    SUPERSEDED = "SUPERSEDED"


class AsyncJobRecordSource(str, Enum):
    STAGED_ARTIFACT = "STAGED_ARTIFACT"
    RUNTIME_STATE = "RUNTIME_STATE"


class AsyncSubmissionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"


class AsyncControlActionType(str, Enum):
    RETRY_FAILED_JOB = "RETRY_FAILED_JOB"
    REPLAY_TERMINAL_JOB = "REPLAY_TERMINAL_JOB"
    REQUEUE_ABANDONED_JOB = "REQUEUE_ABANDONED_JOB"
    ABANDON_ACTIVE_JOB = "ABANDON_ACTIVE_JOB"


class AsyncJobTypeDescriptor(BaseModel):
    job_type: str = Field(description="Stable async job type identifier.")
    enabled: bool = Field(description="Whether the async job type is enabled in the current phase.")
    execution_path: str = Field(
        description="Current execution path for the async job type in the active runtime posture."
    )
    notes: str = Field(description="Human-readable notes about the async job type posture.")


class AsyncQueueBackendDescriptor(BaseModel):
    backend_id: str = Field(description="Stable queue backend identifier.")
    enabled: bool = Field(
        description="Whether the queue backend is currently enabled for live lotus-ai async execution."
    )
    backend_class: str = Field(
        description="Operational category describing the queue backend architecture."
    )
    selection_state: str = Field(
        description="Governed runtime selection posture for the queue backend."
    )
    supports_durable_queue: bool = Field(
        description="Whether the backend is designed to provide durable queue semantics."
    )
    supports_worker_scaling: bool = Field(
        description="Whether the backend is intended to support horizontally scaled workers."
    )
    notes: str = Field(description="Human-readable notes about the queue backend posture.")


class AsyncWorkerExecutionDescriptor(BaseModel):
    worker_id: str = Field(description="Stable worker execution strategy identifier.")
    enabled: bool = Field(
        description="Whether the worker execution strategy is currently enabled for live execution."
    )
    execution_class: str = Field(
        description="Operational category describing the worker execution architecture."
    )
    selection_state: str = Field(
        description="Governed runtime selection posture for the worker execution strategy."
    )
    supports_horizontal_scaling: bool = Field(
        description="Whether the worker execution strategy is designed for horizontal scale-out."
    )
    supports_job_isolation: bool = Field(
        description="Whether the strategy is designed to isolate job execution from API-serving nodes."
    )
    notes: str = Field(description="Human-readable notes about the worker execution posture.")


class AsyncJobArtifactDescriptor(BaseModel):
    job_id: str = Field(description="Stable async job artifact identifier.")
    job_type: str = Field(description="Stable async job type identifier.")
    target_id: str | None = Field(
        default=None,
        description="Optional stable runtime target identifier associated with the async job.",
    )
    status: AsyncJobStatus = Field(description="Lifecycle status for the async job artifact.")
    record_source: AsyncJobRecordSource = Field(
        default=AsyncJobRecordSource.STAGED_ARTIFACT,
        description="Whether this async job record comes from staged governed artifacts or durable runtime state.",
    )
    submitted_at: str = Field(description="UTC timestamp when the async job artifact was created.")
    caller_app: str = Field(description="Lotus caller associated with the async job artifact.")
    related_evaluation_run_id: str | None = Field(
        default=None,
        description="Related evaluation run artifact identifier when the async job contributes to evaluation history.",
    )
    execution_path: str = Field(
        description="Current execution path assigned to the async job artifact."
    )
    artifact_refs: list[ArtifactDescriptor] = Field(
        default_factory=list,
        description="Governed artifact descriptors attached to the runtime-backed async job.",
    )
    notes: str = Field(description="Human-readable description of the async job artifact.")


class AsyncJobAttemptDescriptor(BaseModel):
    attempt_id: str = Field(description="Stable async job attempt identifier.")
    attempt_number: int = Field(description="Monotonic attempt number for the async job.")
    status: str = Field(description="Lifecycle status for the recorded async job attempt.")
    worker_id: str | None = Field(
        default=None,
        description="Worker identifier currently or previously associated with the attempt.",
    )
    claimed_at: str | None = Field(
        default=None,
        description="UTC timestamp when the attempt was claimed by a worker.",
    )
    heartbeat_at: str | None = Field(
        default=None,
        description="UTC timestamp for the last recorded worker heartbeat.",
    )
    started_at: str | None = Field(
        default=None,
        description="UTC timestamp when the attempt entered running execution.",
    )
    completed_at: str | None = Field(
        default=None,
        description="UTC timestamp when the attempt reached a terminal state.",
    )
    failure_reason: str | None = Field(
        default=None,
        description="Failure reason when the attempt did not complete successfully.",
    )
    recorded_message: str = Field(
        description="Human-readable message describing the attempt state transition.",
    )


class AsyncJobLeaseDescriptor(BaseModel):
    lease_id: str = Field(description="Stable async worker lease identifier.")
    attempt_id: str = Field(description="Async job attempt currently associated with the lease.")
    worker_id: str = Field(description="Worker identifier holding the active lease.")
    claimed_at: str = Field(description="UTC timestamp when the lease was claimed.")
    heartbeat_at: str = Field(description="UTC timestamp of the last recorded worker heartbeat.")
    lease_expires_at: str = Field(
        description="UTC timestamp when the active lease becomes recoverable if not renewed."
    )


class AsyncControlEventDescriptor(BaseModel):
    event_id: str = Field(description="Stable identifier for the recorded async control action.")
    job_id: str = Field(description="Async job identifier affected by the control action.")
    action_type: AsyncControlActionType = Field(
        description="Type of governed async control action that was recorded."
    )
    requested_by: str = Field(description="Operator or system identity requesting the action.")
    approved_by: str = Field(description="Approver identity recorded for the action.")
    reason: str = Field(description="Human-readable reason for the async control action.")
    prior_status: str = Field(description="Async job status before the action was applied.")
    resulting_status: str = Field(description="Async job status after the action was applied.")
    affected_attempt_id: str | None = Field(
        default=None,
        description="Attempt identifier directly affected or created by the action, when applicable.",
    )
    authorization: AuthorizationDecision = Field(
        description="Typed caller-authorization decision recorded for the control action."
    )
    recorded_at: str = Field(description="Timestamp when the action was recorded.")


class AsyncJobCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the async job catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    job_count: int = Field(description="Number of recorded async job artifacts currently exposed.")
    queued_job_count: int = Field(
        description="Number of queued async job artifacts currently exposed."
    )
    jobs: list[AsyncJobArtifactDescriptor] = Field(
        description="Recorded async job artifacts available for inspection."
    )


class AsyncJobDetailResponse(BaseModel):
    service: str = Field(description="Service name emitting the async job detail.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    job: AsyncJobArtifactDescriptor = Field(description="Recorded async job artifact detail.")
    attempts: list[AsyncJobAttemptDescriptor] = Field(
        description="Recorded attempt history for runtime-backed async jobs."
    )
    active_lease: AsyncJobLeaseDescriptor | None = Field(
        default=None,
        description="Active worker lease detail for runtime-backed jobs when a lease is held.",
    )
    control_events: list[AsyncControlEventDescriptor] = Field(
        default_factory=list,
        description="Governed async control-plane history for runtime-backed jobs.",
    )


class AsyncJobSubmissionRequest(BaseModel):
    job_type: str = Field(description="Stable async job type identifier requested by the caller.")
    target_id: str | None = Field(
        default=None,
        description="Optional stable target identifier for job types that operate on a specific runtime record.",
    )
    caller_app: str = Field(
        description="Calling Lotus application submitting the async job request."
    )
    correlation_id: str = Field(
        description="Caller-provided correlation identifier for the request."
    )
    payload_summary: str = Field(
        description="Short description of the intended async work payload."
    )


class AsyncJobSubmissionResponse(BaseModel):
    service: str = Field(description="Service name emitting the async job submission response.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    submission_status: AsyncSubmissionStatus = Field(
        description="Submission outcome under the current async runtime posture."
    )
    cutover_state: AsyncCutoverState = Field(
        description="Current async worker-fleet cutover state governing the submission."
    )
    queue_mode: AsyncQueueMode = Field(
        description="Queue mode that governed the submission decision."
    )
    worker_mode: AsyncWorkerMode = Field(
        description="Worker mode that governed the submission decision."
    )
    job_type: str = Field(description="Stable async job type identifier evaluated for submission.")
    target_id: str | None = Field(
        default=None,
        description="Stable target identifier when the accepted or evaluated async job maps to a concrete runtime record.",
    )
    existing_job_id: str | None = Field(
        default=None,
        description="Existing active async job identifier when a duplicate submission is rejected explicitly.",
    )
    accepted: bool = Field(description="Whether the async submission was accepted.")
    job_id: str | None = Field(
        default=None, description="Assigned async job id when submission is accepted."
    )
    message: str = Field(description="Human-readable explanation of the submission outcome.")


class AsyncRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the async runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    cutover_state: AsyncCutoverState = Field(
        description="Current async worker-fleet cutover state."
    )
    queue_mode: AsyncQueueMode = Field(description="Current queue execution mode.")
    worker_mode: AsyncWorkerMode = Field(description="Current worker runtime mode.")
    queue_backend: str = Field(description="Current queue backend posture label.")
    supported_queue_backends: list[AsyncQueueBackendDescriptor] = Field(
        description="Known queue backend strategies and their current selection posture."
    )
    active_worker_execution: str = Field(
        description="Current active worker execution posture label."
    )
    supported_worker_executions: list[AsyncWorkerExecutionDescriptor] = Field(
        description="Known worker execution strategies and their current selection posture."
    )
    active_worker_count: int = Field(
        description="Number of active worker replicas currently exposed."
    )
    active_worker_ids: list[str] = Field(
        description="Worker identities currently holding active async leases."
    )
    enqueued_job_count: int = Field(description="Number of queued async jobs currently visible.")
    recorded_job_count: int = Field(
        description="Number of recorded async job artifacts currently exposed."
    )
    queue_backlog_count: int = Field(
        description="Number of queue delivery messages currently pending for the active backend."
    )
    duplicate_delivery_count: int = Field(
        description="Observed duplicate queue deliveries rejected safely by the bounded queue seam."
    )
    redelivery_count: int = Field(
        description="Observed queue redelivery count under the bounded queue seam."
    )
    drain_mode_active: bool = Field(
        description="Whether dedicated workers are currently in drain mode and refusing new claims."
    )
    degraded_findings: list[str] = Field(
        description="Human-readable findings describing degraded or operator-significant async worker posture."
    )
    supported_job_types: list[AsyncJobTypeDescriptor] = Field(
        description="Known async job types and their current runtime posture."
    )
    message: str = Field(
        description="Human-readable explanation of the current async runtime posture."
    )


class AsyncQueueBackendCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the queue backend catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    active_queue_backend: str = Field(description="Current active queue backend posture label.")
    backend_count: int = Field(description="Number of queue backend strategies currently exposed.")
    backends: list[AsyncQueueBackendDescriptor] = Field(
        description="Known queue backend strategies and their current posture."
    )


class AsyncWorkerExecutionCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the worker execution catalog.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    active_worker_execution: str = Field(
        description="Current active worker execution posture label."
    )
    worker_count: int = Field(
        description="Number of worker execution strategies currently exposed."
    )
    workers: list[AsyncWorkerExecutionDescriptor] = Field(
        description="Known worker execution strategies and their current posture."
    )


class AsyncActivationReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the async activation readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    cutover_state: AsyncCutoverState = Field(
        description="Current async worker-fleet cutover state."
    )
    activation_ready: bool = Field(
        description="Whether lotus-ai async execution is currently ready for live activation."
    )
    queue_backend: str = Field(description="Current active queue backend posture label.")
    worker_execution: str = Field(description="Current active worker execution posture label.")
    queue_mode: AsyncQueueMode = Field(description="Current queue execution mode.")
    worker_mode: AsyncWorkerMode = Field(description="Current worker runtime mode.")
    supported_job_type_count: int = Field(
        description="Number of governed async job types currently exposed."
    )
    blocking_findings: list[str] = Field(
        description="Human-readable reasons why async execution is not yet activatable."
    )
    activation_path: list[str] = Field(
        description="Governed high-level path required before live async execution can be enabled."
    )


class AsyncRunbookReadinessItem(BaseModel):
    runbook_id: str = Field(description="Stable async runbook readiness item identifier.")
    status: str = Field(description="Current readiness posture for the runbook requirement.")
    required_for_activation: bool = Field(
        description="Whether this runbook item must be complete before live async activation."
    )
    notes: str = Field(description="Human-readable explanation of the runbook requirement.")


class AsyncRunbookReadinessResponse(BaseModel):
    service: str = Field(description="Service name emitting the async runbook readiness view.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    runbook_ready: bool = Field(
        description="Whether async operational runbook readiness is currently sufficient for activation."
    )
    required_item_count: int = Field(
        description="Number of runbook items currently required for activation."
    )
    completed_required_item_count: int = Field(
        description="Number of required runbook items currently marked complete."
    )
    items: list[AsyncRunbookReadinessItem] = Field(
        description="Governed async operational runbook readiness items."
    )


class AsyncGovernanceStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the async governance status view.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    governance_ready: bool = Field(
        description="Whether async governance posture is currently sufficient for live activation."
    )
    activation_readiness: AsyncActivationReadinessResponse = Field(
        description="Technical activation-readiness summary for async execution."
    )
    runbook_readiness: AsyncRunbookReadinessResponse = Field(
        description="Operational runbook-readiness summary for async execution."
    )
    blocking_area_count: int = Field(
        description="Number of top-level governance areas currently blocking activation."
    )
    governance_summary: list[str] = Field(
        description="Human-readable summary of the current async governance posture."
    )


class AsyncControlHistoryResponse(BaseModel):
    service: str = Field(description="Service name emitting the async control history view.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    control_plane_store_mode: str = Field(
        description="Configured async-runtime store mode backing async control-plane truth."
    )
    supported_action_types: list[AsyncControlActionType] = Field(
        description="Supported governed async control action types."
    )
    latest_events: list[AsyncControlEventDescriptor] = Field(
        default_factory=list,
        description="Most recent recorded async control-plane actions.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Human-readable notes describing duplicate, replay, retry, and recovery semantics.",
    )


class AsyncControlActionRequest(BaseModel):
    job_id: str = Field(description="Async job identifier targeted by the control action.")
    action_type: AsyncControlActionType = Field(description="Requested async control action.")
    caller_app: str = Field(
        min_length=1,
        description="Caller application identity authorized to issue the async control action.",
    )
    requested_by: str = Field(
        min_length=1,
        description="Operator or system identity requesting the async control action.",
    )
    approved_by: str = Field(
        min_length=1,
        description="Approver identity authorizing the async control action.",
    )
    reason: str = Field(min_length=1, description="Human-readable reason for the control action.")


class AsyncControlActionResponse(BaseModel):
    service: str = Field(description="Service name emitting the async control action response.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
    event: AsyncControlEventDescriptor = Field(description="Recorded async control-plane event.")
    summary: list[str] = Field(
        default_factory=list,
        description="Human-readable summary of the applied async control action.",
    )
