from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.contracts.evidence import ExecutionEvidenceBundle
from app.contracts.safety import SafetyExecutionOutcome


class TaskCategory(str, Enum):
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    GENERATE_STRUCTURED = "generate_structured"
    KNOWLEDGE_SEARCH = "knowledge_search"
    KNOWLEDGE_ANSWER = "knowledge_answer"


class OutputLabel(str, Enum):
    EXPLANATION_ONLY = "EXPLANATION_ONLY"
    DRAFT = "DRAFT"
    CLASSIFICATION = "CLASSIFICATION"
    RETRIEVAL_ANSWER = "RETRIEVAL_ANSWER"


class TaskInputMode(str, Enum):
    STRUCTURED_CONTEXT = "STRUCTURED_CONTEXT"


class TaskExecutionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class CapabilityDescriptor(BaseModel):
    task_id: str = Field(description="Stable task identifier.")
    category: TaskCategory = Field(description="Task category owned by lotus-ai.")
    enabled: bool = Field(description="Whether the task is currently enabled.")
    output_label: OutputLabel = Field(description="Intended use label for the task output.")
    description: str = Field(description="Human-readable task description.")


class CapabilityCatalogResponse(BaseModel):
    service: str = Field(description="Service name emitting the catalog.")
    version: str = Field(description="Service version.")
    phase: str = Field(description="Current delivery phase for lotus-ai.")
    tasks: list[CapabilityDescriptor] = Field(
        description="Bounded AI task capabilities currently exposed by the service."
    )


class CallerMetadata(BaseModel):
    caller_app: str = Field(description="Calling Lotus application or platform component.")
    correlation_id: str = Field(description="Correlation identifier propagated by the caller.")
    requested_by: str | None = Field(
        default=None,
        description="Optional human or system identity associated with the request.",
    )
    tenant_id: str | None = Field(
        default=None,
        description="Optional tenant or environment ownership marker for the request.",
    )


class TaskContextEnvelope(BaseModel):
    summary: str = Field(description="Short human-readable description of the provided context.")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured task context assembled by the calling Lotus application.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="Optional source references carried by the calling system.",
    )


class TaskExecutionRequest(BaseModel):
    task_id: str = Field(description="Stable Lotus AI task identifier.")
    input_mode: TaskInputMode = Field(description="How the task input context is provided.")
    caller: CallerMetadata = Field(description="Calling system metadata.")
    context: TaskContextEnvelope = Field(description="Structured context envelope for execution.")
    expected_output_label: OutputLabel | None = Field(
        default=None,
        description="Optional caller assertion about the expected output label for the task.",
    )


class TaskAuditMetadata(BaseModel):
    request_id: str = Field(description="Generated task execution request identifier.")
    task_id: str = Field(description="Task identifier evaluated for this execution.")
    output_label: OutputLabel = Field(description="Output label attached to the execution.")
    prompt_version: str = Field(description="Prompt version associated with the execution.")
    provider_mode: str = Field(description="Provider mode active for the execution.")
    safety: SafetyExecutionOutcome = Field(description="Safety posture resolved for the execution.")
    generated_at: str = Field(description="UTC timestamp when the result was generated.")
    stubbed: bool = Field(description="Whether the result came from deterministic stub execution.")


class TaskExecutionResult(BaseModel):
    message: str = Field(description="Primary human-readable result string.")
    structured_output: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured result payload returned by the task execution layer.",
    )


class TaskExecutionResponse(BaseModel):
    status: TaskExecutionStatus = Field(description="Execution outcome for the task request.")
    task_id: str = Field(description="Executed task identifier.")
    category: TaskCategory = Field(description="Task category associated with the task id.")
    output_label: OutputLabel = Field(description="Output label emitted by the task.")
    result: TaskExecutionResult = Field(description="Task result payload.")
    audit: TaskAuditMetadata = Field(description="Audit metadata for the execution.")
    evidence: ExecutionEvidenceBundle = Field(
        description="Structured execution evidence explaining how the result was produced."
    )
