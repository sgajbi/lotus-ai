from __future__ import annotations

from fastapi import HTTPException, status

from app.contracts.prompts import PromptDescriptor
from app.prompts.registry import get_prompt_by_task_id, list_prompts


def get_prompt_or_raise(task_id: str) -> PromptDescriptor:
    prompt = get_prompt_by_task_id(task_id)
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered prompt definition for task_id: {task_id}",
        )
    return prompt


def list_registered_prompts() -> list[PromptDescriptor]:
    return list_prompts()
