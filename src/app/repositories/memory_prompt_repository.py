from __future__ import annotations

from copy import deepcopy

from app.contracts.prompts import PromptDescriptor
from app.prompts.registry import get_prompt_by_task_id, list_prompts
from app.repositories.prompt_repository import PromptRepository


class InMemoryPromptRepository(PromptRepository):
    def list_prompts(self) -> list[PromptDescriptor]:
        return deepcopy(list_prompts())

    def get_prompt(self, task_id: str) -> PromptDescriptor | None:
        prompt = get_prompt_by_task_id(task_id)
        if prompt is None:
            return None
        return deepcopy(prompt)
