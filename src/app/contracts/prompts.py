from __future__ import annotations

from pydantic import BaseModel, Field


class PromptDescriptor(BaseModel):
    task_id: str = Field(description="Stable task identifier associated with the prompt.")
    prompt_version: str = Field(description="Version of the prompt definition.")
    prompt_kind: str = Field(description="High-level type of prompt definition.")
    system_instructions: str = Field(description="Primary system instructions for the task.")
    output_contract_notes: str = Field(
        description="Contract notes constraining how task output should behave."
    )
