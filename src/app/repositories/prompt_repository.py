from __future__ import annotations

from typing import Protocol

from app.contracts.prompts import PromptDescriptor
from app.services.prompt_rollout_models import (
    PromptRolloutEventRecord,
    PromptRolloutStateRecord,
)


class PromptRepository(Protocol):
    def list_prompts(self) -> list[PromptDescriptor]: ...

    def get_prompt(self, task_id: str) -> PromptDescriptor | None: ...

    def list_prompt_versions(self) -> list[PromptDescriptor]: ...

    def get_prompt_version(self, task_id: str, prompt_version: str) -> PromptDescriptor | None: ...

    def list_prompt_rollout_states(self) -> list[PromptRolloutStateRecord]: ...

    def get_prompt_rollout_state(self, task_id: str) -> PromptRolloutStateRecord | None: ...

    def list_prompt_rollout_events(
        self, task_id: str | None = None, limit: int = 20
    ) -> list[PromptRolloutEventRecord]: ...

    def save_prompt_rollout_transition(
        self,
        *,
        rollout_state: PromptRolloutStateRecord,
        updated_prompts: list[PromptDescriptor],
        event: PromptRolloutEventRecord,
    ) -> None: ...
