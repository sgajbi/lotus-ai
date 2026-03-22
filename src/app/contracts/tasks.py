from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


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
