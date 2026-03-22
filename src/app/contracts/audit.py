from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AuditRecordResponse(BaseModel):
    request_id: str = Field(description="Generated task execution request identifier.")
    task_id: str = Field(description="Task identifier evaluated for this execution.")
    caller_app: str = Field(description="Calling Lotus application associated with the request.")
    correlation_id: str = Field(description="Correlation identifier propagated by the caller.")
    prompt_version: str = Field(description="Prompt version associated with the execution.")
    provider_mode: str = Field(description="Provider mode active for the execution.")
    generated_at: str = Field(description="UTC timestamp when the record was created.")
    stubbed: bool = Field(description="Whether the execution result was stubbed.")
    context_summary: str = Field(description="Short summary of the caller-provided context.")
    context_keys: list[str] = Field(description="Sorted list of structured context keys.")
    source_refs: list[str] = Field(description="Source references carried by the caller.")
    result_preview: str = Field(description="Short preview of the generated result.")
    structured_output: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured task result stored in the audit record.",
    )
