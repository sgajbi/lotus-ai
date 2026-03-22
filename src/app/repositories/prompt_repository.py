from __future__ import annotations

from typing import Protocol

from app.contracts.prompts import PromptDescriptor


class PromptRepository(Protocol):
    def list_prompts(self) -> list[PromptDescriptor]: ...

    def get_prompt(self, task_id: str) -> PromptDescriptor | None: ...
