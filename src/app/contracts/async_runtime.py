from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AsyncQueueMode(str, Enum):
    DISABLED = "DISABLED"
    STUBBED = "STUBBED"


class AsyncWorkerMode(str, Enum):
    DOCUMENTED_ONLY = "DOCUMENTED_ONLY"
    STUBBED = "STUBBED"


class AsyncJobTypeDescriptor(BaseModel):
    job_type: str = Field(description="Stable async job type identifier.")
    enabled: bool = Field(description="Whether the async job type is enabled in the current phase.")
    execution_path: str = Field(
        description="Current execution path for the async job type in the active runtime posture."
    )
    notes: str = Field(description="Human-readable notes about the async job type posture.")


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
    enqueued_job_count: int = Field(description="Number of enqueued async jobs currently visible.")
    supported_job_types: list[AsyncJobTypeDescriptor] = Field(
        description="Known async job types and their current runtime posture."
    )
    message: str = Field(
        description="Human-readable explanation of the current async runtime posture."
    )
