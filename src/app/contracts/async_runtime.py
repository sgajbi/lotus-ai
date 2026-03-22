from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AsyncQueueMode(str, Enum):
    DISABLED = "DISABLED"
    STUBBED = "STUBBED"


class AsyncWorkerMode(str, Enum):
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    STUBBED = "STUBBED"


class AsyncJobStatus(str, Enum):
    QUEUED = "QUEUED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class AsyncSubmissionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


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
    status: AsyncJobStatus = Field(description="Lifecycle status for the async job artifact.")
    submitted_at: str = Field(description="UTC timestamp when the async job artifact was created.")
    caller_app: str = Field(description="Lotus caller associated with the async job artifact.")
    related_evaluation_run_id: str | None = Field(
        default=None,
        description="Related evaluation run artifact identifier when the async job contributes to evaluation history.",
    )
    execution_path: str = Field(
        description="Current execution path assigned to the async job artifact."
    )
    notes: str = Field(description="Human-readable description of the async job artifact.")


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


class AsyncJobSubmissionRequest(BaseModel):
    job_type: str = Field(description="Stable async job type identifier requested by the caller.")
    caller_app: str = Field(
        description="Calling Lotus application submitting the async job request."
    )
    correlation_id: str = Field(
        description="Caller-provided correlation identifier for the request."
    )
    target_id: str | None = Field(
        default=None,
        description="Optional target identifier for job types that act on a specific governed resource.",
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
    queue_mode: AsyncQueueMode = Field(
        description="Queue mode that governed the submission decision."
    )
    worker_mode: AsyncWorkerMode = Field(
        description="Worker mode that governed the submission decision."
    )
    job_type: str = Field(description="Stable async job type identifier evaluated for submission.")
    accepted: bool = Field(description="Whether the async submission was accepted.")
    job_id: str | None = Field(
        default=None, description="Assigned async job id when submission is accepted."
    )
    message: str = Field(description="Human-readable explanation of the submission outcome.")


class AsyncRuntimeStatusResponse(BaseModel):
    service: str = Field(description="Service name emitting the async runtime status.")
    version: str = Field(description="Current lotus-ai service version.")
    delivery_phase: str = Field(description="Current lotus-ai delivery phase.")
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
    enqueued_job_count: int = Field(description="Number of queued async jobs currently visible.")
    recorded_job_count: int = Field(
        description="Number of recorded async job artifacts currently exposed."
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
