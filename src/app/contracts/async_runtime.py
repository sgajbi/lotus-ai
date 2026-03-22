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
