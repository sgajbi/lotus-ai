from __future__ import annotations

from app.contracts.prompts import PromptDescriptor
from app.services.prompt_runtime import (
    list_registered_prompts as list_registered_runtime_prompts,
    resolve_runtime_prompt_or_raise,
)


def get_prompt_or_raise(task_id: str) -> PromptDescriptor:
    return resolve_runtime_prompt_or_raise(task_id).prompt


def list_registered_prompts() -> list[PromptDescriptor]:
    return list_registered_runtime_prompts()
