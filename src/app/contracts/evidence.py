from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutionEvidenceDescriptor(BaseModel):
    evidence_type: str = Field(description="Stable type label for the execution evidence item.")
    summary: str = Field(description="Human-readable explanation of the evidence item.")
    attributes: dict[str, object] = Field(
        default_factory=dict,
        description="Structured evidence attributes associated with the execution decision.",
    )


class ExecutionEvidenceBundle(BaseModel):
    descriptors: list[ExecutionEvidenceDescriptor] = Field(
        description="Structured evidence items describing how the execution result was produced."
    )
